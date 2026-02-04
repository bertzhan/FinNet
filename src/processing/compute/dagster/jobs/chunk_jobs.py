# -*- coding: utf-8 -*-
"""
Dagster 文本分块作业定义
自动扫描已解析的文档并执行文本分块

按照 plan.md 设计：
- 处理层（Processing Layer）→ Dagster 调度
- 文本分块 → Silver 层（structure.json, chunks.json）
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
)

# 导入分块服务和数据库模块
from src.processing.text import get_text_chunker
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.storage.metadata.models import Document, ParsedDocument
from src.common.constants import DocType, Market
from src.common.config import common_config

# 获取项目根目录
PROJECT_ROOT = Path(common_config.PROJECT_ROOT)


# ==================== 配置 Schema ====================

CHUNK_CONFIG_SCHEMA = {
    "batch_size": Field(
        int,
        default_value=10,
        description="每批处理的文档数量（1-50）"
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
    "stock_codes": Field(
        list,
        is_required=False,
        description="按股票代码列表过滤（None = 不过滤，指定后将只处理这些股票代码的文档）。例如: ['000001', '000002']"
    ),
    "limit": Field(
        int,
        default_value=100,
        description="本次作业最多处理的文档数量（1-1000）"
    ),
    "force_rechunk": Field(
        bool,
        default_value=False,
        description="是否强制重新分块（删除旧分块）"
    ),
}


# ==================== Dagster Ops ====================

@op(config_schema=CHUNK_CONFIG_SCHEMA)
def scan_parsed_documents_op(context) -> Dict:
    """
    扫描已解析但未分块的文档
    
    查找状态为 'parsed' 且有 markdown_path 但未分块的文档
    
    Returns:
        包含待分块文档列表的字典
    """
    config = context.op_config
    logger = get_dagster_logger()
    
    batch_size = config.get("batch_size", 10)
    limit = config.get("limit", 100)
    market_filter = config.get("market")
    doc_type_filter = config.get("doc_type")
    stock_codes_filter = config.get("stock_codes")

    logger.info(f"开始扫描待分块文档...")
    force_rechunk = config.get("force_rechunk", False)
    logger.info(f"配置: batch_size={batch_size}, limit={limit}, market={market_filter}, doc_type={doc_type_filter}, stock_codes={stock_codes_filter}, force_rechunk={force_rechunk}")
    
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 构建查询
            query = session.query(ParsedDocument).join(
                Document, ParsedDocument.document_id == Document.id
            ).filter(
                ParsedDocument.markdown_path.isnot(None),
                ParsedDocument.markdown_path != ""
            )
            
            # 应用市场过滤
            if market_filter:
                query = query.filter(Document.market == market_filter)
            
            # 应用文档类型过滤
            if doc_type_filter:
                query = query.filter(Document.doc_type == doc_type_filter)

            # 应用股票代码过滤
            if stock_codes_filter:
                logger.info(f"按股票代码过滤: {stock_codes_filter}")
                query = query.filter(Document.stock_code.in_(stock_codes_filter))

            # 过滤掉已分块的文档（除非 force_rechunk）
            if not force_rechunk:
                query = query.filter(ParsedDocument.chunks_count == 0)
                logger.info("过滤条件: 只扫描未分块的文档 (chunks_count == 0)")
            else:
                logger.info("⚠️ force_rechunk=True: 将扫描所有文档（包括已分块的）")
            
            # 限制数量并执行查询
            parsed_docs = query.limit(limit).all()
            
            logger.info(f"找到 {len(parsed_docs)} 个待分块的文档")
            
            # 将文档列表转换为字典格式（便于 Dagster 传递）
            document_list = []
            for parsed_doc in parsed_docs:
                doc = session.query(Document).filter(Document.id == parsed_doc.document_id).first()
                if not doc:
                    continue
                
                document_list.append({
                    "document_id": str(doc.id),
                    "parsed_document_id": str(parsed_doc.id),
                    "stock_code": doc.stock_code,
                    "company_name": doc.company_name,
                    "market": doc.market,
                    "doc_type": doc.doc_type,
                    "year": doc.year,
                    "quarter": doc.quarter,
                    "markdown_path": parsed_doc.markdown_path,
                    "chunks_count": parsed_doc.chunks_count or 0,
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
                "documents": document_list,
            }
            
    except Exception as e:
        logger.error(f"扫描待分块文档失败: {e}", exc_info=True)
        return {
            "success": False,
            "error_message": str(e),
            "total_documents": 0,
            "total_batches": 0,
            "batches": [],
            "documents": [],
        }


@op(
    config_schema={
        "force_rechunk": Field(
            bool,
            default_value=False,
            description="是否强制重新分块（删除旧分块）"
        ),
    }
)
def chunk_documents_op(context, scan_result: Dict) -> Dict:
    """
    批量执行分块
    
    对扫描到的文档进行文本分块，并保存到 Silver 层和数据库
    
    Args:
        scan_result: scan_parsed_documents_op 的返回结果
        
    Returns:
        分块结果统计
    """
    logger = get_dagster_logger()
    
    # 检查 scan_result 是否为 None
    if scan_result is None:
        logger.error("scan_result 为 None，无法继续分块")
        return {
            "success": False,
            "error_message": "scan_result 为 None",
            "chunked_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
        }
    
    # 安全获取 config
    config = context.op_config if hasattr(context, 'op_config') else {}
    force_rechunk = config.get("force_rechunk", False) if config else False
    
    if not scan_result.get("success"):
        logger.error(f"扫描失败，跳过分块: {scan_result.get('error_message')}")
        return {
            "success": False,
            "error_message": "扫描失败",
            "chunked_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
        }
    
    documents = scan_result.get("documents", [])
    if not documents:
        logger.info("没有待分块的文档")
        return {
            "success": True,
            "chunked_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
        }
    
    logger.info(f"🚀 开始分块: 共 {len(documents)} 个文档")

    # 初始化分块服务
    chunker = get_text_chunker()

    chunked_count = 0
    failed_count = 0
    skipped_count = 0
    failed_documents = []

    for idx, doc_info in enumerate(documents):
        document_id = doc_info["document_id"]
        stock_code = doc_info["stock_code"]
        company_name = doc_info.get("company_name", "")
        markdown_path = doc_info["markdown_path"]

        # 显示进度：每10个或每10%显示一次，或最后一个
        total = len(documents)
        if (idx + 1) % 10 == 0 or (idx + 1) % max(1, total // 10) == 0 or (idx + 1) == total:
            progress_pct = (idx + 1) / total * 100
            logger.info(f"📦 [{idx+1}/{total}] {progress_pct:.1f}% | 分块: {stock_code} - {company_name}")
        
        try:
            result = chunker.chunk_document(
                document_id=document_id,
                force_rechunk=force_rechunk
            )
            
            # 检查 result 是否为 None
            if result is None:
                failed_count += 1
                error_msg = "分块服务返回 None"
                logger.error(f"❌ 分块失败: document_id={document_id}, error={error_msg}")
                failed_documents.append({
                    "document_id": document_id,
                    "stock_code": stock_code,
                    "error": error_msg
                })
                continue
            
            if result.get("success"):
                chunked_count += 1
                chunks_count = result.get("chunks_count", 0)
                structure_path = result.get("structure_path", "N/A")
                chunks_path = result.get("chunks_path", "N/A")
                logger.info(
                    f"✅ 分块成功: document_id={document_id}, "
                    f"chunks_count={chunks_count}, "
                    f"structure_path={structure_path}, "
                    f"chunks_path={chunks_path}"
                )
            else:
                # 检查是否是跳过（已分块）
                if "已分块" in result.get("error_message", ""):
                    skipped_count += 1
                    logger.info(f"⏭️ 跳过已分块文档: document_id={document_id}")
                else:
                    failed_count += 1
                    error_msg = result.get("error_message", "未知错误")
                    logger.error(f"❌ 分块失败: document_id={document_id}, error={error_msg}")
                    failed_documents.append({
                        "document_id": document_id,
                        "stock_code": stock_code,
                        "error": error_msg
                    })
                
        except Exception as e:
            failed_count += 1
            error_msg = str(e)
            logger.error(f"❌ 分块异常: document_id={document_id}, error={error_msg}", exc_info=True)
            failed_documents.append({
                "document_id": document_id,
                "stock_code": stock_code,
                "error": error_msg
            })
    
    logger.info(
        f"分块完成: 成功={chunked_count}, 失败={failed_count}, 跳过={skipped_count}"
    )
    
    return {
        "success": True,
        "chunked_count": chunked_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "total_documents": len(documents),
        "failed_documents": failed_documents[:10],  # 最多返回10个失败记录
    }


@op
def validate_chunk_results_op(context, chunk_results: Dict) -> Dict:
    """
    验证分块结果
    
    检查分块结果的质量，记录统计信息
    
    Args:
        chunk_results: chunk_documents_op 的返回结果
        
    Returns:
        验证结果统计
    """
    logger = get_dagster_logger()
    
    # 检查 chunk_results 是否为 None
    if chunk_results is None:
        logger.error("chunk_results 为 None，无法验证")
        return {
            "success": False,
            "validation_passed": False,
            "error_message": "chunk_results 为 None",
        }
    
    if not chunk_results.get("success"):
        logger.warning("分块作业失败，跳过验证")
        return {
            "success": False,
            "validation_passed": False,
        }
    
    chunked_count = chunk_results.get("chunked_count", 0)
    failed_count = chunk_results.get("failed_count", 0)
    total_documents = chunk_results.get("total_documents", 0)
    
    # 计算成功率
    success_rate = chunked_count / total_documents if total_documents > 0 else 0
    
    logger.info(f"分块结果验证:")
    logger.info(f"  总文档数: {total_documents}")
    logger.info(f"  成功分块: {chunked_count}")
    logger.info(f"  分块失败: {failed_count}")
    logger.info(f"  成功率: {success_rate:.2%}")
    
    # 验证规则：成功率 >= 80% 认为通过
    validation_passed = success_rate >= 0.8 if total_documents > 0 else True
    
    if not validation_passed:
        logger.warning(f"⚠️ 分块成功率 {success_rate:.2%} 低于阈值 80%")
    
    # 记录失败文档（如果有）
    failed_documents = chunk_results.get("failed_documents", [])
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
        "chunked_count": chunked_count,
        "failed_count": failed_count,
        "success_rate": success_rate,
        "failed_documents_count": len(failed_documents),
    }


# ==================== Dagster Jobs ====================

@job(
    config={
        "ops": {
            "scan_parsed_documents_op": {
                "config": {
                    "batch_size": 5,
                    "limit": 20,
                    # doc_type 是可选的，不设置表示所有类型
                }
            },
            "chunk_documents_op": {
                "config": {
                    "force_rechunk": False,
                }
            }
        }
    },
    description="文本分块作业 - 默认配置"
)
def chunk_documents_job():
    """
    文本分块作业

    完整流程：
    1. 扫描已解析文档（状态为 'parsed'，有 markdown_path，未分块）
    2. 批量执行分块（调用 TextChunker）
    3. 验证分块结果

    默认配置：
    - scan_parsed_documents_op:
        - batch_size: 5 (每批处理5个文档)
        - limit: 20 (最多处理20个文档)
    - chunk_documents_op:
        - force_rechunk: False (不强制重新分块)
    """
    scan_result = scan_parsed_documents_op()
    chunk_results = chunk_documents_op(scan_result)
    validate_chunk_results_op(chunk_results)


# ==================== Schedules ====================

@schedule(
    job=chunk_documents_job,
    cron_schedule="0 */2 * * *",  # 每2小时执行一次
    default_status=DefaultScheduleStatus.STOPPED,  # 默认停止，需要手动启用
)
def hourly_chunk_schedule(context):
    """
    每小时定时分块作业
    """
    return RunRequest()


@schedule(
    job=chunk_documents_job,
    cron_schedule="0 5 * * *",  # 每天凌晨5点执行（解析完成后）
    default_status=DefaultScheduleStatus.STOPPED,  # 默认停止
)
def daily_chunk_schedule(context):
    """
    每日定时分块作业（在解析作业之后执行）
    """
    return RunRequest()


# ==================== Sensors ====================

@sensor(
    job=chunk_documents_job,
    default_status=DefaultSensorStatus.STOPPED,
)
def manual_trigger_chunk_sensor(context):
    """
    手动触发分块传感器
    可以通过 Dagster UI 手动触发
    """
    return RunRequest()
