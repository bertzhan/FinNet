#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库初始化脚本
创建所有必要的数据库表
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.storage.metadata.postgres_client import get_postgres_client
from src.common.logger import get_logger

logger = get_logger(__name__)


def init_database():
    """初始化数据库表"""
    print("=" * 60)
    print("数据库初始化")
    print("=" * 60)
    
    try:
        # 获取 PostgreSQL 客户端
        pg_client = get_postgres_client()
        
        # 测试连接
        print("\n1️⃣ 测试数据库连接...")
        if pg_client.test_connection():
            print("   ✅ 数据库连接成功")
        else:
            print("   ❌ 数据库连接失败")
            return False
        
        # 检查表是否存在
        print("\n2️⃣ 检查数据库表...")
        required_tables = [
            # 基础表
            'documents', 'document_chunks', 'crawl_tasks', 'parse_tasks', 
            'validation_logs', 'quarantine_records', 'embedding_tasks',
            # 新增表（Silver 层）
            'parsed_documents', 'images', 'image_annotations'
        ]
        
        missing_tables = []
        for table_name in required_tables:
            if pg_client.table_exists(table_name):
                print(f"   ✅ 表 '{table_name}' 已存在")
            else:
                print(f"   ⚠️  表 '{table_name}' 不存在")
                missing_tables.append(table_name)
        
        # 创建缺失的表
        if missing_tables:
            print(f"\n3️⃣ 创建缺失的表 ({len(missing_tables)} 个)...")
            try:
                pg_client.create_tables(checkfirst=True)
                print("   ✅ 数据库表创建成功")
            except Exception as e:
                # 如果是因为索引已存在而失败，可以忽略
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    print(f"   ⚠️  部分表/索引已存在，跳过: {e}")
                else:
                    raise
        else:
            print("\n3️⃣ 所有表已存在，跳过创建")
        
        # 检查表
        print("\n4️⃣ 检查创建的表...")
        table_info = pg_client.get_table_info()
        print("   📊 表统计:")
        for table_name, count in table_info.items():
            print(f"      - {table_name}: {count} 条记录")
        
        # 列出所有表
        print("\n5️⃣ 已创建的表:")
        required_tables = [
            # 基础表
            'documents', 'document_chunks', 'crawl_tasks', 'parse_tasks', 
            'validation_logs', 'quarantine_records', 'embedding_tasks',
            # 新增表（Silver 层）
            'parsed_documents', 'images', 'image_annotations'
        ]
        for table in required_tables:
            if pg_client.table_exists(table):
                print(f"      ✅ {table}")
            else:
                print(f"      ❌ {table} (未创建)")
        
        print("\n" + "=" * 60)
        print("✅ 数据库初始化完成！")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = init_database()
    sys.exit(0 if success else 1)
