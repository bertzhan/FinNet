# -*- coding: utf-8 -*-
"""
Dagster 图构建作业定义
自动扫描已分块的文档并构建图结构

按照 plan.md 设计：
- 处理层（Processing Layer）→ Dagster 调度
- 图构建 → Neo4j 存储
- 依赖：分块作业（chunk_jobs），不依赖向量化作业
"""

import uuid
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

# 导入图构建服务和数据库模块
from src.processing.graph.graph_builder import GraphBuilder
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import Document, DocumentChunk
from src.common.constants import DocType, Market
from src.common.config import common_config


# ==================== 配置 Schema ====================

GRAPH_CONFIG_SCHEMA = {
    "batch_size": Field(
        int,
        default_value=50,
        description="每批处理的文档数量（1-200）"
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
    "force_rebuild": Field(
        bool,
        default_value=False,
        description="是否强制重新构建图（删除旧图）"
    ),
}


# ==================== Dagster Ops ====================

@op(config_schema=GRAPH_CONFIG_SCHEMA)
def scan_chunked_documents_for_graph_op(context) -> Dict:
    """
    扫描已分块但未建图的文档
    
    查找有 DocumentChunk 记录且尚未在 Neo4j 中建图的文档
    注意：不依赖向量化状态，只要文档有分块即可建图
    
    Returns:
        包含待建图文档列表的字典
    """
    config = context.op_config
    logger = get_dagster_logger()
    
    batch_size = config.get("batch_size", 50)
    limit = config.get("limit", 100)
    market_filter = config.get("market")
    doc_type_filter = config.get("doc_type")
    force_rebuild = config.get("force_rebuild", False)
    
    logger.info(f"开始扫描待建图文档...")
    logger.info(
        f"配置: batch_size={batch_size}, limit={limit}, "
        f"market={market_filter}, doc_type={doc_type_filter}, "
        f"force_rebuild={force_rebuild}"
    )
    
    pg_client = get_postgres_client()
    builder = GraphBuilder()
    
    try:
        with pg_client.get_session() as session:
            # 构建查询：查找有分块的文档
            # 使用 EXISTS 子查询，更可靠且性能更好
            from sqlalchemy import exists
            
            # 先统计总数（用于调试）
            total_docs_query = session.query(Document)
            if market_filter:
                total_docs_query = total_docs_query.filter(Document.market == market_filter)
            if doc_type_filter:
                total_docs_query = total_docs_query.filter(Document.doc_type == doc_type_filter)
            total_docs_count = total_docs_query.count()
            logger.info(f"数据库中符合条件的文档总数: {total_docs_count} (market={market_filter}, doc_type={doc_type_filter})")
            
            # 统计有分块的文档总数
            chunked_docs_query = session.query(Document.id).filter(
                exists().where(DocumentChunk.document_id == Document.id)
            )
            if market_filter:
                chunked_docs_query = chunked_docs_query.filter(Document.market == market_filter)
            if doc_type_filter:
                chunked_docs_query = chunked_docs_query.filter(Document.doc_type == doc_type_filter)
            chunked_docs_count = chunked_docs_query.count()
            logger.info(f"有分块的文档总数: {chunked_docs_count}")
            
            # 统计分块总数（用于调试）
            chunks_query = session.query(DocumentChunk).join(
                Document, DocumentChunk.document_id == Document.id
            )
            if market_filter:
                chunks_query = chunks_query.filter(Document.market == market_filter)
            if doc_type_filter:
                chunks_query = chunks_query.filter(Document.doc_type == doc_type_filter)
            total_chunks_count = chunks_query.count()
            logger.info(f"分块总数: {total_chunks_count}")
            
            # 获取所有符合条件的文档ID（不先应用 limit）
            all_document_ids = [row[0] for row in chunked_docs_query.all()]
            
            logger.info(f"找到 {len(all_document_ids)} 个已分块的文档（过滤前）")
            
            # 验证：检查是否有文档ID丢失
            if len(all_document_ids) != chunked_docs_count:
                logger.warning(
                    f"⚠️ 文档ID数量不一致: count()={chunked_docs_count}, "
                    f"实际获取={len(all_document_ids)}"
                )
            
            # 如果强制重建，跳过检查，直接使用所有文档
            if force_rebuild:
                document_ids_to_process = all_document_ids
                logger.info("强制重建模式，跳过图中检查")
            else:
                # 批量检查哪些文档已在图中
                logger.info(f"批量检查 {len(all_document_ids)} 个文档是否已在图中...")
                
                # 如果文档数量为0，直接返回
                if not all_document_ids:
                    logger.warning("⚠️ 没有找到已分块的文档，无法进行图构建")
                    document_ids_to_process = []
                else:
                    exists_map = builder.batch_check_documents_in_graph(all_document_ids)
                    
                    # 调试：检查批量检查的结果
                    logger.info(f"批量检查返回结果数量: {len(exists_map)}")
                    if exists_map:
                        # 统计已存在和不存在的情况
                        existing_count = sum(1 for exists in exists_map.values() if exists)
                        not_existing_count = len(exists_map) - existing_count
                        logger.info(
                            f"批量检查结果: 已在图中={existing_count}, "
                            f"未在图中={not_existing_count}"
                        )
                        
                        # 如果所有文档都在图中，记录前几个示例
                        if existing_count == len(exists_map) and len(exists_map) > 0:
                            sample_ids = list(all_document_ids[:3])
                            logger.info(
                                f"⚠️ 所有文档都在图中，示例文档ID: "
                                f"{[str(doc_id) for doc_id in sample_ids]}"
                            )
                    
                    # 过滤出未建图的文档
                    document_ids_to_process = [
                        doc_id for doc_id in all_document_ids 
                        if not exists_map.get(doc_id, False)
                    ]
                    
                    already_graphed_count = len(all_document_ids) - len(document_ids_to_process)
                    logger.info(
                        f"图中检查完成: 已在图中={already_graphed_count}, "
                        f"待建图={len(document_ids_to_process)}"
                    )
                    
                    # 如果待建图文档为0，记录详细信息
                    if len(document_ids_to_process) == 0 and len(all_document_ids) > 0:
                        logger.warning(
                            f"⚠️ 所有 {len(all_document_ids)} 个文档都已建图，"
                            f"没有待处理的文档"
                        )
            
            # 应用 limit 限制（在过滤之后）
            if limit and limit > 0:
                document_ids_to_process = document_ids_to_process[:limit]
                logger.info(f"应用 limit={limit}，最终处理 {len(document_ids_to_process)} 个文档")
            
            # 根据文档ID查询完整文档信息
            documents = session.query(Document).filter(
                Document.id.in_(document_ids_to_process)
            ).all() if document_ids_to_process else []
            
            # 构建文档列表
            document_list = []
            for doc in documents:
                document_list.append({
                    "document_id": str(doc.id),
                    "stock_code": doc.stock_code,
                    "company_name": doc.company_name,
                    "market": doc.market,
                    "doc_type": doc.doc_type,
                    "year": doc.year,
                    "quarter": doc.quarter,
                })
            
            logger.info(f"找到 {len(document_list)} 个待建图文档")
            
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
        logger.error(f"扫描待建图文档失败: {e}", exc_info=True)
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
        "force_rebuild": Field(
            bool,
            default_value=False,
            description="是否强制重新构建图（删除旧图）"
        ),
    }
)
def build_graph_op(context, scan_result: Dict) -> Dict:
    """
    执行图构建
    
    对扫描到的文档构建图结构
    
    Args:
        scan_result: scan_chunked_documents_for_graph_op 的返回结果
        
    Returns:
        图构建结果统计
    """
    logger = get_dagster_logger()
    
    # 检查 scan_result 是否为 None
    if scan_result is None:
        logger.error("scan_result 为 None，无法继续构建图")
        return {
            "success": False,
            "error_message": "scan_result 为 None",
            "documents_processed": 0,
            "chunks_created": 0,
            "belongs_to_edges_created": 0,
            "has_child_edges_created": 0,
        }
    
    # 安全获取 config
    config = context.op_config if hasattr(context, 'op_config') else {}
    force_rebuild = config.get("force_rebuild", False) if config else False
    
    if not scan_result.get("success"):
        logger.error(f"扫描失败，跳过图构建: {scan_result.get('error_message')}")
        return {
            "success": False,
            "error_message": "扫描失败",
            "documents_processed": 0,
            "chunks_created": 0,
            "belongs_to_edges_created": 0,
            "has_child_edges_created": 0,
        }
    
    documents = scan_result.get("documents", [])
    if not documents:
        logger.info("没有待建图的文档")
        return {
            "success": True,
            "documents_processed": 0,
            "chunks_created": 0,
            "belongs_to_edges_created": 0,
            "has_child_edges_created": 0,
        }
    
    logger.info(f"开始构建图结构，文档数量: {len(documents)}")
    
    # 初始化图构建服务
    builder = GraphBuilder()
    
    # 提取文档ID列表
    document_ids = [uuid.UUID(doc["document_id"]) for doc in documents]
    
    try:
        # 构建图
        result = builder.build_document_chunk_graph(
            document_ids=document_ids,
            batch_size=50
        )
        
        documents_processed = result.get("documents_processed", 0)
        chunks_created = result.get("chunks_created", 0)
        belongs_to_edges_created = result.get("belongs_to_edges_created", 0)
        has_child_edges_created = result.get("has_child_edges_created", 0)
        failed_documents = result.get("failed_documents", [])
        
        logger.info(
            f"图构建完成: 文档={documents_processed}, 分块={chunks_created}, "
            f"BELONGS_TO边={belongs_to_edges_created}, HAS_CHILD边={has_child_edges_created}"
        )
        
        if failed_documents:
            logger.warning(f"失败的文档数量: {len(failed_documents)}")
            # 只记录前10个失败的文档
            for doc_id in failed_documents[:10]:
                logger.warning(f"  - 失败文档: {doc_id}")
        
        return {
            "success": result.get("success", True),
            "documents_processed": documents_processed,
            "chunks_created": chunks_created,
            "belongs_to_edges_created": belongs_to_edges_created,
            "has_child_edges_created": has_child_edges_created,
            "failed_documents": failed_documents[:10],  # 最多返回10个失败记录
        }
        
    except Exception as e:
        logger.error(f"图构建异常: {e}", exc_info=True)
        return {
            "success": False,
            "error_message": str(e),
            "documents_processed": 0,
            "chunks_created": 0,
            "belongs_to_edges_created": 0,
            "has_child_edges_created": 0,
            "total_documents": len(documents),
        }


