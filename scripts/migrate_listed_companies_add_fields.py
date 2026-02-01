#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移脚本：为 listed_companies 表添加新字段

新增字段：
- full_name: 公司全称（如：平安银行股份有限公司）
- former_names: 曾用名（逗号分隔）
- english_name: 英文名称
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.storage.metadata import get_postgres_client
from src.common.logger import get_logger

logger = get_logger(__name__)


def migrate():
    """执行迁移"""
    print("=" * 60)
    print("数据库迁移：为 listed_companies 表添加新字段")
    print("=" * 60)
    print()
    
    pg_client = get_postgres_client()
    
    # 检查表是否存在
    if not pg_client.table_exists('listed_companies'):
        print("❌ listed_companies 表不存在")
        print("   请先运行: python scripts/migrate_listed_companies_table.py")
        return False
    
    print("✅ listed_companies 表存在")
    
    # 要添加的字段
    new_columns = [
        ("full_name", "VARCHAR(500)", "公司全称"),
        ("former_names", "TEXT", "曾用名"),
        ("english_name", "VARCHAR(500)", "英文名称"),
    ]
    
    with pg_client.get_session() as session:
        for col_name, col_type, col_desc in new_columns:
            try:
                # 检查字段是否已存在
                check_sql = text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'listed_companies' 
                    AND column_name = :col_name
                """)
                result = session.execute(check_sql, {"col_name": col_name})
                
                if result.fetchone():
                    print(f"⏭️  字段 {col_name} 已存在，跳过")
                    continue
                
                # 添加字段
                alter_sql = text(f"""
                    ALTER TABLE listed_companies 
                    ADD COLUMN {col_name} {col_type}
                """)
                session.execute(alter_sql)
                print(f"✅ 添加字段: {col_name} ({col_desc})")
                
            except Exception as e:
                print(f"❌ 添加字段 {col_name} 失败: {e}")
                return False
        
        session.commit()
    
    print()
    print("✅ 迁移完成！")
    print()
    print("新增字段：")
    print("  - full_name: 公司全称（如：平安银行股份有限公司）")
    print("  - former_names: 曾用名（逗号分隔，如：深发展A,深发展）")
    print("  - english_name: 英文名称")
    print()
    print("下一步：运行获取公司全称的作业来填充这些字段")
    print("  dagster job execute -j fetch_company_full_names_job -m src.processing.compute.dagster")
    
    return True


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
