#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库重建脚本
删除所有表并重新创建（使用新的 UUID 主键）
⚠️ 警告：此操作会删除所有数据！
"""

import sys
import os
import argparse

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.storage.metadata.postgres_client import get_postgres_client
from src.common.logger import get_logger

logger = get_logger(__name__)


def recreate_database(force: bool = False):
    """删除所有表并重新创建"""
    print("=" * 60)
    print("数据库重建脚本")
    print("⚠️  警告：此操作会删除所有数据！")
    print("=" * 60)
    
    try:
        # 获取 PostgreSQL 客户端
        pg_client = get_postgres_client()
        
        # 测试连接
        print("\n1️⃣ 测试数据库连接...")
        if not pg_client.test_connection():
            print("   ❌ 数据库连接失败")
            return False
        print("   ✅ 数据库连接成功")
        
        # 检查现有表
        print("\n2️⃣ 检查现有表...")
        required_tables = [
            'documents', 'document_chunks', 'crawl_tasks', 'parse_tasks', 
            'validation_logs', 'quarantine_records', 'embedding_tasks',
            'parsed_documents', 'images', 'image_annotations'
        ]
        
        existing_tables = []
        for table_name in required_tables:
            if pg_client.table_exists(table_name):
                count = pg_client.get_table_count(table_name)
                print(f"   📊 表 '{table_name}': {count} 条记录")
                existing_tables.append(table_name)
        
        if existing_tables:
            print(f"\n   发现 {len(existing_tables)} 个现有表")
        else:
            print("   未发现现有表")
        
        # 确认删除
        print("\n3️⃣ 准备删除所有表...")
        if not force:
            try:
                response = input("   确认删除所有表并重建？(yes/no): ").strip().lower()
                if response not in ['yes', 'y']:
                    print("   ❌ 操作已取消")
                    return False
            except EOFError:
                print("   ❌ 非交互式环境，请使用 --yes 参数自动确认")
                return False
        else:
            print("   ⚠️  使用 --yes 参数，自动确认删除")
        
        # 删除所有表（使用 CASCADE 确保删除所有依赖对象）
        print("\n4️⃣ 删除所有表...")
        try:
            # 使用原生 SQL 彻底删除所有表和相关对象
            from sqlalchemy import text
            with pg_client.engine.connect() as conn:
                # 先删除所有索引（包括独立的索引）
                conn.execute(text("""
                    DO $$ 
                    DECLARE 
                        r RECORD;
                    BEGIN
                        -- 删除所有索引
                        FOR r IN (
                            SELECT indexname 
                            FROM pg_indexes 
                            WHERE schemaname = 'public'
                        ) 
                        LOOP
                            EXECUTE 'DROP INDEX IF EXISTS public.' || quote_ident(r.indexname) || ' CASCADE';
                        END LOOP;
                    END $$;
                """))
                # 删除所有表（CASCADE 会自动删除约束等）
                conn.execute(text("""
                    DO $$ 
                    DECLARE 
                        r RECORD;
                    BEGIN
                        -- 删除所有表（CASCADE 会删除所有依赖对象）
                        FOR r IN (
                            SELECT tablename 
                            FROM pg_tables 
                            WHERE schemaname = 'public'
                        ) 
                        LOOP
                            EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE';
                        END LOOP;
                    END $$;
                """))
                conn.commit()
            print("   ✅ 所有表、索引和依赖对象已删除")
        except Exception as e:
            print(f"   ⚠️  删除表时出现警告: {e}")
            # 尝试使用 SQLAlchemy 的方法作为备选
            try:
                pg_client.drop_tables()
                print("   ✅ SQLAlchemy drop_all 完成")
            except Exception as e2:
                print(f"   ⚠️  drop_all 也失败: {e2}")
                # 继续执行，可能表已经不存在
        
        # 重新创建所有表
        print("\n5️⃣ 重新创建所有表（使用 UUID 主键）...")
        try:
            pg_client.create_tables(checkfirst=False)
            print("   ✅ 所有表已创建")
        except Exception as e:
            print(f"   ❌ 创建表失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # 验证创建的表
        print("\n6️⃣ 验证创建的表...")
        created_tables = []
        for table_name in required_tables:
            if pg_client.table_exists(table_name):
                print(f"   ✅ 表 '{table_name}' 已创建")
                created_tables.append(table_name)
            else:
                print(f"   ❌ 表 '{table_name}' 未创建")
        
        if len(created_tables) == len(required_tables):
            print(f"\n   ✅ 成功创建 {len(created_tables)} 个表")
        else:
            print(f"\n   ⚠️  只创建了 {len(created_tables)}/{len(required_tables)} 个表")
        
        # 显示表结构信息
        print("\n7️⃣ 表结构信息:")
        for table_name in created_tables:
            count = pg_client.get_table_count(table_name)
            print(f"   - {table_name}: {count} 条记录")
        
        # 显示数据库大小
        db_size = pg_client.get_database_size()
        if db_size:
            print(f"\n   数据库大小: {db_size}")
        
        print("\n" + "=" * 60)
        print("✅ 数据库重建完成！")
        print("=" * 60)
        print("\n📝 注意：")
        print("   - 所有表的主键已改为 UUID 类型")
        print("   - 所有外键也已更新为 UUID 类型")
        print("   - 请确保相关代码已更新以使用 UUID")
        
        return True
        
    except KeyboardInterrupt:
        print("\n\n❌ 操作被用户中断")
        return False
    except Exception as e:
        print(f"\n❌ 数据库重建失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 关闭连接
        try:
            pg_client.close()
        except:
            pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='重建数据库（删除所有表并重新创建）')
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='自动确认，跳过交互式提示'
    )
    args = parser.parse_args()
    
    success = recreate_database(force=args.yes)
    sys.exit(0 if success else 1)
