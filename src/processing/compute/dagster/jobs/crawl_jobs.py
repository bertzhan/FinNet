# -*- coding: utf-8 -*-
"""
Dagster 爬虫作业定义
集成新的 ingestion 层爬虫到 Dagster 调度系统

按照 plan.md 设计：
- 数据采集层（Ingestion Layer）→ Dagster 调度
- 支持定时调度、数据质量检查、可视化监控
"""

import os
from datetime import datetime
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
    asset,
    AssetMaterialization,
    MetadataValue,
)

# 导入新的爬虫模块
from src.ingestion.a_share import ReportCrawler, CninfoIPOProspectusCrawler
from src.ingestion.base.base_crawler import CrawlTask, CrawlResult
from src.common.constants import Market, DocType
from src.common.config import common_config
from src.storage.metadata.quarantine_manager import QuarantineManager
from src.storage.metadata import get_postgres_client, crud

# 获取项目根目录
PROJECT_ROOT = Path(common_config.PROJECT_ROOT)
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "downloads"


# ==================== 配置 Schema ====================

# 使用 config_schema 字典方式（兼容所有 Dagster 版本）
REPORT_CRAWL_CONFIG_SCHEMA = {
    "output_root": Field(
        str,
        is_required=False,
        description="Output root directory (default: downloads/)"
    ),
    "workers": Field(
        int,
        default_value=4,
        description="Number of parallel workers (1-16)"
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
        is_required=False,
        description="Year to crawl (None = auto: current and previous quarter, specified = all quarters of that year)"
    ),
    "limit": Field(
        int,
        is_required=False,
        description="Limit number of companies to crawl (None = all companies)"
    ),
    "stock_codes": Field(
        list,
        is_required=False,
        description="List of stock codes to crawl (None = use limit filter, specified = only crawl these codes). Example: ['000001', '000002']"
    ),
}

