# -*- coding: utf-8 -*-
"""
Dagster 向量化作业定义
自动扫描未向量化的文档分块并执行向量化

按照 plan.md 设计：
- 处理层（Processing Layer）→ Dagster 调度
- 向量化 → Milvus 存储
"""

from datetime import datetime
from typing import List, Dict, Optional

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

# 导入向量化服务和数据库模块
from src.processing.ai.embedding.vectorizer import get_vectorizer
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.storage.metadata.models import Document, DocumentChunk
from src.common.constants import DocType, Market
from src.common.config import common_config


# ==================== 配置 Schema ====================

VECTORIZE_CONFIG_SCHEMA = {
    "batch_size": Field(
        int,
        default_value=32,
        description="每批向量化的分块数量（1-100）"
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
        is_required=False,
        description="本次作业最多处理的分块数量（1-10000），None 或不设置表示处理全部未向量化的分块"
    ),
    "force_revectorize": Field(
        bool,
        default_value=False,
        description="是否强制重新向量化（删除旧向量）"
    ),
}


# ==================== Dagster Ops ====================

@op(config_schema=VECTORIZE_CONFIG_SCHEMA)
def scan_unvectorized_chunks_op(context) -> Dict:
    """
    扫描未向量化的文档分块
    
    查找 vectorized_at IS NULL 的分块
    
    Returns:
        包含待向量化分块列表的字典
    """
    config = context.op_config
    logger = get_dagster_logger()
    
    batch_size = config.get("batch_size", 32)
    limit = config.get("limit")  # None 表示处理全部
    market_filter = config.get("market")
    doc_type_filter = config.get("doc_type")
    force_revectorize = config.get("force_revectorize", False)
    
    logger.info(f"开始扫描待向量化分块...")
    if limit is not None:
        logger.info(
            f"配置: batch_size={batch_size}, limit={limit}, "
            f"market={market_filter}, doc_type={doc_type_filter}, "
            f"force_revectorize={force_revectorize}"
        )
    else:
        logger.info(
            f"配置: batch_size={batch_size}, limit=无限制（处理全部）, "
            f"market={market_filter}, doc_type={doc_type_filter}, "
            f"force_revectorize={force_revectorize}"
        )
    
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 构建查询：查找未向量化的分块
            query = session.query(DocumentChunk).join(
                Document, DocumentChunk.document_id == Document.id
            )
            
            # 应用过滤条件
            if not force_revectorize:
                query = query.filter(DocumentChunk.vectorized_at.is_(None))
                logger.info("过滤条件: 只扫描未向量化的分块 (vectorized_at IS NULL)")
            else:
                logger.info("⚠️ force_revectorize=True: 将扫描所有分块（包括已向量化的）")
            
            # 注意：不再过滤表格分块，而是在向量化时提取表格文本内容
            # 表格分块会在vectorizer中提取文本后再向量化
            
            # 应用市场过滤
            if market_filter:
                query = query.filter(Document.market == market_filter)
            
            # 应用文档类型过滤
            if doc_type_filter:
                query = query.filter(Document.doc_type == doc_type_filter)
            
            # 限制数量并执行查询（包含表格分块，将在向量化时提取文本）
            if limit is not None:
                chunks = query.limit(limit).all()
            else:
                # limit 为 None 时，处理全部未向量化的分块
                chunks = query.all()
            
            # 统计表格分块数量（用于日志）
            table_chunks_count = sum(1 for chunk in chunks if chunk.is_table)
            
            if table_chunks_count > 0:
                logger.info(
                    f"找到 {len(chunks)} 个待向量化的分块（其中 {table_chunks_count} 个包含表格，"
                    f"将在向量化时提取文本内容）"
                )
            else:
                logger.info(f"找到 {len(chunks)} 个待向量化的分块")
            
            # 将分块列表转换为字典格式（便于 Dagster 传递）
            chunk_list = []
            for chunk in chunks:
                doc = session.query(Document).filter(Document.id == chunk.document_id).first()
                if not doc:
                    continue
                
                chunk_list.append({
                    "chunk_id": str(chunk.id),
                    "document_id": str(chunk.document_id),
                    "chunk_index": chunk.chunk_index,
                    "chunk_text": chunk.chunk_text[:100] + "..." if len(chunk.chunk_text) > 100 else chunk.chunk_text,  # 只保存前100字符用于日志
                    "stock_code": doc.stock_code,
                    "company_name": doc.company_name,
                    "market": doc.market,
                    "doc_type": doc.doc_type,
                    "year": doc.year,
                    "quarter": doc.quarter,
                    "vectorized_at": chunk.vectorized_at.isoformat() if chunk.vectorized_at else None,
                })
            
            # 按批次分组
            batches = []
            for i in range(0, len(chunk_list), batch_size):
                batch = chunk_list[i:i + batch_size]
                batches.append(batch)
            
            logger.info(f"分为 {len(batches)} 个批次，每批 {batch_size} 个分块")
            
            return {
                "success": True,
                "total_chunks": len(chunk_list),
                "total_batches": len(batches),
                "batches": batches,
                "chunks": chunk_list,
            }
            
    except Exception as e:
        logger.error(f"扫描待向量化分块失败: {e}", exc_info=True)
        return {
            "success": False,
            "error_message": str(e),
            "total_chunks": 0,
            "total_batches": 0,
            "batches": [],
            "chunks": [],
        }


