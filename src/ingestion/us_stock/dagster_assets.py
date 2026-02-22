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

from src.ingestion.us_stock.jobs.get_us_companies_job import get_us_companies_job as get_us_companies_job_fn
from src.ingestion.us_stock.jobs.crawl_us_reports_job import crawl_us_reports_job as crawl_us_reports_job_fn
from src.common.config import common_config

# 获取项目根目录
PROJECT_ROOT = Path(common_config.PROJECT_ROOT)


# ==================== 配置 Schema ====================

# 公司列表同步配置（与 A股/港股 统一为两个参数）
SYNC_COMPANIES_CONFIG_SCHEMA = {
    "clear_before_update": Field(
        bool,
        default_value=False,
        description="是否在更新前清空除 org_id 外的所有字段（默认 False，使用 upsert 策略；org_id 为主键）"
    ),
    "basic_info_only": Field(
        bool,
        default_value=False,
        description="是否仅获取基础信息，跳过 submissions 详情拉取"
    ),
}

# 财报爬取配置（与 crawl_hs_reports_op 对齐）
FILINGS_CRAWL_CONFIG_SCHEMA = {
    "output_root": Field(
        str,
        is_required=False,
        description="Output root directory (default: downloads/, 美股主要用于临时文件)"
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
def get_us_companies_op(context) -> Dict:
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

    clear_before_update = config.get("clear_before_update", False)
    basic_info_only = config.get("basic_info_only", False)

    logger.info(
        f"[get_us_companies] 开始更新美股公司列表 | "
        f"clear_before_update={clear_before_update}, basic_info_only={basic_info_only}"
    )

    def progress_callback(current: int, total: int, code: str) -> None:
        progress_pct = (current / total) * 100
        logger.info(f"📦 [{current}/{total}] {progress_pct:.1f}% | 写入数据库 | {code}")

    try:
        # 调用更新 Job
        result = get_us_companies_job_fn(
            clear_before_update=clear_before_update,
            basic_info_only=basic_info_only,
            progress_callback=progress_callback,
        )

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

        logger.info(
            f"[get_us_companies] 更新完成 | "
            f"总={result['total_companies']}, 新增={result['companies_added']}, "
            f"更新={result['companies_updated']}, 耗时={result['duration_seconds']}s"
        )

        return result

    except Exception as e:
        logger.error(f"[get_us_companies] 更新失败: {e}", exc_info=True)
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
    logger.info(f"开始爬取 美股 SEC财报 | 年份: {year} | 日期: {start_date} ~ {end_date}")

    try:
        # 每文档 AssetMaterialization 回调（与 A股/港股 统一格式）
        def on_filing_success(crawl_result, success_count: int, filings_discovered: int):
            task = crawl_result.task
            doc_type_str = task.doc_type.value  # 10k, 10q, 20f, 40f
            asset_key = ["bronze", "us_stock", doc_type_str, str(task.year)]
            if task.quarter is not None:
                asset_key.append(f"Q{task.quarter}")
            context.log_event(
                AssetMaterialization(
                    asset_key=asset_key,
                    description=f"{task.company_name} {task.year} {f'Q{task.quarter}' if task.quarter else 'FY'}",
                    metadata={
                        "stock_code": MetadataValue.text(task.stock_code),
                        "company_name": MetadataValue.text(task.company_name),
                        "minio_path": MetadataValue.text(crawl_result.minio_object_path or ""),
                        "file_size": MetadataValue.int(crawl_result.file_size or 0),
                        "file_hash": MetadataValue.text(crawl_result.file_hash or ""),
                        "document_id": MetadataValue.text(str(crawl_result.document_id) if crawl_result.document_id else ""),
                        "progress": MetadataValue.text(f"{success_count}/{filings_discovered} ({success_count/max(1,filings_discovered)*100:.1f}%)"),
                    }
                )
            )

        # 调用爬取 Job
        result = crawl_us_reports_job_fn(
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            tickers=stock_codes,
            enable_minio=True,
            enable_postgres=True,
            on_filing_success=on_filing_success,
        )

        total = result['filings_downloaded'] + result['filings_failed']
        logger.info(f"爬取完成: 成功 {result['filings_downloaded']}/{total}, 失败 {result['filings_failed']}/{total}")
        return result

    except Exception as e:
        logger.error(f"爬取失败: {e}", exc_info=True)
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
def get_us_companies_job():
    """
    美股公司列表更新作业

    流程：
    1. 从 SEC API 获取所有公司列表
    2. Upsert 到 us_listed_companies 表
    """
    get_us_companies_op()


@job
def crawl_us_reports_job():
    """
    美股财报爬取作业

    流程：
    1. 查询目标公司列表（us_listed_companies）
    2. 爬取财报（10-K、10-Q、20-F、40-F）
    3. 上传到 MinIO 和 PostgreSQL

    通过 run_config 配置 year（日期范围：{year}-01-01 至 {year}-12-31）
    """
    crawl_us_reports_op()


# ==================== Schedules ====================

@schedule(
    job=get_us_companies_job,
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

    按当前年份爬取财报（10-K、10-Q、20-F、40-F）
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
    job=get_us_companies_job,
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

    可以通过 Dagster UI 手动触发，支持配置 year 等参数
    """
    # 这个 sensor 不会自动触发，仅用于手动触发
    return None


# ==================== 导出 ====================

__all__ = [
    # Jobs
    "get_us_companies_job",
    "crawl_us_reports_job",
    # Schedules
    "weekly_update_us_companies_schedule",
    "weekly_crawl_us_reports_schedule",
    # Sensors
    "manual_trigger_update_us_companies_sensor",
    "manual_trigger_crawl_us_reports_sensor",
]
