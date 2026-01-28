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
from src.common.utils import extract_text_from_table


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

                # 检查是否已向量化（使用 vectorized_at 判断）
                if not force_revectorize and chunk.vectorized_at:
                    self.logger.debug(f"分块已向量化，跳过: {chunk_id}, vectorized_at={chunk.vectorized_at}")
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

                # 处理表格chunk：提取文本内容
                chunk_text = chunk.chunk_text
                if chunk.is_table:
                    # 从表格HTML中提取文本内容
                    extracted_text = extract_text_from_table(chunk.chunk_text)
                    
                    # 检查提取的文本是否有实际内容（至少10个字符）
                    if not extracted_text or len(extracted_text.strip()) < 10:
                        self.logger.debug(
                            f"分块包含表格但无有效文本内容，跳过向量化: "
                            f"chunk_id={chunk_id}, extracted_length={len(extracted_text) if extracted_text else 0}"
                        )
                        continue
                    
                    # 使用提取的文本进行向量化
                    chunk_text = extracted_text
                    self.logger.debug(
                        f"分块包含表格，已提取文本内容: chunk_id={chunk_id}, "
                        f"original_length={len(chunk.chunk_text)}, extracted_length={len(chunk_text)}"
                    )

                # 在 session 关闭前提取所有需要的数据
                chunks_data.append({
                    "chunk_id": str(chunk.id),
                    "document_id": str(chunk.document_id),
                    "chunk_text": chunk_text,  # 使用处理后的文本（表格chunk使用提取的文本）
                    "stock_code": doc.stock_code,
                    "company_name": doc.company_name,
                    "doc_type": doc.doc_type,
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
        failed_embedding_indices = set()  # 在try外部定义，确保后续可以使用
        
        try:
            embeddings = self.embedder.embed_batch(texts)
            
            # ✅ 检查是否有零向量（表示部分失败）
            if embeddings and len(embeddings) > 0:
                dimension = len(embeddings[0])
                zero_vector = [0.0] * dimension
                
                for i, emb in enumerate(embeddings):
                    # 检查是否是零向量（所有元素都是0或接近0）
                    if isinstance(emb, list) and len(emb) == dimension:
                        if all(abs(x) < 1e-10 for x in emb):  # 使用小的阈值判断零向量
                            failed_embedding_indices.add(i)
                            chunk_text_preview = chunks_data[i].get("chunk_text", "")[:200]
                            self.logger.warning(
                                f"检测到零向量（索引 {i}），表示该分块向量化失败:\n"
                                f"  Chunk ID: {chunks_data[i]['chunk_id']}\n"
                                f"  股票代码: {chunks_data[i].get('stock_code', 'N/A')}\n"
                                f"  Chunk Text (前200字符):\n"
                                f"  {chunk_text_preview}\n"
                                f"  {'...' if len(chunks_data[i].get('chunk_text', '')) > 200 else ''}"
                            )
                
                # 如果有失败的向量，记录但继续处理成功的
                if failed_embedding_indices:
                    self.logger.warning(
                        f"⚠️  检测到 {len(failed_embedding_indices)} 个零向量（部分失败），"
                        f"将跳过这些分块，继续处理成功的分块"
                    )
        except Exception as e:
            self.logger.error(f"生成向量失败: {e}", exc_info=True)
            
            # 打印所有失败分块的 chunk_text
            self.logger.error("=" * 80)
            self.logger.error(f"批量向量化失败，共 {len(chunks_data)} 个分块:")
            self.logger.error("=" * 80)
            for i, item in enumerate(chunks_data, 1):
                chunk_text_preview = item.get("chunk_text", "")[:200]  # 前200字符
                self.logger.error(
                    f"\n失败分块 {i}/{len(chunks_data)}:\n"
                    f"  Chunk ID: {item['chunk_id']}\n"
                    f"  Document ID: {item['document_id']}\n"
                    f"  股票代码: {item.get('stock_code', 'N/A')}\n"
                    f"  Chunk Text (前200字符):\n"
                    f"  {chunk_text_preview}\n"
                    f"  {'...' if len(item.get('chunk_text', '')) > 200 else ''}"
                )
            self.logger.error("=" * 80)
            
            return {
                "vectorized_count": 0,
                "failed_count": len(chunks_data),
                "failed_chunks": [item["chunk_id"] for item in chunks_data]
            }

        if len(embeddings) != len(chunks_data):
            self.logger.error(
                f"向量数量不匹配: 期望={len(chunks_data)}, 实际={len(embeddings)}"
            )
            
            # 打印所有分块的 chunk_text
            self.logger.error("=" * 80)
            self.logger.error("向量数量不匹配，所有分块信息:")
            self.logger.error("=" * 80)
            for i, item in enumerate(chunks_data, 1):
                chunk_text_preview = item.get("chunk_text", "")[:200]
                self.logger.error(
                    f"\n分块 {i}/{len(chunks_data)}:\n"
                    f"  Chunk ID: {item['chunk_id']}\n"
                    f"  Document ID: {item['document_id']}\n"
                    f"  股票代码: {item.get('stock_code', 'N/A')}\n"
                    f"  Chunk Text (前200字符):\n"
                    f"  {chunk_text_preview}\n"
                    f"  {'...' if len(item.get('chunk_text', '')) > 200 else ''}"
                )
            self.logger.error("=" * 80)
            
            return {
                "vectorized_count": 0,
                "failed_count": len(chunks_data),
                "failed_chunks": [item["chunk_id"] for item in chunks_data]
            }

        # ✅ 过滤掉零向量（失败的分块），只处理成功的
        successful_data = []
        successful_embeddings = []
        failed_from_zero_vector = []
        
        for i, (item, emb) in enumerate(zip(chunks_data, embeddings)):
            if i in failed_embedding_indices:
                # 这是零向量，标记为失败
                failed_from_zero_vector.append(item["chunk_id"])
            else:
                # 成功的向量，添加到处理列表
                successful_data.append(item)
                successful_embeddings.append(emb)
        
        if failed_from_zero_vector:
            self.logger.info(
                f"过滤掉 {len(failed_from_zero_vector)} 个失败的分块（零向量），"
                f"继续处理 {len(successful_data)} 个成功的分块"
            )
        
        # 如果没有成功的分块，直接返回
        if not successful_data:
            self.logger.warning("所有分块都失败（零向量），无法继续处理")
            return {
                "vectorized_count": 0,
                "failed_count": len(chunks_data),
                "failed_chunks": [item["chunk_id"] for item in chunks_data]
            }

        # 准备Milvus插入数据（只包含成功的分块）
        collection_name = MilvusCollection.DOCUMENTS
        document_ids = []
        chunk_ids = []
        stock_codes = []
        company_names = []
        doc_types = []
        years = []
        quarters = []

        for item in successful_data:
            document_ids.append(item["document_id"])
            chunk_ids.append(item["chunk_id"])
            stock_codes.append(item["stock_code"])
            company_names.append(item["company_name"])
            doc_types.append(item["doc_type"])
            years.append(item["year"])
            quarters.append(item["quarter"])

        # 插入Milvus（只插入成功的向量）
        try:
            vector_ids = self.milvus_client.insert_vectors(
                collection_name=collection_name,
                embeddings=successful_embeddings,
                document_ids=document_ids,
                chunk_ids=chunk_ids,
                stock_codes=stock_codes,
                company_names=company_names,
                doc_types=doc_types,
                years=years,
                quarters=quarters
            )
        except Exception as e:
            self.logger.error(f"插入Milvus失败: {e}", exc_info=True)
            
            # 打印所有分块的 chunk_text
            self.logger.error("=" * 80)
            self.logger.error("插入Milvus失败，所有分块信息:")
            self.logger.error("=" * 80)
            for i, item in enumerate(chunks_data, 1):
                chunk_text_preview = item.get("chunk_text", "")[:200]
                self.logger.error(
                    f"\n分块 {i}/{len(chunks_data)}:\n"
                    f"  Chunk ID: {item['chunk_id']}\n"
                    f"  Document ID: {item['document_id']}\n"
                    f"  股票代码: {item.get('stock_code', 'N/A')}\n"
                    f"  Chunk Text (前200字符):\n"
                    f"  {chunk_text_preview}\n"
                    f"  {'...' if len(item.get('chunk_text', '')) > 200 else ''}"
                )
            self.logger.error("=" * 80)
            return {
                "vectorized_count": 0,
                "failed_count": len(chunks_data),
                "failed_chunks": [item["chunk_id"] for item in chunks_data]
            }

        if len(vector_ids) != len(successful_data):
            self.logger.error(
                f"Milvus返回的向量ID数量不匹配: 期望={len(successful_data)}, 实际={len(vector_ids)}"
            )

        # 更新数据库（重新查询对象，因为之前的对象已 detached）
        # 注意：只处理成功的分块，失败的分块已经在 failed_from_zero_vector 中
        vectorized_count = 0
        failed_count = len(failed_from_zero_vector)  # 从零向量开始的失败数
        failed_chunks = failed_from_zero_vector.copy()  # 复制零向量失败的分块
        model_name = self.embedder.get_model_name()

        with self.pg_client.get_session() as session:
            # 只处理成功的分块
            for i, item in enumerate(successful_data):
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
                        chunk_text_preview = item.get("chunk_text", "")[:200]
                        self.logger.warning(
                            f"分块不存在: {chunk_id_uuid}\n"
                            f"  Document ID: {item['document_id']}\n"
                            f"  股票代码: {item.get('stock_code', 'N/A')}\n"
                            f"  Chunk Text (前200字符):\n"
                            f"  {chunk_text_preview}\n"
                            f"  {'...' if len(item.get('chunk_text', '')) > 200 else ''}"
                        )
                        continue

                    # 注意：由于 Milvus 使用 chunk_id 作为主键，
                    # 重新插入相同 chunk_id 的向量时会自动覆盖旧向量（upsert 行为）
                    # 因此不需要手动删除旧向量

                    # 更新分块的向量化信息（不再需要 vector_id，因为 Milvus 主键就是 chunk_id）
                    success = crud.update_chunk_embedding(
                        session=session,
                        chunk_id=chunk_id_uuid,
                        embedding_model=model_name
                    )

                    if success:
                        vectorized_count += 1
                        self.logger.debug(
                            f"更新分块向量化信息成功: chunk_id={chunk_id_uuid}, model={model_name}"
                        )
                    else:
                        failed_count += 1
                        failed_chunks.append(item["chunk_id"])
                        chunk_text_preview = item.get("chunk_text", "")[:200]
                        self.logger.warning(
                            f"更新分块向量ID失败: chunk_id={chunk_id_uuid}\n"
                            f"  Document ID: {item['document_id']}\n"
                            f"  股票代码: {item.get('stock_code', 'N/A')}\n"
                            f"  Chunk Text (前200字符):\n"
                            f"  {chunk_text_preview}\n"
                            f"  {'...' if len(item.get('chunk_text', '')) > 200 else ''}"
                        )

                except Exception as e:
                    failed_count += 1
                    failed_chunks.append(item["chunk_id"])
                    chunk_text_preview = item.get("chunk_text", "")[:200]
                    self.logger.error(
                        f"更新分块向量ID异常: chunk_id={chunk_id_uuid}, error={e}\n"
                        f"  Document ID: {item['document_id']}\n"
                        f"  股票代码: {item.get('stock_code', 'N/A')}\n"
                        f"  Chunk Text (前200字符):\n"
                        f"  {chunk_text_preview}\n"
                        f"  {'...' if len(item.get('chunk_text', '')) > 200 else ''}",
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
