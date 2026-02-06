# -*- coding: utf-8 -*-
"""
港股数据采集模块

提供港股定期报告的爬取功能，包括：
- 年报 (HK_ANNUAL_REPORT)
- 中期报告 (HK_INTERIM_REPORT)
- 季度报告 (HK_QUARTERLY_REPORT)
"""

from .crawlers.report_crawler import HKReportCrawler
from .api.hkex_client import HKEXClient, HKEXDocType, HKEXDocument
from .utils.rate_limiter import AdaptiveRateLimiter
from .utils.parser import HKEXTitleParser

__all__ = [
    'HKReportCrawler',
    'HKEXClient',
    'HKEXDocType',
    'HKEXDocument',
    'AdaptiveRateLimiter',
    'HKEXTitleParser',
]
