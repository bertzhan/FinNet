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
from src.ingestion.hs_stock import ReportCrawler, CninfoIPOProspectusCrawler
from src.ingestion.hk_stock import HKReportCrawler
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
        is_required=True,
        description="Year to crawl. Will crawl all quarters (Q1, Q2, Q3, Q4) of that year"
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

# 港股爬取配置 Schema
HK_REPORT_CRAWL_CONFIG_SCHEMA = {
    "output_root": Field(
        str,
        is_required=False,
        description="Output root directory (default: downloads/, 港股主要用于临时文件)"
    ),
    "workers": Field(
        int,
        default_value=4,
        description="Number of parallel workers (1-16, 港股使用多线程并行)"
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
        description="Year to crawl. start_date will be {year}-01-01, end_date will be {year+1}-06-30"
    ),
    "limit": Field(
        int,
        is_required=False,
        description="Limit number of companies to crawl (None = all companies)"
    ),
    "stock_codes": Field(
        list,
        is_required=False,
        description="List of stock codes to crawl (5-digit codes). Example: ['00001', '00700']"
    ),
}

# 港股公司列表更新配置 Schema（与 A股/美股 统一为两个参数）
HK_COMPANY_UPDATE_CONFIG_SCHEMA = {
    "clear_before_update": Field(
        bool,
        default_value=False,
        description="是否在更新前清空除 org_id 外的所有字段（默认 False，使用 upsert 策略；org_id 为主键）"
    ),
    "basic_info_only": Field(
        bool,
        default_value=False,
        description="是否仅获取基础信息，跳过 akshare 详情拉取"
    ),
}


# ==================== 辅助函数 ====================

