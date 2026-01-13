# -*- coding: utf-8 -*-
"""
Milvus 向量数据库客户端
提供向量插入、检索、删除等操作
"""

from typing import Optional, List, Dict, Any, Tuple
import numpy as np
from pymilvus import (
    connections, Collection, CollectionSchema, FieldSchema,
    DataType, utility, MilvusException
)

from src.common.config import milvus_config, embedding_config
from src.common.logger import get_logger, LoggerMixin
from src.common.constants import MilvusCollection


class MilvusClient(LoggerMixin):
    """
    Milvus 客户端封装
    提供向量数据库的所有操作
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        alias: str = "default"
    ):
        """
        初始化 Milvus 客户端

        Args:
            host: Milvus 主机地址（默认从配置读取）
            port: Milvus 端口（默认从配置读取）
            user: 用户名（可选）
            password: 密码（可选）
            alias: 连接别名
        """
        self.host = host or milvus_config.MILVUS_HOST
        self.port = port or milvus_config.MILVUS_PORT
        self.user = user or milvus_config.MILVUS_USER
        self.password = password or milvus_config.MILVUS_PASSWORD
        self.alias = alias

        # 连接到 Milvus
        self._connect()

    def _connect(self) -> None:
        """连接到 Milvus"""
        try:
            connections.connect(
                alias=self.alias,
                host=self.host,
                port=str(self.port),
                user=self.user,
                password=self.password
            )
            self.logger.info(f"Milvus 连接成功: {self.host}:{self.port}")
        except MilvusException as e:
            self.logger.error(f"Milvus 连接失败: {e}")
            raise

    def create_collection(
        self,
        collection_name: str,
        dimension: int,
        description: str = "",
        index_type: str = "IVF_FLAT",
        metric_type: str = "L2",
        nlist: int = 128
    ) -> Collection:
        """
        创建 Collection

        Args:
            collection_name: Collection 名称
            dimension: 向量维度
            description: 描述
            index_type: 索引类型（IVF_FLAT, IVF_SQ8, HNSW）
            metric_type: 距离度量（L2, IP, COSINE）
            nlist: IVF 聚类中心数量

        Returns:
            Collection 对象

        Example:
            >>> client = MilvusClient()
            >>> collection = client.create_collection(
            ...     "financial_documents",
            ...     dimension=1024,
            ...     description="金融文档向量集合"
            ... )
        """
        try:
            # 检查 Collection 是否已存在
            if utility.has_collection(collection_name):
                self.logger.info(f"Collection 已存在: {collection_name}")
                return Collection(collection_name)

            # 定义 Schema
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="document_id", dtype=DataType.INT64),
                FieldSchema(name="chunk_id", dtype=DataType.INT64),
                FieldSchema(name="stock_code", dtype=DataType.VARCHAR, max_length=20),
                FieldSchema(name="year", dtype=DataType.INT32),
                FieldSchema(name="quarter", dtype=DataType.INT32),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension)
            ]

            schema = CollectionSchema(
                fields=fields,
                description=description
            )

            # 创建 Collection
            collection = Collection(
                name=collection_name,
                schema=schema,
                using=self.alias
            )

            # 创建索引
            index_params = {
                "index_type": index_type,
                "metric_type": metric_type,
                "params": {"nlist": nlist}
            }

            collection.create_index(
                field_name="embedding",
                index_params=index_params
            )

            self.logger.info(f"Collection 创建成功: {collection_name}, dim={dimension}")
            return collection

        except MilvusException as e:
            self.logger.error(f"创建 Collection 失败: {e}")
            raise

    def get_collection(self, collection_name: str) -> Optional[Collection]:
        """
        获取 Collection

        Args:
            collection_name: Collection 名称

        Returns:
            Collection 对象，如果不存在则返回 None
        """
        try:
            if not utility.has_collection(collection_name):
                self.logger.warning(f"Collection 不存在: {collection_name}")
                return None

            return Collection(collection_name)
        except MilvusException as e:
            self.logger.error(f"获取 Collection 失败: {e}")
            return None

    def insert_vectors(
        self,
        collection_name: str,
        embeddings: List[List[float]],
        document_ids: List[int],
        chunk_ids: List[int],
        stock_codes: List[str],
        years: List[int],
        quarters: List[int]
    ) -> List[int]:
        """
        插入向量

        Args:
            collection_name: Collection 名称
            embeddings: 向量列表
            document_ids: 文档 ID 列表
            chunk_ids: 分块 ID 列表
            stock_codes: 股票代码列表
            years: 年份列表
            quarters: 季度列表

        Returns:
            插入的向量 ID 列表

        Example:
            >>> client = MilvusClient()
            >>> ids = client.insert_vectors(
            ...     "financial_documents",
            ...     embeddings=[[0.1]*1024, [0.2]*1024],
            ...     document_ids=[1, 1],
            ...     chunk_ids=[1, 2],
            ...     stock_codes=["000001", "000001"],
            ...     years=[2023, 2023],
            ...     quarters=[3, 3]
            ... )
        """
        try:
            collection = self.get_collection(collection_name)
            if collection is None:
                raise ValueError(f"Collection 不存在: {collection_name}")

            # 构建数据
            data = [
                document_ids,
                chunk_ids,
                stock_codes,
                years,
                quarters,
                embeddings
            ]

            # 插入数据
            mr = collection.insert(data)

            # 刷新 Collection（确保数据持久化）
            collection.flush()

            self.logger.info(f"插入向量成功: {collection_name}, count={len(embeddings)}")
            return mr.primary_keys

        except MilvusException as e:
            self.logger.error(f"插入向量失败: {e}")
            raise

    def search_vectors(
        self,
        collection_name: str,
        query_vectors: List[List[float]],
        top_k: int = 10,
        expr: Optional[str] = None,
        output_fields: Optional[List[str]] = None
    ) -> List[List[Dict[str, Any]]]:
        """
        检索向量

        Args:
            collection_name: Collection 名称
            query_vectors: 查询向量列表
            top_k: 返回 Top-K 结果
            expr: 过滤表达式（如 "stock_code == '000001' and year == 2023"）
            output_fields: 返回的字段列表

        Returns:
            检索结果列表，每个查询向量返回一个结果列表

        Example:
            >>> client = MilvusClient()
            >>> results = client.search_vectors(
            ...     "financial_documents",
            ...     query_vectors=[[0.1]*1024],
            ...     top_k=5,
            ...     expr="stock_code == '000001'",
            ...     output_fields=["document_id", "chunk_id", "stock_code"]
            ... )
            >>> for hits in results:
            ...     for hit in hits:
            ...         print(hit['distance'], hit['entity'])
        """
        try:
            collection = self.get_collection(collection_name)
            if collection is None:
                raise ValueError(f"Collection 不存在: {collection_name}")

            # 加载 Collection 到内存（如果未加载）
            if not utility.loading_progress(collection_name):
                collection.load()

            # 搜索参数
            search_params = {
                "metric_type": "L2",
                "params": {"nprobe": 10}
            }

            # 执行搜索
            results = collection.search(
                data=query_vectors,
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=output_fields or ["document_id", "chunk_id", "stock_code", "year", "quarter"]
            )

            # 格式化结果
            formatted_results = []
            for hits in results:
                hit_list = []
                for hit in hits:
                    hit_list.append({
                        'id': hit.id,
                        'distance': hit.distance,
                        'entity': hit.entity.to_dict()
                    })
                formatted_results.append(hit_list)

            self.logger.debug(f"检索向量成功: {collection_name}, queries={len(query_vectors)}, top_k={top_k}")
            return formatted_results

        except MilvusException as e:
            self.logger.error(f"检索向量失败: {e}")
            raise

    def delete_vectors(
        self,
        collection_name: str,
        expr: str
    ) -> int:
        """
        删除向量

        Args:
            collection_name: Collection 名称
            expr: 删除条件表达式（如 "document_id == 1"）

        Returns:
            删除的向量数量

        Example:
            >>> client = MilvusClient()
            >>> count = client.delete_vectors(
            ...     "financial_documents",
            ...     expr="document_id == 1"
            ... )
            >>> print(f"删除了 {count} 个向量")
        """
        try:
            collection = self.get_collection(collection_name)
            if collection is None:
                raise ValueError(f"Collection 不存在: {collection_name}")

            # 删除数据
            collection.delete(expr)
            collection.flush()

            self.logger.info(f"删除向量成功: {collection_name}, expr={expr}")
            return 0  # Milvus 不返回删除数量

        except MilvusException as e:
            self.logger.error(f"删除向量失败: {e}")
            raise

    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """
        获取 Collection 统计信息

        Args:
            collection_name: Collection 名称

        Returns:
            统计信息字典

        Example:
            >>> client = MilvusClient()
            >>> stats = client.get_collection_stats("financial_documents")
            >>> print(stats['row_count'])
        """
        try:
            collection = self.get_collection(collection_name)
            if collection is None:
                return {}

            stats = collection.num_entities
            return {
                'collection_name': collection_name,
                'row_count': stats
            }
        except MilvusException as e:
            self.logger.error(f"获取 Collection 统计失败: {e}")
            return {}

    def drop_collection(self, collection_name: str) -> bool:
        """
        删除 Collection（谨慎使用！）

        Args:
            collection_name: Collection 名称

        Returns:
            是否删除成功

        Example:
            >>> client = MilvusClient()
            >>> client.drop_collection("test_collection")
        """
        try:
            if not utility.has_collection(collection_name):
                self.logger.warning(f"Collection 不存在: {collection_name}")
                return False

            utility.drop_collection(collection_name)
            self.logger.warning(f"Collection 已删除: {collection_name}")
            return True

        except MilvusException as e:
            self.logger.error(f"删除 Collection 失败: {e}")
            return False

    def list_collections(self) -> List[str]:
        """
        列出所有 Collection

        Returns:
            Collection 名称列表

        Example:
            >>> client = MilvusClient()
            >>> collections = client.list_collections()
            >>> for name in collections:
            ...     print(name)
        """
        try:
            return utility.list_collections()
        except MilvusException as e:
            self.logger.error(f"列出 Collection 失败: {e}")
            return []

    def disconnect(self) -> None:
        """
        断开连接

        Example:
            >>> client = MilvusClient()
            >>> # ... 使用 Milvus ...
            >>> client.disconnect()
        """
        try:
            connections.disconnect(self.alias)
            self.logger.info("Milvus 连接已断开")
        except Exception as e:
            self.logger.error(f"断开连接失败: {e}")


# 全局客户端实例（单例模式）
_milvus_client: Optional[MilvusClient] = None


def get_milvus_client() -> MilvusClient:
    """
    获取全局 Milvus 客户端实例（单例）

    Returns:
        Milvus 客户端

    Example:
        >>> from src.storage.vector.milvus_client import get_milvus_client
        >>> client = get_milvus_client()
        >>> results = client.search_vectors("financial_documents", [[0.1]*1024], top_k=5)
    """
    global _milvus_client
    if _milvus_client is None:
        _milvus_client = MilvusClient()
    return _milvus_client