@op(
    config_schema={
        "force_revectorize": Field(
            bool,
            default_value=False,
            description="是否强制重新向量化（删除旧向量）"
        ),
    }
)
def vectorize_chunks_op(context, scan_result: Dict) -> Dict:
    """
    批量执行向量化
    
    对扫描到的分块进行向量化，并保存到 Milvus 和数据库
    
    Args:
        scan_result: scan_unvectorized_chunks_op 的返回结果
        
    Returns:
        向量化结果统计
    """
    logger = get_dagster_logger()
    
    # 检查 scan_result 是否为 None
    if scan_result is None:
        logger.error("scan_result 为 None，无法继续向量化")
        return {
            "success": False,
            "error_message": "scan_result 为 None",
            "vectorized_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
        }
    
    # 安全获取 config
    config = context.op_config if hasattr(context, 'op_config') else {}
    force_revectorize = config.get("force_revectorize", False) if config else False
    
    if not scan_result.get("success"):
        logger.error(f"扫描失败，跳过向量化: {scan_result.get('error_message')}")
        return {
            "success": False,
            "error_message": "扫描失败",
            "vectorized_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
        }
    
    chunks = scan_result.get("chunks", [])
    if not chunks:
        logger.info("没有待向量化的分块")
        return {
            "success": True,
            "vectorized_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
        }
    
    logger.info(f"开始向量化 {len(chunks)} 个分块...")
    
    # 初始化向量化服务
    vectorizer = get_vectorizer()
    
    # 提取分块ID列表
    chunk_ids = [chunk["chunk_id"] for chunk in chunks]
    
    try:
        # 批量向量化
        result = vectorizer.vectorize_chunks(
            chunk_ids=chunk_ids,
            force_revectorize=force_revectorize
        )
        
        vectorized_count = result.get("vectorized_count", 0)
        failed_count = result.get("failed_count", 0)
        failed_chunks = result.get("failed_chunks", [])
        
        logger.info(
            f"向量化完成: 成功={vectorized_count}, 失败={failed_count}"
        )
        
        if failed_chunks:
            logger.warning(f"失败的分块数量: {len(failed_chunks)}")
            logger.warning("=" * 80)
            logger.warning("失败分块详细信息（包含 chunk_text）:")
            logger.warning("=" * 80)
            
            # 从数据库查询失败分块的详细信息（包括chunk_text）
            from src.storage.metadata.postgres_client import get_postgres_client
            from src.storage.metadata.models import DocumentChunk, Document
            import uuid as uuid_lib
            
            pg_client = get_postgres_client()
            try:
                with pg_client.get_session() as session:
                    # 打印所有失败的分块（不只是前10个）
                    for i, chunk_id in enumerate(failed_chunks, 1):
                        try:
                            chunk = session.query(DocumentChunk).filter(
                                DocumentChunk.id == uuid_lib.UUID(chunk_id)
                            ).first()
                            
                            if chunk:
                                chunk_text_preview = chunk.chunk_text[:200] if chunk.chunk_text else ""
                                doc = session.query(Document).filter(
                                    Document.id == chunk.document_id
                                ).first()
                                
                                logger.warning(
                                    f"\n失败分块 {i}/{len(failed_chunks)}:\n"
                                    f"  Chunk ID: {chunk_id}\n"
                                    f"  Document ID: {chunk.document_id}\n"
                                    f"  股票代码: {doc.stock_code if doc else 'N/A'}\n"
                                    f"  公司名称: {doc.company_name if doc else 'N/A'}\n"
                                    f"  Chunk Index: {chunk.chunk_index}\n"
                                    f"  Chunk Text (前200字符):\n"
                                    f"  {chunk_text_preview}\n"
                                    f"  {'...' if len(chunk.chunk_text or '') > 200 else ''}"
                                )
                            else:
                                logger.warning(f"失败分块 {i}: Chunk ID {chunk_id} 不存在")
                        except Exception as e:
                            logger.error(f"查询失败分块 {chunk_id} 信息异常: {e}")
            except Exception as e:
                logger.error(f"查询失败分块信息异常: {e}", exc_info=True)
            
            logger.warning("=" * 80)
        
        return {
            "success": True,
            "vectorized_count": vectorized_count,
            "failed_count": failed_count,
            "skipped_count": 0,
            "total_chunks": len(chunks),
            "failed_chunks": failed_chunks[:10],  # 最多返回10个失败记录
        }
        
    except Exception as e:
        logger.error(f"向量化异常: {e}", exc_info=True)
        return {
            "success": False,
            "error_message": str(e),
            "vectorized_count": 0,
            "failed_count": len(chunks),
            "skipped_count": 0,
            "total_chunks": len(chunks),
        }


