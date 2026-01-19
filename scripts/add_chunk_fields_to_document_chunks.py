#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为 document_chunks 表添加 heading_index 和 is_table 字段
数据库迁移脚本
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.common.logger import get_logger

logger = get_logger(__name__)


def column_exists(session, table_name: str, column_name: str) -> bool:
    """检查列是否存在"""
    from sqlalchemy import text
    query = text("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = :table_name 
            AND column_name = :column_name
        )
    """)
    result = session.execute(query, {"table_name": table_name, "column_name": column_name})
    return result.scalar()


def index_exists(session, index_name: str) -> bool:
    """检查索引是否存在"""
    from sqlalchemy import text
    query = text("""
        SELECT EXISTS (
            SELECT 1 
            FROM pg_indexes 
            WHERE indexname = :index_name
        )
    """)
    result = session.execute(query, {"index_name": index_name})
    return result.scalar()


def main():
    """执行数据库迁移"""
    logger.info("=" * 80)
    logger.info("开始为 document_chunks 表添加 heading_index 和 is_table 字段")
    logger.info("=" * 80)

    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            from sqlalchemy import text
            
            # 1. 添加 heading_index 字段
            if not column_exists(session, "document_chunks", "heading_index"):
                logger.info("添加 heading_index 字段...")
                session.execute(text("""
                    ALTER TABLE document_chunks 
                    ADD COLUMN heading_index INTEGER
                """))
                session.commit()
                logger.info("✅ heading_index 字段添加成功")
            else:
                logger.info("⏭️  heading_index 字段已存在，跳过")
            
            # 2. 添加 is_table 字段
            if not column_exists(session, "document_chunks", "is_table"):
                logger.info("添加 is_table 字段...")
                session.execute(text("""
                    ALTER TABLE document_chunks 
                    ADD COLUMN is_table BOOLEAN DEFAULT FALSE
                """))
                session.commit()
                logger.info("✅ is_table 字段添加成功")
            else:
                logger.info("⏭️  is_table 字段已存在，跳过")
            
            # 3. 添加注释
            logger.info("添加字段注释...")
            session.execute(text("""
                COMMENT ON COLUMN document_chunks.heading_index IS '标题索引（在文档结构中的索引位置）'
            """))
            session.execute(text("""
                COMMENT ON COLUMN document_chunks.is_table IS '是否是表格分块'
            """))
            session.commit()
            logger.info("✅ 字段注释添加成功")
            
            # 4. 创建索引
            if not index_exists(session, "idx_document_chunks_heading_index"):
                logger.info("创建 heading_index 索引...")
                session.execute(text("""
                    CREATE INDEX idx_document_chunks_heading_index 
                    ON document_chunks(heading_index)
                """))
                session.commit()
                logger.info("✅ heading_index 索引创建成功")
            else:
                logger.info("⏭️  heading_index 索引已存在，跳过")
            
            if not index_exists(session, "idx_document_chunks_is_table"):
                logger.info("创建 is_table 索引...")
                session.execute(text("""
                    CREATE INDEX idx_document_chunks_is_table 
                    ON document_chunks(is_table)
                """))
                session.commit()
                logger.info("✅ is_table 索引创建成功")
            else:
                logger.info("⏭️  is_table 索引已存在，跳过")
            
            logger.info("=" * 80)
            logger.info("✅ 数据库迁移完成！")
            logger.info("=" * 80)
            
    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
