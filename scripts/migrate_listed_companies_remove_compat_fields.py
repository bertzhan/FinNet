#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
删除 listed_companies 表的兼容字段

删除以下兼容字段：
- full_name (已由 org_name_cn 替代)
- former_names (已由 pre_name_cn 替代)
- english_name (已由 org_name_en 替代)
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from sqlalchemy import text

def remove_compat_fields():
    """删除兼容字段"""
    pg_client = get_postgres_client()
    
    print("=" * 60)
    print("删除 listed_companies 表的兼容字段")
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
            print("❌ listed_companies 表不存在，跳过迁移")
            return False
        
        print("✅ listed_companies 表存在")
        print()
        
        # 检查字段是否存在
        fields_to_remove = [
            ('full_name', 'org_name_cn'),
            ('former_names', 'pre_name_cn'),
            ('english_name', 'org_name_en'),
        ]
        
        existing_fields = []
        for old_field, new_field in fields_to_remove:
            result = session.execute(text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'listed_companies' 
                    AND column_name = '{old_field}'
                );
            """))
            if result.scalar():
                existing_fields.append((old_field, new_field))
        
        if not existing_fields:
            print("✅ 所有兼容字段已不存在，无需删除")
            return True
        
        print(f"发现 {len(existing_fields)} 个兼容字段需要删除：")
        for old_field, new_field in existing_fields:
            print(f"  - {old_field} (已由 {new_field} 替代)")
        print()
        
        # 确认删除
        print("开始删除兼容字段...")
        print()
        
        for old_field, new_field in existing_fields:
            try:
                # 删除字段
                session.execute(text(f"""
                    ALTER TABLE listed_companies 
                    DROP COLUMN IF EXISTS {old_field};
                """))
                session.commit()
                print(f"✅ 已删除字段: {old_field}")
            except Exception as e:
                session.rollback()
                print(f"❌ 删除字段 {old_field} 失败: {e}")
                return False
        
        print()
        print("=" * 60)
        print("✅ 兼容字段删除完成")
        print("=" * 60)
        print()
        print("已删除的字段：")
        for old_field, new_field in existing_fields:
            print(f"  - {old_field} -> 使用 {new_field} 替代")
        
        return True

if __name__ == "__main__":
    try:
        success = remove_compat_fields()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ 迁移失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
