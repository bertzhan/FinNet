# -*- coding: utf-8 -*-
"""
A股 (HS) 数据采集 Jobs
纯业务逻辑，无 Dagster 依赖，可独立测试
"""

from .get_hs_companies_job import get_hs_companies_job
from .crawl_hs_reports_job import crawl_hs_reports_job
from .crawl_hs_ipo_job import crawl_hs_ipo_job

__all__ = [
    "get_hs_companies_job",
    "crawl_hs_reports_job",
    "crawl_hs_ipo_job",
]
