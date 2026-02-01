#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移脚本：扩展 listed_companies 表中可能超长的字段长度

修复 "value too long for type character varying(50)" 错误
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
    print("数据库迁移：扩展 listed_companies 表字段长度")
    print("=" * 60)
    print()
    
    pg_client = get_postgres_client()
    
    # 检查表是否存在
    if not pg_client.table_exists('listed_companies'):
        print("❌ listed_companies 表不存在")
        return False
    
    print("✅ listed_companies 表存在")
    
    # 需要扩展长度的字段
    field_extensions = [
        ("org_id", "VARCHAR(100)", "机构ID（从50扩展到100）"),
        ("telephone", "VARCHAR(200)", "电话（从50扩展到200，可能包含多个号码）"),
        ("fax", "VARCHAR(200)", "传真（从50扩展到200，可能包含多个号码）"),
        ("district_encode", "VARCHAR(100)", "地区编码（从50扩展到100）"),
        ("currency_encode", "VARCHAR(100)", "货币编码（从50扩展到100）"),
        ("currency", "VARCHAR(20)", "货币（从10扩展到20）"),
    ]
    
    with pg_client.get_session() as session:
        for col_name, new_type, description in field_extensions:
            try:
                # 检查字段是否存在
                check_sql = text("""
                    SELECT column_name, data_type, character_maximum_length
                    FROM information_schema.columns 
                    WHERE table_name = 'listed_companies' 
                    AND column_name = :col_name
                """)
                result = session.execute(check_sql, {"col_name": col_name})
                row = result.fetchone()
                
                if not row:
                    print(f"⚠️  字段 {col_name} 不存在，跳过")
                    continue
                
                current_length = row[2]
                # 提取新长度
                new_length = int(new_type.split('(')[1].split(')')[0])
                
                if current_length and current_length >= new_length:
                    print(f"⏭️  字段 {col_name} 长度已足够（当前: {current_length}），跳过")
                    continue
                
                # 修改字段类型
                alter_sql = text(f"""
                    ALTER TABLE listed_companies 
                    ALTER COLUMN {col_name} TYPE {new_type}
                """)
                session.execute(alter_sql)
                print(f"✅ 扩展字段: {col_name} ({description})")
                
            except Exception as e:
                print(f"❌ 扩展字段 {col_name} 失败: {e}")
                return False
        
        session.commit()
    
    print()
    print("✅ 迁移完成！")
    print()
    print("已扩展的字段：")
    print("  - org_id: 50 -> 100")
    print("  - telephone: 50 -> 200")
    print("  - fax: 50 -> 200")
    print("  - district_encode: 50 -> 100")
    print("  - currency_encode: 50 -> 100")
    print("  - currency: 10 -> 20")
    
    return True


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
