#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复数据库：删除孤立索引并重新创建表
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.storage.metadata.postgres_client import get_postgres_client
from sqlalchemy import text
from src.common.logger import get_logger

logger = get_logger(__name__)


def fix_database():
    """修复数据库：删除孤立索引并创建表"""
    print("=" * 60)
    print("数据库修复")
    print("=" * 60)
    
    try:
        pg_client = get_postgres_client()
        
        # 测试连接
        print("\n1️⃣ 测试数据库连接...")
        if pg_client.test_connection():
            print("   ✅ 数据库连接成功")
        else:
            print("   ❌ 数据库连接失败")
            return False
        
        # 检查并删除孤立的索引
        print("\n2️⃣ 检查孤立索引...")
        with pg_client.engine.connect() as conn:
            # 查找可能存在的孤立索引
            result = conn.execute(text("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE schemaname = 'public' 
                AND indexname = 'idx_status_created'
            """))
            indexes = [r[0] for r in result]
            
            if indexes:
                print(f"   发现孤立索引: {indexes}")
                try:
                    conn.execute(text("DROP INDEX IF EXISTS idx_status_created"))
                    conn.commit()
                    print("   ✅ 已删除孤立索引")
                except Exception as e:
                    print(f"   ⚠️  删除索引失败（可能已不存在）: {e}")
                    conn.rollback()
            else:
                print("   ✅ 没有发现孤立索引")
        
        # 创建表
        print("\n3️⃣ 创建数据库表...")
        try:
            pg_client.create_tables(checkfirst=True)
            print("   ✅ 数据库表创建成功")
        except Exception as e:
            # 如果是因为索引已存在而失败，尝试手动处理
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                print(f"   ⚠️  部分对象已存在，尝试继续...")
                # 尝试逐个创建表
                from src.storage.metadata.models import Base
                for table in Base.metadata.sorted_tables:
                    try:
                        table.create(bind=pg_client.engine, checkfirst=True)
                        print(f"      ✅ 表 '{table.name}' 创建成功")
                    except Exception as e2:
                        if "already exists" in str(e2).lower():
                            print(f"      ⚠️  表 '{table.name}' 已存在，跳过")
                        else:
                            print(f"      ❌ 表 '{table.name}' 创建失败: {e2}")
            else:
                raise
        
        # 验证表
        print("\n4️⃣ 验证创建的表...")
        required_tables = ['documents', 'document_chunks', 'crawl_tasks', 'parse_tasks', 
                          'validation_logs', 'quarantine_records', 'embedding_tasks']
        
        all_exist = True
        for table_name in required_tables:
            if pg_client.table_exists(table_name):
                count = pg_client.get_table_count(table_name)
                print(f"   ✅ {table_name}: {count} 条记录")
            else:
                print(f"   ❌ {table_name}: 不存在")
                all_exist = False
        
        print("\n" + "=" * 60)
        if all_exist:
            print("✅ 数据库修复完成！所有表已创建")
        else:
            print("⚠️  数据库修复部分完成，部分表未创建")
        print("=" * 60)
        
        return all_exist
        
    except Exception as e:
        print(f"\n❌ 数据库修复失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = fix_database()
    sys.exit(0 if success else 1)