@op
def validate_vectorize_results_op(context, vectorize_results: Dict) -> Dict:
    """
    验证向量化结果
    
    检查向量化结果的质量，记录统计信息
    
    Args:
        vectorize_results: vectorize_chunks_op 的返回结果
        
    Returns:
        验证结果统计
    """
    logger = get_dagster_logger()
    
    # 检查 vectorize_results 是否为 None
    if vectorize_results is None:
        logger.error("vectorize_results 为 None，无法验证")
        return {
            "success": False,
            "validation_passed": False,
            "error_message": "vectorize_results 为 None",
        }
    
    if not vectorize_results.get("success"):
        logger.warning("向量化作业失败，跳过验证")
        return {
            "success": False,
            "validation_passed": False,
        }
    
    vectorized_count = vectorize_results.get("vectorized_count", 0)
    failed_count = vectorize_results.get("failed_count", 0)
    total_chunks = vectorize_results.get("total_chunks", 0)
    
    # 计算成功率
    success_rate = vectorized_count / total_chunks if total_chunks > 0 else 0
    
    logger.info(f"向量化结果验证:")
    logger.info(f"  总分块数: {total_chunks}")
    logger.info(f"  成功向量化: {vectorized_count}")
    logger.info(f"  向量化失败: {failed_count}")
    logger.info(f"  成功率: {success_rate:.2%}")
    
    # 验证规则：成功率 >= 80% 认为通过
    validation_passed = success_rate >= 0.8 if total_chunks > 0 else True
    
    if not validation_passed:
        logger.warning(f"⚠️ 向量化成功率 {success_rate:.2%} 低于阈值 80%")
    
    # 记录失败分块（如果有）
    failed_chunks = vectorize_results.get("failed_chunks", [])
    if failed_chunks:
        logger.warning(f"失败分块列表（前10个）:")
        for chunk_id in failed_chunks:
            logger.warning(f"  - chunk_id={chunk_id}")
    
    return {
        "success": True,
        "validation_passed": validation_passed,
        "total_chunks": total_chunks,
        "vectorized_count": vectorized_count,
        "failed_count": failed_count,
        "success_rate": success_rate,
        "failed_chunks_count": len(failed_chunks),
    }


# ==================== Dagster Jobs ====================

@job(
    config={
        "ops": {
            "scan_unvectorized_chunks_op": {
                "config": {
                    "batch_size": 32,
                    # limit 不设置表示处理全部未向量化的分块
                    # market 和 doc_type 是可选的，不设置表示所有类型
                }
            },
            "vectorize_chunks_op": {
                "config": {
                    "force_revectorize": False,
                }
            }
        }
    },
    description="向量化作业 - 默认配置"
)
def vectorize_documents_job():
    """
    向量化作业

    完整流程：
    1. 扫描未向量化分块（vectorized_at IS NULL）
    2. 批量执行向量化（调用 Vectorizer）
    3. 验证向量化结果

    默认配置：
    - scan_unvectorized_chunks_op:
        - batch_size: 32 (每批处理32个分块)
        - limit: 不设置 (处理全部未向量化的分块)
    - vectorize_chunks_op:
        - force_revectorize: False (不强制重新向量化)
    """
    scan_result = scan_unvectorized_chunks_op()
    vectorize_results = vectorize_chunks_op(scan_result)
    validate_vectorize_results_op(vectorize_results)


# ==================== Schedules ====================

@schedule(
    job=vectorize_documents_job,
    cron_schedule="0 */2 * * *",  # 每2小时执行一次
    default_status=DefaultScheduleStatus.STOPPED,  # 默认停止，需要手动启用
)
def hourly_vectorize_schedule(context):
    """
    每2小时定时向量化作业
    """
    return RunRequest()


@schedule(
    job=vectorize_documents_job,
    cron_schedule="0 6 * * *",  # 每天凌晨6点执行（分块完成后）
    default_status=DefaultScheduleStatus.STOPPED,  # 默认停止
)
def daily_vectorize_schedule(context):
    """
    每日定时向量化作业（在分块作业之后执行）
    """
    return RunRequest()


# ==================== Sensors ====================

@sensor(
    job=vectorize_documents_job,
    default_status=DefaultSensorStatus.STOPPED,
)
def manual_trigger_vectorize_sensor(context):
    """
    手动触发向量化传感器
    可以通过 Dagster UI 手动触发
    """
    return RunRequest()
