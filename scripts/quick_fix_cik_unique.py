#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速修复：删除 us_listed_companies.cik 的 UNIQUE 约束

这是一个简化的修复脚本，专门用于删除 CIK UNIQUE 约束
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
    logger.info("快速修复：删除 CIK UNIQUE 约束")
    logger.info("=" * 80)

    pg_client = get_postgres_client()

    try:
        with pg_client.get_session() as session:
            # 1. 查找 CIK UNIQUE 约束
            logger.info("查找 CIK UNIQUE 约束...")
            result = session.execute(text("""
                SELECT tc.constraint_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.constraint_column_usage ccu
                    ON tc.constraint_name = ccu.constraint_name
                    AND tc.table_schema = ccu.table_schema
                WHERE tc.table_name = 'us_listed_companies'
                    AND ccu.column_name = 'cik'
                    AND tc.constraint_type = 'UNIQUE';
            """))

            constraint_row = result.fetchone()

            if not constraint_row:
                logger.info("✅ 未发现 CIK UNIQUE 约束，无需修复")
                logger.info("\n表结构已正确配置，可以直接运行同步任务：")
                logger.info("  python src/ingestion/us_stock/jobs/sync_us_companies_job.py")
                return

            constraint_name = constraint_row[0]
            logger.warning(f"⚠️  发现 CIK UNIQUE 约束: {constraint_name}")

            # 2. 删除约束
            logger.info(f"删除约束 {constraint_name}...")
            session.execute(text(f"ALTER TABLE us_listed_companies DROP CONSTRAINT {constraint_name};"))
            session.commit()
            logger.info(f"✅ 约束 {constraint_name} 已删除")

            # 3. 确保索引存在（用于查询性能）
            logger.info("检查 CIK 索引...")
            result = session.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE indexname = 'idx_us_cik'
                );
            """))
            has_index = result.scalar()

            if not has_index:
                logger.info("创建 CIK 索引...")
                session.execute(text("CREATE INDEX idx_us_cik ON us_listed_companies(cik);"))
                session.commit()
                logger.info("✅ 索引 idx_us_cik 已创建")
            else:
                logger.info("✅ 索引 idx_us_cik 已存在")

            # 4. 验证结果
            logger.info("\n验证修复结果...")
            result = session.execute(text("""
                SELECT
                    tc.constraint_name,
                    tc.constraint_type
                FROM information_schema.table_constraints tc
                WHERE tc.table_name = 'us_listed_companies'
                    AND tc.constraint_type = 'UNIQUE'
                ORDER BY tc.constraint_name;
            """))

            remaining_unique = result.fetchall()
            if remaining_unique:
                logger.info("剩余 UNIQUE 约束：")
                for row in remaining_unique:
                    logger.info(f"  - {row[0]} ({row[1]})")
            else:
                logger.info("✅ 无 UNIQUE 约束（除主键外）")

            logger.info("\n" + "=" * 80)
            logger.info("✅ 修复完成！")
            logger.info("=" * 80)
            logger.info("\n现在可以运行同步任务：")
            logger.info("  python src/ingestion/us_stock/jobs/sync_us_companies_job.py")
            logger.info("\n说明：")
            logger.info("  - CIK 是公司级别的标识符")
            logger.info("  - 同一公司可能有多个证券（stock, warrant, unit）")
            logger.info("  - 这些证券共享同一个 CIK，但有不同的 Ticker")
            logger.info("  - 例如：DNMX, DNMXU, DNMXW 共享 CIK 0002081125")

    except Exception as e:
        logger.error(f"❌ 修复失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
