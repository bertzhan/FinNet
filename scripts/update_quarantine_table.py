#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新 quarantine_records 表结构
执行数据库迁移以支持完整的隔离管理功能
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.storage.metadata.postgres_client import get_postgres_client
from src.common.logger import get_logger

logger = get_logger(__name__)


def main():
    """执行数据库迁移"""
    logger.info("=" * 80)
    logger.info("开始更新 quarantine_records 表结构")
    logger.info("=" * 80)

    # 读取 SQL 脚本
    sql_file = project_root / "scripts" / "update_quarantine_table.sql"
    if not sql_file.exists():
        logger.error(f"SQL 文件不存在: {sql_file}")
        sys.exit(1)

    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_script = f.read()

    logger.info(f"读取 SQL 脚本: {sql_file}")

    # 执行迁移
    pg_client = get_postgres_client()

    try:
        with pg_client.get_session() as session:
            logger.info("开始执行数据库迁移...")

            # 分割 SQL 语句并执行
            statements = [s.strip() for s in sql_script.split(';') if s.strip() and not s.strip().startswith('--')]

            for i, statement in enumerate(statements, 1):
                if statement:
                    try:
                        logger.debug(f"执行语句 {i}/{len(statements)}: {statement[:100]}...")
                        session.execute(text(statement))
                        logger.debug(f"✅ 语句 {i} 执行成功")
                    except Exception as e:
                        # 某些语句可能失败（如字段已存在），继续执行
                        logger.warning(f"⚠️ 语句 {i} 执行失败（可能已存在）: {e}")

            session.commit()
            logger.info("✅ 数据库迁移执行成功")

    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {e}", exc_info=True)
        sys.exit(1)

    logger.info("=" * 80)
    logger.info("quarantine_records 表结构更新完成")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
