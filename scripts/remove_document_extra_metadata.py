# -*- coding: utf-8 -*-
"""
删除 documents 表的 extra_metadata 字段
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


def remove_extra_metadata_column():
    """删除 documents 表的 extra_metadata 字段"""
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 检查字段是否存在
            check_sql = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'documents' 
                    AND column_name = 'extra_metadata'
            """)
            result = session.execute(check_sql)
            existing = result.fetchone()
            
            if not existing:
                logger.info("✅ extra_metadata 字段不存在，跳过删除")
                return True
            
            # 删除字段
            logger.info("正在删除 extra_metadata 字段...")
            session.execute(text("""
                ALTER TABLE documents
                    DROP COLUMN extra_metadata
            """))
            
            session.commit()
            logger.info("✅ extra_metadata 字段删除成功")
            
            # 验证
            result = session.execute(check_sql)
            if not result.fetchone():
                logger.info("✅ 验证通过：extra_metadata 字段已删除")
                return True
            else:
                logger.error("❌ 验证失败：extra_metadata 字段仍然存在")
                return False
                
    except Exception as e:
        logger.error(f"❌ 删除字段失败: {e}", exc_info=True)
        return False


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='删除 documents 表的 extra_metadata 字段')
    parser.add_argument('--yes', '-y', action='store_true', help='跳过确认，直接执行')
    args = parser.parse_args()
    
    print("=" * 60)
    print("删除 documents 表的 extra_metadata 字段")
    print("=" * 60)
    
    if not args.yes:
        print("\n⚠️  警告：此操作将永久删除 extra_metadata 字段及其所有数据！")
        print("   请确保已备份重要数据。")
        print("   使用 --yes 或 -y 参数可跳过确认")
        sys.exit(1)
    
    success = remove_extra_metadata_column()
    
    if success:
        print("\n✅ 迁移完成！")
        sys.exit(0)
    else:
        print("\n❌ 迁移失败！")
        sys.exit(1)


if __name__ == '__main__':
    main()
