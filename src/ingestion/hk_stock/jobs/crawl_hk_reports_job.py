# -*- coding: utf-8 -*-
"""
港股定期报告爬取 Job
纯业务逻辑，无 Dagster 依赖
"""

import os
from typing import Dict, List, Optional, Callable

from src.ingestion.hk_stock import HKReportCrawler
from src.ingestion.hk_stock.jobs.db_helpers import load_hk_company_list_from_db
from src.ingestion.base.base_crawler import CrawlTask
from src.common.constants import Market, DocType
from pathlib import Path
from src.common.config import common_config
from src.common.logger import get_logger

logger = get_logger(__name__)

DEFAULT_OUTPUT_ROOT = str(Path(common_config.PROJECT_ROOT) / "downloads")


def crawl_hk_reports_job(
    year: int,
    output_root: Optional[str] = None,
    workers: int = 4,
    limit: Optional[int] = None,
    stock_codes: Optional[List[str]] = None,
    on_success: Optional[Callable[[object, int, int], None]] = None,
) -> Dict:
    """
    爬取港股定期报告（年报/中报）

    Args:
        year: 年份
        output_root: 输出目录
        workers: 并行数
        limit: 限制公司数量
        stock_codes: 指定股票代码列表（5位）
        on_success: 每成功一个时回调 (result, idx, total)

    Returns:
        Dict with success, total, success_count, fail_count, results, source_type
    """
    output_root = output_root or DEFAULT_OUTPUT_ROOT
    start_date = f"{year}-01-01"
    end_date = f"{year + 1}-06-30"
    os.makedirs(output_root, exist_ok=True)

    try:
        companies = load_hk_company_list_from_db(
            limit=limit,
            stock_codes=stock_codes,
            with_org_id_only=True,
            logger=logger,
        )
    except Exception as e:
        logger.error(f"加载港股公司列表失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "total": 0,
            "success_count": 0,
            "fail_count": 0,
            "results": [],
            "source_type": "hk_stock",
        }

    if not companies:
        logger.warning("未找到港股公司，请先运行 get_hk_companies_job 更新公司列表")
        return {
            "success": False,
            "error": "未找到港股公司列表",
            "total": 0,
            "success_count": 0,
            "fail_count": 0,
            "results": [],
            "source_type": "hk_stock",
        }

    crawler = HKReportCrawler(
        enable_minio=True,
        enable_postgres=True,
        start_date=start_date,
        end_date=end_date,
        workers=workers,
    )

    quarter_doc_type_map = {
        1: DocType.HK_QUARTERLY_REPORT,
        2: DocType.HK_INTERIM_REPORT,
        3: DocType.HK_QUARTERLY_REPORT,
        4: DocType.HK_ANNUAL_REPORT,
    }

    tasks = []
    for company in companies:
        for quarter, doc_type in quarter_doc_type_map.items():
            tasks.append(CrawlTask(
                stock_code=company["code"],
                company_name=company["name"],
                market=Market.HK_STOCK,
                doc_type=doc_type,
                year=year,
                quarter=quarter,
                metadata={"org_id": company.get("org_id")} if company.get("org_id") else {},
            ))

    logger.info(f"生成 {len(tasks)} 个爬取任务")
    results = crawler.crawl_batch(tasks)

    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count
    total = len(results)
    logger.info(f"爬取完成: 成功 {success_count}/{total}, 失败 {fail_count}/{total}")

    # 调用 on_success 回调（用于 Dagster AssetMaterialization）
    if on_success:
        for idx, result in enumerate(results, 1):
            if result.success:
                try:
                    on_success(result, idx, total)
                except Exception as e:
                    logger.warning(f"on_success 回调失败: {e}")

    def _doc_type_str(q: int) -> str:
        if q == 4:
            return "annual_report"
        if q == 2:
            return "interim_report"
        return "quarterly_report"

    return {
        "success": True,
        "total": len(results),
        "success_count": success_count,
        "fail_count": fail_count,
        "source_type": "hk_stock",
        "results": [
            {
                "stock_code": r.task.stock_code,
                "company_name": r.task.company_name,
                "year": r.task.year,
                "quarter": r.task.quarter,
                "doc_type": _doc_type_str(r.task.quarter or 0),
                "success": r.success,
                "minio_object_path": r.minio_object_path if r.success else None,
                "document_id": str(r.document_id) if r.success and r.document_id else None,
                "error": r.error_message if not r.success else None,
            }
            for r in results
        ],
    }
