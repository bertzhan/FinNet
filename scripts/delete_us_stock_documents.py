#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
删除 documents 表中的 us_stock 文档

用法:
    python scripts/delete_us_stock_documents.py [--dry-run] [--limit N] [--yes] [--delete-minio]

参数:
    --dry-run: 只显示将要删除的文档，不实际删除（默认）
    --limit: 限制删除的文档数量
    --yes: 跳过确认，直接执行删除（非交互模式）
    --delete-minio: 同时删除 MinIO 中的文件
"""

import argparse
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.storage.metadata import get_postgres_client
from src.storage.metadata.models import Document
from src.common.constants import Market
from src.common.logger import get_logger

logger = get_logger(__name__)


def find_us_stock_documents(session, limit=None):
    """
    查找 market='us_stock' 的文档

    Args:
        session: 数据库会话
        limit: 限制返回数量

    Returns:
        us_stock 文档列表
    """
    query = session.query(Document).filter(
        Document.market == Market.US_STOCK.value
    ).order_by(Document.created_at)

    if limit:
        query = query.limit(limit)

    return query.all()


def delete_us_stock_documents(
    dry_run: bool = True,
    limit: int = None,
    skip_confirm: bool = False,
    delete_minio: bool = False,
):
    """
    删除 us_stock 文档

    Args:
        dry_run: 如果为 True，只显示将要删除的文档，不实际删除
        limit: 限制删除数量
        skip_confirm: 跳过确认提示
        delete_minio: 是否同时删除 MinIO 中的文件
    """
    pg_client = get_postgres_client()

    with pg_client.get_session() as session:
        logger.info("正在查找 us_stock 文档...")
        docs = find_us_stock_documents(session, limit=limit)

        if not docs:
            logger.info("✅ 没有找到 us_stock 文档")
            return

        logger.info(f"找到 {len(docs)} 个 us_stock 文档")

        # 显示前 10 个文档的信息
        logger.info("\n前 10 个 us_stock 文档:")
        for i, doc in enumerate(docs[:10], 1):
            logger.info(
                f"  {i}. {doc.stock_code} - {doc.company_name} "
                f"({doc.year}Q{doc.quarter if doc.quarter else 'N/A'}) "
                f"- {doc.doc_type} - {doc.minio_object_path}"
            )

        if len(docs) > 10:
            logger.info(f"  ... 还有 {len(docs) - 10} 个文档")

        if dry_run:
            logger.info("\n🔍 [DRY RUN] 上述文档将被删除（实际未删除）")
            logger.info("如需实际删除，请运行: python scripts/delete_us_stock_documents.py --yes")
            return

        # 确认删除
        if not skip_confirm:
            logger.warning(f"\n⚠️  即将删除 {len(docs)} 个 us_stock 文档")
            confirm = input("确认删除？(yes/no): ")

            if confirm.lower() != "yes":
                logger.info("取消删除操作")
                return

        # 可选：MinIO 客户端（用于删除文件）
        minio_client = None
        if delete_minio:
            try:
                from src.storage.object_store.minio_client import MinIOClient

                minio_client = MinIOClient()
            except Exception as e:
                logger.warning(f"MinIO 客户端初始化失败，将只删除数据库记录: {e}")

        # 执行删除
        deleted_count = 0
        failed_count = 0

        for doc in docs:
            try:
                # 1. 删除 MinIO 文件（如果启用）
                if delete_minio and minio_client and doc.minio_object_path:
                    try:
                        if minio_client.file_exists(doc.minio_object_path):
                            minio_client.delete_file(doc.minio_object_path)
                            logger.debug(f"已删除 MinIO 文件: {doc.minio_object_path}")
                    except Exception as e:
                        logger.warning(f"删除 MinIO 文件失败 {doc.minio_object_path}: {e}")

                # 2. 删除数据库记录（CASCADE 会自动删除 parse_tasks, parsed_documents, document_chunks 等）
                session.delete(doc)
                deleted_count += 1

                if deleted_count % 100 == 0:
                    logger.info(f"已删除 {deleted_count}/{len(docs)} 个文档...")
                    session.commit()
            except Exception as e:
                logger.error(f"删除文档失败 {doc.id}: {e}")
                failed_count += 1

        try:
            session.commit()
            logger.info(
                f"\n✅ 删除完成: 成功 {deleted_count} 个，失败 {failed_count} 个"
            )
        except Exception as e:
            logger.error(f"提交事务失败: {e}")
            session.rollback()


def main():
    parser = argparse.ArgumentParser(
        description="删除 documents 表中的 us_stock 文档"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只显示将要删除的文档，不实际删除（默认）",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="跳过确认，直接执行删除",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="限制删除的文档数量",
    )
    parser.add_argument(
        "--delete-minio",
        action="store_true",
        help="同时删除 MinIO 中的文件",
    )

    args = parser.parse_args()

    # --dry-run 或未指定 --yes 时为预览模式；--yes 时实际删除
    dry_run = args.dry_run or (not args.yes)

    logger.info("=" * 60)
    logger.info("删除 us_stock 文档脚本")
    logger.info("=" * 60)

    if dry_run:
        logger.info("模式: DRY RUN（预览模式，不会实际删除）")
    else:
        logger.info("模式: 实际删除")

    if args.limit:
        logger.info(f"限制: {args.limit} 个文档")

    if args.delete_minio:
        logger.info("同时删除 MinIO 文件: 是")

    logger.info("")

    try:
        delete_us_stock_documents(
            dry_run=dry_run,
            limit=args.limit,
            skip_confirm=args.yes,
            delete_minio=args.delete_minio,
        )
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
