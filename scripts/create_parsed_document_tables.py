# -*- coding: utf-8 -*-
"""
创建 ParsedDocument、Image 和 ImageAnnotation 表的 Python 脚本
使用 SQLAlchemy 执行 SQL 迁移
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.storage.metadata.postgres_client import get_postgres_client
from src.common.logger import get_logger
from sqlalchemy import text

logger = get_logger(__name__)


def create_tables():
    """创建新表 - 使用 SQLAlchemy create_all"""
    pg_client = get_postgres_client()
    
    try:
        # 导入新模型
        from src.storage.metadata.models import ParsedDocument, Image, ImageAnnotation
        
        # 使用 SQLAlchemy 的 create_all 创建表
        logger.info("创建 parsed_documents, images, image_annotations 表...")
        pg_client.create_tables(checkfirst=True)
        
        logger.info("✅ 所有表创建成功！")
        return True
        
    except Exception as e:
        # 如果是表已存在的错误，忽略
        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            logger.warning(f"⚠️  表或索引已存在，跳过: {e}")
            return True
        else:
            logger.error(f"❌ 创建表失败: {e}", exc_info=True)
            return False


def verify_tables():
    """验证表是否创建成功"""
    pg_client = get_postgres_client()
    
    tables_to_check = ['parsed_documents', 'images', 'image_annotations']
    
    try:
        with pg_client.engine.connect() as conn:
            for table_name in tables_to_check:
                result = conn.execute(text(
                    f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table_name}')"
                ))
                exists = result.scalar()
                
                if exists:
                    # 获取表结构
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                    count = result.scalar()
                    logger.info(f"✅ 表 '{table_name}' 存在，记录数: {count}")
                else:
                    logger.error(f"❌ 表 '{table_name}' 不存在")
                    return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 验证失败: {e}", exc_info=True)
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("创建 ParsedDocument、Image 和 ImageAnnotation 表")
    print("=" * 60)
    print()
    
    # 创建表
    if create_tables():
        print()
        print("验证表创建...")
        if verify_tables():
            print()
            print("=" * 60)
            print("✅ 所有表创建成功！")
            print("=" * 60)
            return 0
        else:
            print()
            print("=" * 60)
            print("⚠️  表创建完成，但验证失败")
            print("=" * 60)
            return 1
    else:
        print()
        print("=" * 60)
        print("❌ 表创建失败")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    sys.exit(main())