@op
def validate_graph_op(context, build_results: Dict) -> Dict:
    """
    验证图构建结果
    
    检查图构建结果的质量，记录统计信息
    
    Args:
        build_results: build_graph_op 的返回结果
        
    Returns:
        验证结果统计
    """
    logger = get_dagster_logger()
    
    # 检查 build_results 是否为 None
    if build_results is None:
        logger.error("build_results 为 None，无法验证")
        return {
            "success": False,
            "validation_passed": False,
            "error_message": "build_results 为 None",
        }
    
    if not build_results.get("success"):
        logger.warning("图构建作业失败，跳过验证")
        return {
            "success": False,
            "validation_passed": False,
        }
    
    documents_processed = build_results.get("documents_processed", 0)
    chunks_created = build_results.get("chunks_created", 0)
    belongs_to_edges_created = build_results.get("belongs_to_edges_created", 0)
    has_child_edges_created = build_results.get("has_child_edges_created", 0)
    
    logger.info(f"图构建结果验证:")
    logger.info(f"  处理文档数: {documents_processed}")
    logger.info(f"  创建分块节点: {chunks_created}")
    logger.info(f"  创建 BELONGS_TO 边: {belongs_to_edges_created}")
    logger.info(f"  创建 HAS_CHILD 边: {has_child_edges_created}")
    
    # 获取图统计信息
    try:
        builder = GraphBuilder()
        graph_stats = builder.get_graph_stats()
        
        logger.info(f"图统计信息:")
        logger.info(f"  文档节点总数: {graph_stats.get('document_nodes', 0)}")
        logger.info(f"  分块节点总数: {graph_stats.get('chunk_nodes', 0)}")
        logger.info(f"  BELONGS_TO 边总数: {graph_stats.get('belongs_to_edges', 0)}")
        logger.info(f"  HAS_CHILD 边总数: {graph_stats.get('has_child_edges', 0)}")
        
        # 验证规则：如果处理了文档，应该有对应的分块和边
        validation_passed = True
        if documents_processed > 0:
            if chunks_created == 0:
                logger.warning("⚠️ 处理了文档但没有创建分块节点")
                validation_passed = False
            if belongs_to_edges_created == 0:
                logger.warning("⚠️ 创建了分块但没有创建 BELONGS_TO 边")
                validation_passed = False
        
        if not validation_passed:
            logger.warning("⚠️ 图构建验证未通过")
        
        return {
            "success": True,
            "validation_passed": validation_passed,
            "documents_processed": documents_processed,
            "chunks_created": chunks_created,
            "belongs_to_edges_created": belongs_to_edges_created,
            "has_child_edges_created": has_child_edges_created,
            "graph_stats": graph_stats,
        }
    except Exception as e:
        logger.error(f"获取图统计信息失败: {e}", exc_info=True)
        return {
            "success": True,
            "validation_passed": True,  # 即使统计失败，也不影响整体流程
            "documents_processed": documents_processed,
            "chunks_created": chunks_created,
            "belongs_to_edges_created": belongs_to_edges_created,
            "has_child_edges_created": has_child_edges_created,
            "error_message": f"获取统计信息失败: {str(e)}",
        }


