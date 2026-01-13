# -*- coding: utf-8 -*-
"""
Dagster调度作业定义
按照plan.md设计集成爬虫到Dagster调度系统
"""

from dagster import (
    job,
    op,
    schedule,
    DefaultSensorStatus,
    DefaultScheduleStatus,
    sensor,
    RunRequest,
    Config,
    Field,
    get_dagster_logger,
    asset,
    AssetMaterialization,
    MetadataValue,
)
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import os
import sys

# 添加路径以便导入爬虫模块
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from src.crawler.base_crawler import Market, DocType, CrawlTask, CrawlResult
from src.crawler.zh.cninfo_crawler import CNInfoCrawler
from src.crawler.validation import DataValidator, ValidationStage
from src.crawler.storage import StorageManager


# 获取项目根目录，用于设置默认输出路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUTPUT_ROOT = os.path.join(PROJECT_ROOT, "reports")

# 如果设置了环境变量，优先使用环境变量
if os.getenv("FINNET_DATA_ROOT"):
    DEFAULT_OUTPUT_ROOT = os.getenv("FINNET_DATA_ROOT")


# 定义配置 schema（手动定义以避免中文描述问题）
# 注意：默认路径使用项目相对路径，避免权限问题
CRAWLER_CONFIG_SCHEMA = {
    "output_root": Field(
        str,
        default_value=DEFAULT_OUTPUT_ROOT,
        description=f"Output root directory for crawled files (default: {DEFAULT_OUTPUT_ROOT}). "
                   f"On macOS, avoid using /data paths as they may be read-only."
    ),
    "workers": Field(
        int,
        default_value=6,
        description="Number of parallel workers"
    ),
    "old_pdf_dir": Field(
        str,
        is_required=False,
        description="Directory containing old PDF files to avoid re-downloading"
    ),
}


@op(config_schema=CRAWLER_CONFIG_SCHEMA)
def crawl_a_share_quarterly_reports(context) -> Dict:
    """
    爬取A股季度报告
    
    按照plan.md设计：
    - 自动计算上一季度和当前季度
    - 批量爬取所有上市公司报告
    """
    logger = get_dagster_logger()
    config = context.op_config
    
    output_root = config.get("output_root", DEFAULT_OUTPUT_ROOT)
    workers = config.get("workers", 6)
    old_pdf_dir = config.get("old_pdf_dir")
    
    # 验证输出路径：如果路径以 /data 开头且不可写，使用默认路径
    if output_root.startswith("/data") and not os.access("/data", os.W_OK):
        logger.warning(f"路径 {output_root} 不可写，使用默认路径: {DEFAULT_OUTPUT_ROOT}")
        output_root = DEFAULT_OUTPUT_ROOT
    
    # 确保输出目录存在
    try:
        os.makedirs(output_root, exist_ok=True)
    except (OSError, PermissionError) as e:
        logger.error(f"无法创建输出目录 {output_root}: {e}")
        logger.info(f"尝试使用默认路径: {DEFAULT_OUTPUT_ROOT}")
        output_root = DEFAULT_OUTPUT_ROOT
        os.makedirs(output_root, exist_ok=True)
    
    # 检查 MinIO 配置
    use_minio = os.getenv("USE_MINIO", "false").lower() == "true"
    if use_minio:
        minio_endpoint = os.getenv("MINIO_ENDPOINT")
        minio_bucket = os.getenv("MINIO_BUCKET", "company-datalake")
        if minio_endpoint:
            logger.info(f"✓ MinIO 已启用: {minio_endpoint} (bucket: {minio_bucket})")
        else:
            logger.warning("⚠ MinIO 已启用但 MINIO_ENDPOINT 未设置，上传功能可能不可用")
    else:
        logger.info("ℹ MinIO 未启用，文件仅保存到本地。要启用 MinIO 上传，请设置环境变量 USE_MINIO=true")
    
    logger.info(f"开始爬取A股季度报告，输出目录: {output_root}")
    
    # 计算当前季度和上一季度
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
    
    # 创建爬虫实例
    crawler = CNInfoCrawler(
        output_root=output_root,
        workers=workers,
        old_pdf_dir=old_pdf_dir
    )
    
    # 读取公司列表
    company_list_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "crawler",
        "zh",
        "company_list.csv"
    )
    
    if not os.path.exists(company_list_path):
        logger.error(f"公司列表文件不存在: {company_list_path}")
        return {"success": False, "error": "公司列表文件不存在"}
    
    # 读取公司列表并生成任务
    import csv
    tasks = []
    with open(company_list_path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = (row.get('code') or '').strip()
            name = (row.get('name') or '').strip()
            if code and name:
                # 添加上一季度和当前季度任务
                tasks.append(CrawlTask(
                    stock_code=code,
                    company_name=name,
                    year=prev_year,
                    quarter=prev_quarter,
                    doc_type=DocType.QUARTERLY_REPORT,
                    market=Market.A_SHARE
                ))
                tasks.append(CrawlTask(
                    stock_code=code,
                    company_name=name,
                    year=current_year,
                    quarter=current_quarter,
                    doc_type=DocType.QUARTERLY_REPORT,
                    market=Market.A_SHARE
                ))
    
    logger.info(f"生成 {len(tasks)} 个爬取任务")
    
    # 执行批量爬取
    results = crawler.crawl_batch(tasks)
    
    # 统计结果
    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count
    
    logger.info(f"爬取完成: 成功 {success_count}, 失败 {fail_count}")
    
    # 记录资产物化
    for result in results:
        if result.success:
            context.log_event(
                AssetMaterialization(
                    asset_key="a_share_report",
                    description=f"{result.task.company_name} {result.task.year} Q{result.task.quarter}",
                    metadata={
                        "stock_code": MetadataValue.text(result.task.stock_code),
                        "file_path": MetadataValue.path(result.file_path),
                        "file_size": MetadataValue.int(result.file_size),
                    }
                )
            )
    
    return {
        "success": True,
        "output_root": output_root,  # 保存输出路径供后续使用
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
                "file_path": r.file_path if r.success else None,
                "error": r.error_message if not r.success else None,
            }
            for r in results
        ]
    }


