# -*- coding: utf-8 -*-
"""
Storage Metadata 模块
提供元数据存储相关的功能
"""

from .postgres_client import PostgreSQLClient, get_postgres_client
from .models import (
    Base,
    Document,
    DocumentChunk,
    CrawlTask,
    ParseTask,
    ValidationLog,
    QuarantineRecord,
    EmbeddingTask,
    ParsedDocument,
    Image,
    ImageAnnotation,
    ListedCompany
)
from . import crud
from .quarantine_manager import QuarantineManager, get_quarantine_manager

__all__ = [
    # 客户端
    'PostgreSQLClient',
    'get_postgres_client',
    # 模型
    'Base',
    'Document',
    'DocumentChunk',
    'CrawlTask',
    'ParseTask',
    'ValidationLog',
    'QuarantineRecord',
    'EmbeddingTask',
    'ParsedDocument',
    'Image',
    'ImageAnnotation',
    'ListedCompany',
    # CRUD
    'crud',
    # 隔离管理器
    'QuarantineManager',
    'get_quarantine_manager',
]
