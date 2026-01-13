# -*- coding: utf-8 -*-
"""
爬虫模块
统一的数据采集接口
"""

from .base_crawler import (
    BaseCrawler,
    Market,
    DocType,
    CrawlTask,
    CrawlResult,
)

from .validation import (
    DataValidator,
    ValidationStage,
    ValidationLevel,
    ValidationResult,
)

from .storage import StorageManager

__all__ = [
    "BaseCrawler",
    "Market",
    "DocType",
    "CrawlTask",
    "CrawlResult",
    "DataValidator",
    "ValidationStage",
    "ValidationLevel",
    "ValidationResult",
    "StorageManager",
]