@op
def validate_crawled_data(context, crawl_result: Dict) -> Dict:
    """
    验证爬取的数据
    
    按照plan.md设计实现全链路验证
    """
    logger = get_dagster_logger()
    
    if not crawl_result.get("success"):
        logger.warning("爬取失败，跳过验证")
        return {"validated": False, "reason": "爬取失败"}
    
    results = crawl_result.get("results", [])
    validator = DataValidator(Market.A_SHARE)
    # 从爬取结果中获取 output_root，如果没有则使用默认值
    output_root = crawl_result.get("output_root", DEFAULT_OUTPUT_ROOT)
    storage_manager = StorageManager(output_root)
    
    validated_count = 0
    failed_count = 0
    quarantined_count = 0
    
    for result_info in results:
        if not result_info.get("success"):
            continue
        
        file_path = result_info.get("file_path")
        if not file_path or not os.path.exists(file_path):
            continue
        
        # 创建CrawlResult对象用于验证
        from src.crawler.base_crawler import CrawlTask
        crawl_result_obj = CrawlResult(
            success=True,
            task=CrawlTask(
                stock_code=result_info["stock_code"],
                company_name=result_info["company_name"],
                year=result_info["year"],
                quarter=result_info["quarter"],
                doc_type=DocType.QUARTERLY_REPORT,
                market=Market.A_SHARE
            ),
            file_path=file_path,
            file_size=os.path.getsize(file_path) if os.path.exists(file_path) else None,
            metadata={
                "stock_code": result_info["stock_code"],
                "company_name": result_info["company_name"],
                "year": result_info["year"],
                "quarter": result_info["quarter"],
            }
        )
        
        # 执行全链路验证
        validation_results = validator.validate_all(crawl_result_obj)
        
        # 检查是否有验证失败
        all_passed = True
        for stage, stage_results in validation_results.items():
            for vr in stage_results:
                if not vr.passed and vr.level.value in ["error", "critical"]:
                    all_passed = False
                    break
            if not all_passed:
                break
        
        if all_passed:
            validated_count += 1
        else:
            failed_count += 1
            # 移动到隔离区
            try:
                quarantine_path = storage_manager.move_to_quarantine(
                    file_path,
                    "validation_failed",
                    reason="validation_failed"
                )
                quarantined_count += 1
                logger.warning(f"验证失败，已移动到隔离区: {quarantine_path}")
            except Exception as e:
                logger.error(f"移动到隔离区失败: {e}")
    
    logger.info(f"验证完成: 通过 {validated_count}, 失败 {failed_count}, 隔离 {quarantined_count}")
    
    return {
        "validated": True,
        "validated_count": validated_count,
        "failed_count": failed_count,
        "quarantined_count": quarantined_count,
    }


@job
def crawl_a_share_reports_job():
    """
    A股报告爬取作业
    
    流程：
    1. 爬取季度报告
    2. 验证爬取数据
    """
    crawl_result = crawl_a_share_quarterly_reports()
    validate_crawled_data(crawl_result)


@schedule(
    job=crawl_a_share_reports_job,
    cron_schedule="0 2 * * *",  # 每天凌晨2点执行
    default_status=DefaultScheduleStatus.STOPPED,
)
def daily_crawl_schedule(context):
    """
    每日定时爬取调度
    """
    return RunRequest()


@sensor(
    job=crawl_a_share_reports_job,
    default_status=DefaultSensorStatus.STOPPED,
)
def manual_trigger_sensor(context):
    """
    手动触发传感器
    可以通过Dagster UI手动触发
    """
    return RunRequest()
