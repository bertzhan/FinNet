# -*- coding: utf-8 -*-
"""
共享爬取结果验证逻辑
供 A股、港股等 crawl jobs 使用

validate_crawl_results_op: 数据质量检查、隔离失败文档
source_type 从 crawl_results 中读取，支持 hs_stock、hk_stock
"""

from typing import Dict

from dagster import op, get_dagster_logger, AssetMaterialization, MetadataValue

from src.storage.metadata.quarantine_manager import QuarantineManager
from src.common.constants import Market, DocType


# source_type -> Market 映射（用于 create_document 的 market 参数）
SOURCE_TYPE_TO_MARKET = {
    "hs_stock": Market.HS,
    "hk_stock": Market.HK_STOCK,
}


def _doc_type_str_to_enum(doc_type: str) -> DocType:
    """将 doc_type 字符串转换为 DocType 枚举"""
    mapping = {
        "quarterly_report": DocType.QUARTERLY_REPORT,
        "annual_report": DocType.ANNUAL_REPORT,
        "interim_report": DocType.INTERIM_REPORT,
        "ipo_prospectus": DocType.IPO_PROSPECTUS,
    }
    return mapping.get(doc_type, DocType.QUARTERLY_REPORT)


@op
def validate_crawl_results_op(context, crawl_results: Dict) -> Dict:
    """
    验证爬取结果（数据质量检查）

    按照 plan.md 7.1 全链路验证架构：
    - 文件完整性检查
    - 数据量检查
    - 元数据完整性检查

    source_type 从 crawl_results 读取（hs_stock / hk_stock），用于隔离和数据库记录
    """
    logger = get_dagster_logger()

    if not crawl_results.get("success"):
        logger.warning("爬取失败，跳过验证")
        return {
            "validated": False,
            "reason": "爬取失败",
            "validated_count": 0,
            "failed_count": 0,
        }

    results = crawl_results.get("results", [])
    source_type = crawl_results.get("source_type", "hs_stock")
    market = SOURCE_TYPE_TO_MARKET.get(source_type, Market.HS)

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
                "reason": reason,
            })
            failed_count += 1

            # 如果文件已上传但爬取失败，隔离文件
            if quarantine_manager and minio_path and doc_id:
                try:
                    quarantine_manager.quarantine_document(
                        document_id=doc_id,
                        source_type=source_type,
                        doc_type=doc_type,
                        original_path=minio_path,
                        failure_stage="ingestion_failed",
                        failure_reason=reason,
                        failure_details=error_msg,
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
                "reason": reason,
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
                            doc_type_enum = _doc_type_str_to_enum(doc_type)
                            doc = crud.create_document(
                                session=session,
                                stock_code=stock_code,
                                company_name=company_name,
                                market=market.value,
                                doc_type=doc_type_enum.value,
                                year=year,
                                quarter=quarter,
                                minio_object_path=minio_path,
                                file_size=None,
                                file_hash=None,
                                metadata=None,
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
                    "reason": reason,
                })
                failed_count += 1

                # 隔离文件（如果已上传到MinIO）
                if quarantine_manager and minio_path:
                    try:
                        quarantine_manager.quarantine_document(
                            document_id=None,
                            source_type=source_type,
                            doc_type=doc_type,
                            original_path=minio_path,
                            failure_stage="validation_failed",
                            failure_reason=reason,
                            failure_details="文档记录未成功创建到数据库，且重新创建失败",
                        )
                        quarantined_count += 1
                        logger.info(f"✅ 已隔离缺少数据库ID的文档: {minio_path}")
                    except Exception as e:
                        logger.error(f"❌ 隔离失败: {e}")
                continue

            # 重新创建成功，继续验证流程
            logger.info(f"✅ 数据库记录已恢复: {stock_code}, document_id={doc_id}")

        # 验证通过
        passed_results.append({
            "stock_code": stock_code,
            "company_name": company_name,
            "year": year,
            "quarter": quarter,
            "minio_path": minio_path,
            "document_id": doc_id,
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
            },
        )
    )

    return {
        "validated": True,
        "total": total,
        "passed": validated_count,
        "failed": failed_count,
        "quarantined": quarantined_count,
        "success_rate": success_rate,
        "passed_results": passed_results[:10],
        "failed_results": failed_results[:10],
    }
