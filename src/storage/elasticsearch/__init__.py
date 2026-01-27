# -*- coding: utf-8 -*-
"""
Elasticsearch 存储模块
提供全文搜索引擎的客户端封装
"""

from src.storage.elasticsearch.elasticsearch_client import ElasticsearchClient, get_elasticsearch_client

__all__ = [
    "ElasticsearchClient",
    "get_elasticsearch_client",
]
