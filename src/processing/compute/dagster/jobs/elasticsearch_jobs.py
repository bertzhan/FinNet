# -*- coding: utf-8 -*-
"""
Dagster Elasticsearch 索引作业定义
自动扫描已分块的文档并索引到 Elasticsearch

按照 plan.md 设计：
- 处理层（Processing Layer）→ Dagster 调度
- 全文检索索引 → Elasticsearch 存储
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

# 导入 Elasticsearch 客户端和数据库模块
from src.storage.elasticsearch import get_elasticsearch_client
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.storage.metadata.models import Document, DocumentChunk
from src.common.constants import DocType, Market
from src.common.config import common_config


# ==================== 配置 Schema ====================

ELASTICSEARCH_CONFIG_SCHEMA = {
    "batch_size": Field(
        int,
        default_value=100,
        description="每批索引的分块数量（1-1000）"
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
        default_value=1000,
        description="本次作业最多处理的分块数量（1-10000）"
    ),
    "force_reindex": Field(
        bool,
        default_value=False,
        description="是否强制重新索引（删除旧索引）"
    ),
}


# ==================== Dagster Ops ====================

@op(config_schema=ELASTICSEARCH_CONFIG_SCHEMA)
def scan_chunked_documents_op(context) -> Dict:
    """
    扫描已分块的文档分块（用于索引到 Elasticsearch）
    
    查找已分块但可能未索引到 Elasticsearch 的分块
    
    Returns:
        包含待索引分块列表的字典
    """
    config = context.op_config
    logger = get_dagster_logger()
    
    batch_size = config.get("batch_size", 100)
    limit = config.get("limit", 1000)
    market_filter = config.get("market")
    doc_type_filter = config.get("doc_type")
    force_reindex = config.get("force_reindex", False)
    
    logger.info(f"开始扫描待索引分块...")
    logger.info(
        f"配置: batch_size={batch_size}, limit={limit}, "
        f"market={market_filter}, doc_type={doc_type_filter}, "
        f"force_reindex={force_reindex}"
    )
    
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 构建查询：查找已分块的分块（chunk_text 不为空）
            query = session.query(DocumentChunk).join(
                Document, DocumentChunk.document_id == Document.id
            ).filter(
                DocumentChunk.chunk_text.isnot(None),
                DocumentChunk.chunk_text != ""
            )
            
            # 如果不是强制重新索引，只查询未索引到 ES 的分块
            if not force_reindex:
                query = query.filter(DocumentChunk.es_indexed_at.is_(None))
            
            # 应用市场过滤
            if market_filter:
                query = query.filter(Document.market == market_filter)
            
            # 应用文档类型过滤
            if doc_type_filter:
                query = query.filter(Document.doc_type == doc_type_filter)
            
            # 限制数量并执行查询
            chunks = query.limit(limit).all()
            
            logger.info(f"找到 {len(chunks)} 个已分块的分块")
            
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
                    "chunk_text": chunk.chunk_text,
                    "title": chunk.title or "",
                    "title_level": chunk.title_level,
                    "chunk_size": chunk.chunk_size,
                    "is_table": chunk.is_table or False,
                    "stock_code": doc.stock_code,
                    "company_name": doc.company_name,
                    "market": doc.market,
                    "doc_type": doc.doc_type,
                    "year": doc.year,
                    "quarter": doc.quarter,
                    "publish_date": doc.publish_date.isoformat() if doc.publish_date else None,
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
        logger.error(f"扫描待索引分块失败: {e}", exc_info=True)
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
        "force_reindex": Field(
            bool,
            default_value=False,
            description="是否强制重新索引（删除旧索引）"
        ),
    }
)
def index_chunks_to_elasticsearch_op(context, scan_result: Dict) -> Dict:
    """
    批量索引分块到 Elasticsearch
    
    对扫描到的分块进行索引，并保存到 Elasticsearch
    
    Args:
        scan_result: scan_chunked_documents_op 的返回结果
        
    Returns:
        索引结果统计
    """
    logger = get_dagster_logger()
    
    # 检查 scan_result 是否为 None
    if scan_result is None:
        logger.error("scan_result 为 None，无法继续索引")
        return {
            "success": False,
            "error_message": "scan_result 为 None",
            "indexed_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
        }
    
    # 安全获取 config
    config = context.op_config if hasattr(context, 'op_config') else {}
    force_reindex = config.get("force_reindex", False) if config else False
    
    if not scan_result.get("success"):
        logger.error(f"扫描失败，跳过索引: {scan_result.get('error_message')}")
        return {
            "success": False,
            "error_message": "扫描失败",
            "indexed_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
        }
    
    chunks = scan_result.get("chunks", [])
    if not chunks:
        logger.info("没有待索引的分块")
        return {
            "success": True,
            "indexed_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
        }
    
    logger.info(f"开始索引 {len(chunks)} 个分块到 Elasticsearch...")
    
    # 初始化 Elasticsearch 客户端
    es_client = get_elasticsearch_client()
    
    # 确保索引存在
    index_name = "chunks"
    try:
        es_client.create_index(index_name)
    except Exception as e:
        logger.error(f"创建索引失败: {e}")
        return {
            "success": False,
            "error_message": f"创建索引失败: {e}",
            "indexed_count": 0,
            "failed_count": len(chunks),
            "skipped_count": 0,
        }
    
    indexed_count = 0
    failed_count = 0
    skipped_count = 0
    failed_chunks = []
    
    # 批量索引（分批处理）
    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        
        try:
            # 准备文档数据
            documents = []
            for chunk in batch:
                # 构建 Elasticsearch 文档
                doc = {
                    "id": chunk["chunk_id"],
                    "document_id": chunk["document_id"],
                    "chunk_index": chunk["chunk_index"],
                    "chunk_text": chunk["chunk_text"],
                    "title": chunk.get("title", ""),
                    "title_level": chunk.get("title_level"),
                    "chunk_size": chunk.get("chunk_size", 0),
                    "is_table": chunk.get("is_table", False),
                    "stock_code": chunk["stock_code"],
                    "company_name": chunk["company_name"],
                    "market": chunk["market"],
                    "doc_type": chunk["doc_type"],
                    "year": chunk["year"],
                    "quarter": chunk.get("quarter"),
                    "publish_date": chunk.get("publish_date"),
                    "created_at": datetime.now().isoformat(),
                }
                documents.append(doc)
            
            # 批量索引
            result = es_client.bulk_index_documents(
                index_name=index_name,
                documents=documents,
                document_id_field="id"
            )
            
            success_count = result.get("success_count", 0)
            failed_items = result.get("failed_items", [])
            
            indexed_count += success_count
            failed_count += len(failed_items)
            
            if failed_items:
                for item in failed_items[:10]:  # 只记录前10个失败项
                    failed_chunks.append(item.get("_id", "unknown"))
            
            logger.info(
                f"批次 {i//batch_size + 1}: 成功={success_count}, 失败={len(failed_items)}"
            )
            
        except Exception as e:
            logger.error(f"批量索引失败（批次 {i//batch_size + 1}）: {e}", exc_info=True)
            failed_count += len(batch)
            failed_chunks.extend([chunk["chunk_id"] for chunk in batch])
    
    # 刷新索引（使新索引的文档立即可搜索）
    try:
        es_client.refresh_index(index_name)
    except Exception as e:
        logger.warning(f"刷新索引失败: {e}")
    
    # 更新成功索引的分块的 es_indexed_at 字段
    if indexed_count > 0:
        try:
            pg_client = get_postgres_client()
            # 收集成功索引的 chunk_id（排除失败的）
            failed_set = set(failed_chunks)
            success_chunk_ids = [
                chunk["chunk_id"] for chunk in chunks
                if chunk["chunk_id"] not in failed_set
            ]
            
            if success_chunk_ids:
                with pg_client.get_session() as session:
                    from sqlalchemy import update
                    import uuid
                    
                    # 批量更新 es_indexed_at 字段
                    stmt = update(DocumentChunk).where(
                        DocumentChunk.id.in_([uuid.UUID(cid) for cid in success_chunk_ids])
                    ).values(es_indexed_at=datetime.now())
                    
                    session.execute(stmt)
                    session.commit()
                    
                logger.info(f"已更新 {len(success_chunk_ids)} 个分块的 es_indexed_at 字段")
        except Exception as e:
            logger.error(f"更新 es_indexed_at 字段失败: {e}", exc_info=True)
    
    logger.info(
        f"索引完成: 成功={indexed_count}, 失败={failed_count}, 跳过={skipped_count}"
    )
    
    if failed_chunks:
        logger.warning(f"失败的分块数量: {len(failed_chunks)}")
        # 只记录前10个失败的分块
        for chunk_id in failed_chunks[:10]:
            logger.warning(f"  - 失败分块: {chunk_id}")
    
    return {
        "success": True,
        "indexed_count": indexed_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "total_chunks": len(chunks),
        "failed_chunks": failed_chunks[:10],  # 最多返回10个失败记录
    }


@op
def validate_elasticsearch_results_op(context, index_results: Dict) -> Dict:
    """
    验证 Elasticsearch 索引结果
    
    检查索引结果的质量，记录统计信息
    
    Args:
        index_results: index_chunks_to_elasticsearch_op 的返回结果
        
    Returns:
        验证结果统计
    """
    logger = get_dagster_logger()
    
    # 检查 index_results 是否为 None
    if index_results is None:
        logger.error("index_results 为 None，无法验证")
        return {
            "success": False,
            "error_message": "index_results 为 None",
            "validation_passed": False,
        }
    
    if not index_results.get("success"):
        logger.error(f"索引失败: {index_results.get('error_message')}")
        return {
            "success": False,
            "error_message": index_results.get("error_message"),
            "validation_passed": False,
        }
    
    indexed_count = index_results.get("indexed_count", 0)
    failed_count = index_results.get("failed_count", 0)
    total_chunks = index_results.get("total_chunks", 0)
    
    # 计算成功率
    if total_chunks > 0:
        success_rate = indexed_count / total_chunks
    else:
        success_rate = 0.0
    
    logger.info(
        f"索引验证: 总数={total_chunks}, "
        f"成功={indexed_count}, 失败={failed_count}, "
        f"成功率={success_rate:.2%}"
    )
    
    # 验证规则：成功率 >= 90%
    validation_passed = success_rate >= 0.9
    
    if not validation_passed:
        logger.warning(
            f"⚠️ 索引成功率低于90%: {success_rate:.2%}, "
            f"失败数量={failed_count}"
        )
    
    return {
        "success": True,
        "validation_passed": validation_passed,
        "total_chunks": total_chunks,
        "indexed_count": indexed_count,
        "failed_count": failed_count,
        "success_rate": success_rate,
        "failed_chunks_count": len(index_results.get("failed_chunks", [])),
    }


# ==================== Dagster Jobs ====================

@job(
    config={
        "ops": {
            "scan_chunked_documents_op": {
                "config": {
                    "batch_size": 100,
                    "limit": 1000,
                    # market 和 doc_type 是可选的，不设置表示所有类型
                }
            },
            "index_chunks_to_elasticsearch_op": {
                "config": {
                    "force_reindex": False,
                }
            }
        }
    },
    description="Elasticsearch 索引作业 - 默认配置"
)
def elasticsearch_index_job():
    """
    Elasticsearch 索引作业

    完整流程：
    1. 扫描已分块的文档分块
    2. 批量索引到 Elasticsearch
    3. 验证索引结果

    默认配置：
    - scan_chunked_documents_op:
        - batch_size: 100 (每批处理100个分块)
        - limit: 1000 (最多处理1000个分块)
    - index_chunks_to_elasticsearch_op:
        - force_reindex: False (不强制重新索引)
    """
    scan_result = scan_chunked_documents_op()
    index_results = index_chunks_to_elasticsearch_op(scan_result)
    validate_elasticsearch_results_op(index_results)


# ==================== Schedules ====================

@schedule(
    job=elasticsearch_index_job,
    cron_schedule="0 */3 * * *",  # 每3小时执行一次
    default_status=DefaultScheduleStatus.STOPPED,  # 默认停止，需要手动启用
)
def hourly_elasticsearch_schedule(context):
    """
    每3小时定时索引作业
    """
    return RunRequest()


@schedule(
    job=elasticsearch_index_job,
    cron_schedule="0 6 * * *",  # 每天凌晨6点执行（在分块作业之后）
    default_status=DefaultScheduleStatus.STOPPED,  # 默认停止
)
def daily_elasticsearch_schedule(context):
    """
    每日定时索引作业（在分块作业之后执行）
    """
    return RunRequest()


# ==================== Sensors ====================

@sensor(
    job=elasticsearch_index_job,
    default_status=DefaultSensorStatus.STOPPED,
)
def manual_trigger_elasticsearch_sensor(context):
    """
    手动触发 Elasticsearch 索引传感器
    
    可以通过 Dagster UI 手动触发索引作业
    """
    return RunRequest()
