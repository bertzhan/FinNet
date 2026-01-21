# -*- coding: utf-8 -*-
"""
RAG 检索器
基于 Milvus 进行向量检索，从 PostgreSQL 获取分块文本和元数据
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import uuid

from src.processing.ai.embedding.embedder_factory import get_embedder_by_mode
from src.storage.vector.milvus_client import get_milvus_client
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import DocumentChunk, Document
from src.common.constants import MilvusCollection
from src.common.logger import get_logger, LoggerMixin


@dataclass
class RetrievalResult:
    """检索结果"""
    chunk_id: str
    document_id: str
    chunk_text: str
    title: Optional[str]
    title_level: Optional[int]
    score: float  # 相似度分数（0-1）
    metadata: Dict[str, Any]  # 文档元数据（stock_code, company_name, doc_type, year, quarter等）


class Retriever(LoggerMixin):
    """
    RAG 检索器
    基于 Milvus 进行向量检索，从 PostgreSQL 获取完整的分块信息
    """

    def __init__(
        self,
        collection_name: str = MilvusCollection.DOCUMENTS,
        embedder=None,
        milvus_client=None,
        pg_client=None
    ):
        """
        初始化检索器

        Args:
            collection_name: Milvus Collection 名称
            embedder: Embedder 实例（默认自动创建）
            milvus_client: Milvus 客户端（默认自动创建）
            pg_client: PostgreSQL 客户端（默认自动创建）
        """
        self.collection_name = collection_name
        self.embedder = embedder or get_embedder_by_mode()
        self.milvus_client = milvus_client or get_milvus_client()
        self.pg_client = pg_client or get_postgres_client()

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """
        检索相关文档分块

        Args:
            query: 用户问题（文本）
            top_k: 返回数量（默认 5）
            filters: 过滤条件
                - stock_code: 股票代码
                - year: 年份
                - quarter: 季度
                - doc_type: 文档类型
                - market: 市场

        Returns:
            检索结果列表

        Example:
            >>> retriever = Retriever()
            >>> results = retriever.retrieve(
            ...     "平安银行营业收入",
            ...     top_k=5,
            ...     filters={"stock_code": "000001", "year": 2023}
            ... )
            >>> for result in results:
            ...     print(f"Score: {result.score}, Text: {result.chunk_text[:100]}")
        """
        # 1. 查询向量化
        self.logger.debug(f"查询向量化: {query[:50]}...")
        query_vector = self.embedder.embed_text(query)
        if not query_vector:
            self.logger.warning("查询向量化失败")
            return []

        # 2. 构建过滤表达式
        filter_expr = self._build_filter_expr(filters) if filters else None
        if filter_expr:
            self.logger.debug(f"过滤条件: {filter_expr}")

        # 3. Milvus 向量检索
        self.logger.debug(f"Milvus 检索: top_k={top_k}")
        try:
            search_results = self.milvus_client.search_vectors(
                collection_name=self.collection_name,
                query_vectors=[query_vector],
                top_k=top_k,
                expr=filter_expr,
                output_fields=["document_id", "chunk_id", "stock_code", "year", "quarter"]
            )
        except Exception as e:
            self.logger.error(f"Milvus 检索失败: {e}", exc_info=True)
            return []

        if not search_results or not search_results[0]:
            self.logger.warning("Milvus 检索结果为空")
            return []

        # 4. 从 PostgreSQL 获取分块文本和元数据
        hits = search_results[0]
        chunk_ids = [hit['entity']['chunk_id'] for hit in hits]
        
        self.logger.debug(f"从 PostgreSQL 获取 {len(chunk_ids)} 个分块信息")
        retrieval_results = self._fetch_chunks_from_db(chunk_ids, hits)

        self.logger.info(f"检索完成: 查询='{query[:50]}...', 返回 {len(retrieval_results)} 个结果")
        return retrieval_results

    def _build_filter_expr(self, filters: Dict[str, Any]) -> Optional[str]:
        """
        构建 Milvus 过滤表达式

        Args:
            filters: 过滤条件字典

        Returns:
            过滤表达式字符串，如 "stock_code == '000001' and year == 2023"
        """
        conditions = []

        if filters.get("stock_code"):
            stock_code = filters["stock_code"]
            conditions.append(f"stock_code == '{stock_code}'")

        if filters.get("year"):
            year = filters["year"]
            conditions.append(f"year == {year}")

        if filters.get("quarter"):
            quarter = filters["quarter"]
            conditions.append(f"quarter == {quarter}")

        # 注意：Milvus 中可能没有直接存储 doc_type 和 market
        # 这些信息需要从 PostgreSQL 查询后过滤
        # 如果需要这些过滤，可以在获取结果后过滤

        return " and ".join(conditions) if conditions else None

    def _fetch_chunks_from_db(
        self,
        chunk_ids: List[str],
        hits: List[Dict[str, Any]]
    ) -> List[RetrievalResult]:
        """
        从 PostgreSQL 获取分块文本和元数据

        Args:
            chunk_ids: 分块 ID 列表
            hits: Milvus 检索结果（包含距离和元数据）

        Returns:
            检索结果列表
        """
        # 构建 chunk_id 到 hit 的映射（用于获取距离）
        chunk_id_to_hit = {}
        for hit in hits:
            chunk_id = hit['entity']['chunk_id']
            chunk_id_to_hit[chunk_id] = hit

        # 转换为 UUID
        try:
            chunk_uuids = [uuid.UUID(chunk_id) for chunk_id in chunk_ids]
        except ValueError as e:
            self.logger.error(f"无效的 chunk_id: {e}")
            return []

        # 从 PostgreSQL 查询
        results = []
        try:
            with self.pg_client.get_session() as session:
                # 查询分块和文档信息（JOIN）
                chunks = session.query(DocumentChunk, Document).join(
                    Document, DocumentChunk.document_id == Document.id
                ).filter(
                    DocumentChunk.id.in_(chunk_uuids)
                ).all()

                # 构建结果
                for chunk, doc in chunks:
                    chunk_id_str = str(chunk.id)
                    hit = chunk_id_to_hit.get(chunk_id_str)
                    
                    if not hit:
                        self.logger.warning(f"未找到 chunk_id 对应的 hit: {chunk_id_str}")
                        continue

                    # 距离转相似度分数（L2距离越小，相似度越高）
                    distance = hit['distance']
                    score = self._distance_to_score(distance)

                    # 构建元数据
                    metadata = {
                        "stock_code": doc.stock_code,
                        "company_name": doc.company_name,
                        "market": doc.market,
                        "doc_type": doc.doc_type,
                        "year": doc.year,
                        "quarter": doc.quarter,
                        "chunk_index": chunk.chunk_index,
                    }

                    result = RetrievalResult(
                        chunk_id=chunk_id_str,
                        document_id=str(chunk.document_id),
                        chunk_text=chunk.chunk_text or "",
                        title=chunk.title,
                        title_level=chunk.title_level,
                        score=score,
                        metadata=metadata
                    )
                    results.append(result)

                # 按原始顺序排序（保持 Milvus 返回的顺序）
                results.sort(key=lambda r: chunk_ids.index(r.chunk_id) if r.chunk_id in chunk_ids else 999)

        except Exception as e:
            self.logger.error(f"从 PostgreSQL 获取分块失败: {e}", exc_info=True)
            return []

        return results

    def _distance_to_score(self, distance: float) -> float:
        """
        将 L2 距离转换为相似度分数（0-1）

        Args:
            distance: L2 距离

        Returns:
            相似度分数（0-1，1 表示最相似）
        """
        # 简单的转换公式：score = 1 / (1 + distance)
        # 可以根据实际效果调整
        score = 1.0 / (1.0 + distance)
        return min(max(score, 0.0), 1.0)  # 限制在 [0, 1] 范围内