def load_company_list_from_db(
    limit: Optional[int] = None,
    stock_codes: Optional[List[str]] = None,
    logger=None
) -> List[Dict[str, str]]:
    """
    从数据库加载公司列表（A股）

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


def load_hk_company_list_from_db(
    limit: Optional[int] = None,
    stock_codes: Optional[List[str]] = None,
    with_org_id_only: bool = True,
    logger=None
) -> List[Dict]:
    """
    从数据库加载港股公司列表

    Args:
        limit: 限制返回数量（None 表示返回所有）
        stock_codes: 按股票代码列表过滤（None 表示不过滤）
        with_org_id_only: 是否只返回有 orgId 的公司
        logger: 日志记录器

    Returns:
        公司列表 [{'code': '00001', 'name': '長和', 'org_id': 1}, ...]
    """
    if logger is None:
        import logging
        logger = logging.getLogger(__name__)

    companies = []
    try:
        pg_client = get_postgres_client()
        with pg_client.get_session() as session:
            if stock_codes:
                from src.storage.metadata.models import HKListedCompany
                # 查询指定的股票代码
                listed_companies = session.query(HKListedCompany).filter(
                    HKListedCompany.code.in_(stock_codes)
                ).all()
                logger.info(f"港股按股票代码过滤: 指定 {len(stock_codes)} 个代码，找到 {len(listed_companies)} 家公司")
            else:
                # 使用 CRUD 函数
                listed_companies = crud.get_all_hk_listed_companies(
                    session,
                    limit=limit,
                    with_org_id_only=with_org_id_only
                )

            for company in listed_companies:
                companies.append({
                    'code': company.code,
                    'name': company.name,
                    'org_id': company.org_id,
                })

        logger.info(f"从数据库加载了 {len(companies)} 家港股公司")
    except Exception as e:
        logger.error(f"从数据库加载港股公司列表失败: {e}", exc_info=True)
        raise

    return companies


# ==================== Dagster Ops ====================

@op(config_schema=REPORT_CRAWL_CONFIG_SCHEMA)
def crawl_hs_reports_op(context) -> Dict:
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
    
    # 获取年份（必需参数）
    year = config.get("year")
    
    if year is None:
        logger.error("year 参数是必需的")
        return {
            "success": False,
            "error": "year 参数是必需的",
            "total": 0,
            "success_count": 0,
            "fail_count": 0,
            "results": []
        }
    
    # 爬取该年的所有季度（Q1, Q2, Q3, Q4）
    years_quarters = [
        (year, 1),  # Q1: 季度报告
        (year, 2),  # Q2: 半年报
        (year, 3),  # Q3: 季度报告
        (year, 4),  # Q4: 年报
    ]
    logger.info(f"爬取年份 {year} 的所有季度报告: Q1, Q2, Q3, Q4")

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
                logger.warning("⚠️ 公司列表为空，请先运行 get_hs_companies_job 更新公司列表")
                return {
                    "success": False,
                    "error": "公司列表为空，请先运行 get_hs_companies_job 更新公司列表",
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
                market=Market.HS,
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
                                asset_key=["bronze", "hs_stock", doc_type_str, str(result.task.year), f"Q{result.task.quarter}"],
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
def crawl_hs_ipo_op(context) -> Dict:
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
                logger.warning("⚠️ 公司列表为空，请先运行 get_hs_companies_job 更新公司列表")
                return {
                    "success": False,
                    "error": "公司列表为空，请先运行 get_hs_companies_job 更新公司列表",
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
            market=Market.HS,
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
                        source_type="hs_stock",
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
                                market=Market.HS.value,
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
                            source_type="hs_stock",
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
def crawl_hs_reports_job():
    """
    A股定期报告爬取作业
    
    完整流程：
    1. 爬取季度报告/年报
    2. 验证爬取结果
    """
    crawl_results = crawl_hs_reports_op()
    validate_crawl_results_op(crawl_results)


@job
def crawl_hs_ipo_job():
    """
    A股IPO招股说明书爬取作业
    
    完整流程：
    1. 爬取IPO招股说明书
    2. 验证爬取结果
    """
    crawl_results = crawl_hs_ipo_op()
    validate_crawl_results_op(crawl_results)


# ==================== Schedules ====================

@schedule(
    job=crawl_hs_reports_job,
    cron_schedule="0 2 * * *",  # 每天凌晨2点执行
    default_status=DefaultScheduleStatus.STOPPED,  # 默认停止，需要手动启用
)
def daily_crawl_reports_schedule(context):
    """
    每日定时爬取A股报告
    """
    return RunRequest()


@schedule(
    job=crawl_hs_ipo_job,
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
    job=crawl_hs_reports_job,
    default_status=DefaultSensorStatus.STOPPED,
)
def manual_trigger_reports_sensor(context):
    """
    手动触发爬取报告传感器
    可以通过Dagster UI手动触发
    """
    return RunRequest()


@sensor(
    job=crawl_hs_ipo_job,
    default_status=DefaultSensorStatus.STOPPED,
)
def manual_trigger_ipo_sensor(context):
    """
    手动触发爬取IPO传感器
    可以通过Dagster UI手动触发
    """
    return RunRequest()


# ==================== 港股 Dagster Ops ====================

@op(config_schema=HK_COMPANY_UPDATE_CONFIG_SCHEMA)
def get_hk_companies_op(context) -> Dict:
    """
    更新港股公司列表
    
    从披露易获取最新的股票列表，并同步到数据库
    默认只获取股本证券（过滤债券、窝轮、衍生品等）
    """
    config = context.op_config
    logger = get_dagster_logger()
    start_time = datetime.now()

    clear_before_update = config.get("clear_before_update", False)
    basic_info_only = config.get("basic_info_only", False)

    logger.info(
        f"[get_hk_companies] 开始更新港股公司列表 | "
        f"clear_before_update={clear_before_update}, basic_info_only={basic_info_only}"
    )
    
    try:
        # 使用 HKEX 客户端获取股票列表（硬编码：仅股本证券，不含已退市）
        from src.ingestion.hk_stock import HKEXClient
        
        hkex_client = HKEXClient()
        stocks = hkex_client.get_stock_list(
            include_inactive=False,
            equity_only=True
        )
        
        if not stocks:
            logger.error("[get_hk_companies] 更新失败: 未获取到港股公司列表")
            return {
                "success": False,
                "error": "未获取到港股公司列表",
                "count": 0
            }
        
        logger.info(f"从披露易获取了 {len(stocks)} 家股本证券公司")
        
        pg_client = get_postgres_client()
        
        # 使用 akshare 获取公司详细信息（basic_info_only=False 时执行，增量：仅新公司或 org_name_cn 缺失/变化时拉取）
        if not basic_info_only:
            from src.ingestion.hk_stock.utils.akshare_helper import batch_get_company_profiles
            with pg_client.get_session() as session:
                existing_list = crud.get_all_hk_listed_companies(session)
                # 在 session 内提取字段，避免 DetachedInstanceError（ORM 对象在 session 关闭后无法访问属性）
                existing_by_code = {
                    c.code: {"org_name_cn": c.org_name_cn, "name": c.name}
                    for c in existing_list if c.code
                }
            
            # 增量：仅对新公司或 org_name_cn 为空/变化时拉取
            # org_name_cn 是否变化：拉取后与 DB 比较，若不同则更新；拉取前用 name 作为代理（name 变更常伴随 org_name_cn 变更）
            def _need_fetch_profile(stock: dict, existing: dict | None) -> bool:
                if existing is None:
                    return True
                if not (existing.get("org_name_cn") or '').strip():
                    return True
                # org_name_cn 是否变化（代理：HKEX name 与 DB name 不同）
                return (existing.get("name") or '').strip() != (stock.get('name') or '').strip()
            
            stocks_to_fetch = [
                s for s in stocks
                if _need_fetch_profile(s, existing_by_code.get(s.get('code')))
            ]
            stock_codes_to_fetch = [s['code'] for s in stocks_to_fetch]
            skipped_count = len(stocks) - len(stock_codes_to_fetch)
            
            if stock_codes_to_fetch:
                logger.info(f"增量拉取 akshare 详情: {len(stock_codes_to_fetch)} 家（跳过 {skipped_count} 家 org_name_cn 未变）")
                
                last_logged_pct = -1

                def progress_callback(current: int, total: int, code: str) -> None:
                    nonlocal last_logged_pct
                    progress_pct = (current / total) * 100
                    progress_pct_int = int(progress_pct)
                    if (
                        progress_pct_int % 5 == 0
                        and progress_pct_int != last_logged_pct
                    ) or current == total:
                        logger.info(
                            f"📦 [{current}/{total}] {progress_pct:.1f}% | 获取公司详情 | {code}"
                        )
                        last_logged_pct = progress_pct_int
                
                profiles = batch_get_company_profiles(
                    stock_codes_to_fetch,
                    delay=0.1,
                    max_workers=10,
                    progress_callback=progress_callback
                )
            else:
                profiles = {}
                logger.info(f"无需拉取 akshare 详情（{len(stocks)} 家 org_name_cn 均未变）")
            
            # 合并详细信息到 stocks（仅对拉取过的）
            enriched_count = 0
            company_info_count = 0
            security_info_count = 0
            
            for stock in stocks:
                code = stock['code']
                profile = profiles.get(code)
                if profile is not None:
                    company_fields = ['org_name_cn', 'org_name_en', 'org_cn_introduction',
                                    'established_date', 'staff_num', 'industry']
                    security_fields = ['listed_date', 'fiscal_year_end', 'is_sh_hk_connect', 'is_sz_hk_connect']
                    
                    has_company_info = any(k in profile for k in company_fields)
                    has_security_info = any(k in profile for k in security_fields)
                    
                    if has_company_info:
                        company_info_count += 1
                    if has_security_info:
                        security_info_count += 1
                    
                    stock.update(profile)
                    if len(profile) > 0:
                        enriched_count += 1
            
            if enriched_count > 0:
                logger.info(
                    f"获取详情完成: {enriched_count}/{len(stocks)} 家 "
                    f"（公司信息 {company_info_count} 家，证券信息 {security_info_count} 家）"
                )

        # 保存到数据库
        if clear_before_update:
            with pg_client.get_session() as session:
                count = crud.clear_hk_listed_companies_except_org_id(session)
                session.commit()
            logger.info(f"已清空 hk_listed_companies 中 {count} 条记录的非主键字段")
        with pg_client.get_session() as session:
            count = crud.batch_upsert_hk_listed_companies(session, stocks)
            session.commit()

        duration_seconds = int((datetime.now() - start_time).total_seconds())
        logger.info(
            f"[get_hk_companies] 更新完成 | 总={len(stocks)}, 耗时={duration_seconds}s"
        )

        # 记录 Asset Materialization
        context.log_event(
            AssetMaterialization(
                asset_key=["hk_stock", "companies"],
                description=f"更新港股公司列表: {len(stocks)} 家股本证券",
                metadata={
                    "total_count": MetadataValue.int(len(stocks)),
                    "clear_before_update": MetadataValue.bool(clear_before_update),
                    "basic_info_only": MetadataValue.bool(basic_info_only),
                }
            )
        )
        
        return {
            "success": True,
            "count": len(stocks),
            "message": f"成功更新 {len(stocks)} 家港股股本证券公司"
        }
        
    except Exception as e:
        logger.error(f"[get_hk_companies] 更新失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "count": 0
        }


@op(config_schema=HK_REPORT_CRAWL_CONFIG_SCHEMA)
def crawl_hk_reports_op(context) -> Dict:
    """
    爬取港股定期报告（年报/中报）
    
    功能：
    - 从数据库加载港股公司列表
    - 使用 HKReportCrawler 批量爬取报告（支持多线程并行）
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
    year = config.get("year")
    
    if year is None:
        logger.error("year 参数是必需的")
        return {
            "success": False,
            "error": "year 参数是必需的",
            "total": 0,
            "success_count": 0,
            "fail_count": 0,
            "results": []
        }
    
    # 根据 year 计算 start_date 和 end_date
    # start_date: year 的 1月1日
    # end_date: year+1 的 6月30日（因为年报通常在次年3-4月发布）
    start_date = f"{year}-01-01"
    end_date = f"{year + 1}-06-30"
    
    limit = config.get("limit")
    stock_codes = config.get("stock_codes")
    
    logger.info(f"爬取年份: {year}, 查询日期范围: {start_date} ~ {end_date}, 将爬取所有季度 (Q1, Q2, Q3, Q4)")
    
    # 从数据库加载港股公司列表
    try:
        companies = load_hk_company_list_from_db(
            limit=limit,
            stock_codes=stock_codes,
            with_org_id_only=True,  # 只爬取有 orgId 的公司
            logger=logger
        )
        
        if not companies:
            logger.warning("未找到港股公司，请先运行 get_hk_companies_op 更新公司列表")
            return {
                "success": False,
                "error": "未找到港股公司列表",
                "total": 0,
                "success_count": 0,
                "fail_count": 0,
                "results": []
            }
        
        logger.info(f"加载了 {len(companies)} 家港股公司")
        
    except Exception as e:
        logger.error(f"加载港股公司列表失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "total": 0,
            "success_count": 0,
            "fail_count": 0,
            "results": []
        }
    
    # 确保输出目录存在（虽然港股主要使用临时目录，但为了接口一致性保留）
    os.makedirs(output_root, exist_ok=True)
    
    # 创建爬虫实例
    crawler = HKReportCrawler(
        enable_minio=enable_minio,
        enable_postgres=enable_postgres,
        start_date=start_date,
        end_date=end_date,
        workers=workers
    )
    
    logger.info(f"港股爬虫配置: workers={workers}, start_date={start_date}, end_date={end_date}")
    
    # 构建任务列表：为每个公司生成 Q1, Q2, Q3, Q4 的所有任务
    tasks = []
    for company in companies:
        stock_code = company['code']
        company_name = company['name']
        org_id = company.get('org_id')
        
        # 季度到文档类型的映射
        quarter_doc_type_map = {
            1: DocType.HK_QUARTERLY_REPORT,   # Q1: 季度报告
            2: DocType.HK_INTERIM_REPORT,     # Q2: 中期报告
            3: DocType.HK_QUARTERLY_REPORT,   # Q3: 季度报告
            4: DocType.HK_ANNUAL_REPORT,      # Q4: 年报
        }
        
        # 为每个季度生成任务
        for quarter, doc_type in quarter_doc_type_map.items():
            tasks.append(CrawlTask(
                stock_code=stock_code,
                company_name=company_name,
                market=Market.HK_STOCK,
                doc_type=doc_type,
                year=year,
                quarter=quarter,
                metadata={'org_id': org_id} if org_id else {}
            ))
    
    logger.info(f"生成了 {len(tasks)} 个爬取任务")
    
    # 执行爬取
    results = crawler.crawl_batch(tasks)
    
    # 统计结果
    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count
    
    logger.info(f"港股报告爬取完成: 成功 {success_count}, 失败 {fail_count}")
    
    # 记录 Asset Materialization
    for result in results:
        if result.success and result.minio_object_path:
            context.log_event(
                AssetMaterialization(
                    asset_key=["hk_stock", "reports", result.task.stock_code],
                    description=f"港股报告: {result.task.stock_code} {result.task.year} Q{result.task.quarter}",
                    metadata={
                        "stock_code": MetadataValue.text(result.task.stock_code),
                        "company_name": MetadataValue.text(result.task.company_name),
                        "year": MetadataValue.int(result.task.year),
                        "quarter": MetadataValue.int(result.task.quarter) if result.task.quarter else MetadataValue.int(0),
                        "minio_path": MetadataValue.text(result.minio_object_path),
                        "file_size": MetadataValue.int(result.file_size) if result.file_size else MetadataValue.int(0),
                    }
                )
            )
    
    return {
        "success": True,
        "total": len(results),
        "success_count": success_count,
        "fail_count": fail_count,
        "results": [
            {
                "stock_code": r.task.stock_code,
                "company_name": r.task.company_name,
                "year": r.task.year,
                "quarter": r.task.quarter,
                "success": r.success,
                "minio_object_path": r.minio_object_path if r.success else None,
                "document_id": str(r.document_id) if r.success and r.document_id else None,
                "error": r.error_message if not r.success else None,
            }
            for r in results
        ]
    }


