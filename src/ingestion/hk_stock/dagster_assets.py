# -*- coding: utf-8 -*-
"""
Dagster 调度定义（港股模块）
集成港股爬虫到 Dagster 调度系统

包含：
- 公司列表更新 Job (get_hk_companies_job)
- 定期报告爬取 Job (crawl_hk_reports_job)
- 定时调度 Schedules
- 手动触发 Sensors
"""

from pathlib import Path
from typing import Dict

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

from src.ingestion.hk_stock.jobs.get_hk_companies_job import get_hk_companies_job as get_hk_companies_job_fn
from src.ingestion.hk_stock.jobs.crawl_hk_reports_job import crawl_hk_reports_job as crawl_hk_reports_job_fn
from src.ingestion.base.crawl_validation import validate_crawl_results_op
from src.common.config import common_config

PROJECT_ROOT = Path(common_config.PROJECT_ROOT)
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "downloads"

# ==================== 配置 Schema ====================

HK_COMPANY_UPDATE_CONFIG_SCHEMA = {
    "clear_before_update": Field(
        bool,
        default_value=False,
        description="是否在更新前清空除 org_id 外的所有字段",
    ),
    "basic_info_only": Field(
        bool,
        default_value=False,
        description="是否仅获取基础信息，跳过 akshare 详情拉取",
    ),
}

HK_REPORT_CRAWL_CONFIG_SCHEMA = {
    "output_root": Field(str, is_required=False, description="Output root directory"),
    "workers": Field(int, default_value=4, description="Number of parallel workers"),
    "year": Field(
        int,
        is_required=True,
        description="Year to crawl. start_date={year}-01-01, end_date={year+1}-06-30",
    ),
    "limit": Field(int, is_required=False, description="Limit number of companies"),
    "stock_codes": Field(
        list,
        is_required=False,
        description="List of stock codes (5-digit). Example: ['00001', '00700']",
    ),
}

# ==================== Ops ====================


@op(config_schema=HK_COMPANY_UPDATE_CONFIG_SCHEMA)
def get_hk_companies_op(context) -> Dict:
    """更新港股公司列表"""
    logger = get_dagster_logger()
    config = context.op_config

    clear_before_update = config.get("clear_before_update", False)
    basic_info_only = config.get("basic_info_only", False)

    def progress_callback(current: int, total: int, code: str) -> None:
        progress_pct = (current / total) * 100
        logger.info(f"📦 [{current}/{total}] {progress_pct:.1f}% | 获取公司详情 | {code}")

    try:
        result = get_hk_companies_job_fn(
            clear_before_update=clear_before_update,
            basic_info_only=basic_info_only,
            progress_callback=progress_callback,
        )

        if result.get("success"):
            context.log_event(
                AssetMaterialization(
                    asset_key=["hk_stock", "companies"],
                    description=f"更新港股公司列表: {result['count']} 家股本证券",
                    metadata={
                        "total_count": MetadataValue.int(result["count"]),
                        "clear_before_update": MetadataValue.bool(clear_before_update),
                        "basic_info_only": MetadataValue.bool(basic_info_only),
                    },
                )
            )

        return result
    except Exception as e:
        logger.error(f"[get_hk_companies] 更新失败: {e}", exc_info=True)
        return {"success": False, "error": str(e), "count": 0}


@op(config_schema=HK_REPORT_CRAWL_CONFIG_SCHEMA)
def crawl_hk_reports_op(context) -> Dict:
    """爬取港股定期报告（年报/中报）"""
    logger = get_dagster_logger()
    config = context.op_config

    output_root = config.get("output_root") or str(DEFAULT_OUTPUT_ROOT)
    workers = config.get("workers", 4)
    year = config.get("year")
    limit = config.get("limit")
    stock_codes = config.get("stock_codes")

    if year is None:
        logger.error("year 参数是必需的")
        return {
            "success": False,
            "error": "year 参数是必需的",
            "total": 0,
            "success_count": 0,
            "fail_count": 0,
            "results": [],
            "source_type": "hk_stock",
        }

    logger.info(f"开始爬取 港股 定期报告 | 年份: {year} | 日期: {year}-01-01 ~ {year+1}-06-30")

    def on_success(result, idx: int, total: int) -> None:
        q = result.task.quarter or 0
        doc_type_str = "annual_report" if q == 4 else ("interim_report" if q == 2 else "quarterly_report")
        context.log_event(
            AssetMaterialization(
                asset_key=["bronze", "hk_stock", doc_type_str, str(result.task.year), f"Q{q}"],
                description=f"{result.task.company_name} {result.task.year} Q{q}",
                metadata={
                    "stock_code": MetadataValue.text(result.task.stock_code),
                    "company_name": MetadataValue.text(result.task.company_name),
                    "minio_path": MetadataValue.text(result.minio_object_path or ""),
                    "file_size": MetadataValue.int(result.file_size or 0),
                    "file_hash": MetadataValue.text(result.file_hash or ""),
                    "document_id": MetadataValue.text(str(result.document_id) if result.document_id else ""),
                    "progress": MetadataValue.text(f"{idx}/{total} ({idx/total*100:.1f}%)"),
                },
            )
        )

    try:
        return crawl_hk_reports_job_fn(
            year=year,
            output_root=output_root,
            workers=workers,
            limit=limit,
            stock_codes=stock_codes,
            on_success=on_success,
        )
    except Exception as e:
        logger.error(f"爬取失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "total": 0,
            "success_count": 0,
            "fail_count": 0,
            "results": [],
            "source_type": "hk_stock",
        }


# ==================== Jobs ====================


@job
def get_hk_companies_job():
    """港股公司列表更新作业"""
    get_hk_companies_op()


@job
def crawl_hk_reports_job():
    """港股定期报告爬取作业（爬取 + 验证）"""
    crawl_results = crawl_hk_reports_op()
    validate_crawl_results_op(crawl_results)


# ==================== Schedules ====================


@schedule(
    job=get_hk_companies_job,
    cron_schedule="0 1 * * 1",
    default_status=DefaultScheduleStatus.STOPPED,
)
def weekly_update_hk_companies_schedule(context):
    """每周一凌晨1点更新港股公司列表"""
    return RunRequest()


@schedule(
    job=crawl_hk_reports_job,
    cron_schedule="0 4 * * *",
    default_status=DefaultScheduleStatus.STOPPED,
)
def daily_crawl_hk_reports_schedule(context):
    """每日凌晨4点爬取港股报告"""
    return RunRequest()


# ==================== Sensors ====================


@sensor(job=get_hk_companies_job, default_status=DefaultSensorStatus.STOPPED)
def manual_trigger_update_hk_companies_sensor(context):
    """手动触发更新港股公司列表"""
    return RunRequest()


@sensor(job=crawl_hk_reports_job, default_status=DefaultSensorStatus.STOPPED)
def manual_trigger_hk_reports_sensor(context):
    """手动触发爬取港股报告"""
    return RunRequest()


# ==================== 导出 ====================

__all__ = [
    "get_hk_companies_job",
    "crawl_hk_reports_job",
    "get_hk_companies_op",
    "crawl_hk_reports_op",
    "weekly_update_hk_companies_schedule",
    "daily_crawl_hk_reports_schedule",
    "manual_trigger_update_hk_companies_sensor",
    "manual_trigger_hk_reports_sensor",
]
