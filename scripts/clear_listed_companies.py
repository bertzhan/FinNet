#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
清空 listed_companies 表

删除表中所有数据，但保留表结构
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import ListedCompany
from sqlalchemy import text

def clear_listed_companies(confirm: bool = False):
    """清空 listed_companies 表"""
    pg_client = get_postgres_client()
    
    print("=" * 60)
    print("清空 listed_companies 表")
    print("=" * 60)
    print()
    
    # 检查表是否存在
    with pg_client.get_session() as session:
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'listed_companies'
            );
        """))
        table_exists = result.scalar()
        
        if not table_exists:
            print("❌ listed_companies 表不存在")
            return False
        
        print("✅ listed_companies 表存在")
        
        # 获取当前记录数
        count_result = session.execute(text("SELECT COUNT(*) FROM listed_companies"))
        count = count_result.scalar()
        print(f"   当前记录数: {count} 家")
        print()
        
        if count == 0:
            print("✅ 表已经是空的，无需清空")
            return True
        
        # 确认操作
        if not confirm:
            print("⚠️  警告：此操作将删除表中的所有数据（但保留表结构）")
            response = input("确认继续吗？(yes/no): ").strip().lower()
            
            if response != 'yes':
                print("操作已取消")
                return False
        
        # 检查是否有锁或正在运行的查询
        print("\n检查表状态...")
        try:
            with pg_client.get_session() as session:
                # 检查是否有其他连接正在使用这个表
                lock_result = session.execute(text("""
                    SELECT 
                        pid,
                        usename,
                        application_name,
                        state,
                        query_start,
                        now() - query_start as duration,
                        query
                    FROM pg_stat_activity
                    WHERE state != 'idle'
                      AND query LIKE '%listed_companies%'
                      AND pid != pg_backend_pid();
                """))
                locks = lock_result.fetchall()
                
                if locks:
                    print("⚠️  发现其他连接正在使用 listed_companies 表：")
                    for lock in locks:
                        print(f"   PID: {lock[0]}, 用户: {lock[1]}, 状态: {lock[3]}, 持续时间: {lock[5]}")
                        print(f"   查询: {lock[6][:100]}...")
                    print("\n   建议：先关闭这些连接，或使用 DELETE 方式清空（较慢但不会卡住）")
                    
                    if not confirm:
                        response = input("\n是否继续使用 DELETE 方式清空？(yes/no): ").strip().lower()
                        if response != 'yes':
                            print("操作已取消")
                            return False
                    use_delete = True
                else:
                    print("✅ 表未被锁定，可以使用 TRUNCATE")
                    use_delete = False
        except Exception as e:
            print(f"⚠️  检查锁状态失败: {e}")
            print("   将使用 DELETE 方式清空（较慢但更安全）")
            use_delete = True
        
        # 清空表
        print("\n开始清空表...")
        try:
            with pg_client.get_session() as session:
                if use_delete:
                    # 使用 DELETE（较慢但不会因为锁而卡住）
                    print("   使用 DELETE 方式清空（可能需要一些时间）...")
                    result = session.execute(text("DELETE FROM listed_companies;"))
                    deleted_count = result.rowcount
                    session.commit()
                    print(f"   ✅ 已删除 {deleted_count} 条记录")
                else:
                    # 使用 TRUNCATE（快速但需要排他锁）
                    print("   使用 TRUNCATE 方式清空...")
                    # 设置语句超时（30秒）
                    session.execute(text("SET statement_timeout = '30s';"))
                    try:
                        session.execute(text("TRUNCATE TABLE listed_companies RESTART IDENTITY CASCADE;"))
                        session.commit()
                        print("   ✅ TRUNCATE 完成")
                    except Exception as truncate_error:
                        if "timeout" in str(truncate_error).lower() or "lock" in str(truncate_error).lower():
                            print("   ⚠️  TRUNCATE 超时或被锁定，改用 DELETE 方式...")
                            session.rollback()
                            session.execute(text("SET statement_timeout = '0';"))  # 取消超时
                            result = session.execute(text("DELETE FROM listed_companies;"))
                            deleted_count = result.rowcount
                            session.commit()
                            print(f"   ✅ 已删除 {deleted_count} 条记录")
                        else:
                            raise
            
            print("✅ 表已清空")
            
            # 验证
            with pg_client.get_session() as session:
                count_result = session.execute(text("SELECT COUNT(*) FROM listed_companies"))
                new_count = count_result.scalar()
                print(f"   当前记录数: {new_count} 家")
            
            return True
            
        except Exception as e:
            print(f"❌ 清空表失败: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="清空 listed_companies 表")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="跳过确认提示（谨慎使用）"
    )
    
    args = parser.parse_args()
    
    try:
        success = clear_listed_companies(confirm=args.confirm)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n操作已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 操作失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