# ==================== 港股 Dagster Jobs ====================

@job
def get_hk_companies_job():
    """
    港股公司列表更新作业
    
    从披露易获取最新的股票列表并同步到数据库
    """
    get_hk_companies_op()


@job
def crawl_hk_reports_job():
    """
    港股定期报告爬取作业
    
    完整流程：
    1. 爬取年报/中报
    2. 验证爬取结果
    """
    crawl_results = crawl_hk_reports_op()
    validate_crawl_results_op(crawl_results)


# ==================== 港股 Schedules ====================

@schedule(
    job=get_hk_companies_job,
    cron_schedule="0 1 * * 1",  # 每周一凌晨1点执行
    default_status=DefaultScheduleStatus.STOPPED,
)
def weekly_update_hk_companies_schedule(context):
    """
    每周定时更新港股公司列表
    """
    return RunRequest()


@schedule(
    job=crawl_hk_reports_job,
    cron_schedule="0 4 * * *",  # 每天凌晨4点执行
    default_status=DefaultScheduleStatus.STOPPED,
)
def daily_crawl_hk_reports_schedule(context):
    """
    每日定时爬取港股报告
    """
    return RunRequest()


# ==================== 港股 Sensors ====================

@sensor(
    job=get_hk_companies_job,
    default_status=DefaultSensorStatus.STOPPED,
)
def manual_trigger_update_hk_companies_sensor(context):
    """
    手动触发更新港股公司列表
    """
    return RunRequest()


@sensor(
    job=crawl_hk_reports_job,
    default_status=DefaultSensorStatus.STOPPED,
)
def manual_trigger_hk_reports_sensor(context):
    """
    手动触发爬取港股报告
    """
    return RunRequest()
