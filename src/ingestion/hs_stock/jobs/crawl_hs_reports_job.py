# -*- coding: utf-8 -*-
"""
A股定期报告爬取 Job
纯业务逻辑，无 Dagster 依赖
"""

import os
from typing import Dict, List, Optional, Callable

from src.ingestion.hs_stock import ReportCrawler
from src.ingestion.hs_stock.jobs.db_helpers import load_company_list_from_db
from src.ingestion.base.base_crawler import CrawlTask, CrawlResult
from src.common.constants import Market, DocType
from pathlib import Path
from src.common.config import common_config
from src.common.logger import get_logger
from src.storage.metadata.postgres_client import get_postgres_client

logger = get_logger(__name__)

DEFAULT_OUTPUT_ROOT = str(Path(common_config.PROJECT_ROOT) / "downloads")


def crawl_hs_reports_job(
    year: int,
    output_root: Optional[str] = None,
    workers: int = 4,
    limit: Optional[int] = None,
    stock_codes: Optional[List[str]] = None,
    force_recrawl: bool = False,
    on_success: Optional[Callable[[object, int, int], None]] = None,
) -> Dict:
    """
    爬取A股定期报告（年报/季报）

    Args:
        year: 年份
        output_root: 输出目录
        workers: 并行数
        limit: 限制公司数量
        stock_codes: 指定股票代码列表
        on_success: 每成功一个时回调 (result, idx, total)

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

    years_quarters = [(year, 1), (year, 2), (year, 3), (year, 4)]
    crawler = ReportCrawler(
        enable_minio=True,
        enable_postgres=True,
        workers=workers,
        force_recrawl=force_recrawl
    )

    # 预过滤：排除 documents 表中已存在的任务（force_recrawl 时不过滤）
    existing_keys = set()
    if not force_recrawl:
        try:
            pg = get_postgres_client()
            with pg.get_session() as session:
                from src.storage.metadata.models import Document
                from sqlalchemy import and_
                rows = session.query(Document.stock_code, Document.year, Document.quarter).filter(
                    and_(
                        Document.market == "hs_stock",
                        Document.year == year,
                    )
                ).all()
                existing_keys = {(r.stock_code, r.year, r.quarter) for r in rows}
            if existing_keys:
                logger.info(f"documents 表已存在 {len(existing_keys)} 条记录（stock_code/year/quarter），将跳过对应任务")
        except Exception as e:
            logger.warning(f"查询 documents 表失败，将不进行预过滤: {e}")

    tasks = []
    for company in companies:
        for y, q in years_quarters:
            if not force_recrawl and (company["code"], y, q) in existing_keys:
                continue
            doc_type = DocType.ANNUAL_REPORT if q == 4 else (
                DocType.INTERIM_REPORT if q == 2 else DocType.QUARTERLY_REPORT
            )
            tasks.append(CrawlTask(
                stock_code=company["code"],
                company_name=company["name"],
                market=Market.HS,
                doc_type=doc_type,
                year=y,
                quarter=q,
            ))

    logger.info(f"生成 {len(tasks)} 个爬取任务" + (f"（已排除 {len(existing_keys)} 条已存在记录）" if existing_keys else ""))
    results = []
    success_count = 0
    fail_count = 0
    total = len(tasks)

    try:
        for idx, task in enumerate(tasks, 1):
            if idx % 10 == 0 or idx % max(1, total // 10) == 0 or idx == total:
                logger.info(f"[{idx}/{total}] {idx/total*100:.1f}% | {task.stock_code} - {task.company_name} {task.year}Q{task.quarter}")

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
        logger.error(f"批量爬取异常: {e}", exc_info=True)
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
                "year": r.task.year,
                "quarter": r.task.quarter,
                "doc_type": r.task.doc_type.value if r.task.doc_type else "quarterly_report",
                "success": r.success,
                "minio_object_path": r.minio_object_path if r.success else None,
                "document_id": r.document_id if r.success else None,
                "error": r.error_message if not r.success else None,
            }
            for r in results
        ],
    }
