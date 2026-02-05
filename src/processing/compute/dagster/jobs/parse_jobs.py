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
        default_value=50,
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
    "stock_codes": Field(
        list,
        is_required=False,
        description="按股票代码列表过滤（None = 不过滤，指定后将只处理这些股票代码的文档）。例如: ['000001', '000002']"
    ),
    "limit": Field(
        int,
        is_required=False,
        description="本次作业最多处理的文档数量，None 或不设置表示处理全部"
    ),
    "force_reparse": Field(
        bool,
        default_value=False,
        description="是否强制重新解析已解析的文档（默认 False，只解析未解析的文档）"
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
    支持 force_reparse 强制重新解析已解析的文档

    Returns:
        包含待解析文档列表的字典
    """
    config = context.op_config
    logger = get_dagster_logger()

    batch_size = config.get("batch_size", 10)
    limit = config.get("limit")
    market_filter = config.get("market")
    doc_type_filter = config.get("doc_type")
    stock_codes_filter = config.get("stock_codes")
    force_reparse = config.get("force_reparse", False)

    logger.info(f"开始扫描待解析文档...")
    logger.info(f"配置: batch_size={batch_size}, limit={limit}, market={market_filter}, doc_type={doc_type_filter}, stock_codes={stock_codes_filter}, force_reparse={force_reparse}")

    pg_client = get_postgres_client()

    try:
        with pg_client.get_session() as session:
            # 根据 force_reparse 决定查询哪些状态的文档
            # 注意：这里不应用 limit，先获取所有符合条件的文档
            if force_reparse:
                # 强制重新解析：查询 'crawled' 和 'parsed' 状态的文档
                logger.info("强制重新解析模式：将解析 'crawled' 和 'parsed' 状态的文档")
                documents_crawled = crud.get_documents_by_status(
                    session=session,
                    status=DocumentStatus.CRAWLED.value,
                    limit=None,  # 不限制，获取所有
                    offset=0
                )
                documents_parsed = crud.get_documents_by_status(
                    session=session,
                    status=DocumentStatus.PARSED.value,
                    limit=None,  # 不限制，获取所有
                    offset=0
                )
                documents = documents_crawled + documents_parsed
                # 去重（如果有重复）
                seen_ids = set()
                unique_documents = []
                for doc in documents:
                    if doc.id not in seen_ids:
                        seen_ids.add(doc.id)
                        unique_documents.append(doc)
                documents = unique_documents
            else:
                # 正常模式：只查找状态为 'crawled' 的文档
                documents = crud.get_documents_by_status(
                    session=session,
                    status=DocumentStatus.CRAWLED.value,
                    limit=None,  # 不限制，获取所有
                    offset=0
                )

            logger.info(f"查询到 {len(documents)} 个文档（应用过滤前）")

            # 应用市场过滤
            if market_filter:
                documents = [d for d in documents if d.market == market_filter]
                logger.info(f"市场过滤后: {len(documents)} 个文档")

            # 应用文档类型过滤
            if doc_type_filter:
                documents = [d for d in documents if d.doc_type == doc_type_filter]
                logger.info(f"文档类型过滤后: {len(documents)} 个文档")

                logger.info(f"行业过滤后: {len(documents)} 个文档")

            # 应用股票代码过滤
            if stock_codes_filter:
                logger.info(f"按股票代码过滤: {stock_codes_filter}")
                documents = [d for d in documents if d.stock_code in stock_codes_filter]
                logger.info(f"股票代码过滤后: {len(documents)} 个文档")

            # 应用 limit（最后应用）
            if limit and len(documents) > limit:
                logger.info(f"应用 limit={limit}，从 {len(documents)} 个文档中截取前 {limit} 个")
                documents = documents[:limit]
            
            # 只处理 PDF 文档
            pdf_documents = [
                d for d in documents
                if d.minio_object_path and d.minio_object_path.endswith('.pdf')
            ]
            
            # 验证文件是否在 MinIO 中存在（避免解析不存在的文件）
            from src.storage.object_store.minio_client import MinIOClient
            minio_client = MinIOClient()
            existing_pdf_documents = []
            for doc in pdf_documents:
                if minio_client.file_exists(doc.minio_object_path):
                    existing_pdf_documents.append(doc)
                else:
                    logger.warning(f"文档文件不存在，跳过: document_id={doc.id}, path={doc.minio_object_path}")
            
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
                    "minio_object_path": doc.minio_object_path,
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
                "force_reparse": force_reparse,  # 传递 force_reparse 配置
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


@op(
    config_schema={
        "enable_silver_upload": Field(
            bool,
            default_value=True,
            description="是否上传解析结果到 Silver 层"
        ),
        "start_page_id": Field(
            int,
            default_value=0,
            description="起始页码（从0开始），默认0"
        ),
        "end_page_id": Field(
            int,
            is_required=False,
            description="结束页码（从0开始），None 表示解析到最后。例如：设置为 4 表示解析前5页（0-4）"
        ),
    }
)
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

    # 调试：打印配置信息
    logger.info(f"🔍 DEBUG: config = {config}")
    logger.info(f"🔍 DEBUG: hasattr(context, 'op_config') = {hasattr(context, 'op_config')}")

    enable_silver_upload = config.get("enable_silver_upload", True) if config else True
    start_page_id = config.get("start_page_id", 0) if config else 0
    end_page_id = config.get("end_page_id") if config else None

    # 从 scan_result 中获取 force_reparse 配置
    force_reparse = scan_result.get("force_reparse", False)

    logger.info(f"🔍 DEBUG: enable_silver_upload={enable_silver_upload}, start_page_id={start_page_id}, end_page_id={end_page_id}, force_reparse={force_reparse}")

    if end_page_id is not None:
        logger.info(f"📄 页面范围: {start_page_id} - {end_page_id} (共 {end_page_id - start_page_id + 1} 页)")
    else:
        logger.info(f"📄 页面范围: {start_page_id} - 最后 (解析全部)")

    if force_reparse:
        logger.info(f"⚠️  强制重新解析模式：将重新解析已解析的文档")
    
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
    
    logger.info(f"🚀 开始解析: 共 {len(documents)} 个文档")

    # 初始化解析器
    parser = get_mineru_parser()

    pg_client = get_postgres_client()

    parsed_count = 0
    failed_count = 0
    skipped_count = 0
    failed_documents = []

    for idx, doc_info in enumerate(documents):
        document_id = doc_info["document_id"]
        stock_code = doc_info["stock_code"]
        company_name = doc_info.get("company_name", "")
        minio_path = doc_info["minio_object_path"]

        # 显示进度：每10个或每10%显示一次，或最后一个
        total = len(documents)
        if (idx + 1) % 10 == 0 or (idx + 1) % max(1, total // 10) == 0 or (idx + 1) == total:
            progress_pct = (idx + 1) / total * 100
            logger.info(f"📦 [{idx+1}/{total}] {progress_pct:.1f}% | 解析: {stock_code} - {company_name}")
        
        try:
            # 注意：parse_document 方法内部会重新查询数据库获取 Document 对象
            # 所以这里直接传递 document_id 即可，不需要传递 Document 对象
            result = parser.parse_document(
                document_id=document_id,
                save_to_silver=enable_silver_upload,
                start_page_id=start_page_id,
                end_page_id=end_page_id,
                force_reparse=force_reparse  # 传递强制重新解析标志
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
                page_count = result.get("page_count", 0)
                logger.info(
                    f"✅ 解析成功: document_id={document_id}, "
                    f"output_path={output_path}, "
                    f"text_length={text_length}"
                )
                
                # 记录资产物化（Dagster 数据血缘）
                try:
                    market = doc_info.get("market", "")
                    doc_type = doc_info.get("doc_type", "")
                    year = doc_info.get("year")
                    quarter = doc_info.get("quarter")
                    
                    # 构建资产key: ["silver", "parsed_documents", market, doc_type, stock_code, year, quarter]
                    asset_key = ["silver", "parsed_documents", market, doc_type, stock_code]
                    if year:
                        asset_key.append(str(year))
                    if quarter:
                        asset_key.append(f"Q{quarter}")
                    
                    # 构建父资产key（指向bronze层）
                    parent_asset_key = ["bronze", market, doc_type]
                    if year:
                        parent_asset_key.append(str(year))
                    if quarter:
                        parent_asset_key.append(f"Q{quarter}")
                    
                    context.log_event(
                        AssetMaterialization(
                            asset_key=asset_key,
                            description=f"{company_name} {year or ''} Q{quarter or ''} 解析完成",
                            metadata={
                                "document_id": MetadataValue.text(str(document_id)),
                                "stock_code": MetadataValue.text(stock_code),
                                "company_name": MetadataValue.text(company_name or ""),
                                "market": MetadataValue.text(market),
                                "doc_type": MetadataValue.text(doc_type),
                                "year": MetadataValue.int(year) if year else MetadataValue.int(0),
                                "quarter": MetadataValue.int(quarter) if quarter else MetadataValue.int(0),
                                "text_length": MetadataValue.int(text_length),
                                "page_count": MetadataValue.int(page_count),
                                "silver_path": MetadataValue.text(output_path),
                                "parsed_at": MetadataValue.text(datetime.now().isoformat()),
                                "parent_asset_key": MetadataValue.text("/".join(parent_asset_key)),
                            }
                        )
                    )
                except Exception as e:
                    logger.warning(f"记录 AssetMaterialization 事件失败 (document_id={document_id}): {e}")
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
            # 检查是否是 Dagster 中断异常（DagsterExecutionInterruptedError 等）
            error_type = type(e).__name__
            if "Interrupt" in error_type or "Interrupted" in error_type:
                logger.warning(f"⚠️ 解析被中断: document_id={document_id}, error_type={error_type}")
                # 重新抛出异常，让 Dagster 知道任务被中断
                raise
            
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
    
    # 检查 parse_results 是否为 None（可能是上游被中断）
    if parse_results is None:
        logger.warning("parse_results 为 None，可能是上游步骤被中断，跳过验证")
        return {
            "success": False,
            "validation_passed": False,
            "error_message": "parse_results 为 None（可能被中断）",
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
    
    # 记录数据质量指标
    try:
        context.log_event(
            AssetMaterialization(
                asset_key=["quality_metrics", "parse_validation"],
                description=f"解析数据质量检查: 通过率 {success_rate:.2%}",
                metadata={
                    "total": MetadataValue.int(total_documents),
                    "parsed": MetadataValue.int(parsed_count),
                    "failed": MetadataValue.int(failed_count),
                    "success_rate": MetadataValue.float(success_rate),
                    "validation_passed": MetadataValue.bool(validation_passed),
                }
            )
        )
    except Exception as e:
        logger.warning(f"记录质量指标 AssetMaterialization 事件失败: {e}")
    
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

@job(
    config={
        "ops": {
            "scan_pending_documents_op": {
                "config": {
                    "batch_size": 50,
                    # limit 不设置表示处理全部，doc_type 是可选的，不设置表示所有类型
                }
            },
            "parse_documents_op": {
                "config": {
                    "enable_silver_upload": True,
                    "start_page_id": 0,
                }
            }
        }
    },
    description="PDF 解析作业"
)
def parse_pdf_job():
    """
    PDF 解析作业（解析全部页面）

    完整流程：
    1. 扫描待解析文档（状态为 'crawled'）
    2. 批量解析文档（调用 MinerU 解析器）
    3. 验证解析结果

    默认配置：
    - scan_pending_documents_op:
        - batch_size: 2 (并发解析2个文档)
        - limit: 10 (最多处理10个文档)
    - parse_documents_op:
        - start_page_id: 0
        - enable_silver_upload: True

    如需指定页面范围，请在 Launchpad 中配置 end_page_id：
    ops:
      parse_documents_op:
        config:
          enable_silver_upload: true
          start_page_id: 0
          end_page_id: 4  # 例如：只解析前5页（0-4）
    """
    scan_result = scan_pending_documents_op()
    parse_results = parse_documents_op(scan_result)
    validate_parse_results_op(parse_results)


@job(
    config={
        "ops": {
            "scan_pending_documents_op": {
                "config": {
                    "batch_size": 50,
                    # limit 不设置表示处理全部，doc_type 是可选的，不设置表示所有类型
                }
            },
            "parse_documents_op": {
                "config": {
                    "enable_silver_upload": True,
                    "start_page_id": 0,
                    # 不设置 end_page_id，解析完整文档
                }
            }
        }
    },
    description="PDF 解析作业 - 解析完整文档（所有页）"
)
def parse_pdf_full_job():
    """
    PDF 解析作业（解析完整文档）

    完整流程：
    1. 扫描待解析文档（状态为 'crawled'）
    2. 批量解析文档（调用 MinerU 解析器）
    3. 验证解析结果

    默认配置：
    - scan_pending_documents_op:
        - batch_size: 5 (并发解析5个文档)
        - limit: 100 (最多处理100个文档)
    - parse_documents_op:
        - start_page_id: 0
        - end_page_id: None (解析所有页面)

    ⚠️ 注意：解析完整文档可能需要较长时间
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
