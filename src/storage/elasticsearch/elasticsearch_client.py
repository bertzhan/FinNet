# -*- coding: utf-8 -*-
"""
Elasticsearch 全文搜索引擎客户端
提供索引创建、文档插入、查询等操作

按照 plan.md 设计：
- 存储层（Storage Layer）→ Elasticsearch
- 全文检索、结构化查询、聚合分析
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import (
    ConnectionError,
    AuthenticationException,
    RequestError,
    NotFoundError
)

from src.common.config import elasticsearch_config
from src.common.logger import get_logger, LoggerMixin


# 全局客户端实例
_elasticsearch_client: Optional['ElasticsearchClient'] = None


def get_elasticsearch_client(force_new: bool = False) -> 'ElasticsearchClient':
    """
    获取全局 Elasticsearch 客户端实例（单例模式）

    Args:
        force_new: 是否强制创建新实例（用于重置连接）

    Returns:
        ElasticsearchClient 实例
    """
    global _elasticsearch_client
    if _elasticsearch_client is None or force_new:
        try:
            _elasticsearch_client = ElasticsearchClient()
        except Exception as e:
            # 如果连接失败，清除实例以便下次重试
            _elasticsearch_client = None
            raise
    return _elasticsearch_client


class ElasticsearchClient(LoggerMixin):
    """
    Elasticsearch 客户端封装
    提供全文搜索引擎的所有操作
    """

    def __init__(
        self,
        hosts: Optional[List[str]] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        use_ssl: Optional[bool] = None,
        verify_certs: Optional[bool] = None,
        ca_certs: Optional[str] = None,
        index_prefix: Optional[str] = None
    ):
        """
        初始化 Elasticsearch 客户端

        Args:
            hosts: Elasticsearch 主机列表（默认从配置读取）
            user: 用户名（可选）
            password: 密码（可选）
            use_ssl: 是否使用 SSL（默认从配置读取）
            verify_certs: 是否验证证书（默认从配置读取）
            ca_certs: CA 证书路径（可选）
            index_prefix: 索引前缀（默认从配置读取）
        """
        self.hosts = hosts or elasticsearch_config.hosts_list
        self.user = user or elasticsearch_config.ELASTICSEARCH_USER
        self.password = password or elasticsearch_config.ELASTICSEARCH_PASSWORD
        self.use_ssl = use_ssl if use_ssl is not None else elasticsearch_config.ELASTICSEARCH_USE_SSL
        self.verify_certs = verify_certs if verify_certs is not None else elasticsearch_config.ELASTICSEARCH_VERIFY_CERTS
        self.ca_certs = ca_certs or elasticsearch_config.ELASTICSEARCH_CA_CERTS
        self.index_prefix = index_prefix or elasticsearch_config.ELASTICSEARCH_INDEX_PREFIX

        # 连接到 Elasticsearch
        self._connect()

    def _connect(self) -> None:
        """连接到 Elasticsearch"""
        try:
            # 构建连接参数（Elasticsearch 8.x API）
            # 确保 hosts 是列表格式
            hosts_list = self.hosts if isinstance(self.hosts, list) else [self.hosts]
            
            connection_params = {
                "hosts": hosts_list,
            }

            # 添加认证信息（仅在启用安全认证时使用）
            # 注意：如果 Elasticsearch 配置了 xpack.security.enabled=false（开发环境），则不需要认证
            # 只有当明确配置了用户名和密码时才使用 basic_auth
            if self.user and self.password:
                connection_params["basic_auth"] = (self.user, self.password)
                self.logger.debug(f"使用认证连接: user={self.user}")
            else:
                self.logger.debug("使用无认证连接（适用于开发环境）")

            # 添加 SSL 配置
            if self.use_ssl:
                connection_params["use_ssl"] = True
                connection_params["verify_certs"] = self.verify_certs
                if self.ca_certs:
                    connection_params["ca_certs"] = self.ca_certs

            # 创建客户端（使用最简单的配置，让 Elasticsearch 客户端使用默认值）
            # 检查客户端版本兼容性（8.x 客户端连接 8.x 服务器）
            import elasticsearch
            client_version = getattr(elasticsearch, '__version__', None)
            if client_version:
                if isinstance(client_version, tuple) and len(client_version) > 0:
                    major_version = client_version[0]
                elif isinstance(client_version, str):
                    major_version = int(client_version.split('.')[0])
                else:
                    major_version = None
                
                if major_version and major_version >= 9:
                    error_msg = (
                        f"版本不兼容：Elasticsearch Python 客户端版本 {client_version} 与服务器版本 8.11.0 不兼容。"
                        f"请安装兼容版本：pip install 'elasticsearch>=8.0.0,<9.0.0'"
                    )
                    self.logger.error(error_msg)
                    raise ValueError(error_msg)
            
            self.client = Elasticsearch(**connection_params)

            # 验证连接
            try:
                # 先尝试获取集群信息（比 ping 提供更多信息）
                try:
                    info = self.client.info()
                    self.logger.debug(f"Elasticsearch 连接成功: {info.get('cluster_name')}, version={info.get('version', {}).get('number')}")
                except Exception as info_error:
                    # 如果 info 失败，尝试 ping
                    ping_result = self.client.ping()
                    if not ping_result:
                        raise ConnectionError("Elasticsearch 连接失败：ping 返回 False")
            except Exception as ping_error:
                error_msg = str(ping_error)
                error_type = type(ping_error).__name__
                self.logger.error(f"Elasticsearch 连接失败: {error_msg}")
                self.logger.error(f"错误类型: {error_type}")
                self.logger.error(f"尝试连接的主机: {self.hosts}")
                self.logger.error(f"连接参数: {connection_params}")
                
                # 记录完整的异常信息
                import traceback
                self.logger.error(f"完整错误堆栈:\n{traceback.format_exc()}")
                
                # 提供更详细的错误信息和排查建议
                if "Connection refused" in error_msg or "Connection error" in error_msg:
                    self.logger.error("可能的原因：")
                    self.logger.error("  1. Elasticsearch 服务未启动")
                    self.logger.error("  2. Elasticsearch 服务正在启动中（请等待 30-60 秒）")
                    self.logger.error("  3. 端口映射不正确")
                    self.logger.error("  4. 认证配置错误（如果启用了安全认证）")
                    self.logger.error("请运行: docker-compose ps elasticsearch")
                    self.logger.error("请运行: curl http://localhost:9200/_cluster/health")
                
                # 重新抛出原始异常以保留完整的堆栈信息
                raise

            self.logger.info(f"Elasticsearch 连接成功: {self.hosts}")
        except ConnectionError as e:
            self.logger.error(f"Elasticsearch 连接失败: {e}")
            self.logger.error(f"请检查：1. Elasticsearch 服务是否运行 2. 主机地址是否正确: {self.hosts}")
            raise
        except AuthenticationException as e:
            self.logger.error(f"Elasticsearch 认证失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Elasticsearch 初始化失败: {e}")
            self.logger.error(f"连接参数: hosts={self.hosts}, use_ssl={self.use_ssl}")
            raise

    def create_index(
        self,
        index_name: str,
        mapping: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        创建索引

        Args:
            index_name: 索引名称（会自动添加前缀）
            mapping: 字段映射定义
            settings: 索引设置

        Returns:
            是否创建成功

        Example:
            >>> client = ElasticsearchClient()
            >>> mapping = {
            ...     "properties": {
            ...         "chunk_text": {"type": "text", "analyzer": "ik_max_word"},
            ...         "stock_code": {"type": "keyword"},
            ...         "publish_date": {"type": "date"}
            ...     }
            ... }
            >>> client.create_index("chunks", mapping=mapping)
        """
        full_index_name = f"{self.index_prefix}_{index_name}"

        try:
            # 检查索引是否已存在
            if self.client.indices.exists(index=full_index_name):
                self.logger.info(f"索引已存在: {full_index_name}")
                return True

            # 检查 IK Analyzer 是否可用
            ik_available = False
            try:
                # 尝试获取已安装的插件列表
                plugins = self.client.cat.plugins(format="json")
                plugin_names = [p.get("component", "") for p in plugins]
                ik_available = any("ik" in name.lower() for name in plugin_names)
            except Exception:
                # 如果无法检查插件，尝试使用 IK analyzer（如果失败会回退到标准分析器）
                try:
                    # 尝试创建一个测试索引来检查 IK analyzer 是否可用
                    test_index = f"{full_index_name}_test_ik"
                    self.client.indices.create(
                        index=test_index,
                        mappings={"properties": {"test": {"type": "text", "analyzer": "ik_smart"}}}
                    )
                    ik_available = True
                    self.client.indices.delete(index=test_index)
                except Exception:
                    ik_available = False
            
            # 根据 IK Analyzer 是否可用选择分析器
            if ik_available:
                text_analyzer = "ik_max_word"
                search_analyzer = "ik_smart"
                self.logger.info("使用 IK Analyzer 进行中文分词")
            else:
                text_analyzer = "standard"  # 标准分析器（支持中文，但效果不如 IK）
                search_analyzer = "standard"
                self.logger.warning("IK Analyzer 不可用，使用标准分析器。建议安装 IK Analyzer 以获得更好的中文分词效果")
            
            # 默认 mapping（中文分词）
            default_mapping = {
                "properties": {
                    "id": {"type": "keyword"},
                    "document_id": {"type": "keyword"},
                    "chunk_index": {"type": "integer"},
                    "chunk_text": {
                        "type": "text",
                        "analyzer": text_analyzer,
                        "search_analyzer": search_analyzer,
                        "fields": {
                            "keyword": {"type": "keyword", "ignore_above": 256}
                        }
                    },
                    "title": {
                        "type": "text",
                        "analyzer": text_analyzer,
                        "fields": {
                            "keyword": {"type": "keyword", "ignore_above": 256}
                        }
                    },
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

            # 默认 settings（只在 IK Analyzer 可用时添加）
            default_settings = {
                "number_of_shards": 5,
                "number_of_replicas": 1,
            }
            
            if ik_available:
                default_settings["analysis"] = {
                    "analyzer": {
                        "ik_max_word": {
                            "type": "ik_max_word"
                        },
                        "ik_smart": {
                            "type": "ik_smart"
                        }
                    }
                }

            # 合并用户提供的 mapping 和 settings
            final_mapping = mapping or default_mapping
            final_settings = settings or default_settings

            # 创建索引（新版本 API，直接传递参数）
            self.client.indices.create(
                index=full_index_name,
                mappings=final_mapping,
                settings=final_settings
            )
            self.logger.info(f"索引创建成功: {full_index_name}")
            return True

        except RequestError as e:
            # 检查是否是资源已存在的错误
            error_info = str(e).lower()
            if "resource_already_exists" in error_info or "already_exists" in error_info:
                self.logger.info(f"索引已存在: {full_index_name}")
                return True
            self.logger.error(f"创建索引失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"创建索引失败: {e}")
            raise

    def index_document(
        self,
        index_name: str,
        document: Dict[str, Any],
        document_id: Optional[str] = None
    ) -> str:
        """
        索引单个文档

        Args:
            index_name: 索引名称（会自动添加前缀）
            document: 文档内容
            document_id: 文档 ID（可选，不提供则自动生成）

        Returns:
            文档 ID

        Example:
            >>> client = ElasticsearchClient()
            >>> doc = {
            ...     "id": "chunk-123",
            ...     "document_id": "doc-456",
            ...     "chunk_text": "这是分块文本内容",
            ...     "stock_code": "000001",
            ...     "market": "a_share"
            ... }
            >>> doc_id = client.index_document("chunks", doc, document_id="chunk-123")
        """
        full_index_name = f"{self.index_prefix}_{index_name}"

        try:
            # 确保索引存在
            if not self.client.indices.exists(index=full_index_name):
                self.create_index(index_name)

            # 索引文档
            response = self.client.index(
                index=full_index_name,
                id=document_id,
                document=document
            )

            doc_id = response.get("_id")
            self.logger.debug(f"文档索引成功: {full_index_name}, id={doc_id}")
            return doc_id

        except Exception as e:
            self.logger.error(f"索引文档失败: {e}, document_id={document_id}")
            raise

    def bulk_index_documents(
        self,
        index_name: str,
        documents: List[Dict[str, Any]],
        document_id_field: Optional[str] = "id"
    ) -> Dict[str, Any]:
        """
        批量索引文档

        Args:
            index_name: 索引名称（会自动添加前缀）
            documents: 文档列表
            document_id_field: 文档 ID 字段名（用于提取文档 ID）

        Returns:
            批量操作结果统计

        Example:
            >>> client = ElasticsearchClient()
            >>> docs = [
            ...     {"id": "chunk-1", "chunk_text": "内容1", ...},
            ...     {"id": "chunk-2", "chunk_text": "内容2", ...}
            ... ]
            >>> result = client.bulk_index_documents("chunks", docs)
        """
        full_index_name = f"{self.index_prefix}_{index_name}"

        try:
            # 确保索引存在
            if not self.client.indices.exists(index=full_index_name):
                self.create_index(index_name)

            # 构建批量操作
            actions = []
            for doc in documents:
                doc_id = doc.get(document_id_field) if document_id_field else None
                action = {
                    "_index": full_index_name,
                    "_id": doc_id,
                    "_source": doc
                }
                actions.append(action)

            # 执行批量操作
            from elasticsearch.helpers import bulk
            success_count, failed_items = bulk(self.client, actions)

            result = {
                "success_count": success_count,
                "failed_count": len(failed_items),
                "failed_items": failed_items
            }

            self.logger.info(
                f"批量索引完成: {full_index_name}, "
                f"成功={success_count}, 失败={len(failed_items)}"
            )

            return result

        except Exception as e:
            self.logger.error(f"批量索引失败: {e}")
            raise

    def search(
        self,
        index_name: str,
        query: Dict[str, Any],
        size: int = 10,
        from_: int = 0,
        sort: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        执行搜索查询

        Args:
            index_name: 索引名称（会自动添加前缀）
            query: 查询 DSL
            size: 返回结果数量
            from_: 起始位置
            sort: 排序规则

        Returns:
            搜索结果

        Example:
            >>> client = ElasticsearchClient()
            >>> query = {
            ...     "bool": {
            ...         "must": [
            ...             {"match": {"chunk_text": "财务报告"}},
            ...             {"term": {"stock_code": "000001"}}
            ...         ]
            ...     }
            ... }
            >>> results = client.search("chunks", query, size=20)
        """
        full_index_name = f"{self.index_prefix}_{index_name}"

        try:
            # 新版本 API，直接传递参数
            search_params = {
                "index": full_index_name,
                "query": query,
                "size": size,
                "from": from_
            }

            if sort:
                search_params["sort"] = sort

            response = self.client.search(**search_params)
            return response

        except Exception as e:
            self.logger.error(f"搜索失败: {e}")
            raise

    def delete_document(
        self,
        index_name: str,
        document_id: str
    ) -> bool:
        """
        删除文档

        Args:
            index_name: 索引名称（会自动添加前缀）
            document_id: 文档 ID

        Returns:
            是否删除成功
        """
        full_index_name = f"{self.index_prefix}_{index_name}"

        try:
            response = self.client.delete(index=full_index_name, id=document_id)
            self.logger.info(f"文档删除成功: {full_index_name}, id={document_id}")
            return response.get("result") == "deleted"

        except NotFoundError:
            self.logger.warning(f"文档不存在: {full_index_name}, id={document_id}")
            return False
        except Exception as e:
            self.logger.error(f"删除文档失败: {e}")
            raise

    def delete_index(self, index_name: str) -> bool:
        """
        删除索引

        Args:
            index_name: 索引名称（会自动添加前缀）

        Returns:
            是否删除成功
        """
        full_index_name = f"{self.index_prefix}_{index_name}"

        try:
            if not self.client.indices.exists(index=full_index_name):
                self.logger.warning(f"索引不存在: {full_index_name}")
                return False

            self.client.indices.delete(index=full_index_name)
            self.logger.info(f"索引删除成功: {full_index_name}")
            return True

        except Exception as e:
            self.logger.error(f"删除索引失败: {e}")
            raise

    def refresh_index(self, index_name: str) -> None:
        """
        刷新索引（使新索引的文档立即可搜索）

        Args:
            index_name: 索引名称（会自动添加前缀）
        """
        full_index_name = f"{self.index_prefix}_{index_name}"

        try:
            self.client.indices.refresh(index=full_index_name)
            self.logger.debug(f"索引刷新成功: {full_index_name}")
        except Exception as e:
            self.logger.error(f"刷新索引失败: {e}")
            raise
