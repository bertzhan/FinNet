# -*- coding: utf-8 -*-
"""
Ingestion layer - Data collection from various sources

Modules:
- base: Base crawler classes and common components
- a_share: A-share crawler (CNINFO)
- hk_stock: HK stock crawler (TBD)
- us_stock: US stock crawler (TBD)
"""

from .base import BaseCrawler, CrawlTask, CrawlResult
from .a_share import ReportCrawler, CninfoAShareCrawler

__all__ = [
    'BaseCrawler',
    'CrawlTask',
    'CrawlResult',
    'CninfoAShareCrawler',
]
