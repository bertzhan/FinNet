# -*- coding: utf-8 -*-
"""
Elasticsearch 客户端封装
提供连接管理、索引创建、批量索引、全文搜索等功能
"""

from typing import List, Dict, Any, Optional

from elasticsearch import Elasticsearch

from src.common.config import elasticsearch_config
from src.common.logger import get_logger

logger = get_logger(__name__)


class ElasticsearchClient:
    """
    Elasticsearch 客户端封装
    支持连接管理、索引创建、批量索引、全文搜索
    """

    def __init__(
        self,
        hosts: Optional[List[str]] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        use_ssl: Optional[bool] = None,
        verify_certs: Optional[bool] = None,
        ca_certs: Optional[str] = None,
        index_prefix: Optional[str] = None,
    ):
        """
        初始化 Elasticsearch 客户端

        Args:
            hosts: 主机列表（默认从配置读取）
            user: 用户名（可选，无认证时传 None）
            password: 密码（可选）
            use_ssl: 是否使用 SSL
            verify_certs: 是否验证证书
            ca_certs: CA 证书路径（可选）
            index_prefix: 索引前缀（默认 finnet）
        """
        config = elasticsearch_config
        hosts = hosts or config.hosts_list
        user = user if user is not None else config.ELASTICSEARCH_USER
        password = password if password is not None else config.ELASTICSEARCH_PASSWORD
        use_ssl = use_ssl if use_ssl is not None else config.ELASTICSEARCH_USE_SSL
        verify_certs = (
            verify_certs if verify_certs is not None else config.ELASTICSEARCH_VERIFY_CERTS
        )
        ca_certs = ca_certs or config.ELASTICSEARCH_CA_CERTS
        self.index_prefix = index_prefix or config.ELASTICSEARCH_INDEX_PREFIX

        # 构建连接参数
        es_kwargs: Dict[str, Any] = {
            "hosts": hosts,
            "use_ssl": use_ssl,
            "verify_certs": verify_certs,
        }
        if ca_certs:
            es_kwargs["ca_certs"] = ca_certs
        if user and password:
            es_kwargs["basic_auth"] = (user, password)

        self.client = Elasticsearch(**es_kwargs)
        logger.debug(f"Elasticsearch 客户端已初始化: hosts={hosts}")

    def _full_index_name(self, index_name: str) -> str:
        """获取带前缀的完整索引名"""
        return f"{self.index_prefix}_{index_name}"

    def create_index(self, index_name: str) -> bool:
        """
        创建索引（如果不存在）
        自动检测 IK 分词器，不可用时使用标准分析器

        Args:
            index_name: 索引名称（不含前缀）

        Returns:
            是否创建成功
        """
        full_name = self._full_index_name(index_name)
        if self.client.indices.exists(index=full_name):
            logger.info(f"索引已存在: {full_name}")
            return True

        # 尝试使用 IK 分词器
        mappings = {
            "properties": {
                "id": {"type": "keyword"},
                "document_id": {"type": "keyword"},
                "chunk_index": {"type": "integer"},
                "chunk_text": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_smart"},
                "title": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_smart"},
                "title_level": {"type": "integer"},
                "chunk_size": {"type": "integer"},
                "is_table": {"type": "boolean"},
                "stock_code": {"type": "keyword"},
                "company_name": {"type": "keyword"},
                "market": {"type": "keyword"},
                "doc_type": {"type": "keyword"},
                "year": {"type": "integer"},
                "quarter": {"type": "integer"},
                "publish_date": {"type": "date"},
                "created_at": {"type": "date"},
            }
        }

        try:
            self.client.indices.create(index=full_name, body={"mappings": mappings})
            logger.info(f"索引创建成功: {full_name}")
            return True
        except Exception as e:
            if "analysis-ik" in str(e).lower() or "analyzer" in str(e).lower():
                # IK 不可用，使用标准分析器
                logger.warning(f"IK 分词器不可用，使用标准分析器: {e}")
                mappings["properties"]["chunk_text"] = {"type": "text"}
                mappings["properties"]["title"] = {"type": "text"}
                self.client.indices.create(index=full_name, body={"mappings": mappings})
                return True
            raise

    def bulk_index_documents(
        self,
        index_name: str,
        documents: List[Dict[str, Any]],
        document_id_field: str = "id",
    ) -> Dict[str, Any]:
        """
        批量索引文档

        Args:
            index_name: 索引名称（不含前缀）
            documents: 文档列表
            document_id_field: 文档 ID 字段名

        Returns:
            包含 success_count, failed_count, failed_items 的字典
        """
        full_name = self._full_index_name(index_name)
        failed_items: List[Dict[str, Any]] = []

        if not documents:
            return {"success_count": 0, "failed_count": 0, "failed_items": []}

        # 构建 actions，过滤缺少 id 的文档
        actions = []
        for doc in documents:
            doc_id = doc.get(document_id_field)
            if doc_id is None:
                failed_items.append({"doc": doc, "error": "missing document_id"})
                continue
            actions.append({
                "_index": full_name,
                "_id": str(doc_id),
                "_source": doc,
            })

        if not actions:
            return {"success_count": 0, "failed_count": len(failed_items), "failed_items": failed_items}

        from elasticsearch.helpers import bulk

        try:
            success_count, errors = bulk(
                self.client,
                actions,
                raise_on_error=False,
                raise_on_exception=False,
            )
            failed_items.extend(errors)
        except Exception as e:
            logger.error(f"批量索引失败: {e}", exc_info=True)
            failed_items.append({"error": str(e)})

        return {
            "success_count": success_count,
            "failed_count": len(failed_items),
            "failed_items": failed_items,
        }

    def search(
        self,
        index_name: str,
        query: Dict[str, Any],
        size: int = 10,
        from_: int = 0,
    ) -> Dict[str, Any]:
        """
        执行搜索

        Args:
            index_name: 索引名称（不含前缀）
            query: Elasticsearch 查询 DSL
            size: 返回数量
            from_: 起始偏移

        Returns:
            搜索结果，包含 hits 等
        """
        full_name = self._full_index_name(index_name)
        body = {
            "query": query,
            "size": size,
            "from": from_,
        }
        return self.client.search(index=full_name, body=body)


# 单例客户端
_es_client: Optional[ElasticsearchClient] = None


def get_elasticsearch_client() -> ElasticsearchClient:
    """获取 Elasticsearch 客户端单例"""
    global _es_client
    if _es_client is None:
        _es_client = ElasticsearchClient()
    return _es_client
