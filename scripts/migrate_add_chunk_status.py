#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移脚本：为 DocumentChunk 添加 status 字段和失败追踪机制

变更内容：
1. 添加 status 字段（VARCHAR(50)，默认 'pending'）
2. 添加 vectorization_error 字段（TEXT，可空）
3. 添加 vectorization_retry_count 字段（INTEGER，默认 0）
4. 创建 idx_chunk_status 索引
5. 初始化现有数据的 status（已向量化的设为 'vectorized'）

使用方法：
  # 试运行（默认）
  python scripts/migrate_add_chunk_status.py

  # 实际执行
  python scripts/migrate_add_chunk_status.py --force
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.common.logger import get_logger
from sqlalchemy import text

logger = get_logger(__name__)


def check_migration_status(session):
    """检查迁移状态"""
    logger.info("=" * 80)
    logger.info("检查 document_chunks 表迁移状态")
    logger.info("=" * 80)

    # 检查表是否存在
    result = session.execute(text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name = 'document_chunks'
    """)).fetchone()

    if not result:
        logger.error("❌ document_chunks 表不存在")
        return False, None

    logger.info("✓ document_chunks 表存在")

    # 检查字段是否已存在
    columns = session.execute(text("""
        SELECT column_name, data_type, column_default
        FROM information_schema.columns
        WHERE table_name = 'document_chunks'
        AND column_name IN ('status', 'vectorization_error', 'vectorization_retry_count')
        ORDER BY column_name
    """)).fetchall()

    existing_columns = {col[0] for col in columns}

    logger.info(f"\n现有字段:")
    for col in columns:
        logger.info(f"  {col[0]}: {col[1]} (默认值: {col[2]})")

    # 检查索引是否已存在
    index_exists = session.execute(text("""
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'document_chunks'
        AND indexname = 'idx_chunk_status'
    """)).fetchone()

    logger.info(f"\nidx_chunk_status 索引: {'存在' if index_exists else '不存在'}")

    # 统计当前数据状态
    result = session.execute(text("""
        SELECT
            COUNT(*) as total,
            COUNT(vectorized_at) as has_vectorized_at
        FROM document_chunks
    """)).fetchone()

    total_chunks = result[0] if result else 0
    vectorized_chunks = result[1] if result else 0

    logger.info(f"\n当前数据状态:")
    logger.info(f"  总分块数: {total_chunks:,}")
    logger.info(f"  已向量化: {vectorized_chunks:,} (vectorized_at IS NOT NULL)")
    logger.info(f"  待向量化: {total_chunks - vectorized_chunks:,}")

    # 判断是否需要迁移
    needs_migration = (
        'status' not in existing_columns or
        'vectorization_error' not in existing_columns or
        'vectorization_retry_count' not in existing_columns or
        not index_exists
    )

    return True, {
        'needs_migration': needs_migration,
        'has_status': 'status' in existing_columns,
        'has_error': 'vectorization_error' in existing_columns,
        'has_retry': 'vectorization_retry_count' in existing_columns,
        'has_index': bool(index_exists),
        'total_chunks': total_chunks,
        'vectorized_chunks': vectorized_chunks,
    }


def migrate_add_fields(session, dry_run=True):
    """添加新字段"""
    logger.info("=" * 80)
    logger.info("步骤 1: 添加新字段")
    logger.info("=" * 80)

    fields_to_add = [
        ('status', "VARCHAR(50) DEFAULT 'pending'", "向量化状态"),
        ('vectorization_error', "TEXT", "向量化失败原因"),
        ('vectorization_retry_count', "INTEGER DEFAULT 0", "向量化重试次数"),
    ]

    for field_name, field_def, field_desc in fields_to_add:
        # 检查字段是否已存在
        result = session.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'document_chunks'
            AND column_name = :field_name
        """), {"field_name": field_name}).fetchone()

        if result:
            logger.info(f"⏭️  字段 {field_name} 已存在，跳过")
            continue

        if dry_run:
            logger.info(f"🔍 DRY RUN: 将添加字段 {field_name} ({field_desc})")
            logger.info(f"   SQL: ALTER TABLE document_chunks ADD COLUMN {field_name} {field_def}")
        else:
            logger.info(f"正在添加字段 {field_name} ({field_desc})...")
            try:
                session.execute(text(f"""
                    ALTER TABLE document_chunks
                    ADD COLUMN IF NOT EXISTS {field_name} {field_def}
                """))
                session.commit()
                logger.info(f"✓ 字段 {field_name} 添加成功")
            except Exception as e:
                logger.error(f"❌ 添加字段 {field_name} 失败: {e}")
                session.rollback()
                return False

    return True


