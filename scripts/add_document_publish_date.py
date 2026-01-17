# -*- coding: utf-8 -*-
"""
添加 documents 表的 publish_date 字段
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


def add_publish_date_column():
    """添加 publish_date 字段到 documents 表"""
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 检查字段是否已存在
            check_sql = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'documents' 
                    AND column_name = 'publish_date'
            """)
            result = session.execute(check_sql)
            existing = result.fetchone()
            
            if existing:
                logger.info("✅ publish_date 字段已存在，跳过添加")
                return True
            
            # 添加字段
            logger.info("正在添加 publish_date 字段...")
            session.execute(text("""
                ALTER TABLE documents
                    ADD COLUMN publish_date TIMESTAMP
            """))
            
            # 创建索引
            logger.info("正在创建索引...")
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_documents_publish_date 
                    ON documents(publish_date)
            """))
            
            # 添加注释
            logger.info("正在添加注释...")
            session.execute(text("""
                COMMENT ON COLUMN documents.publish_date IS '文档发布日期（文档在原始网站发布的日期）'
            """))
            
            session.commit()
            logger.info("✅ publish_date 字段添加成功")
            
            # 验证
            result = session.execute(check_sql)
            if result.fetchone():
                logger.info("✅ 验证通过：publish_date 字段已存在")
                return True
            else:
                logger.error("❌ 验证失败：publish_date 字段未找到")
                return False
                
    except Exception as e:
        logger.error(f"❌ 添加字段失败: {e}", exc_info=True)
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("添加 documents 表的 publish_date 字段")
    print("=" * 60)
    
    success = add_publish_date_column()
    
    if success:
        print("\n✅ 迁移完成！")
        sys.exit(0)
    else:
        print("\n❌ 迁移失败！")
        sys.exit(1)


if __name__ == '__main__':
    main()