IPO_CRAWL_CONFIG_SCHEMA = {
    "output_root": Field(
        str,
        is_required=False,
        description="Output root directory (default: downloads/)"
    ),
    "workers": Field(
        int,
        default_value=4,
        description="Number of parallel workers (1-16)"
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
    "limit": Field(
        int,
        is_required=False,
        description="Limit number of companies to crawl (None = all companies)"
    ),
    "stock_codes": Field(
        list,
        is_required=False,
        description="List of stock codes to crawl (None = use limit filter, specified = only crawl these codes). Example: ['000001', '000002']"
    ),
}


# ==================== 辅助函数 ====================

def load_company_list_from_db(
    limit: Optional[int] = None,
    stock_codes: Optional[List[str]] = None,
    logger=None
) -> List[Dict[str, str]]:
    """
    从数据库加载公司列表

    Args:
        limit: 限制返回数量（None 表示返回所有）
        stock_codes: 按股票代码列表过滤（None 表示不过滤）
        logger: 日志记录器（如果为 None，使用标准 logging）

    Returns:
        公司列表 [{'code': '000001', 'name': '平安银行'}, ...]
    """
    if logger is None:
        import logging
        logger = logging.getLogger(__name__)

    companies = []
    try:
        pg_client = get_postgres_client()
        with pg_client.get_session() as session:
            # 如果指定了股票代码列表，优先使用股票代码过滤
            if stock_codes:
                from src.storage.metadata.models import ListedCompany
                # 查询指定的股票代码
                listed_companies = session.query(ListedCompany).filter(
                    ListedCompany.code.in_(stock_codes)
                ).all()
                logger.info(f"按股票代码过滤: 指定 {len(stock_codes)} 个代码，找到 {len(listed_companies)} 家公司")
            else:
                # 使用原有的 limit 过滤
                listed_companies = crud.get_all_listed_companies(session, limit=limit)

            for company in listed_companies:
                companies.append({
                    'code': company.code,
                    'name': company.name
                })

        if stock_codes:
            logger.info(f"从数据库加载了 {len(companies)} 家公司（按股票代码: {stock_codes}）")
        else:
            logger.info(f"从数据库加载了 {len(companies)} 家公司")
    except Exception as e:
        logger.error(f"从数据库加载公司列表失败: {e}", exc_info=True)
        raise  # 重新抛出异常，让调用者知道失败

    return companies


def calculate_quarters() -> tuple:
    """
    计算当前季度和上一季度
    
    Returns:
        (current_year, current_quarter, prev_year, prev_quarter)
    """
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    
    if current_month <= 3:
        current_quarter = 1
    elif current_month <= 6:
        current_quarter = 2
    elif current_month <= 9:
        current_quarter = 3
    else:
        current_quarter = 4
    
    # 计算上一季度
    if current_quarter == 1:
        prev_year = current_year - 1
        prev_quarter = 4
    else:
        prev_year = current_year
        prev_quarter = current_quarter - 1
    
    return current_year, current_quarter, prev_year, prev_quarter


# ==================== Dagster Ops ====================

@op(config_schema=REPORT_CRAWL_CONFIG_SCHEMA)
def crawl_a_share_reports_op(context) -> Dict:
    """
    爬取A股定期报告（年报/季报）
    
    按照 plan.md 设计：
    - 自动计算上一季度和当前季度
    - 批量爬取所有上市公司报告
    - 自动上传到 MinIO（Bronze层）
    - 自动记录到 PostgreSQL
    """
    config = context.op_config
    logger = get_dagster_logger()
    
    # 解析配置
    output_root = config.get("output_root") or str(DEFAULT_OUTPUT_ROOT)
    workers = config.get("workers", 4)
    enable_minio = config.get("enable_minio", True)
    enable_postgres = config.get("enable_postgres", True)
    
    # 计算年份和季度
    year = config.get("year")
    
    if year is None:
        # 自动计算：爬取当前季度和上一季度
        current_year, current_quarter, prev_year, prev_quarter = calculate_quarters()
        years_quarters = [
            (prev_year, prev_quarter),
            (current_year, current_quarter),
        ]
        logger.info(f"自动计算季度: {prev_year}Q{prev_quarter}, {current_year}Q{current_quarter}")
    else:
        # 指定年份：爬取该年的所有季度（Q1, Q2, Q3, Q4）
        years_quarters = [
            (year, 1),  # Q1: 季度报告
            (year, 2),  # Q2: 半年报
            (year, 3),  # Q3: 季度报告
            (year, 4),  # Q4: 年报
        ]
        logger.info(f"指定年份 {year}，将爬取该年的所有季度报告: Q1, Q2, Q3, Q4")

    # 确保输出目录存在
    os.makedirs(output_root, exist_ok=True)

    # 从数据库加载公司列表
    limit = config.get("limit")
    stock_codes = config.get("stock_codes")

    # 构建日志信息
    if stock_codes:
        logger.info(f"从数据库加载公司列表（按股票代码: {stock_codes}）...")
    elif limit is not None:
        logger.info(f"从数据库加载公司列表（限制前 {limit} 家）...")
    else:
        logger.info("从数据库加载公司列表...")

    try:
        companies = load_company_list_from_db(
            limit=limit,
            stock_codes=stock_codes,
            logger=logger
        )
        if not companies:
            if stock_codes:
                logger.warning(f"⚠️ 公司列表为空，未找到指定的股票代码: {stock_codes}")
                return {
                    "success": False,
                    "error": f"未找到指定的股票代码: {stock_codes}",
                    "total": 0,
                    "success_count": 0,
                    "fail_count": 0,
                    "results": []
                }
            else:
                logger.warning("⚠️ 公司列表为空，请先运行 update_listed_companies_job 更新公司列表")
                return {
                    "success": False,
                    "error": "公司列表为空，请先运行 update_listed_companies_job 更新公司列表",
                    "total": 0,
                    "success_count": 0,
                    "fail_count": 0,
                    "results": []
                }

        # 构建过滤信息
        filter_info = ""
        if stock_codes:
            filter_info = f"（按股票代码: {stock_codes}）"
        elif limit is not None:
            filter_info = f"（限制为前 {limit} 家）"
        logger.info(f"✅ 成功加载 {len(companies)} 家公司{filter_info}")
    except Exception as e:
        logger.error(f"❌ 从数据库加载公司列表失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"从数据库加载公司列表失败: {str(e)}",
            "total": 0,
            "success_count": 0,
            "fail_count": 0,
            "results": []
        }
    
    # 记录配置信息
    logger.info(f"爬虫配置: enable_minio={enable_minio}, enable_postgres={enable_postgres}, workers={workers}" + (f", limit={limit}" if limit is not None else ""))
    
    # 创建爬虫实例（不再使用 old_pdf_dir）
    crawler = ReportCrawler(
        enable_minio=enable_minio,
        enable_postgres=enable_postgres,
        workers=workers
    )
    
    # 验证 MinIO 配置
    if enable_minio:
        if crawler.enable_minio and crawler.minio_client:
            logger.info("✅ MinIO 已启用且客户端初始化成功")
        else:
            logger.error(f"❌ MinIO 配置异常: enable_minio={crawler.enable_minio}, client={crawler.minio_client is not None}")
    else:
        logger.warning("⚠️ MinIO 未启用（配置中 enable_minio=False）")
    
    # 生成任务列表
    tasks = []
    for company in companies:
        for y, q in years_quarters:
            # 根据季度自动确定文档类型
            # Q1, Q3: 季度报告 (quarterly_report)
            # Q2: 半年报 (interim_report)
            # Q4: 年报 (annual_report)
            if q == 4:
                task_doc_type = DocType.ANNUAL_REPORT
            elif q == 2:
                task_doc_type = DocType.INTERIM_REPORT
            else:
                task_doc_type = DocType.QUARTERLY_REPORT

            tasks.append(CrawlTask(
                stock_code=company['code'],
                company_name=company['name'],
                market=Market.A_SHARE,
                doc_type=task_doc_type,
                year=y,
                quarter=q
            ))
    
    logger.info(f"生成 {len(tasks)} 个爬取任务（{len(companies)} 家公司 × {len(years_quarters)} 个季度）")
    
    # 执行批量爬取（实时记录进度和资产）
    results = []
    success_count = 0
    fail_count = 0
    total = len(tasks)
    
    try:
        # 自己循环调用 crawl()，以便实时记录进度和 AssetMaterialization
        for idx, task in enumerate(tasks, 1):
            # 实时进度日志（每10个或每10%显示一次，或最后一个）
            if idx % 10 == 0 or idx % max(1, total // 10) == 0 or idx == total:
                progress_pct = idx / total * 100
                logger.info(
                    f"📦 [{idx}/{total}] {progress_pct:.1f}% | "
                    f"正在爬取: {task.stock_code} - {task.company_name} "
                    f"{task.year}Q{task.quarter if task.quarter else ''}"
                )
            
            # 执行单个任务
            try:
                result = crawler.crawl(task)
                results.append(result)
                
                # 实时记录 AssetMaterialization（成功时立即记录）
                if result.success:
                    success_count += 1
                    
                    # 根据季度确定文档类型字符串（用于资产key）
                    if result.task.quarter == 4:
                        doc_type_str = "annual_report"
                    elif result.task.quarter == 2:
                        doc_type_str = "interim_report"
                    else:
                        doc_type_str = "quarterly_report"
                    
                    # 立即记录 AssetMaterialization，无需等待所有任务完成
                    try:
                        context.log_event(
                            AssetMaterialization(
                                asset_key=["bronze", "a_share", doc_type_str, str(result.task.year), f"Q{result.task.quarter}"],
                                description=f"{result.task.company_name} {result.task.year} Q{result.task.quarter}",
                                metadata={
                                    "stock_code": MetadataValue.text(result.task.stock_code),
                                    "company_name": MetadataValue.text(result.task.company_name),
                                    "minio_path": MetadataValue.text(result.minio_object_path or ""),
                                    "file_size": MetadataValue.int(result.file_size or 0),
                                    "file_hash": MetadataValue.text(result.file_hash or ""),
                                    "document_id": MetadataValue.text(str(result.document_id) if result.document_id else ""),
                                    "progress": MetadataValue.text(f"{idx}/{total} ({idx/total*100:.1f}%)"),
                                }
                            )
                        )
                        logger.debug(f"✅ 已记录资产: {result.task.stock_code} {result.task.year} Q{result.task.quarter}")
                    except Exception as e:
                        logger.warning(f"记录 AssetMaterialization 失败 (task={result.task.stock_code}): {e}")
                else:
                    fail_count += 1
                    logger.warning(
                        f"❌ 爬取失败: {task.stock_code} ({task.company_name}) "
                        f"{task.year} Q{task.quarter} - {result.error_message}"
                    )
            except KeyboardInterrupt:
                # 用户手动中断（Ctrl+C）
                logger.warning(f"⚠️ 爬取被用户中断: {task.stock_code}")
                raise
            except Exception as e:
                # 检查是否是 Dagster 中断异常
                error_type = type(e).__name__
                if "Interrupt" in error_type or "Interrupted" in error_type:
                    logger.warning(f"⚠️ 爬取被中断: {task.stock_code}, error_type={error_type}")
                    raise
                
                fail_count += 1
                logger.error(f"❌ 任务执行异常: {task.stock_code} - {e}", exc_info=True)
                # 创建失败结果
                from src.ingestion.base.base_crawler import CrawlResult
                results.append(CrawlResult(
                    task=task,
                    success=False,
                    error_message=str(e)
                ))
        
        logger.info(f"✅ 爬取完成: 成功 {success_count}/{total}, 失败 {fail_count}/{total}")
        
        # 记录失败任务的详细信息
        if fail_count > 0:
            logger.warning(f"⚠️ 有 {fail_count} 个任务失败，详细错误信息：")
            failed_results = [r for r in results if not r.success]
            for i, result in enumerate(failed_results[:10], 1):  # 最多显示10个
                logger.error(
                    f"  失败任务 {i}: {result.task.stock_code} ({result.task.company_name}) "
                    f"{result.task.year} Q{result.task.quarter} - {result.error_message}"
                )
            if fail_count > 10:
                logger.warning(f"  ... 还有 {fail_count - 10} 个失败任务")
    
    except KeyboardInterrupt:
        logger.warning("⚠️ 批量爬取被用户中断")
        raise
    except Exception as e:
        # 检查是否是 Dagster 中断异常
        error_type = type(e).__name__
        if "Interrupt" in error_type or "Interrupted" in error_type:
            logger.warning(f"⚠️ 批量爬取被中断: {error_type}")
            raise
        
        logger.error(f"❌ 批量爬取过程中发生异常: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"批量爬取异常: {str(e)}",
            "total": len(tasks),
            "success_count": 0,
            "fail_count": len(tasks),
            "results": []
        }
    
    # 返回结果
    return {
        "success": True,
        "output_root": output_root,
        "total": len(results),
        "success_count": success_count,
        "fail_count": fail_count,
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
        ]
    }


@op(config_schema=IPO_CRAWL_CONFIG_SCHEMA)
def crawl_a_share_ipo_op(context) -> Dict:
    """
    爬取A股IPO招股说明书
    
    按照 plan.md 设计：
    - 批量爬取所有IPO招股说明书
    - 自动上传到 MinIO（Bronze层）
    - 自动记录到 PostgreSQL
    """
    config = context.op_config
    logger = get_dagster_logger()
    
    # 解析配置
    output_root = config.get("output_root") or str(DEFAULT_OUTPUT_ROOT)
    workers = config.get("workers", 4)
    enable_minio = config.get("enable_minio", True)
    enable_postgres = config.get("enable_postgres", True)
    
    # 确保输出目录存在
    os.makedirs(output_root, exist_ok=True)
    
    # 从数据库加载公司列表
    limit = config.get("limit")
    stock_codes = config.get("stock_codes")

    # 构建日志信息
    if stock_codes:
        logger.info(f"从数据库加载公司列表（按股票代码: {stock_codes}）...")
    elif limit is not None:
        logger.info(f"从数据库加载公司列表（限制前 {limit} 家）...")
    else:
        logger.info("从数据库加载公司列表...")

    try:
        companies = load_company_list_from_db(
            limit=limit,
            stock_codes=stock_codes,
            logger=logger
        )
        if not companies:
            if stock_codes:
                logger.warning(f"⚠️ 公司列表为空，未找到指定的股票代码: {stock_codes}")
                return {
                    "success": False,
                    "error": f"未找到指定的股票代码: {stock_codes}",
                    "total": 0,
                    "success_count": 0,
                    "fail_count": 0,
                    "results": []
                }
            else:
                logger.warning("⚠️ 公司列表为空，请先运行 update_listed_companies_job 更新公司列表")
                return {
                    "success": False,
                    "error": "公司列表为空，请先运行 update_listed_companies_job 更新公司列表",
                    "total": 0,
                    "success_count": 0,
                    "fail_count": 0,
                    "results": []
                }

        # 构建过滤信息
        filter_info = ""
        if stock_codes:
            filter_info = f"（按股票代码: {stock_codes}）"
        elif limit is not None:
            filter_info = f"（限制为前 {limit} 家）"
        logger.info(f"✅ 成功加载 {len(companies)} 家公司{filter_info}")
    except Exception as e:
        logger.error(f"❌ 从数据库加载公司列表失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"从数据库加载公司列表失败: {str(e)}",
            "total": 0,
            "success_count": 0,
            "fail_count": 0,
            "results": []
        }
    
    # 创建爬虫实例（不再使用 old_pdf_dir）
    crawler = CninfoIPOProspectusCrawler(
        enable_minio=enable_minio,
        enable_postgres=enable_postgres,
        workers=workers
    )
    
    # 生成任务列表（IPO不需要year和quarter）
    tasks = [
        CrawlTask(
            stock_code=company['code'],
            company_name=company['name'],
            market=Market.A_SHARE,
            doc_type=DocType.IPO_PROSPECTUS,
            year=None,
            quarter=None
        )
        for company in companies
    ]
    
    logger.info(f"生成 {len(tasks)} 个IPO爬取任务")
    
    # 执行批量爬取（实时记录进度和资产）
    results = []
    success_count = 0
    fail_count = 0
    minio_upload_count = 0
    minio_fail_count = 0
    total = len(tasks)
    
    try:
        # 自己循环调用 crawl()，以便实时记录进度和 AssetMaterialization
        for idx, task in enumerate(tasks, 1):
            # 实时进度日志（每10个或每10%显示一次，或最后一个）
            if idx % 10 == 0 or idx % max(1, total // 10) == 0 or idx == total:
                progress_pct = idx / total * 100
                logger.info(
                    f"📦 [{idx}/{total}] {progress_pct:.1f}% | "
                    f"正在爬取IPO: {task.stock_code} - {task.company_name}"
                )
            
            # 执行单个任务
            try:
                result = crawler.crawl(task)
                results.append(result)
                
                # 实时记录 AssetMaterialization（成功时立即记录）
                if result.success:
                    success_count += 1
                    
                    # 统计 MinIO 上传情况
                    if result.minio_object_path:
                        minio_upload_count += 1
                    else:
                        minio_fail_count += 1
                    
                    # 立即记录 AssetMaterialization，无需等待所有任务完成
                    try:
                        context.log_event(
                            AssetMaterialization(
                                asset_key=["bronze", "a_share", "ipo_prospectus"],
                                description=f"{result.task.company_name} IPO招股说明书",
                                metadata={
                                    "stock_code": MetadataValue.text(result.task.stock_code),
                                    "company_name": MetadataValue.text(result.task.company_name),
                                    "minio_path": MetadataValue.text(result.minio_object_path or ""),
                                    "file_size": MetadataValue.int(result.file_size or 0),
                                    "file_hash": MetadataValue.text(result.file_hash or ""),
                                    "document_id": MetadataValue.text(str(result.document_id) if result.document_id else ""),
                                    "progress": MetadataValue.text(f"{idx}/{total} ({idx/total*100:.1f}%)"),
                                }
                            )
                        )
                        logger.debug(f"✅ 已记录资产: {result.task.stock_code} IPO")
                    except Exception as e:
                        logger.warning(f"记录 AssetMaterialization 失败 (task={result.task.stock_code}): {e}")
                else:
                    fail_count += 1
                    logger.warning(
                        f"❌ IPO爬取失败: {task.stock_code} ({task.company_name}) - {result.error_message}"
                    )
            except KeyboardInterrupt:
                # 用户手动中断（Ctrl+C）
                logger.warning(f"⚠️ IPO爬取被用户中断: {task.stock_code}")
                raise
            except Exception as e:
                # 检查是否是 Dagster 中断异常
                error_type = type(e).__name__
                if "Interrupt" in error_type or "Interrupted" in error_type:
                    logger.warning(f"⚠️ IPO爬取被中断: {task.stock_code}, error_type={error_type}")
                    raise
                
                fail_count += 1
                logger.error(f"❌ IPO任务执行异常: {task.stock_code} - {e}", exc_info=True)
                # 创建失败结果
                from src.ingestion.base.base_crawler import CrawlResult
                results.append(CrawlResult(
                    task=task,
                    success=False,
                    error_message=str(e)
                ))
        
        logger.info(f"✅ IPO爬取完成: 成功 {success_count}/{total}, 失败 {fail_count}/{total}")
        if enable_minio:
            logger.info(f"MinIO 上传: 成功 {minio_upload_count}, 失败 {minio_fail_count}")
            if minio_fail_count > 0:
                logger.warning(f"⚠️ 有 {minio_fail_count} 个文件下载成功但未上传到 MinIO")
        else:
            logger.warning("⚠️ MinIO 未启用，文件未上传")
    
    except KeyboardInterrupt:
        logger.warning("⚠️ IPO批量爬取被用户中断")
        raise
    except Exception as e:
        # 检查是否是 Dagster 中断异常
        error_type = type(e).__name__
        if "Interrupt" in error_type or "Interrupted" in error_type:
            logger.warning(f"⚠️ IPO批量爬取被中断: {error_type}")
            raise
        
        logger.error(f"❌ IPO批量爬取过程中发生异常: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"IPO批量爬取异常: {str(e)}",
            "total": len(tasks),
            "success_count": 0,
            "fail_count": len(tasks),
            "results": []
        }
    
    return {
        "success": True,
        "output_root": output_root,
        "total": len(results),
        "success_count": success_count,
        "fail_count": fail_count,
        "results": [
            {
                "stock_code": r.task.stock_code,
                "company_name": r.task.company_name,
                "success": r.success,
                "minio_object_path": r.minio_object_path if r.success else None,
                "document_id": r.document_id if r.success else None,
                "error": r.error_message if not r.success else None,
            }
            for r in results
        ]
    }


@op
def validate_crawl_results_op(context, crawl_results: Dict) -> Dict:
    """
    验证爬取结果（数据质量检查）
    
    按照 plan.md 7.1 全链路验证架构：
    - 文件完整性检查
    - 数据量检查
    - 元数据完整性检查
    """
    logger = get_dagster_logger()
    
    if not crawl_results.get("success"):
        logger.warning("爬取失败，跳过验证")
        return {
            "validated": False,
            "reason": "爬取失败",
            "validated_count": 0,
            "failed_count": 0
        }
    
    results = crawl_results.get("results", [])
    validated_count = 0
    failed_count = 0
    quarantined_count = 0
    
    # 初始化隔离管理器
    quarantine_manager = None
    try:
        quarantine_manager = QuarantineManager()
        logger.info("隔离管理器初始化成功")
    except Exception as e:
        logger.warning(f"隔离管理器初始化失败: {e}，将跳过自动隔离")
    
    # 数据质量检查
    failed_results = []
    passed_results = []
    
    for result_info in results:
        stock_code = result_info.get("stock_code", "未知")
        company_name = result_info.get("company_name", "未知")
        year = result_info.get("year")
        quarter = result_info.get("quarter")
        doc_type = result_info.get("doc_type", "quarterly_report")
        minio_path = result_info.get("minio_object_path")
        doc_id = result_info.get("document_id")
        
        # 如果任务本身失败，记录失败原因
        if not result_info.get("success"):
            error_msg = result_info.get("error", "未知错误")
            reason = f"爬取失败: {error_msg}"
            failed_results.append({
                "stock_code": stock_code,
                "company_name": company_name,
                "year": year,
                "quarter": quarter,
                "reason": reason
            })
            failed_count += 1
            
            # 如果文件已上传但爬取失败，隔离文件
            if quarantine_manager and minio_path and doc_id:
                try:
                    quarantine_manager.quarantine_document(
                        document_id=doc_id,
                        source_type="a_share",
                        doc_type=doc_type,
                        original_path=minio_path,
                        failure_stage="ingestion_failed",
                        failure_reason=reason,
                        failure_details=error_msg
                    )
                    quarantined_count += 1
                    logger.info(f"✅ 已隔离爬取失败的文档: {minio_path}")
                except Exception as e:
                    logger.error(f"❌ 隔离失败: {e}")
            continue
        
        # 检查1: MinIO路径是否存在
        if not minio_path:
            logger.warning(f"缺少MinIO路径: {stock_code}")
            reason = "缺少MinIO路径"
            failed_results.append({
                "stock_code": stock_code,
                "company_name": company_name,
                "year": year,
                "quarter": quarter,
                "reason": reason
            })
            failed_count += 1
            continue
        
        # 检查2: 数据库ID是否存在
        if not doc_id:
            logger.warning(f"缺少数据库ID: {stock_code}")
            
            # 先尝试重新创建数据库记录
            retry_success = False
            if minio_path and stock_code and company_name and year:
                try:
                    from src.storage.metadata import get_postgres_client, crud
                    from src.common.constants import Market, DocType
                    
                    pg_client = get_postgres_client()
                    with pg_client.get_session() as session:
                        # 检查是否已存在（可能在其他地方已创建）
                        existing_doc = crud.get_document_by_path(session, minio_path)
                        if existing_doc:
                            doc_id = existing_doc.id
                            logger.info(f"✅ 发现已存在的数据库记录: id={doc_id}")
                            retry_success = True
                        else:
                            # 尝试创建新记录
                            # 将doc_type字符串转换为DocType枚举
                            doc_type_enum = None
                            if doc_type == "quarterly_report":
                                doc_type_enum = DocType.QUARTERLY_REPORT
                            elif doc_type == "annual_report":
                                doc_type_enum = DocType.ANNUAL_REPORT
                            elif doc_type == "interim_report":
                                doc_type_enum = DocType.INTERIM_REPORT
                            elif doc_type == "ipo_prospectus":
                                doc_type_enum = DocType.IPO_PROSPECTUS
                            else:
                                doc_type_enum = DocType.QUARTERLY_REPORT  # 默认值
                            
                            doc = crud.create_document(
                                session=session,
                                stock_code=stock_code,
                                company_name=company_name,
                                market=Market.A_SHARE.value,
                                doc_type=doc_type_enum.value,
                                year=year,
                                quarter=quarter,
                                minio_object_path=minio_path,
                                file_size=None,  # 验证阶段无法获取文件大小
                                file_hash=None,  # 验证阶段无法获取文件哈希
                                metadata=None
                            )
                            doc_id = doc.id
                            logger.info(f"✅ 重新创建数据库记录成功: id={doc_id}")
                            retry_success = True
                except Exception as e:
                    logger.error(f"❌ 重新创建数据库记录失败: {e}", exc_info=True)
            
            # 如果重新创建失败，则隔离文件
            if not retry_success:
                reason = "缺少数据库ID且重新创建失败"
                failed_results.append({
                    "stock_code": stock_code,
                    "company_name": company_name,
                    "year": year,
                    "quarter": quarter,
                    "reason": reason
                })
                failed_count += 1
                
                # 隔离文件（如果已上传到MinIO）
                if quarantine_manager and minio_path:
                    try:
                        quarantine_manager.quarantine_document(
                            document_id=None,
                            source_type="a_share",
                            doc_type=doc_type,
                            original_path=minio_path,
                            failure_stage="validation_failed",
                            failure_reason=reason,
                            failure_details="文档记录未成功创建到数据库，且重新创建失败"
                        )
                        quarantined_count += 1
                        logger.info(f"✅ 已隔离缺少数据库ID的文档: {minio_path}")
                    except Exception as e:
                        logger.error(f"❌ 隔离失败: {e}")
                continue
            
            # 重新创建成功，继续验证流程（不continue，继续执行后面的验证）
            logger.info(f"✅ 数据库记录已恢复: {stock_code}, document_id={doc_id}")
        
        # 检查3: 文件大小合理性（PDF应该>10KB）
        # 这个信息在crawl_results中没有，需要从数据库查询
        # 暂时跳过，后续可以从PostgreSQL查询
        
        # 验证通过
        passed_results.append({
            "stock_code": stock_code,
            "company_name": company_name,
            "year": year,
            "quarter": quarter,
            "minio_path": minio_path,
            "document_id": doc_id
        })
        validated_count += 1
    
    logger.info(f"验证完成: 通过 {validated_count}, 失败 {failed_count}, 隔离 {quarantined_count}")
    
    # 数据质量指标
    total = len(results)
    success_rate = validated_count / total if total > 0 else 0
    
    # 记录数据质量指标
    context.log_event(
        AssetMaterialization(
            asset_key=["quality_metrics", "crawl_validation"],
            description=f"爬取数据质量检查: 通过率 {success_rate:.2%}",
            metadata={
                "total": MetadataValue.int(total),
                "validated": MetadataValue.int(validated_count),
                "failed": MetadataValue.int(failed_count),
                "quarantined": MetadataValue.int(quarantined_count),
                "success_rate": MetadataValue.float(success_rate),
            }
        )
    )
    
    return {
        "validated": True,
        "total": total,
        "passed": validated_count,
        "failed": failed_count,
        "quarantined": quarantined_count,
        "success_rate": success_rate,
        "passed_results": passed_results[:10],  # 最多返回10个通过的任务
        "failed_results": failed_results[:10]   # 最多返回10个失败的任务
    }


# ==================== Dagster Jobs ====================

@job
def crawl_a_share_reports_job():
    """
    A股定期报告爬取作业
    
    完整流程：
    1. 爬取季度报告/年报
    2. 验证爬取结果
    """
    crawl_results = crawl_a_share_reports_op()
    validate_crawl_results_op(crawl_results)


@job
def crawl_a_share_ipo_job():
    """
    A股IPO招股说明书爬取作业
    
    完整流程：
    1. 爬取IPO招股说明书
    2. 验证爬取结果
    """
    crawl_results = crawl_a_share_ipo_op()
    validate_crawl_results_op(crawl_results)


# ==================== Schedules ====================

@schedule(
    job=crawl_a_share_reports_job,
    cron_schedule="0 2 * * *",  # 每天凌晨2点执行
    default_status=DefaultScheduleStatus.STOPPED,  # 默认停止，需要手动启用
)
def daily_crawl_reports_schedule(context):
    """
    每日定时爬取A股报告
    """
    return RunRequest()


@schedule(
    job=crawl_a_share_ipo_job,
    cron_schedule="0 3 * * *",  # 每天凌晨3点执行
    default_status=DefaultScheduleStatus.STOPPED,  # 默认停止
)
def daily_crawl_ipo_schedule(context):
    """
    每日定时爬取IPO招股说明书
    """
    return RunRequest()


# ==================== Sensors ====================

@sensor(
    job=crawl_a_share_reports_job,
    default_status=DefaultSensorStatus.STOPPED,
)
def manual_trigger_reports_sensor(context):
    """
    手动触发爬取报告传感器
    可以通过Dagster UI手动触发
    """
    return RunRequest()


@sensor(
    job=crawl_a_share_ipo_job,
    default_status=DefaultSensorStatus.STOPPED,
)
def manual_trigger_ipo_sensor(context):
    """
    手动触发爬取IPO传感器
    可以通过Dagster UI手动触发
    """
    return RunRequest()
