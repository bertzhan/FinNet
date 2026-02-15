# -*- coding: utf-8 -*-
"""
Dagster 调度定义（美股模块）
集成美股爬虫到 Dagster 调度系统

包含：
- 公司列表更新 Job
- SEC 财报爬取 Job（通过 year、stock_codes 等参数配置，与 A 股对齐）
- 定时调度 Schedules
- 手动触发 Sensors
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path

from dagster import (
    job,
    op,
    schedule,
    sensor,
    DefaultSensorStatus,
    DefaultScheduleStatus,
    RunRequest,
    Field,
    get_dagster_logger,
    AssetMaterialization,
    MetadataValue,
)

from src.ingestion.us_stock.jobs.update_us_companies_job import update_us_companies_job
from src.ingestion.us_stock.jobs.crawl_us_reports_job import crawl_us_reports_job as crawl_us_reports_job_fn
from src.common.config import common_config

# 获取项目根目录
PROJECT_ROOT = Path(common_config.PROJECT_ROOT)


# ==================== 配置 Schema ====================

# 公司列表同步配置
SYNC_COMPANIES_CONFIG_SCHEMA = {
    "force_refresh": Field(
        bool,
        default_value=False,
        description="Force refresh all companies (normally only new/updated companies are synced)"
    ),
}

# 财报爬取配置（与 crawl_a_share_reports_op 对齐）
FILINGS_CRAWL_CONFIG_SCHEMA = {
    "output_root": Field(
        str,
        is_required=False,
        description="Output root directory (default: downloads/, 美股主要用于临时文件)"
    ),
    "enable_minio": Field(
        bool,
        default_value=True,
        description="Enable MinIO upload"
    ),
    "enable_postgres": Field(
        bool,
        default_value=True,
        description="Enable PostgreSQL metadata recording"
    ),
    "year": Field(
        int,
        is_required=True,
        description="Year to crawl. start_date={year}-01-01, end_date={year}-12-31"
    ),
    "limit": Field(
        int,
        is_required=False,
        description="Limit number of companies to crawl (None = all companies)"
    ),
    "stock_codes": Field(
        list,
        is_required=False,
        description="List of stock codes to crawl (None = all companies). Example: ['AAPL', 'MSFT', 'GOOGL']"
    ),
}


# ==================== Ops ====================

@op(config_schema=SYNC_COMPANIES_CONFIG_SCHEMA)
def update_us_companies_op(context) -> Dict:
    """
    更新美股公司列表

    从 SEC API 获取所有 13,000+ 上市公司，写入 us_listed_companies 表

    Returns:
        {
            'total_companies': 13000,
            'companies_added': 500,
            'companies_updated': 12500,
            'duration_seconds': 45
        }
    """
    logger = get_dagster_logger()
    config = context.op_config

    force_refresh = config.get("force_refresh", False)

    logger.info("开始更新美股公司列表")
    logger.info(f"  强制刷新: {force_refresh}")

    try:
        # 调用更新 Job
        result = update_us_companies_job()

        # 记录 Asset Materialization
        context.log_event(
            AssetMaterialization(
                asset_key="us_listed_companies",
                description=f"更新美股公司列表完成",
                metadata={
                    "total_companies": MetadataValue.int(result['total_companies']),
                    "companies_added": MetadataValue.int(result['companies_added']),
                    "companies_updated": MetadataValue.int(result['companies_updated']),
                    "duration_seconds": MetadataValue.int(result['duration_seconds']),
                }
            )
        )

        logger.info("✅ 美股公司列表更新完成")
        logger.info(f"  总公司数: {result['total_companies']}")
        logger.info(f"  新增: {result['companies_added']}")
        logger.info(f"  更新: {result['companies_updated']}")
        logger.info(f"  耗时: {result['duration_seconds']}秒")

        return result

    except Exception as e:
        logger.error(f"❌ 美股公司列表更新失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@op(config_schema=FILINGS_CRAWL_CONFIG_SCHEMA)
def crawl_us_reports_op(context) -> Dict:
    """
    爬取 SEC 财报

    按 year 爬取该年度的财报，日期范围：{year}-01-01 至 {year}-12-31

    Returns:
        {
            'companies_processed': 100,
            'filings_discovered': 500,
            'filings_downloaded': 480,
            'filings_failed': 20,
            'filings_skipped': 300,
            'duration_seconds': 1800
        }
    """
    logger = get_dagster_logger()
    config = context.op_config

    output_root = config.get("output_root") or str(PROJECT_ROOT / "downloads")
    enable_minio = config.get("enable_minio", True)
    enable_postgres = config.get("enable_postgres", True)
    year = config.get("year")
    limit = config.get("limit")
    stock_codes = config.get("stock_codes")

    if year is None:
        logger.error("year 参数是必需的")
        return {
            "success": False,
            "error": "year 参数是必需的",
            "companies_processed": 0,
            "filings_discovered": 0,
            "filings_downloaded": 0,
            "filings_failed": 0,
            "filings_skipped": 0,
            "duration_seconds": 0,
        }

    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"

    logger.info("开始爬取 SEC 财报")
    logger.info(f"  年份: {year}，日期范围: {start_date} 到 {end_date}")
    logger.info(f"  配置: enable_minio={enable_minio}, enable_postgres={enable_postgres}")
    if limit:
        logger.info(f"  限制公司数: {limit}")
    if stock_codes:
        logger.info(f"  指定股票: {stock_codes}")

    try:
        # 调用爬取 Job
        result = crawl_us_reports_job_fn(
            mode="backfill",
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            tickers=stock_codes,
            enable_minio=enable_minio,
            enable_postgres=enable_postgres,
        )

        # 记录 Asset Materialization
        context.log_event(
            AssetMaterialization(
                asset_key="us_sec_filings",
                description=f"SEC 财报爬取完成（year={year}）",
                metadata={
                    "year": MetadataValue.int(year),
                    "companies_processed": MetadataValue.int(result['companies_processed']),
                    "filings_discovered": MetadataValue.int(result['filings_discovered']),
                    "filings_downloaded": MetadataValue.int(result['filings_downloaded']),
                    "filings_failed": MetadataValue.int(result['filings_failed']),
                    "filings_skipped": MetadataValue.int(result['filings_skipped']),
                    "duration_seconds": MetadataValue.int(result['duration_seconds']),
                }
            )
        )

        logger.info("✅ SEC 财报爬取完成")
        logger.info(f"  处理公司数: {result['companies_processed']}")
        logger.info(f"  发现财报数: {result['filings_discovered']}")
        logger.info(f"  下载成功: {result['filings_downloaded']}")
        logger.info(f"  下载失败: {result['filings_failed']}")
        logger.info(f"  已跳过: {result['filings_skipped']}")
        logger.info(f"  耗时: {result['duration_seconds']}秒")

        return result

    except Exception as e:
        logger.error(f"❌ SEC 财报爬取失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "companies_processed": 0,
            "filings_discovered": 0,
            "filings_downloaded": 0,
            "filings_failed": 0,
            "filings_skipped": 0,
            "duration_seconds": 0,
        }


# ==================== Jobs ====================

@job
def update_us_companies_job_dagster():
    """
    美股公司列表更新作业

    流程：
    1. 从 SEC API 获取所有公司列表
    2. Upsert 到 us_listed_companies 表
    """
    update_us_companies_op()


@job
def crawl_us_reports_job():
    """
    美股财报爬取作业

    流程：
    1. 查询目标公司列表（us_listed_companies）
    2. 爬取财报（10-K、10-Q、20-F、40-F）
    3. 上传到 MinIO 和 PostgreSQL

    通过 run_config 配置 mode、start_date、end_date 等参数：
    - mode='incremental': 增量（最近7天）
    - mode='backfill': 回填（需配置 start_date、end_date）
    """
    crawl_us_reports_op()


# ==================== Schedules ====================

@schedule(
    job=update_us_companies_job_dagster,
    cron_schedule="0 1 * * 0",  # 每周日凌晨1点执行（美股公司列表变化较慢）
    default_status=DefaultScheduleStatus.STOPPED,
)
def weekly_update_us_companies_schedule(context):
    """
    每周更新美股公司列表（周日凌晨1点）

    SEC 公司列表变化较慢，每周更新一次即可
    """
    return RunRequest()


@schedule(
    job=crawl_us_reports_job,
    cron_schedule="0 3 * * 1",  # 每周一凌晨3点执行
    default_status=DefaultScheduleStatus.STOPPED,
)
def weekly_crawl_us_reports_schedule(context):
    """
    每周爬取 SEC 财报（周一凌晨3点）

    默认增量模式，爬取最近7天的新财报（10-K、10-Q、20-F、40-F）
    """
    current_year = datetime.now().year
    return RunRequest(
        run_config={
            "ops": {
                "crawl_us_reports_op": {
                    "config": {
                        "year": current_year,
                    }
                }
            }
        }
    )


# ==================== Sensors ====================

@sensor(
    job=update_us_companies_job_dagster,
    default_status=DefaultSensorStatus.STOPPED,
)
def manual_trigger_update_us_companies_sensor(context):
    """
    手动触发美股公司列表更新

    可以通过 Dagster UI 手动触发
    """
    # 这个 sensor 不会自动触发，仅用于手动触发
    return None


@sensor(
    job=crawl_us_reports_job,
    default_status=DefaultSensorStatus.STOPPED,
)
def manual_trigger_crawl_us_reports_sensor(context):
    """
    手动触发 SEC 财报爬取

    可以通过 Dagster UI 手动触发，支持配置 mode、start_date、end_date 等参数
    """
    # 这个 sensor 不会自动触发，仅用于手动触发
    return None


# ==================== 导出 ====================

__all__ = [
    # Jobs
    "update_us_companies_job_dagster",
    "crawl_us_reports_job",
    # Schedules
    "weekly_update_us_companies_schedule",
    "weekly_crawl_us_reports_schedule",
    # Sensors
    "manual_trigger_update_us_companies_sensor",
    "manual_trigger_crawl_us_reports_sensor",
]
