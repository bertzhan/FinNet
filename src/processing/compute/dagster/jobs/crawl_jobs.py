# -*- coding: utf-8 -*-
"""
Dagster 爬虫作业定义
集成新的 ingestion 层爬虫到 Dagster 调度系统

按照 plan.md 设计：
- 数据采集层（Ingestion Layer）→ Dagster 调度
- 支持定时调度、数据质量检查、可视化监控
"""

import os
import csv
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

# 获取项目根目录
PROJECT_ROOT = Path(common_config.PROJECT_ROOT)
DEFAULT_COMPANY_LIST = PROJECT_ROOT / "src" / "crawler" / "zh" / "company_list.csv"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "downloads"


# ==================== 配置 Schema ====================

# 使用 config_schema 字典方式（兼容所有 Dagster 版本）
REPORT_CRAWL_CONFIG_SCHEMA = {
    "company_list_path": Field(
        str,
        default_value=str(DEFAULT_COMPANY_LIST),
        description="Company list CSV file path (code,name columns)"
    ),
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
        description="Year to crawl (None = auto: current and previous quarter)"
    ),
    "quarter": Field(
        int,
        is_required=False,
        description="Quarter to crawl (1-4, None = auto)"
    ),
}

IPO_CRAWL_CONFIG_SCHEMA = {
    "company_list_path": Field(
        str,
        default_value=str(DEFAULT_COMPANY_LIST),
        description="Company list CSV file path (code,name columns)"
    ),
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
}


# ==================== 辅助函数 ====================

def load_company_list(company_list_path: str) -> List[Dict[str, str]]:
    """
    加载公司列表
    
    Args:
        company_list_path: CSV文件路径
        
    Returns:
        公司列表 [(code, name), ...]
    """
    import logging
    logger = logging.getLogger(__name__)
    
    companies = []
    if not os.path.exists(company_list_path):
        logger.warning(f"公司列表文件不存在: {company_list_path}")
        return companies
    
    try:
        with open(company_list_path, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = (row.get('code') or '').strip()
                name = (row.get('name') or '').strip()
                if code and name:
                    companies.append({'code': code, 'name': name})
        logger.info(f"加载了 {len(companies)} 家公司")
    except Exception as e:
        logger.error(f"加载公司列表失败: {e}")
    
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
    company_list_path = config.get("company_list_path", str(DEFAULT_COMPANY_LIST))
    output_root = config.get("output_root") or str(DEFAULT_OUTPUT_ROOT)
    workers = config.get("workers", 4)
    enable_minio = config.get("enable_minio", True)
    enable_postgres = config.get("enable_postgres", True)
    
    # 计算年份和季度
    year = config.get("year")
    quarter = config.get("quarter")
    
    if year is None or quarter is None:
        # 自动计算：爬取当前季度和上一季度
        current_year, current_quarter, prev_year, prev_quarter = calculate_quarters()
        years_quarters = [
            (prev_year, prev_quarter),
            (current_year, current_quarter),
        ]
        logger.info(f"自动计算季度: {prev_year}Q{prev_quarter}, {current_year}Q{current_quarter}")
    else:
        years_quarters = [(year, quarter)]
        logger.info(f"指定季度: {year}Q{quarter}")
    
    # 确保输出目录存在
    os.makedirs(output_root, exist_ok=True)
    
    # 加载公司列表
    companies = load_company_list(company_list_path)
    if not companies:
        return {
            "success": False,
            "error": "公司列表为空",
            "total": 0,
            "success_count": 0,
            "fail_count": 0,
            "results": []
        }
    
    # 记录配置信息
    logger.info(f"爬虫配置: enable_minio={enable_minio}, enable_postgres={enable_postgres}, workers={workers}")
    
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
    
    # 执行批量爬取
    results = crawler.crawl_batch(tasks)
    
    # 统计结果
    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count
    
    logger.info(f"爬取完成: 成功 {success_count}, 失败 {fail_count}")
    
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
    
    # 记录资产物化（Dagster 数据血缘）
    for result in results:
        if result.success:
            # 根据季度确定文档类型字符串（用于资产key）
            if result.task.quarter == 4:
                doc_type_str = "annual_report"
            elif result.task.quarter == 2:
                doc_type_str = "interim_report"
            else:
                doc_type_str = "quarterly_report"
            
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
                    }
                )
            )
    
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
    company_list_path = config.get("company_list_path", str(DEFAULT_COMPANY_LIST))
    output_root = config.get("output_root") or str(DEFAULT_OUTPUT_ROOT)
    workers = config.get("workers", 4)
    enable_minio = config.get("enable_minio", True)
    enable_postgres = config.get("enable_postgres", True)
    
    # 确保输出目录存在
    os.makedirs(output_root, exist_ok=True)
    
    # 加载公司列表
    companies = load_company_list(company_list_path)
    if not companies:
        return {
            "success": False,
            "error": "公司列表为空",
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
    
    # 执行批量爬取
    results = crawler.crawl_batch(tasks)
    
    # 统计结果
    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count
    
    # 统计 MinIO 上传情况
    minio_upload_count = sum(1 for r in results if r.success and r.minio_object_path)
    minio_fail_count = sum(1 for r in results if r.success and not r.minio_object_path)
    
    logger.info(f"IPO爬取完成: 成功 {success_count}, 失败 {fail_count}")
    if enable_minio:
        logger.info(f"MinIO 上传: 成功 {minio_upload_count}, 失败 {minio_fail_count}")
        if minio_fail_count > 0:
            logger.warning(f"⚠️ 有 {minio_fail_count} 个文件下载成功但未上传到 MinIO")
    else:
        logger.warning("⚠️ MinIO 未启用，文件未上传")
    
    # 记录资产物化
    for result in results:
        if result.success:
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
                    }
                )
            )
    
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