def migrate_create_index(session, dry_run=True):
    """创建索引"""
    logger.info("=" * 80)
    logger.info("步骤 2: 创建索引")
    logger.info("=" * 80)

    # 检查索引是否已存在
    result = session.execute(text("""
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'document_chunks'
        AND indexname = 'idx_chunk_status'
    """)).fetchone()

    if result:
        logger.info("⏭️  idx_chunk_status 索引已存在，跳过")
        return True

    if dry_run:
        logger.info("🔍 DRY RUN: 将创建索引 idx_chunk_status")
        logger.info("   SQL: CREATE INDEX idx_chunk_status ON document_chunks(status)")
    else:
        logger.info("正在创建索引 idx_chunk_status...")
        try:
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_chunk_status
                ON document_chunks(status)
            """))
            session.commit()
            logger.info("✓ 索引 idx_chunk_status 创建成功")
        except Exception as e:
            logger.error(f"❌ 创建索引失败: {e}")
            session.rollback()
            return False

    return True


def migrate_initialize_data(session, dry_run=True):
    """初始化现有数据的 status"""
    logger.info("=" * 80)
    logger.info("步骤 3: 初始化现有数据")
    logger.info("=" * 80)

    # 检查 status 字段是否存在
    result = session.execute(text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'document_chunks'
        AND column_name = 'status'
    """)).fetchone()

    if not result:
        if dry_run:
            # 在 dry-run 模式下，估算需要更新的数据
            result = session.execute(text("""
                SELECT COUNT(*)
                FROM document_chunks
                WHERE vectorized_at IS NOT NULL
            """)).fetchone()
            need_update = result[0] if result else 0
            logger.info(f"🔍 DRY RUN: 将更新 {need_update:,} 条记录")
            logger.info("   将已向量化的记录 (vectorized_at IS NOT NULL) 的 status 设为 'vectorized'")
            return True
        else:
            logger.error("❌ status 字段不存在，请先执行步骤 1")
            return False

    # 统计需要初始化的数据
    result = session.execute(text("""
        SELECT COUNT(*)
        FROM document_chunks
        WHERE vectorized_at IS NOT NULL
        AND (status IS NULL OR status = 'pending')
    """)).fetchone()

    need_update = result[0] if result else 0

    if need_update == 0:
        logger.info("⏭️  所有数据已正确初始化，跳过")
        return True

    if dry_run:
        logger.info(f"🔍 DRY RUN: 将更新 {need_update:,} 条记录")
        logger.info("   将已向量化的记录 (vectorized_at IS NOT NULL) 的 status 设为 'vectorized'")
    else:
        logger.info(f"正在初始化 {need_update:,} 条记录...")
        try:
            session.execute(text("""
                UPDATE document_chunks
                SET status = 'vectorized'
                WHERE vectorized_at IS NOT NULL
                AND (status IS NULL OR status = 'pending')
            """))
            session.commit()
            logger.info(f"✓ 成功更新 {need_update:,} 条记录")
        except Exception as e:
            logger.error(f"❌ 初始化数据失败: {e}")
            session.rollback()
            return False

    return True


