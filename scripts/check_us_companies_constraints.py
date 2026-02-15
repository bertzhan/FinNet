#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 us_listed_companies 表的约束和索引

用于诊断 CIK UNIQUE 约束问题
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.common.logger import get_logger
from src.storage.metadata.postgres_client import get_postgres_client

logger = get_logger(__name__)


def main():
    logger.info("=" * 80)
    logger.info("检查 us_listed_companies 表约束")
    logger.info("=" * 80)

    pg_client = get_postgres_client()

    try:
        with pg_client.get_session() as session:
            # 1. 检查表是否存在
            logger.info("\n1. 检查表是否存在...")
            result = session.execute(text("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_name = 'us_listed_companies'
                );
            """))
            exists = result.scalar()

            if not exists:
                logger.error("❌ 表 us_listed_companies 不存在")
                return

            logger.info("✅ 表存在")

            # 2. 检查所有约束
            logger.info("\n2. 检查所有约束...")
            result = session.execute(text("""
                SELECT
                    tc.constraint_name,
                    tc.constraint_type,
                    STRING_AGG(ccu.column_name, ', ') as columns
                FROM information_schema.table_constraints tc
                JOIN information_schema.constraint_column_usage ccu
                    ON tc.constraint_name = ccu.constraint_name
                    AND tc.table_schema = ccu.table_schema
                WHERE tc.table_name = 'us_listed_companies'
                GROUP BY tc.constraint_name, tc.constraint_type
                ORDER BY tc.constraint_type, tc.constraint_name;
            """))

            constraints = result.fetchall()
            if constraints:
                logger.info("发现以下约束：")
                for row in constraints:
                    constraint_name, constraint_type, columns = row
                    logger.info(f"  - {constraint_type:20s} | {constraint_name:40s} | {columns}")

                    # 高亮显示 CIK UNIQUE 约束
                    if constraint_type == 'UNIQUE' and 'cik' in columns:
                        logger.warning(f"    ⚠️  发现 CIK UNIQUE 约束：{constraint_name}")
                        logger.warning(f"    需要删除此约束！")
            else:
                logger.info("未发现约束（除了主键）")

            # 3. 检查所有索引
            logger.info("\n3. 检查所有索引...")
            result = session.execute(text("""
                SELECT
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE tablename = 'us_listed_companies'
                ORDER BY indexname;
            """))

            indexes = result.fetchall()
            if indexes:
                logger.info("发现以下索引：")
                for row in indexes:
                    indexname, indexdef = row
                    logger.info(f"  - {indexname}")
                    logger.info(f"    {indexdef}")
            else:
                logger.info("未发现索引")

            # 4. 检查字段
            logger.info("\n4. 检查字段...")
            result = session.execute(text("""
                SELECT
                    column_name,
                    data_type,
                    character_maximum_length,
                    is_nullable
                FROM information_schema.columns
                WHERE table_name = 'us_listed_companies'
                ORDER BY ordinal_position;
            """))

            columns_info = result.fetchall()
            logger.info("字段列表：")
            for row in columns_info:
                col_name, data_type, max_length, is_nullable = row
                nullable = "NULL" if is_nullable == 'YES' else "NOT NULL"
                length = f"({max_length})" if max_length else ""
                logger.info(f"  - {col_name:20s} {data_type}{length:15s} {nullable}")

            # 5. 查询示例数据（检查是否有重复 CIK）
            logger.info("\n5. 检查重复 CIK...")
            result = session.execute(text("""
                SELECT
                    cik,
                    COUNT(*) as count,
                    STRING_AGG(code, ', ' ORDER BY code) as tickers
                FROM us_listed_companies
                GROUP BY cik
                HAVING COUNT(*) > 1
                ORDER BY count DESC
                LIMIT 10;
            """))

            duplicates = result.fetchall()
            if duplicates:
                logger.info("发现重复 CIK（这是正常的，多个证券共享 CIK）：")
                for row in duplicates:
                    cik, count, tickers = row
                    logger.info(f"  - CIK {cik}: {count} 个证券 ({tickers})")
            else:
                logger.info("未发现重复 CIK")

            # 6. 统计
            logger.info("\n6. 表统计...")
            result = session.execute(text("SELECT COUNT(*) FROM us_listed_companies;"))
            total_count = result.scalar()
            logger.info(f"总记录数: {total_count}")

            result = session.execute(text("SELECT COUNT(DISTINCT cik) FROM us_listed_companies;"))
            unique_cik_count = result.scalar()
            logger.info(f"唯一 CIK 数: {unique_cik_count}")

            if total_count > unique_cik_count:
                logger.info(f"平均每个公司有 {total_count / unique_cik_count:.2f} 个证券")

            # 7. 诊断建议
            logger.info("\n" + "=" * 80)
            logger.info("诊断建议：")
            logger.info("=" * 80)

            has_cik_unique = any(
                row[1] == 'UNIQUE' and 'cik' in row[2]
                for row in constraints
            )

            if has_cik_unique:
                logger.warning("❌ 发现 CIK UNIQUE 约束，需要删除！")
                logger.info("\n请执行以下命令修复：")
                logger.info("  python scripts/migrate_us_companies_db.py")
                logger.info("\n或手动执行 SQL：")
                cik_constraint_name = next(
                    row[0] for row in constraints
                    if row[1] == 'UNIQUE' and 'cik' in row[2]
                )
                logger.info(f"  ALTER TABLE us_listed_companies DROP CONSTRAINT {cik_constraint_name};")
            else:
                logger.info("✅ 未发现 CIK UNIQUE 约束，表结构正确")

    except Exception as e:
        logger.error(f"❌ 检查失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
