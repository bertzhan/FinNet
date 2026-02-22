# -*- coding: utf-8 -*-
"""
Dagster 调度定义（A股模块）
集成 A股爬虫到 Dagster 调度系统

包含：
- 公司列表更新 Job (get_hs_companies_job)
- 定期报告爬取 Job (crawl_hs_reports_job)
- IPO招股书爬取 Job (crawl_hs_ipo_job)
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

from src.ingestion.hs_stock.jobs.get_hs_companies_job import get_hs_companies_job as get_hs_companies_job_fn
from src.ingestion.hs_stock.jobs.crawl_hs_reports_job import crawl_hs_reports_job as crawl_hs_reports_job_fn
from src.ingestion.hs_stock.jobs.crawl_hs_ipo_job import crawl_hs_ipo_job as crawl_hs_ipo_job_fn
from src.ingestion.base.crawl_validation import validate_crawl_results_op
from src.common.config import common_config

PROJECT_ROOT = Path(common_config.PROJECT_ROOT)
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "downloads"

# ==================== 配置 Schema ====================

COMPANY_LIST_UPDATE_CONFIG_SCHEMA = {
    "clear_before_update": Field(
        bool,
        default_value=False,
        description="是否在更新前清空除 org_id 外的所有字段",
    ),
    "basic_info_only": Field(
        bool,
        default_value=False,
        description="是否仅获取基础信息，跳过详细信息的拉取",
    ),
}

REPORT_CRAWL_CONFIG_SCHEMA = {
    "output_root": Field(str, is_required=False, description="Output root directory"),
    "workers": Field(int, default_value=4, description="Number of parallel workers (1-16)"),
    "year": Field(int, is_required=True, description="Year to crawl (Q1-Q4)"),
    "limit": Field(int, is_required=False, description="Limit number of companies"),
    "stock_codes": Field(
        list,
        is_required=False,
        description="List of stock codes. Example: ['000001', '000002']",
    ),
}

IPO_CRAWL_CONFIG_SCHEMA = {
    "output_root": Field(str, is_required=False, description="Output root directory"),
    "workers": Field(int, default_value=4, description="Number of parallel workers"),
    "limit": Field(int, is_required=False, description="Limit number of companies"),
    "stock_codes": Field(
        list,
        is_required=False,
        description="List of stock codes. Example: ['000001', '000002']",
    ),
}

# ==================== Ops ====================


@op(config_schema=COMPANY_LIST_UPDATE_CONFIG_SCHEMA)
def get_hs_companies_op(context) -> Dict:
    """更新A股上市公司列表"""
    logger = get_dagster_logger()
    config = context.op_config

    clear_before_update = config.get("clear_before_update", False)
    basic_info_only = config.get("basic_info_only", False)

    def progress_callback(current: int, total: int, code: str) -> None:
        progress_pct = (current / total) * 100
        logger.info(f"📦 [{current}/{total}] {progress_pct:.1f}% | 写入数据库 | {code}")

    try:
        result = get_hs_companies_job_fn(
            clear_before_update=clear_before_update,
            basic_info_only=basic_info_only,
            progress_callback=progress_callback,
        )

        if result.get("success"):
            context.log_event(
                AssetMaterialization(
                    asset_key=["metadata", "hs_listed_companies"],
                    description="A股上市公司列表已更新",
                    metadata={
                        "total": MetadataValue.int(result["total"]),
                        "inserted": MetadataValue.int(result["inserted"]),
                        "updated": MetadataValue.int(result["updated"]),
                        "full_names_success": MetadataValue.int(result.get("full_names_success", 0)),
                        "full_names_error": MetadataValue.int(result.get("full_names_error", 0)),
                        "updated_at": MetadataValue.text(result.get("updated_at", "")),
                    },
                )
            )

        return result
    except Exception as e:
        logger.error(f"[get_hs_companies] 更新失败: {e}", exc_info=True)
        return {"success": False, "error": str(e), "total": 0, "inserted": 0, "updated": 0}


@op(config_schema=REPORT_CRAWL_CONFIG_SCHEMA)
def crawl_hs_reports_op(context) -> Dict:
    """爬取A股定期报告（年报/季报）"""
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
            "source_type": "hs_stock",
        }

    logger.info(f"开始爬取 A股 定期报告 | 年份: {year} | 季度: Q1-Q4")

    def on_success(result, idx: int, total: int) -> None:
        q = result.task.quarter or 0
        doc_type_str = "annual_report" if q == 4 else ("interim_report" if q == 2 else "quarterly_report")
        context.log_event(
            AssetMaterialization(
                asset_key=["bronze", "hs_stock", doc_type_str, str(result.task.year), f"Q{q}"],
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
        return crawl_hs_reports_job_fn(
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
            "source_type": "hs_stock",
        }


@op(config_schema=IPO_CRAWL_CONFIG_SCHEMA)
def crawl_hs_ipo_op(context) -> Dict:
    """爬取A股IPO招股说明书"""
    logger = get_dagster_logger()
    config = context.op_config

    output_root = config.get("output_root") or str(DEFAULT_OUTPUT_ROOT)
    workers = config.get("workers", 4)
    limit = config.get("limit")
    stock_codes = config.get("stock_codes")

    logger.info("开始爬取 A股 IPO招股书")

    def on_success(result, idx: int, total: int) -> None:
        context.log_event(
            AssetMaterialization(
                asset_key=["bronze", "hs_stock", "ipo_prospectus"],
                description=f"{result.task.company_name} IPO招股说明书",
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
        return crawl_hs_ipo_job_fn(
            output_root=output_root,
            workers=workers,
            limit=limit,
            stock_codes=stock_codes,
            on_success=on_success,
        )
    except Exception as e:
        logger.error(f"IPO爬取失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "total": 0,
            "success_count": 0,
            "fail_count": 0,
            "results": [],
            "source_type": "hs_stock",
        }


# ==================== Jobs ====================


@job
def get_hs_companies_job():
    """A股上市公司列表更新作业"""
    get_hs_companies_op()


@job
def crawl_hs_reports_job():
    """A股定期报告爬取作业（爬取 + 验证）"""
    crawl_results = crawl_hs_reports_op()
    validate_crawl_results_op(crawl_results)


@job
def crawl_hs_ipo_job():
    """A股IPO招股说明书爬取作业（爬取 + 验证）"""
    crawl_results = crawl_hs_ipo_op()
    validate_crawl_results_op(crawl_results)


# ==================== Schedules ====================


@schedule(
    job=get_hs_companies_job,
    cron_schedule="0 1 * * *",
    default_status=DefaultScheduleStatus.STOPPED,
)
def daily_update_companies_schedule(context):
    """每日定时更新A股上市公司列表"""
    return RunRequest()


@schedule(
    job=crawl_hs_reports_job,
    cron_schedule="0 2 * * *",
    default_status=DefaultScheduleStatus.STOPPED,
)
def daily_crawl_reports_schedule(context):
    """每日定时爬取A股报告"""
    return RunRequest()


@schedule(
    job=crawl_hs_ipo_job,
    cron_schedule="0 3 * * *",
    default_status=DefaultScheduleStatus.STOPPED,
)
def daily_crawl_ipo_schedule(context):
    """每日定时爬取IPO招股说明书"""
    return RunRequest()


# ==================== Sensors ====================


@sensor(job=get_hs_companies_job, default_status=DefaultSensorStatus.STOPPED)
def manual_trigger_companies_sensor(context):
    """手动触发更新上市公司列表"""
    return RunRequest()


@sensor(job=crawl_hs_reports_job, default_status=DefaultSensorStatus.STOPPED)
def manual_trigger_reports_sensor(context):
    """手动触发爬取报告"""
    return RunRequest()


@sensor(job=crawl_hs_ipo_job, default_status=DefaultSensorStatus.STOPPED)
def manual_trigger_ipo_sensor(context):
    """手动触发爬取IPO"""
    return RunRequest()


# ==================== 导出 ====================

__all__ = [
    "get_hs_companies_job",
    "crawl_hs_reports_job",
    "crawl_hs_ipo_job",
    "get_hs_companies_op",
    "crawl_hs_reports_op",
    "crawl_hs_ipo_op",
    "daily_update_companies_schedule",
    "daily_crawl_reports_schedule",
    "daily_crawl_ipo_schedule",
    "manual_trigger_companies_sensor",
    "manual_trigger_reports_sensor",
    "manual_trigger_ipo_sensor",
]
