#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为 parsed_documents 表添加分块相关字段（改进版）
执行数据库迁移以支持文本分块功能
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.storage.metadata.postgres_client import get_postgres_client
from src.common.logger import get_logger

logger = get_logger(__name__)


def column_exists(session, table_name: str, column_name: str) -> bool:
    """检查列是否存在"""
    check_sql = text("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = :table_name 
            AND column_name = :column_name
        )
    """)
    result = session.execute(check_sql, {"table_name": table_name, "column_name": column_name})
    return result.scalar()


def main():
    """执行数据库迁移"""
    logger.info("=" * 80)
    logger.info("开始为 parsed_documents 表添加分块相关字段")
    logger.info("=" * 80)

    pg_client = get_postgres_client()
    
    # 需要添加的列定义
    columns_to_add = [
        ("structure_json_path", "VARCHAR(500)", None),
        ("chunks_json_path", "VARCHAR(500)", None),
        ("structure_json_hash", "VARCHAR(64)", None),
        ("chunks_json_hash", "VARCHAR(64)", None),
        ("chunks_count", "INTEGER", "DEFAULT 0"),
        ("chunked_at", "TIMESTAMP", None),
    ]
    
    # 需要创建的索引
    indexes_to_create = [
        ("idx_parsed_documents_structure_hash", "structure_json_hash"),
        ("idx_parsed_documents_chunks_hash", "chunks_json_hash"),
        ("idx_parsed_documents_chunks_count", "chunks_count"),
    ]
    
    try:
        with pg_client.get_session() as session:
            # 1. 添加列
            logger.info("\n步骤 1: 添加列...")
            for column_name, column_type, default in columns_to_add:
                if column_exists(session, "parsed_documents", column_name):
                    logger.info(f"  ✓ 列 {column_name} 已存在，跳过")
                    continue
                
                try:
                    # 构建 ALTER TABLE 语句
                    alter_sql = f"ALTER TABLE parsed_documents ADD COLUMN {column_name} {column_type}"
                    if default:
                        alter_sql += f" {default}"
                    
                    logger.info(f"  添加列: {column_name} ({column_type})...")
                    session.execute(text(alter_sql))
                    session.commit()
                    logger.info(f"  ✅ 列 {column_name} 添加成功")
                except Exception as e:
                    session.rollback()
                    error_msg = str(e).lower()
                    if "already exists" in error_msg or "duplicate" in error_msg:
                        logger.info(f"  ℹ️  列 {column_name} 已存在（通过其他方式）")
                    else:
                        logger.error(f"  ❌ 添加列 {column_name} 失败: {e}")
                        raise
            
            # 2. 创建索引
            logger.info("\n步骤 2: 创建索引...")
            for index_name, column_name in indexes_to_create:
                # 检查索引是否已存在
                check_index_sql = text("""
                    SELECT EXISTS (
                        SELECT 1 
                        FROM pg_indexes 
                        WHERE tablename = 'parsed_documents' 
                        AND indexname = :index_name
                    )
                """)
                index_exists = session.execute(check_index_sql, {"index_name": index_name}).scalar()
                
                if index_exists:
                    logger.info(f"  ✓ 索引 {index_name} 已存在，跳过")
                    continue
                
                # 检查列是否存在
                if not column_exists(session, "parsed_documents", column_name):
                    logger.warning(f"  ⚠️  列 {column_name} 不存在，无法创建索引 {index_name}")
                    continue
                
                try:
                    create_index_sql = f"CREATE INDEX {index_name} ON parsed_documents({column_name})"
                    logger.info(f"  创建索引: {index_name}...")
                    session.execute(text(create_index_sql))
                    session.commit()
                    logger.info(f"  ✅ 索引 {index_name} 创建成功")
                except Exception as e:
                    session.rollback()
                    error_msg = str(e).lower()
                    if "already exists" in error_msg or "duplicate" in error_msg:
                        logger.info(f"  ℹ️  索引 {index_name} 已存在（通过其他方式）")
                    else:
                        logger.error(f"  ❌ 创建索引 {index_name} 失败: {e}")
                        # 索引创建失败不影响整体流程，继续执行
            
            # 3. 添加注释
            logger.info("\n步骤 3: 添加注释...")
            comments = [
                ("structure_json_path", "structure.json 文件路径（Silver 层）"),
                ("chunks_json_path", "chunks.json 文件路径（Silver 层）"),
                ("structure_json_hash", "structure.json 文件哈希（SHA256）"),
                ("chunks_json_hash", "chunks.json 文件哈希（SHA256）"),
                ("chunks_count", "分块数量"),
                ("chunked_at", "分块时间"),
            ]
            
            for column_name, comment_text in comments:
                if not column_exists(session, "parsed_documents", column_name):
                    logger.warning(f"  ⚠️  列 {column_name} 不存在，无法添加注释")
                    continue
                
                try:
                    comment_sql = text(f"COMMENT ON COLUMN parsed_documents.{column_name} IS :comment")
                    session.execute(comment_sql, {"comment": comment_text})
                    session.commit()
                    logger.debug(f"  ✅ 为列 {column_name} 添加注释成功")
                except Exception as e:
                    session.rollback()
                    logger.warning(f"  ⚠️  为列 {column_name} 添加注释失败: {e}")
            
            logger.info("\n✅ 数据库迁移执行完成")
    
    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {e}", exc_info=True)
        sys.exit(1)
    
    # 4. 验证字段
    logger.info("\n步骤 4: 验证字段...")
    try:
        with pg_client.get_session() as session:
            check_sql = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'parsed_documents' 
                AND column_name IN (
                    'structure_json_path', 
                    'chunks_json_path', 
                    'structure_json_hash', 
                    'chunks_json_hash', 
                    'chunks_count', 
                    'chunked_at'
                )
                ORDER BY column_name;
            """)
            result = session.execute(check_sql)
            columns = [row[0] for row in result]
            
            expected_columns = {
                'structure_json_path',
                'chunks_json_path', 
                'structure_json_hash',
                'chunks_json_hash',
                'chunks_count',
                'chunked_at'
            }
            
            logger.info(f"找到字段: {sorted(columns)}")
            
            missing_columns = expected_columns - set(columns)
            if missing_columns:
                logger.error(f"❌ 缺少字段: {sorted(missing_columns)}")
                sys.exit(1)
            else:
                logger.info("✅ 所有字段都已成功添加")
                
    except Exception as e:
        logger.error(f"验证字段时出错: {e}", exc_info=True)
        sys.exit(1)
    
    logger.info("=" * 80)
    logger.info("parsed_documents 表结构更新完成")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
