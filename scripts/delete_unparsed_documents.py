#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
删除 Document 表中没有被 parse 的文档

用法:
    python scripts/delete_unparsed_documents.py [--dry-run] [--limit N]

参数:
    --dry-run: 只显示将要删除的文档，不实际删除
    --limit: 限制删除的文档数量
"""

import argparse
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import and_, not_, exists
from src.storage.metadata import get_postgres_client
from src.storage.metadata.models import Document, ParsedDocument
from src.common.logger import get_logger

logger = get_logger(__name__)


def find_unparsed_documents(session, limit=None):
    """
    查找没有被解析的文档

    Args:
        session: 数据库会话
        limit: 限制返回数量

    Returns:
        未解析的文档列表
    """
    # 构建查询：找到在 Document 表中存在，但在 ParsedDocument 表中没有记录的文档
    query = session.query(Document).filter(
        not_(
            exists().where(ParsedDocument.document_id == Document.id)
        )
    ).order_by(Document.created_at)

    if limit:
        query = query.limit(limit)

    return query.all()


def delete_unparsed_documents(dry_run=True, limit=None):
    """
    删除未被解析的文档

    Args:
        dry_run: 如果为 True，只显示将要删除的文档，不实际删除
        limit: 限制删除数量
    """
    pg_client = get_postgres_client()

    with pg_client.get_session() as session:
        # 查找未解析的文档
        logger.info("正在查找未解析的文档...")
        unparsed_docs = find_unparsed_documents(session, limit=limit)

        if not unparsed_docs:
            logger.info("✅ 没有找到未解析的文档")
            return

        logger.info(f"找到 {len(unparsed_docs)} 个未解析的文档")

        # 显示前 10 个文档的信息
        logger.info("\n前 10 个未解析的文档:")
        for i, doc in enumerate(unparsed_docs[:10], 1):
            logger.info(
                f"  {i}. {doc.stock_code} - {doc.company_name} "
                f"({doc.year}Q{doc.quarter if doc.quarter else 'N/A'}) "
                f"- {doc.doc_type} - {doc.minio_object_path}"
            )

        if len(unparsed_docs) > 10:
            logger.info(f"  ... 还有 {len(unparsed_docs) - 10} 个文档")

        if dry_run:
            logger.info("\n🔍 [DRY RUN] 上述文档将被删除（实际未删除）")
            logger.info("如需实际删除，请运行: python scripts/delete_unparsed_documents.py")
            return

        # 确认删除
        logger.warning(f"\n⚠️  即将删除 {len(unparsed_docs)} 个未解析的文档")
        confirm = input("确认删除？(yes/no): ")

        if confirm.lower() != 'yes':
            logger.info("取消删除操作")
            return

        # 执行删除
        deleted_count = 0
        failed_count = 0

        for doc in unparsed_docs:
            try:
                session.delete(doc)
                deleted_count += 1

                if deleted_count % 100 == 0:
                    logger.info(f"已删除 {deleted_count}/{len(unparsed_docs)} 个文档...")
                    session.commit()  # 每 100 个提交一次
            except Exception as e:
                logger.error(f"删除文档失败 {doc.id}: {e}")
                failed_count += 1

        # 最后提交
        try:
            session.commit()
            logger.info(f"\n✅ 删除完成: 成功 {deleted_count} 个，失败 {failed_count} 个")
        except Exception as e:
            logger.error(f"提交事务失败: {e}")
            session.rollback()


def main():
    parser = argparse.ArgumentParser(
        description='删除 Document 表中没有被 parse 的文档'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='只显示将要删除的文档，不实际删除（默认）'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='限制删除的文档数量'
    )

    args = parser.parse_args()

    # 如果没有指定任何参数，默认启用 dry_run
    dry_run = args.dry_run or (args.limit is None)

    logger.info("=" * 60)
    logger.info("删除未解析的文档脚本")
    logger.info("=" * 60)

    if dry_run:
        logger.info("模式: DRY RUN（预览模式，不会实际删除）")
    else:
        logger.info("模式: 实际删除")

    if args.limit:
        logger.info(f"限制: {args.limit} 个文档")

    logger.info("")

    try:
        delete_unparsed_documents(dry_run=dry_run, limit=args.limit)
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
