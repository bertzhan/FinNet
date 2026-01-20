# -*- coding: utf-8 -*-
"""
向量化服务
封装完整的向量化流程：读取分块 -> 生成向量 -> 存储到Milvus -> 更新数据库
"""

from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import uuid

from src.processing.ai.embedding.embedder_factory import get_embedder_by_mode
from src.storage.vector.milvus_client import get_milvus_client
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.storage.metadata.models import DocumentChunk, Document
from src.common.constants import MilvusCollection
from src.common.logger import LoggerMixin
from src.common.config import embedding_config


class Vectorizer(LoggerMixin):
    """
    向量化服务
    负责将文档分块向量化并存储到Milvus
    """

    def __init__(
        self,
        embedder=None,
        milvus_client=None,
        pg_client=None
    ):
        """
        初始化向量化服务

        Args:
            embedder: Embedder实例（默认创建新实例）
            milvus_client: Milvus客户端（默认创建新实例）
            pg_client: PostgreSQL客户端（默认创建新实例）
        """
        # 如果没有提供 embedder，根据配置自动选择
        if embedder is None:
            # 使用工厂模式，根据配置自动选择本地模型或 API
            self.embedder = get_embedder_by_mode()
        else:
            self.embedder = embedder
        self.milvus_client = milvus_client or get_milvus_client()
        self.pg_client = pg_client or get_postgres_client()
        
        # 确保Milvus Collection存在
        self._ensure_collection_exists()

    def _ensure_collection_exists(self):
        """确保Milvus Collection存在，如果不存在则创建"""
        collection_name = MilvusCollection.DOCUMENTS
        dimension = self.embedder.get_model_dim()
        
        try:
            collection = self.milvus_client.get_collection(collection_name)
            if collection is None:
                self.logger.info(f"Collection不存在，创建新Collection: {collection_name}, dim={dimension}")
                self.milvus_client.create_collection(
                    collection_name=collection_name,
                    dimension=dimension,
                    description="金融文档向量集合",
                    index_type="IVF_FLAT",
                    metric_type="L2"
                )
            else:
                self.logger.debug(f"Collection已存在: {collection_name}")
        except Exception as e:
            self.logger.error(f"确保Collection存在失败: {e}", exc_info=True)
            raise

    def vectorize_chunks(
        self,
        chunk_ids: List[Union[uuid.UUID, str]],
        force_revectorize: bool = False
    ) -> Dict[str, Any]:
        """
        向量化指定的分块

        Args:
            chunk_ids: 分块ID列表
            force_revectorize: 是否强制重新向量化（删除旧向量）

        Returns:
            向量化结果字典，包含：
            - success: 是否成功
            - vectorized_count: 成功向量化的数量
            - failed_count: 失败数量
            - failed_chunks: 失败的分块ID列表
        """
        if not chunk_ids:
            return {
                "success": True,
                "vectorized_count": 0,
                "failed_count": 0,
                "failed_chunks": []
            }

        self.logger.info(f"开始向量化 {len(chunk_ids)} 个分块...")

        # 转换UUID格式
        chunk_ids_uuid = []
        for chunk_id in chunk_ids:
            if isinstance(chunk_id, str):
                chunk_ids_uuid.append(uuid.UUID(chunk_id))
            else:
                chunk_ids_uuid.append(chunk_id)

        vectorized_count = 0
        failed_count = 0
        failed_chunks = []

        # 从数据库读取分块信息
        # 注意：在 session 关闭前提取所有需要的数据，避免 DetachedInstanceError
        chunks_data = []
        with self.pg_client.get_session() as session:
            for chunk_id in chunk_ids_uuid:
                chunk = session.query(DocumentChunk).filter(
                    DocumentChunk.id == chunk_id
                ).first()

                if not chunk:
                    self.logger.warning(f"分块不存在: {chunk_id}")
                    failed_count += 1
                    failed_chunks.append(str(chunk_id))
                    continue

                # 检查是否已向量化
                if not force_revectorize and chunk.vector_id:
                    self.logger.debug(f"分块已向量化，跳过: {chunk_id}, vector_id={chunk.vector_id}")
                    continue

                # 获取关联的Document信息
                doc = session.query(Document).filter(
                    Document.id == chunk.document_id
                ).first()

                if not doc:
                    self.logger.warning(f"文档不存在: {chunk.document_id}")
                    failed_count += 1
                    failed_chunks.append(str(chunk_id))
                    continue

                # 在 session 关闭前提取所有需要的数据
                chunks_data.append({
                    "chunk_id": str(chunk.id),
                    "document_id": str(chunk.document_id),
                    "chunk_text": chunk.chunk_text,  # 提取文本
                    "stock_code": doc.stock_code,
                    "year": doc.year,
                    "quarter": doc.quarter or 0,
                    # 保存对象引用（用于后续更新，但需要重新查询）
                    "_chunk_id_uuid": chunk.id,
                    "_document_id_uuid": chunk.document_id,
                })

        if not chunks_data:
            self.logger.warning("没有需要向量化的分块")
            return {
                "success": True,
                "vectorized_count": 0,
                "failed_count": failed_count,
                "failed_chunks": failed_chunks
            }

        # 批量处理
        batch_size = embedding_config.EMBEDDING_BATCH_SIZE
        for i in range(0, len(chunks_data), batch_size):
            batch = chunks_data[i:i + batch_size]
            try:
                result = self._vectorize_batch(batch, force_revectorize)
                vectorized_count += result["vectorized_count"]
                failed_count += result["failed_count"]
                failed_chunks.extend(result["failed_chunks"])
            except Exception as e:
                self.logger.error(f"批量向量化失败: {e}", exc_info=True)
                # 标记整批为失败
                for item in batch:
                    failed_count += 1
                    failed_chunks.append(item["chunk_id"])

        self.logger.info(
            f"向量化完成: 成功={vectorized_count}, 失败={failed_count}"
        )

        return {
            "success": True,
            "vectorized_count": vectorized_count,
            "failed_count": failed_count,
            "failed_chunks": failed_chunks
        }

    def _vectorize_batch(
        self,
        chunks_data: List[Dict],
        force_revectorize: bool = False
    ) -> Dict[str, Any]:
        """
        批量向量化一批分块

        Args:
            chunks_data: 分块数据列表，每个元素包含chunk和document
            force_revectorize: 是否强制重新向量化

        Returns:
            批量向量化结果
        """
        if not chunks_data:
            return {
                "vectorized_count": 0,
                "failed_count": 0,
                "failed_chunks": []
            }

        # 提取文本（数据已经在 session 关闭前提取）
        texts = []
        chunk_ids_list = []
        for item in chunks_data:
            texts.append(item["chunk_text"])
            chunk_ids_list.append(item["chunk_id"])

        # 批量生成向量
        try:
            embeddings = self.embedder.embed_batch(texts)
        except Exception as e:
            self.logger.error(f"生成向量失败: {e}", exc_info=True)
            return {
                "vectorized_count": 0,
                "failed_count": len(chunks_data),
                "failed_chunks": [item["chunk_id"] for item in chunks_data]
            }

        if len(embeddings) != len(chunks_data):
            self.logger.error(
                f"向量数量不匹配: 期望={len(chunks_data)}, 实际={len(embeddings)}"
            )
            return {
                "vectorized_count": 0,
                "failed_count": len(chunks_data),
                "failed_chunks": [item["chunk_id"] for item in chunks_data]
            }

        # 准备Milvus插入数据（使用已提取的数据）
        collection_name = MilvusCollection.DOCUMENTS
        document_ids = []
        chunk_ids = []
        stock_codes = []
        years = []
        quarters = []

        for item in chunks_data:
            document_ids.append(item["document_id"])
            chunk_ids.append(item["chunk_id"])
            stock_codes.append(item["stock_code"])
            years.append(item["year"])
            quarters.append(item["quarter"])

        # 插入Milvus
        try:
            vector_ids = self.milvus_client.insert_vectors(
                collection_name=collection_name,
                embeddings=embeddings,
                document_ids=document_ids,
                chunk_ids=chunk_ids,
                stock_codes=stock_codes,
                years=years,
                quarters=quarters
            )
        except Exception as e:
            self.logger.error(f"插入Milvus失败: {e}", exc_info=True)
            return {
                "vectorized_count": 0,
                "failed_count": len(chunks_data),
                "failed_chunks": [item["chunk_id"] for item in chunks_data]
            }

        if len(vector_ids) != len(chunks_data):
            self.logger.error(
                f"Milvus返回的向量ID数量不匹配: 期望={len(chunks_data)}, 实际={len(vector_ids)}"
            )

        # 更新数据库（重新查询对象，因为之前的对象已 detached）
        vectorized_count = 0
        failed_count = 0
        failed_chunks = []
        model_name = self.embedder.get_model_name()

        with self.pg_client.get_session() as session:
            for i, item in enumerate(chunks_data):
                chunk_id_uuid = item["_chunk_id_uuid"]
                vector_id = str(vector_ids[i]) if i < len(vector_ids) else None

                try:
                    # 重新查询 chunk（因为之前的对象已 detached）
                    chunk = session.query(DocumentChunk).filter(
                        DocumentChunk.id == chunk_id_uuid
                    ).first()

                    if not chunk:
                        failed_count += 1
                        failed_chunks.append(item["chunk_id"])
                        self.logger.warning(f"分块不存在: {chunk_id_uuid}")
                        continue

                    # 如果强制重新向量化，先删除旧向量
                    if force_revectorize and chunk.vector_id:
                        # 从Milvus删除旧向量（可选，这里先不实现）
                        pass

                    # 更新分块的向量信息
                    success = crud.update_chunk_vector_id(
                        session=session,
                        chunk_id=chunk_id_uuid,
                        vector_id=vector_id or "",
                        embedding_model=model_name
                    )

                    if success:
                        vectorized_count += 1
                        self.logger.debug(
                            f"更新分块向量ID成功: chunk_id={chunk_id_uuid}, vector_id={vector_id}"
                        )
                    else:
                        failed_count += 1
                        failed_chunks.append(item["chunk_id"])
                        self.logger.warning(f"更新分块向量ID失败: chunk_id={chunk_id_uuid}")

                except Exception as e:
                    failed_count += 1
                    failed_chunks.append(item["chunk_id"])
                    self.logger.error(
                        f"更新分块向量ID异常: chunk_id={chunk_id_uuid}, error={e}",
                        exc_info=True
                    )

            session.commit()

        return {
            "vectorized_count": vectorized_count,
            "failed_count": failed_count,
            "failed_chunks": failed_chunks
        }

    def vectorize_document(
        self,
        document_id: Union[uuid.UUID, str],
        force_revectorize: bool = False
    ) -> Dict[str, Any]:
        """
        向量化文档的所有分块

        Args:
            document_id: 文档ID
            force_revectorize: 是否强制重新向量化

        Returns:
            向量化结果字典
        """
        # 获取文档的所有分块
        with self.pg_client.get_session() as session:
            chunks = crud.get_document_chunks(session, document_id)
            
            if not chunks:
                return {
                    "success": True,
                    "vectorized_count": 0,
                    "failed_count": 0,
                    "failed_chunks": [],
                    "message": "文档没有分块"
                }

            chunk_ids = [chunk.id for chunk in chunks]

        # 向量化所有分块
        return self.vectorize_chunks(chunk_ids, force_revectorize=force_revectorize)


# 全局Vectorizer实例（单例模式）
_vectorizer: Optional[Vectorizer] = None


def get_vectorizer() -> Vectorizer:
    """
    获取全局Vectorizer实例（单例）

    Returns:
        Vectorizer实例

    Example:
        >>> from src.processing.ai.embedding.vectorizer import get_vectorizer
        >>> vectorizer = get_vectorizer()
        >>> result = vectorizer.vectorize_chunks(chunk_ids)
    """
    global _vectorizer
    if _vectorizer is None:
        _vectorizer = Vectorizer()
    return _vectorizer
