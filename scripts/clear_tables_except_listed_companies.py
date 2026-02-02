#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清空 PostgreSQL 数据库中除 listed_companies 以外的所有表

⚠️ 警告：此操作将删除除 listed_companies 表外的所有数据，但保留表结构
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text, inspect
from src.common.config import postgres_config
from src.storage.metadata.models import Base
from src.common.logger import get_logger

logger = get_logger(__name__)


def get_all_table_names():
    """获取所有表名（从 SQLAlchemy 模型）"""
    # 从 Base 的元数据中获取所有表名
    table_names = list(Base.metadata.tables.keys())
    return table_names


def clear_tables_except_listed_companies(dry_run=False, skip_confirm=False):
    """
    清空除 listed_companies 以外的所有表的数据
    
    Args:
        dry_run: 如果为 True，只显示将要清空的表，不实际执行
        skip_confirm: 如果为 True，跳过确认提示
    """
    # 创建数据库连接
    engine = create_engine(postgres_config.database_url)

    try:
        # 先获取表信息和记录数（使用只读连接）
        with engine.connect() as read_conn:
            # 获取所有表名
            all_tables = get_all_table_names()
            
            # 排除 listed_companies
            tables_to_clear = [t for t in all_tables if t != 'listed_companies']
            
            if not tables_to_clear:
                print("✅ 没有需要清空的表（只有 listed_companies 表）")
                return
            
            print("=" * 80)
            print("清空数据库表（保留 listed_companies）")
            print("=" * 80)
            print(f"\n找到 {len(all_tables)} 个表，将清空 {len(tables_to_clear)} 个表：")
            print("\n将被清空的表：")
            for table in sorted(tables_to_clear):
                # 获取表记录数
                try:
                    result = read_conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    print(f"  - {table}: {count:,} 条记录")
                except Exception as e:
                    print(f"  - {table}: 无法获取记录数 ({e})")
            
            print("\n保留的表：")
            print(f"  - listed_companies: ", end="")
            try:
                result = read_conn.execute(text("SELECT COUNT(*) FROM listed_companies"))
                count = result.scalar()
                print(f"{count:,} 条记录（将保留）")
            except Exception as e:
                print(f"无法获取记录数 ({e})")
        
        if dry_run:
            print("\n" + "=" * 80)
            print("🔍 DRY RUN 模式 - 不会实际删除数据")
            print("=" * 80)
            return
        
        # 确认操作
        if not skip_confirm:
            print("\n" + "=" * 80)
            print("⚠️  警告：此操作将删除上述表中的所有数据（但保留表结构）")
            print("⚠️  listed_companies 表的数据将被保留")
            print("=" * 80)
            confirm = input("\n确认继续吗？输入 'yes' 继续: ")
            
            if confirm.lower() != 'yes':
                print("操作已取消")
                return
        else:
            print("\n" + "=" * 80)
            print("⚠️  警告：此操作将删除上述表中的所有数据（但保留表结构）")
            print("⚠️  listed_companies 表的数据将被保留")
            print("=" * 80)
        
        # 使用 engine.begin() 自动管理事务
        print("\n开始清空数据...")
        cleared_count = 0
        failed_tables = []
        
        try:
            with engine.begin() as conn:
                # 禁用外键约束（临时）
                conn.execute(text("SET session_replication_role = 'replica';"))
                
                # 按顺序清空表（考虑外键依赖）
                for table in sorted(tables_to_clear):
                    try:
                        print(f"  清空表: {table}...", end=" ")
                        conn.execute(text(f"TRUNCATE TABLE {table} CASCADE;"))
                        cleared_count += 1
                        print("✓")
                    except Exception as e:
                        failed_tables.append((table, str(e)))
                        print(f"✗ 失败: {e}")
                        logger.error(f"清空表 {table} 失败: {e}", exc_info=True)
                
                # 恢复外键约束
                conn.execute(text("SET session_replication_role = 'origin';"))
                
                # engine.begin() 上下文管理器会自动提交事务
        except Exception as e:
            print(f"\n❌ 清空数据失败: {e}")
            logger.error(f"清空数据失败: {e}", exc_info=True)
            raise
        
        print("\n" + "=" * 80)
        print("清空完成！")
        print("=" * 80)
        print(f"成功清空: {cleared_count} 个表")
        if failed_tables:
            print(f"失败: {len(failed_tables)} 个表")
            for table, error in failed_tables:
                print(f"  - {table}: {error}")
        print(f"保留: listed_companies 表")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ 操作失败: {e}")
        logger.error(f"操作失败: {e}", exc_info=True)
        sys.exit(1)
    finally:
        engine.dispose()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="清空 PostgreSQL 数据库中除 listed_companies 以外的所有表",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
⚠️  警告：此操作将删除除 listed_companies 表外的所有数据，但保留表结构

示例:
  # 检查模式（只查看，不删除）
  python scripts/clear_tables_except_listed_companies.py --dry-run
  
  # 实际清空（需要确认）
  python scripts/clear_tables_except_listed_companies.py
  
  # 实际清空（跳过确认）
  python scripts/clear_tables_except_listed_companies.py --yes
        """
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="试运行模式（只查看，不实际删除）"
    )
    
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="跳过确认直接执行"
    )
    
    args = parser.parse_args()
    
    try:
        clear_tables_except_listed_companies(
            dry_run=args.dry_run,
            skip_confirm=args.yes
        )
    except KeyboardInterrupt:
        print("\n\n⚠️  操作已取消")
        sys.exit(1)
    except Exception as e:
        logger.error(f"脚本执行失败: {e}", exc_info=True)
        print(f"\n❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
