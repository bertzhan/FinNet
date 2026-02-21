#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移脚本：更新 us_listed_companies 表

功能：
1. 检查表是否存在
2. 如果存在，删除 exchange 字段和相关索引
3. 如果不存在，创建完整的表结构

使用方法：
    python scripts/migrate_us_companies_db.py [--drop-and-recreate]

参数：
    --drop-and-recreate: 删除现有表并重新创建（慎用！会丢失所有数据）
"""
import sys
import argparse
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.common.logger import get_logger
from src.storage.metadata.postgres_client import get_postgres_client

logger = get_logger(__name__)


def check_table_exists(session) -> bool:
    """检查 us_listed_companies 表是否存在"""
    result = session.execute(text("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'us_listed_companies'
        );
    """))
    exists = result.scalar()
    return exists


def check_column_exists(session, column_name: str) -> bool:
    """检查字段是否存在"""
    result = session.execute(text("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'us_listed_companies'
            AND column_name = :column_name
        );
    """), {'column_name': column_name})
    exists = result.scalar()
    return exists


def check_index_exists(session, index_name: str) -> bool:
    """检查索引是否存在"""
    result = session.execute(text("""
        SELECT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE indexname = :index_name
        );
    """), {'index_name': index_name})
    exists = result.scalar()
    return exists


def drop_table(session):
    """删除表（慎用）"""
    logger.warning("⚠️  删除表 us_listed_companies（所有数据将丢失）")
    session.execute(text("DROP TABLE IF EXISTS us_listed_companies CASCADE;"))
    session.commit()
    logger.info("✅ 表已删除")


def create_table(session):
    """创建表（使用最新的 schema，不包含 exchange 字段）"""
    logger.info("创建表 us_listed_companies...")

    # 读取 SQL 文件
    sql_file = project_root / "migrations" / "add_us_listed_companies.sql"

    if not sql_file.exists():
        logger.error(f"SQL 文件不存在: {sql_file}")
        return False

    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # 执行 SQL（去除注释行）
    sql_statements = []
    for line in sql_content.split('\n'):
        stripped = line.strip()
        if stripped and not stripped.startswith('--'):
            sql_statements.append(line)

    sql_to_execute = '\n'.join(sql_statements)

    try:
        session.execute(text(sql_to_execute))
        session.commit()
        logger.info("✅ 表创建成功")
        return True
    except Exception as e:
        logger.error(f"❌ 表创建失败: {e}")
        session.rollback()
        return False


def update_existing_table(session):
    """更新现有表（删除 exchange 字段，移除 org_id UNIQUE 约束）"""
    logger.info("更新现有表 us_listed_companies...")

    changes_made = False

    # 1. 删除旧索引
    if check_index_exists(session, 'idx_us_exchange'):
        logger.info("删除索引 idx_us_exchange...")
        session.execute(text("DROP INDEX IF EXISTS idx_us_exchange;"))
        session.commit()
        logger.info("✅ 索引 idx_us_exchange 已删除")
        changes_made = True
    else:
        logger.info("索引 idx_us_exchange 不存在，跳过")

    # 2. 删除 exchange 字段
    if check_column_exists(session, 'exchange'):
        logger.info("删除字段 exchange...")
        session.execute(text("ALTER TABLE us_listed_companies DROP COLUMN exchange;"))
        session.commit()
        logger.info("✅ 字段 exchange 已删除")
        changes_made = True
    else:
        logger.info("字段 exchange 不存在，跳过")

    # 3. 删除 org_id UNIQUE 约束（如果存在）
    logger.info("检查 org_id UNIQUE 约束...")
    result = session.execute(text("""
        SELECT tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
            AND tc.table_schema = ccu.table_schema
        WHERE tc.table_name = 'us_listed_companies'
            AND ccu.column_name IN ('cik', 'org_id')
            AND tc.constraint_type = 'UNIQUE';
    """))
    constraint_row = result.fetchone()

    if constraint_row:
        constraint_name = constraint_row[0]
        logger.info(f"删除 org_id UNIQUE 约束: {constraint_name}...")
        session.execute(text(f"ALTER TABLE us_listed_companies DROP CONSTRAINT {constraint_name};"))
        session.commit()
        logger.info(f"✅ UNIQUE 约束 {constraint_name} 已删除")
        logger.info("   原因：多个证券（stocks, warrants, units）可能共享同一个 org_id")
        changes_made = True
    else:
        logger.info("org_id 字段没有 UNIQUE 约束，跳过")

    # 4. 确保 org_id 索引存在（用于查询性能）
    if not check_index_exists(session, 'idx_us_org_id'):
        logger.info("创建索引 idx_us_org_id...")
        session.execute(text("CREATE INDEX idx_us_org_id ON us_listed_companies(org_id);"))
        session.commit()
        logger.info("✅ 索引 idx_us_org_id 已创建")
        changes_made = True
    else:
        logger.info("索引 idx_us_org_id 已存在")

    if not changes_made:
        logger.info("✅ 表结构已是最新，无需更新")
    else:
        logger.info("✅ 表更新完成")

    return True


def show_table_info(session):
    """显示表结构信息"""
    logger.info("=" * 80)
    logger.info("表结构信息：")
    logger.info("=" * 80)

    # 显示字段
    result = session.execute(text("""
        SELECT
            column_name,
            data_type,
            character_maximum_length,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_name = 'us_listed_companies'
        ORDER BY ordinal_position;
    """))

    logger.info("\n字段列表：")
    for row in result:
        nullable = "NULL" if row[3] == 'YES' else "NOT NULL"
        length = f"({row[2]})" if row[2] else ""
        default = f" DEFAULT {row[4]}" if row[4] else ""
        logger.info(f"  - {row[0]}: {row[1]}{length} {nullable}{default}")

    # 显示索引
    result = session.execute(text("""
        SELECT
            indexname,
            indexdef
        FROM pg_indexes
        WHERE tablename = 'us_listed_companies'
        ORDER BY indexname;
    """))

    logger.info("\n索引列表：")
    for row in result:
        logger.info(f"  - {row[0]}")

    # 显示记录数
    result = session.execute(text(
        "SELECT COUNT(*) FROM us_listed_companies;"
    ))
    count = result.scalar()
    logger.info(f"\n记录数: {count}")
    logger.info("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description='更新 us_listed_companies 表结构'
    )
    parser.add_argument(
        '--drop-and-recreate',
        action='store_true',
        help='删除现有表并重新创建（警告：会丢失所有数据！）'
    )
    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("数据库迁移：us_listed_companies 表")
    logger.info("=" * 80)

    # 获取数据库连接
    pg_client = get_postgres_client()

    try:
        with pg_client.get_session() as session:
            # 检查表是否存在
            table_exists = check_table_exists(session)

            if args.drop_and_recreate:
                # 模式1：删除并重新创建
                logger.warning("⚠️  警告：将删除现有表并重新创建！")
                response = input("确认删除所有数据？(输入 'yes' 确认): ")

                if response.lower() != 'yes':
                    logger.info("操作已取消")
                    return

                if table_exists:
                    drop_table(session)

                success = create_table(session)
                if not success:
                    return

            else:
                # 模式2：增量更新
                if table_exists:
                    logger.info("表 us_listed_companies 已存在")

                    # 检查是否需要更新
                    has_exchange = check_column_exists(session, 'exchange')

                    if has_exchange:
                        logger.info("检测到 exchange 字段，需要更新表结构")
                        response = input("是否继续更新？(输入 'yes' 确认): ")

                        if response.lower() != 'yes':
                            logger.info("操作已取消")
                            return

                        success = update_existing_table(session)
                        if not success:
                            return
                    else:
                        logger.info("✅ 表结构已是最新版本")

                else:
                    logger.info("表 us_listed_companies 不存在，创建新表...")
                    success = create_table(session)
                    if not success:
                        return

            # 显示最终的表结构
            show_table_info(session)

            logger.info("=" * 80)
            logger.info("✅ 数据库迁移完成")
            logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ 迁移失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
