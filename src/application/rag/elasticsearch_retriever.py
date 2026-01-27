# -*- coding: utf-8 -*-
"""
Elasticsearch 全文检索器
基于 Elasticsearch 进行全文检索，从 PostgreSQL 获取分块文本和元数据

按照 plan.md 设计：
- 全文检索 → Elasticsearch
- 支持关键词匹配、BM25 评分、元数据过滤
- 与向量检索（Milvus）结合，提供混合检索能力
"""

from typing import List, Dict, Any, Optional
import uuid

from src.storage.elasticsearch import get_elasticsearch_client
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import DocumentChunk, Document
from src.common.logger import get_logger, LoggerMixin
from src.application.rag.retriever import RetrievalResult


class ElasticsearchRetriever(LoggerMixin):
    """
    Elasticsearch 全文检索器
    基于 Elasticsearch 进行全文检索，从 PostgreSQL 获取完整的分块信息
    """

    def __init__(
        self,
        index_name: str = "chunks",
        es_client=None,
        pg_client=None
    ):
        """
        初始化 Elasticsearch 检索器

        Args:
            index_name: Elasticsearch 索引名称（默认 "chunks"）
            es_client: Elasticsearch 客户端（默认自动创建）
            pg_client: PostgreSQL 客户端（默认自动创建）
        """
        self.index_name = index_name
        self.es_client = es_client or get_elasticsearch_client()
        self.pg_client = pg_client or get_postgres_client()

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """
        检索相关文档分块（全文检索）

        Args:
            query: 用户问题（文本）
            top_k: 返回数量（默认 5）
            filters: 过滤条件
                - stock_code: 股票代码
                - year: 年份
                - quarter: 季度
                - doc_type: 文档类型
                - market: 市场
                - company_name: 公司名称

        Returns:
            检索结果列表

        Example:
            >>> retriever = ElasticsearchRetriever()
            >>> results = retriever.retrieve(
            ...     "平安银行营业收入",
            ...     top_k=5,
            ...     filters={"stock_code": "000001", "year": 2023}
            ... )
            >>> for result in results:
            ...     print(f"Score: {result.score}, Text: {result.chunk_text[:100]}")
        """
        try:
            # 1. 构建 Elasticsearch 查询 DSL
            es_query = self._build_query(query, filters)
            self.logger.debug(f"Elasticsearch 查询: {es_query}")

            # 2. 执行 Elasticsearch 搜索
            self.logger.debug(f"Elasticsearch 检索: top_k={top_k}")
            response = self.es_client.search(
                index_name=self.index_name,
                query=es_query,
                size=top_k,
                from_=0
            )

            # 3. 解析搜索结果
            hits = response.get("hits", {}).get("hits", [])
            if not hits:
                self.logger.warning("Elasticsearch 检索结果为空")
                return []

            # 4. 提取 chunk_id 列表
            chunk_ids = [hit["_id"] for hit in hits]
            self.logger.debug(f"从 PostgreSQL 获取 {len(chunk_ids)} 个分块信息")

            # 5. 从 PostgreSQL 获取分块文本和元数据
            retrieval_results = self._fetch_chunks_from_db(chunk_ids, hits)

            self.logger.info(
                f"全文检索完成: 查询='{query[:50]}...', "
                f"返回 {len(retrieval_results)} 个结果"
            )
            return retrieval_results

        except Exception as e:
            self.logger.error(f"Elasticsearch 检索失败: {e}", exc_info=True)
            return []

    def _build_query(
        self,
        query_text: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        构建 Elasticsearch 查询 DSL

        Args:
            query_text: 查询文本
            filters: 过滤条件

        Returns:
            Elasticsearch 查询 DSL
        """
        # 构建 must 子句（必须匹配）
        must_clauses = []

        # 文本查询：在 chunk_text 和 title 字段中搜索
        # 使用 multi_match 查询，支持多个字段
        text_query = {
            "multi_match": {
                "query": query_text,
                "fields": [
                    "chunk_text^2",  # chunk_text 权重更高
                    "title^1.5"       # title 权重中等
                ],
                "type": "best_fields",  # 最佳字段匹配
                "operator": "or",        # 任意词匹配
                "minimum_should_match": "30%"  # 至少匹配 30% 的词
            }
        }
        must_clauses.append(text_query)

        # 构建 filter 子句（精确匹配，不影响评分）
        filter_clauses = []

        if filters:
            # 股票代码过滤
            if filters.get("stock_code"):
                stock_code = filters["stock_code"]
                if isinstance(stock_code, list):
                    filter_clauses.append({
                        "terms": {"stock_code": stock_code}
                    })
                else:
                    filter_clauses.append({
                        "term": {"stock_code": stock_code}
                    })

            # 年份过滤
            if filters.get("year"):
                year = filters["year"]
                if isinstance(year, list):
                    filter_clauses.append({
                        "terms": {"year": year}
                    })
                else:
                    filter_clauses.append({
                        "term": {"year": year}
                    })

            # 季度过滤
            if filters.get("quarter"):
                quarter = filters["quarter"]
                if isinstance(quarter, list):
                    filter_clauses.append({
                        "terms": {"quarter": quarter}
                    })
                else:
                    filter_clauses.append({
                        "term": {"quarter": quarter}
                    })

            # 文档类型过滤（支持单个值或列表）
            if filters.get("doc_type"):
                doc_type = filters["doc_type"]
                if isinstance(doc_type, list):
                    # 使用 terms（复数）查询支持多个值
                    filter_clauses.append({
                        "terms": {"doc_type": doc_type}
                    })
                else:
                    # 使用 term（单数）查询单个值
                    filter_clauses.append({
                        "term": {"doc_type": doc_type}
                    })

            # 市场过滤
            if filters.get("market"):
                market = filters["market"]
                if isinstance(market, list):
                    filter_clauses.append({
                        "terms": {"market": market}
                    })
                else:
                    filter_clauses.append({
                        "term": {"market": market}
                    })

            # 公司名称过滤（支持模糊匹配）
            if filters.get("company_name"):
                filter_clauses.append({
                    "match": {"company_name": filters["company_name"]}
                })

        # 构建完整的 bool 查询
        bool_query = {
            "bool": {
                "must": must_clauses
            }
        }

        # 如果有过滤条件，添加到 filter 子句
        if filter_clauses:
            bool_query["bool"]["filter"] = filter_clauses

        return bool_query

    def _fetch_chunks_from_db(
        self,
        chunk_ids: List[str],
        hits: List[Dict[str, Any]]
    ) -> List[RetrievalResult]:
        """
        从 PostgreSQL 获取分块文本和元数据

        Args:
            chunk_ids: 分块 ID 列表（字符串格式）
            hits: Elasticsearch 检索结果（包含评分和元数据）

        Returns:
            检索结果列表
        """
        # 构建 chunk_id 到 hit 的映射（用于获取评分）
        chunk_id_to_hit = {}
        for hit in hits:
            chunk_id = hit["_id"]
            chunk_id_to_hit[chunk_id] = hit

        # 转换为 UUID
        chunk_uuids = []
        for chunk_id in chunk_ids:
            try:
                chunk_uuids.append(uuid.UUID(chunk_id))
            except ValueError:
                self.logger.warning(f"无效的 chunk_id: {chunk_id}")
                continue

        if not chunk_uuids:
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
                        self.logger.warning(
                            f"未找到 chunk_id 对应的 hit: {chunk_id_str}"
                        )
                        continue

                    # Elasticsearch 评分转相似度分数（0-1）
                    # Elasticsearch 使用 BM25 评分，通常范围较大
                    # 使用归一化方法：score = min(1.0, es_score / max_score)
                    es_score = hit.get("_score", 0.0)
                    max_score = hits[0].get("_score", 1.0) if hits else 1.0
                    score = self._normalize_score(es_score, max_score)

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

                # 按原始顺序排序（保持 Elasticsearch 返回的顺序）
                results.sort(
                    key=lambda r: chunk_ids.index(r.chunk_id)
                    if r.chunk_id in chunk_ids
                    else 999
                )

        except Exception as e:
            self.logger.error(
                f"从 PostgreSQL 获取分块失败: {e}",
                exc_info=True
            )
            return []

        return results

    def _normalize_score(self, es_score: float, max_score: float) -> float:
        """
        将 Elasticsearch BM25 评分转换为相似度分数（0-1）

        Args:
            es_score: Elasticsearch 评分
            max_score: 最高评分（用于归一化）

        Returns:
            相似度分数（0-1，1 表示最相似）
        """
        if max_score <= 0:
            return 0.0

        # 方法1：简单归一化（相对于最高分）
        normalized_score = es_score / max_score

        # 方法2：使用 sigmoid 函数平滑（可选）
        # normalized_score = 1.0 / (1.0 + math.exp(-es_score / max_score))

        # 限制在 [0, 1] 范围内
        return min(max(normalized_score, 0.0), 1.0)
