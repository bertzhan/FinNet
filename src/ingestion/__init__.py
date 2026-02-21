# -*- coding: utf-8 -*-
"""
Ingestion layer - Data collection from various sources

Modules:
- base: Base crawler classes and common components
- hs_stock: A-share crawler (CNINFO)
- hk_stock: HK stock crawler (TBD)
- us_stock: US stock crawler (TBD)
"""

from .base import BaseCrawler, CrawlTask, CrawlResult
from .hs_stock import ReportCrawler, CninfoAShareCrawler

__all__ = [
    'BaseCrawler',
    'CrawlTask',
    'CrawlResult',
    'CninfoAShareCrawler',
]
