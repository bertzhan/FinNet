# -*- coding: utf-8 -*-
"""
Dagster 爬虫作业定义 - 薄 re-export 层

A股、港股爬虫已迁移至各自 ingestion 子包，本文件仅做向后兼容 re-export。
"""

# A股 - 从 hs_stock.dagster_assets 导入
from src.ingestion.hs_stock.dagster_assets import (
    crawl_hs_reports_job,
    crawl_hs_ipo_job,
    crawl_hs_reports_op,
    crawl_hs_ipo_op,
    daily_crawl_reports_schedule,
    daily_crawl_ipo_schedule,
    manual_trigger_reports_sensor,
    manual_trigger_ipo_sensor,
)

# 港股 - 从 hk_stock.dagster_assets 导入
from src.ingestion.hk_stock.dagster_assets import (
    get_hk_companies_job,
    crawl_hk_reports_job,
    get_hk_companies_op,
    crawl_hk_reports_op,
    weekly_update_hk_companies_schedule,
    daily_crawl_hk_reports_schedule,
    manual_trigger_update_hk_companies_sensor,
    manual_trigger_hk_reports_sensor,
)

# 共享验证逻辑
from src.ingestion.base.crawl_validation import validate_crawl_results_op

# 向后兼容：load_company_list_from_db 供测试等使用
from src.ingestion.hs_stock.jobs.db_helpers import load_company_list_from_db

__all__ = [
    "crawl_hs_reports_job",
    "crawl_hs_ipo_job",
    "crawl_hs_reports_op",
    "crawl_hs_ipo_op",
    "get_hk_companies_job",
    "crawl_hk_reports_job",
    "get_hk_companies_op",
    "crawl_hk_reports_op",
    "validate_crawl_results_op",
    "load_company_list_from_db",
    "daily_crawl_reports_schedule",
    "daily_crawl_ipo_schedule",
    "weekly_update_hk_companies_schedule",
    "daily_crawl_hk_reports_schedule",
    "manual_trigger_reports_sensor",
    "manual_trigger_ipo_sensor",
    "manual_trigger_update_hk_companies_sensor",
    "manual_trigger_hk_reports_sensor",
]
