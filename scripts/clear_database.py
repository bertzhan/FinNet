#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清空 PostgreSQL 数据库的所有数据
注意：这将删除所有表中的数据，但保留表结构
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text, inspect
from src.common.config import postgres_config


def clear_all_tables(skip_confirm=False):
    """清空所有表的数据"""
    # 创建数据库连接
    engine = create_engine(postgres_config.database_url)

    try:
        with engine.connect() as conn:
            # 开始事务
            trans = conn.begin()

            try:
                # 获取所有表名
                inspector = inspect(engine)
                tables = inspector.get_table_names()

                if not tables:
                    print("数据库中没有表")
                    return

                print(f"找到 {len(tables)} 个表")
                print("准备清空以下表的数据:")
                for table in tables:
                    print(f"  - {table}")

                # 确认操作
                if not skip_confirm:
                    print("\n⚠️  警告：此操作将删除所有表中的数据（但保留表结构）")
                    confirm = input("确认继续吗？(yes/no): ")

                    if confirm.lower() != 'yes':
                        print("操作已取消")
                        return
                else:
                    print("\n⚠️  警告：此操作将删除所有表中的数据（但保留表结构）")

                print("\n开始清空数据...")

                # 禁用外键约束
                conn.execute(text("SET session_replication_role = 'replica';"))

                # 清空每个表
                for table in tables:
                    print(f"清空表: {table}")
                    conn.execute(text(f"TRUNCATE TABLE {table} CASCADE;"))

                # 恢复外键约束
                conn.execute(text("SET session_replication_role = 'origin';"))

                # 提交事务
                trans.commit()

                print("\n✅ 所有表的数据已成功清空")

            except Exception as e:
                # 回滚事务
                trans.rollback()
                print(f"\n❌ 清空数据失败: {e}")
                raise

    except Exception as e:
        print(f"数据库连接失败: {e}")
        sys.exit(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="清空 PostgreSQL 数据库的所有数据")
    parser.add_argument("-y", "--yes", action="store_true", help="跳过确认直接执行")
    args = parser.parse_args()

    clear_all_tables(skip_confirm=args.yes)
