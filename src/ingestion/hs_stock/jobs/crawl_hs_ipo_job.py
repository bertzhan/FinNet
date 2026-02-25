# -*- coding: utf-8 -*-
"""
A股IPO招股说明书爬取 Job
纯业务逻辑，无 Dagster 依赖
"""

import os
from typing import Dict, List, Optional, Callable

from src.ingestion.hs_stock import CninfoIPOProspectusCrawler
from src.ingestion.hs_stock.jobs.db_helpers import load_company_list_from_db
from src.ingestion.base.base_crawler import CrawlTask, CrawlResult
from src.common.constants import Market, DocType
from pathlib import Path
from src.common.config import common_config
from src.common.logger import get_logger

logger = get_logger(__name__)

DEFAULT_OUTPUT_ROOT = str(Path(common_config.PROJECT_ROOT) / "downloads")


def crawl_hs_ipo_job(
    output_root: Optional[str] = None,
    workers: int = 4,
    limit: Optional[int] = None,
    stock_codes: Optional[List[str]] = None,
    force_recrawl: bool = False,
    on_success: Optional[Callable[[object, int, int], None]] = None,
) -> Dict:
    """
    爬取A股IPO招股说明书

    Returns:
        Dict with success, total, success_count, fail_count, results, source_type
    """
    output_root = output_root or DEFAULT_OUTPUT_ROOT
    os.makedirs(output_root, exist_ok=True)

    try:
        companies = load_company_list_from_db(
            limit=limit,
            stock_codes=stock_codes,
            logger=logger,
        )
    except Exception as e:
        logger.error(f"从数据库加载公司列表失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "total": 0,
            "success_count": 0,
            "fail_count": 0,
            "results": [],
            "source_type": "hs_stock",
        }

    if not companies:
        err = f"未找到指定的股票代码: {stock_codes}" if stock_codes else "公司列表为空，请先运行 get_hs_companies_job"
        logger.warning(f"⚠️ {err}")
        return {
            "success": False,
            "error": err,
            "total": 0,
            "success_count": 0,
            "fail_count": 0,
            "results": [],
            "source_type": "hs_stock",
        }

    crawler = CninfoIPOProspectusCrawler(
        enable_minio=True,
        enable_postgres=True,
        workers=workers,
        force_recrawl=force_recrawl,
    )
    tasks = [
        CrawlTask(
            stock_code=c["code"],
            company_name=c["name"],
            market=Market.HS,
            doc_type=DocType.IPO_PROSPECTUS,
            year=None,
            quarter=None,
        )
        for c in companies
    ]

    logger.info(f"生成 {len(tasks)} 个爬取任务")
    results = []
    success_count = 0
    fail_count = 0
    total = len(tasks)

    try:
        for idx, task in enumerate(tasks, 1):
            if idx % 10 == 0 or idx % max(1, total // 10) == 0 or idx == total:
                logger.info(f"[{idx}/{total}] {idx/total*100:.1f}% | {task.stock_code} - {task.company_name}")

            try:
                result = crawler.crawl(task)
                results.append(result)
                if result.success:
                    success_count += 1
                    if on_success:
                        try:
                            on_success(result, idx, total)
                        except Exception as e:
                            logger.warning(f"on_success 回调失败: {e}")
                else:
                    fail_count += 1
                    logger.warning(f"爬取失败: {task.stock_code} - {result.error_message}")
            except Exception as e:
                error_type = type(e).__name__
                if "Interrupt" in error_type or "Interrupted" in error_type:
                    raise
                fail_count += 1
                logger.error(f"任务执行异常: {task.stock_code} - {e}", exc_info=True)
                results.append(CrawlResult(task=task, success=False, error_message=str(e)))

        logger.info(f"爬取完成: 成功 {success_count}/{total}, 失败 {fail_count}/{total}")
    except (KeyboardInterrupt, Exception) as e:
        if "Interrupt" in type(e).__name__ or "Interrupted" in type(e).__name__:
            raise
        logger.error(f"IPO批量爬取异常: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "total": len(tasks),
            "success_count": 0,
            "fail_count": len(tasks),
            "results": [],
            "source_type": "hs_stock",
        }

    return {
        "success": True,
        "output_root": output_root,
        "total": len(results),
        "success_count": success_count,
        "fail_count": fail_count,
        "source_type": "hs_stock",
        "results": [
            {
                "stock_code": r.task.stock_code,
                "company_name": r.task.company_name,
                "year": None,
                "quarter": None,
                "doc_type": "ipo_prospectus",
                "success": r.success,
                "minio_object_path": r.minio_object_path if r.success else None,
                "document_id": r.document_id if r.success else None,
                "error": r.error_message if not r.success else None,
            }
            for r in results
        ],
    }
