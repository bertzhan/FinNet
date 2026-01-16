# -*- coding: utf-8 -*-
"""
Dagster PDF 解析作业定义
自动扫描待解析的文档并调用 MinerU 解析器

按照 plan.md 设计：
- 处理层（Processing Layer）→ Dagster 调度
- PDF 解析 → Silver 层（text_cleaned）
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

# 导入解析器和数据库模块
from src.processing.ai.pdf_parser import get_mineru_parser
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.storage.metadata.models import Document, ParseTask
from src.common.constants import DocumentStatus, DocType, Market
from src.common.config import common_config

# 获取项目根目录
PROJECT_ROOT = Path(common_config.PROJECT_ROOT)


# ==================== 配置 Schema ====================

PARSE_CONFIG_SCHEMA = {
    "batch_size": Field(
        int,
        default_value=10,
        description="每批处理的文档数量（1-50）"
    ),
    "parser_type": Field(
        str,
        default_value="mineru",
        description="解析器类型：mineru 或 docling"
    ),
    "market": Field(
        str,
        is_required=False,
        description="市场过滤（a_share/hk_stock/us_stock），None 表示所有市场"
    ),
    "doc_type": Field(
        str,
        is_required=False,
        description="文档类型过滤（quarterly_report/annual_report/ipo_prospectus），None 表示所有类型"
    ),
    "limit": Field(
        int,
        default_value=100,
        description="本次作业最多处理的文档数量（1-1000）"
    ),
    "enable_silver_upload": Field(
        bool,
        default_value=True,
        description="是否上传解析结果到 Silver 层"
    ),
    "start_page_id": Field(
        int,
        default_value=0,
        description="起始页码（从0开始），默认0（解析全部）"
    ),
    "end_page_id": Field(
        int,
        is_required=False,
        description="结束页码（从0开始），None 表示解析到最后。例如：设置为 2 表示只解析前3页（0, 1, 2）"
    ),
}


# ==================== Dagster Ops ====================

@op(config_schema=PARSE_CONFIG_SCHEMA)
def scan_pending_documents_op(context) -> Dict:
    """
    扫描待解析的文档
    
    查找状态为 'crawled' 的文档，准备进行 PDF 解析
    
    Returns:
        包含待解析文档列表的字典
    """
    config = context.op_config
    logger = get_dagster_logger()
    
    batch_size = config.get("batch_size", 10)
    limit = config.get("limit", 100)
    market_filter = config.get("market")
    doc_type_filter = config.get("doc_type")
    
    logger.info(f"开始扫描待解析文档...")
    logger.info(f"配置: batch_size={batch_size}, limit={limit}, market={market_filter}, doc_type={doc_type_filter}")
    
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 查找状态为 'crawled' 的文档
            documents = crud.get_documents_by_status(
                session=session,
                status=DocumentStatus.CRAWLED.value,
                limit=limit,
                offset=0
            )
            
            # 应用市场过滤
            if market_filter:
                documents = [d for d in documents if d.market == market_filter]
            
            # 应用文档类型过滤
            if doc_type_filter:
                documents = [d for d in documents if d.doc_type == doc_type_filter]
            
            # 只处理 PDF 文档
            pdf_documents = [
                d for d in documents
                if d.minio_object_name and d.minio_object_name.endswith('.pdf')
            ]
            
            # 验证文件是否在 MinIO 中存在（避免解析不存在的文件）
            from src.storage.object_store.minio_client import MinIOClient
            minio_client = MinIOClient()
            existing_pdf_documents = []
            for doc in pdf_documents:
                if minio_client.file_exists(doc.minio_object_name):
                    existing_pdf_documents.append(doc)
                else:
                    logger.warning(f"文档文件不存在，跳过: document_id={doc.id}, path={doc.minio_object_name}")
            
            pdf_documents = existing_pdf_documents
            logger.info(f"找到 {len(pdf_documents)} 个待解析的 PDF 文档（已过滤不存在的文件）")
            
            # 将文档列表转换为字典格式（便于 Dagster 传递）
            document_list = []
            for doc in pdf_documents:
                document_list.append({
                    "document_id": doc.id,
                    "stock_code": doc.stock_code,
                    "company_name": doc.company_name,
                    "market": doc.market,
                    "doc_type": doc.doc_type,
                    "year": doc.year,
                    "quarter": doc.quarter,
                    "minio_object_name": doc.minio_object_name,
                    "file_size": doc.file_size,
                    "file_hash": doc.file_hash,
                })
            
            # 按批次分组
            batches = []
            for i in range(0, len(document_list), batch_size):
                batch = document_list[i:i + batch_size]
                batches.append(batch)
            
            logger.info(f"分为 {len(batches)} 个批次，每批 {batch_size} 个文档")
            
            return {
                "success": True,
                "total_documents": len(document_list),
                "total_batches": len(batches),
                "batches": batches,
                "documents": document_list,  # 保留完整列表用于后续处理
            }
            
    except Exception as e:
        logger.error(f"扫描待解析文档失败: {e}", exc_info=True)
        return {
            "success": False,
            "error_message": str(e),
            "total_documents": 0,
            "total_batches": 0,
            "batches": [],
            "documents": [],
        }


@op
def parse_documents_op(context, scan_result: Dict) -> Dict:
    """
    批量解析文档
    
    对扫描到的文档进行 PDF 解析，并保存到 Silver 层
    
    Args:
        scan_result: scan_pending_documents_op 的返回结果
        
    Returns:
        解析结果统计
    """
    logger = get_dagster_logger()
    
    # 检查 scan_result 是否为 None
    if scan_result is None:
        logger.error("scan_result 为 None，无法继续解析")
        return {
            "success": False,
            "error_message": "scan_result 为 None",
            "parsed_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
        }
    
    # 安全获取 config
    config = context.op_config if hasattr(context, 'op_config') else {}
    
    enable_silver_upload = config.get("enable_silver_upload", True) if config else True
    start_page_id = config.get("start_page_id", 0) if config else 0
    end_page_id = config.get("end_page_id") if config else None
    
    if end_page_id is not None:
        logger.info(f"页面范围: {start_page_id} - {end_page_id} (共 {end_page_id - start_page_id + 1} 页)")
    else:
        logger.info(f"页面范围: {start_page_id} - 最后 (解析全部)")
    
    if not scan_result.get("success"):
        logger.error(f"扫描失败，跳过解析: {scan_result.get('error_message')}")
        return {
            "success": False,
            "error_message": "扫描失败",
            "parsed_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
        }
    
    documents = scan_result.get("documents", [])
    if not documents:
        logger.info("没有待解析的文档")
        return {
            "success": True,
            "parsed_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
        }
    
    logger.info(f"开始解析 {len(documents)} 个文档...")
    
    # 初始化解析器
    parser = get_mineru_parser()
    
    pg_client = get_postgres_client()
    
    parsed_count = 0
    failed_count = 0
    skipped_count = 0
    failed_documents = []
    
    for doc_info in documents:
        document_id = doc_info["document_id"]
        stock_code = doc_info["stock_code"]
        minio_path = doc_info["minio_object_name"]
        
        logger.info(f"解析文档 {document_id}: {stock_code} - {minio_path}")
        
        try:
            # 注意：parse_document 方法内部会重新查询数据库获取 Document 对象
            # 所以这里直接传递 document_id 即可，不需要传递 Document 对象
            result = parser.parse_document(
                document_id=document_id,
                save_to_silver=enable_silver_upload,
                start_page_id=start_page_id,
                end_page_id=end_page_id
            )
            
            # 检查 result 是否为 None
            if result is None:
                failed_count += 1
                error_msg = "解析器返回 None"
                logger.error(f"❌ 解析失败: document_id={document_id}, error={error_msg}")
                failed_documents.append({
                    "document_id": document_id,
                    "stock_code": stock_code,
                    "error": error_msg
                })
                continue
            
            if result.get("success"):
                parsed_count += 1
                output_path = result.get("output_path", "N/A")
                text_length = result.get("extracted_text_length", 0)
                logger.info(
                    f"✅ 解析成功: document_id={document_id}, "
                    f"output_path={output_path}, "
                    f"text_length={text_length}"
                )
            else:
                failed_count += 1
                error_msg = result.get("error_message", "未知错误")
                logger.error(f"❌ 解析失败: document_id={document_id}, error={error_msg}")
                failed_documents.append({
                    "document_id": document_id,
                    "stock_code": stock_code,
                    "error": error_msg
                })
                
        except Exception as e:
            failed_count += 1
            error_msg = str(e)
            logger.error(f"❌ 解析异常: document_id={document_id}, error={error_msg}", exc_info=True)
            failed_documents.append({
                "document_id": document_id,
                "stock_code": stock_code,
                "error": error_msg
            })
    
    logger.info(
        f"解析完成: 成功={parsed_count}, 失败={failed_count}, 跳过={skipped_count}"
    )
    
    return {
        "success": True,
        "parsed_count": parsed_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "total_documents": len(documents),
        "failed_documents": failed_documents[:10],  # 最多返回10个失败记录
    }


@op
def validate_parse_results_op(context, parse_results: Dict) -> Dict:
    """
    验证解析结果
    
    检查解析结果的质量，记录统计信息
    
    Args:
        parse_results: parse_documents_op 的返回结果
        
    Returns:
        验证结果统计
    """
    logger = get_dagster_logger()
    
    # 检查 parse_results 是否为 None
    if parse_results is None:
        logger.error("parse_results 为 None，无法验证")
        return {
            "success": False,
            "validation_passed": False,
            "error_message": "parse_results 为 None",
        }
    
    if not parse_results.get("success"):
        logger.warning("解析作业失败，跳过验证")
        return {
            "success": False,
            "validation_passed": False,
        }
    
    parsed_count = parse_results.get("parsed_count", 0)
    failed_count = parse_results.get("failed_count", 0)
    total_documents = parse_results.get("total_documents", 0)
    
    # 计算成功率
    success_rate = parsed_count / total_documents if total_documents > 0 else 0
    
    logger.info(f"解析结果验证:")
    logger.info(f"  总文档数: {total_documents}")
    logger.info(f"  成功解析: {parsed_count}")
    logger.info(f"  解析失败: {failed_count}")
    logger.info(f"  成功率: {success_rate:.2%}")
    
    # 验证规则：成功率 >= 80% 认为通过
    validation_passed = success_rate >= 0.8 if total_documents > 0 else True
    
    if not validation_passed:
        logger.warning(f"⚠️ 解析成功率 {success_rate:.2%} 低于阈值 80%")
    
    # 记录失败文档（如果有）
    failed_documents = parse_results.get("failed_documents", [])
    if failed_documents:
        logger.warning(f"失败文档列表（前10个）:")
        for failed in failed_documents:
            logger.warning(f"  - document_id={failed['document_id']}, "
                         f"stock_code={failed['stock_code']}, "
                         f"error={failed['error']}")
    
    return {
        "success": True,
        "validation_passed": validation_passed,
        "total_documents": total_documents,
        "parsed_count": parsed_count,
        "failed_count": failed_count,
        "success_rate": success_rate,
        "failed_documents_count": len(failed_documents),
    }


# ==================== Dagster Jobs ====================

@job
def parse_pdf_job():
    """
    PDF 解析作业
    
    完整流程：
    1. 扫描待解析文档（状态为 'crawled'）
    2. 批量解析文档（调用 MinerU 解析器）
    3. 验证解析结果
    """
    scan_result = scan_pending_documents_op()
    parse_results = parse_documents_op(scan_result)
    validate_parse_results_op(parse_results)


# ==================== Schedules ====================

@schedule(
    job=parse_pdf_job,
    cron_schedule="0 */2 * * *",  # 每2小时执行一次
    default_status=DefaultScheduleStatus.STOPPED,  # 默认停止，需要手动启用
)
def hourly_parse_schedule(context):
    """
    每小时定时解析作业
    """
    return RunRequest()


@schedule(
    job=parse_pdf_job,
    cron_schedule="0 4 * * *",  # 每天凌晨4点执行（爬取完成后）
    default_status=DefaultScheduleStatus.STOPPED,  # 默认停止
)
def daily_parse_schedule(context):
    """
    每日定时解析作业（在爬取作业之后执行）
    """
    return RunRequest()


# ==================== Sensors ====================

@sensor(
    job=parse_pdf_job,
    default_status=DefaultSensorStatus.STOPPED,
)
def manual_trigger_parse_sensor(context):
    """
    手动触发解析传感器
    可以通过 Dagster UI 手动触发
    """
    return RunRequest()