# ==================== Dagster Jobs ====================

@job(
    config={
        "ops": {
            "scan_chunked_documents_for_graph_op": {
                "config": {
                    "batch_size": 50,
                    "limit": 100,
                    # market 和 doc_type 是可选的，不设置表示所有类型
                }
            },
            "build_graph_op": {
                "config": {
                    "force_rebuild": False,
                }
            }
        }
    },
    description="图构建作业 - 默认配置"
)
def build_graph_job():
    """
    图构建作业

    完整流程：
    1. 扫描已分块但未建图的文档（有 DocumentChunk 记录且文档不在 Neo4j 中）
    2. 批量执行图构建（调用 GraphBuilder）
    3. 验证图构建结果

    默认配置：
    - scan_chunked_documents_for_graph_op:
        - batch_size: 50 (每批处理50个文档)
        - limit: 100 (最多处理100个文档)
    - build_graph_op:
        - force_rebuild: False (不强制重新构建)
    """
    scan_result = scan_chunked_documents_for_graph_op()
    build_results = build_graph_op(scan_result)
    validate_graph_op(build_results)


# ==================== Schedules ====================

@schedule(
    job=build_graph_job,
    cron_schedule="0 */4 * * *",  # 每4小时执行一次
    default_status=DefaultScheduleStatus.STOPPED,  # 默认停止，需要手动启用
)
def hourly_graph_schedule(context):
    """
    每4小时定时图构建作业
    """
    return RunRequest()


@schedule(
    job=build_graph_job,
    cron_schedule="0 7 * * *",  # 每天凌晨7点执行（分块完成后）
    default_status=DefaultScheduleStatus.STOPPED,  # 默认停止
)
def daily_graph_schedule(context):
    """
    每日定时图构建作业（在分块作业之后执行）
    """
    return RunRequest()


# ==================== Sensors ====================

@sensor(
    job=build_graph_job,
    default_status=DefaultSensorStatus.STOPPED,
)
def manual_trigger_graph_sensor(context):
    """
    手动触发图构建传感器
    可以通过 Dagster UI 手动触发
    """
    return RunRequest()