def verify_migration(session):
    """验证迁移结果"""
    logger.info("=" * 80)
    logger.info("验证迁移结果")
    logger.info("=" * 80)

    # 检查字段
    columns = session.execute(text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'document_chunks'
        AND column_name IN ('status', 'vectorization_error', 'vectorization_retry_count')
        ORDER BY column_name
    """)).fetchall()

    logger.info(f"\n字段检查:")
    for col in columns:
        logger.info(f"  ✓ {col[0]}")

    # 检查索引
    index = session.execute(text("""
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'document_chunks'
        AND indexname = 'idx_chunk_status'
    """)).fetchone()

    logger.info(f"\n索引检查:")
    if index:
        logger.info(f"  ✓ idx_chunk_status")
    else:
        logger.warning(f"  ⚠️  idx_chunk_status 不存在")

    # 统计数据分布
    result = session.execute(text("""
        SELECT
            status,
            COUNT(*) as count
        FROM document_chunks
        GROUP BY status
        ORDER BY status
    """)).fetchall()

    logger.info(f"\n数据分布:")
    total = 0
    for status, count in result:
        logger.info(f"  {status or 'NULL'}: {count:,}")
        total += count
    logger.info(f"  总计: {total:,}")

    # 检查数据一致性
    result = session.execute(text("""
        SELECT COUNT(*)
        FROM document_chunks
        WHERE vectorized_at IS NOT NULL
        AND status != 'vectorized'
    """)).fetchone()

    inconsistent = result[0] if result else 0
    if inconsistent > 0:
        logger.warning(f"\n⚠️  数据不一致: {inconsistent:,} 条记录 vectorized_at 不为空但 status 不是 'vectorized'")
    else:
        logger.info(f"\n✓ 数据一致性检查通过")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="为 document_chunks 添加 status 字段的数据库迁移工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 试运行（默认）- 只检查不执行
  python scripts/migrate_add_chunk_status.py

  # 实际执行迁移
  python scripts/migrate_add_chunk_status.py --force
        """
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="试运行模式（不实际执行，默认启用）"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制执行迁移（禁用试运行）"
    )

    args = parser.parse_args()

    dry_run = not args.force

    try:
        logger.info("=" * 80)
        logger.info("DocumentChunk Status 字段迁移工具")
        logger.info("=" * 80)
        logger.info(f"模式: {'🔍 DRY RUN (试运行)' if dry_run else '▶️  实际执行'}")
        logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)
        logger.info("")

        pg_client = get_postgres_client()

        with pg_client.get_session() as session:
            # 检查迁移状态
            table_exists, status = check_migration_status(session)

            if not table_exists:
                return 1

            if not status['needs_migration']:
                logger.info("")
                logger.info("=" * 80)
                logger.info("✓ 所有迁移已完成，无需执行")
                logger.info("=" * 80)
                return 0

            logger.info("")

            # 执行迁移步骤
            # 1. 添加字段
            if not migrate_add_fields(session, dry_run=dry_run):
                return 1
            logger.info("")

            # 2. 创建索引
            if not migrate_create_index(session, dry_run=dry_run):
                return 1
            logger.info("")

            # 3. 初始化数据
            if not migrate_initialize_data(session, dry_run=dry_run):
                return 1
            logger.info("")

            # 4. 验证
            if not dry_run:
                verify_migration(session)

        # 输出总结
        logger.info("")
        logger.info("=" * 80)

        if dry_run:
            logger.info("💡 试运行完成 - 没有实际执行迁移")
            logger.info("")
            logger.info("要执行实际迁移，请运行:")
            logger.info("  python scripts/migrate_add_chunk_status.py --force")
            logger.info("")
            logger.info("迁移内容:")
            logger.info("  1. 添加 status 字段 (VARCHAR(50), 默认 'pending')")
            logger.info("  2. 添加 vectorization_error 字段 (TEXT)")
            logger.info("  3. 添加 vectorization_retry_count 字段 (INTEGER, 默认 0)")
            logger.info("  4. 创建 idx_chunk_status 索引")
            logger.info("  5. 初始化现有数据状态")
        else:
            logger.info("✅ 迁移成功完成！")
            logger.info("")
            logger.info("后续步骤:")
            logger.info("  1. 重启应用服务以使用新字段")
            logger.info("  2. 运行 vectorize_chunks_job 会自动重试失败的分块")
            logger.info("  3. 查询失败分块:")
            logger.info("     SELECT * FROM document_chunks WHERE status = 'failed'")

        logger.info("=" * 80)

        return 0

    except KeyboardInterrupt:
        logger.warning("\n\n⚠️  操作已被用户中断")
        return 1
    except Exception as e:
        logger.error(f"\n\n❌ 迁移失败: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
