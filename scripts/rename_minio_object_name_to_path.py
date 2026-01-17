# -*- coding: utf-8 -*-
"""
重命名 documents 表的 minio_object_name 字段为 minio_object_path
执行数据库迁移脚本
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.common.logger import get_logger
from sqlalchemy import text

logger = get_logger(__name__)


def rename_column():
    """重命名 minio_object_name 字段为 minio_object_path"""
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 检查旧字段是否存在
            check_old_sql = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'documents' 
                    AND column_name = 'minio_object_name'
            """)
            result = session.execute(check_old_sql)
            old_exists = result.fetchone()
            
            # 检查新字段是否已存在
            check_new_sql = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'documents' 
                    AND column_name = 'minio_object_path'
            """)
            result = session.execute(check_new_sql)
            new_exists = result.fetchone()
            
            if new_exists:
                logger.info("✅ minio_object_path 字段已存在，跳过重命名")
                return True
            
            if not old_exists:
                logger.error("❌ minio_object_name 字段不存在，无法重命名")
                return False
            
            # 重命名字段
            logger.info("正在重命名字段 minio_object_name -> minio_object_path...")
            session.execute(text("""
                ALTER TABLE documents
                    RENAME COLUMN minio_object_name TO minio_object_path
            """))
            
            # 尝试重命名唯一约束索引
            try:
                session.execute(text("""
                    ALTER INDEX IF EXISTS documents_minio_object_name_key 
                        RENAME TO documents_minio_object_path_key
                """))
                logger.info("✅ 唯一约束索引已重命名")
            except Exception as e:
                logger.warning(f"重命名索引时出现警告（可能索引不存在）: {e}")
            
            session.commit()
            logger.info("✅ 字段重命名成功")
            
            # 验证
            result = session.execute(check_new_sql)
            if result.fetchone():
                logger.info("✅ 验证通过：minio_object_path 字段已存在")
                return True
            else:
                logger.error("❌ 验证失败：minio_object_path 字段未找到")
                return False
                
    except Exception as e:
        logger.error(f"❌ 重命名字段失败: {e}", exc_info=True)
        return False


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='重命名 documents 表的 minio_object_name 字段为 minio_object_path')
    parser.add_argument('--yes', '-y', action='store_true', help='跳过确认，直接执行')
    args = parser.parse_args()
    
    print("=" * 60)
    print("重命名 documents 表的 minio_object_name 字段为 minio_object_path")
    print("=" * 60)
    
    if not args.yes:
        print("\n⚠️  警告：此操作将重命名字段！")
        print("   使用 --yes 或 -y 参数可跳过确认")
        sys.exit(1)
    
    success = rename_column()
    
    if success:
        print("\n✅ 迁移完成！")
        sys.exit(0)
    else:
        print("\n❌ 迁移失败！")
        sys.exit(1)


if __name__ == '__main__':
    main()
