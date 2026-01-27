#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建 listed_companies 表的迁移脚本
用于在现有数据库中添加上市公司列表表
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import ListedCompany
from src.common.logger import get_logger

logger = get_logger(__name__)


def migrate_listed_companies_table():
    """创建 listed_companies 表"""
    print("=" * 60)
    print("数据库迁移：创建 listed_companies 表")
    print("=" * 60)
    print()
    
    try:
        # 获取 PostgreSQL 客户端
        pg_client = get_postgres_client()
        
        # 测试连接
        print("1️⃣ 测试数据库连接...")
        if not pg_client.test_connection():
            print("   ❌ 数据库连接失败")
            print("   提示: 请确保 PostgreSQL 服务正在运行")
            return False
        print("   ✅ 数据库连接成功")
        
        # 检查表是否已存在
        print("\n2️⃣ 检查 listed_companies 表...")
        if pg_client.table_exists('listed_companies'):
            print("   ✅ 表 'listed_companies' 已存在")
            
            # 获取当前记录数
            count = pg_client.get_table_count('listed_companies')
            print(f"   当前记录数: {count} 家")
            
            # 询问是否继续
            print("\n   表已存在，是否要重新创建？")
            print("   ⚠️  警告：重新创建会删除所有现有数据！")
            response = input("   输入 'yes' 继续，其他任意键跳过: ").strip().lower()
            
            if response != 'yes':
                print("   ⏭️  跳过创建，保持现有表")
                return True
            
            # 删除现有表
            print("\n   删除现有表...")
            with pg_client.get_session() as session:
                from sqlalchemy import text
                session.execute(text("DROP TABLE IF EXISTS listed_companies CASCADE"))
                session.commit()
            print("   ✅ 表已删除")
        
        # 创建表
        print("\n3️⃣ 创建 listed_companies 表...")
        try:
            # 只创建 ListedCompany 表
            ListedCompany.__table__.create(bind=pg_client.engine, checkfirst=True)
            print("   ✅ 表创建成功")
        except Exception as e:
            # 如果是因为表已存在而失败，可以忽略
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                print(f"   ⚠️  表已存在，跳过: {e}")
            else:
                raise
        
        # 验证表结构
        print("\n4️⃣ 验证表结构...")
        if pg_client.table_exists('listed_companies'):
            print("   ✅ 表 'listed_companies' 已创建")
            
            # 显示表信息
            from sqlalchemy import inspect
            inspector = inspect(pg_client.engine)
            columns = inspector.get_columns('listed_companies')
            
            print("\n   表结构:")
            for col in columns:
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                default = f" DEFAULT {col['default']}" if col.get('default') else ""
                print(f"     - {col['name']}: {col['type']} {nullable}{default}")
            
            # 显示索引
            indexes = inspector.get_indexes('listed_companies')
            if indexes:
                print("\n   索引:")
                for idx in indexes:
                    cols = ', '.join(idx['column_names'])
                    unique = "UNIQUE" if idx.get('unique') else ""
                    print(f"     - {idx['name']}: {unique} ({cols})")
        else:
            print("   ❌ 表创建失败")
            return False
        
        # 检查记录数
        print("\n5️⃣ 检查记录数...")
        count = pg_client.get_table_count('listed_companies')
        print(f"   当前记录数: {count} 家")
        
        print("\n" + "=" * 60)
        print("✅ 数据库迁移完成！")
        print("=" * 60)
        print()
        print("📝 下一步:")
        print("   1. 运行更新作业: python examples/test_company_list_job.py")
        print("   2. 或使用 Dagster UI 手动触发 update_listed_companies_job")
        print()
        
        return True
        
    except Exception as e:
        print(f"\n❌ 数据库迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = migrate_listed_companies_table()
    sys.exit(0 if success else 1)
