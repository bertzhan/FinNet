#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为 parsed_documents 表添加分块相关字段
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


def main():
    """执行数据库迁移"""
    logger.info("=" * 80)
    logger.info("开始为 parsed_documents 表添加分块相关字段")
    logger.info("=" * 80)

    # 读取 SQL 脚本
    sql_file = project_root / "scripts" / "add_chunk_fields_to_parsed_documents.sql"
    if not sql_file.exists():
        logger.error(f"SQL 文件不存在: {sql_file}")
        sys.exit(1)

    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_script = f.read()

    logger.info(f"读取 SQL 脚本: {sql_file}")

    # 执行迁移
    pg_client = get_postgres_client()

    try:
        # 先检查哪些列已经存在
        logger.info("检查现有列...")
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
            """)
            result = session.execute(check_sql)
            existing_columns = {row[0] for row in result}
            logger.info(f"已存在的列: {existing_columns if existing_columns else '无'}")
        
        # 分割 SQL 语句并执行
        statements = [s.strip() for s in sql_script.split(';') if s.strip() and not s.strip().startswith('--')]
        
        logger.info(f"共 {len(statements)} 条 SQL 语句需要执行")
        logger.info("开始执行数据库迁移...")

        # 每个语句在独立的事务中执行，避免一个失败影响其他
        success_count = 0
        skip_count = 0
        error_count = 0

        for i, statement in enumerate(statements, 1):
            if not statement:
                continue
            
            # 对于 ALTER TABLE 语句，检查列是否已存在
            if statement.strip().upper().startswith('ALTER TABLE'):
                # 提取列名
                column_name = None
                if 'structure_json_path' in statement:
                    column_name = 'structure_json_path'
                elif 'chunks_json_path' in statement:
                    column_name = 'chunks_json_path'
                elif 'structure_json_hash' in statement:
                    column_name = 'structure_json_hash'
                elif 'chunks_json_hash' in statement:
                    column_name = 'chunks_json_hash'
                elif 'chunks_count' in statement:
                    column_name = 'chunks_count'
                elif 'chunked_at' in statement:
                    column_name = 'chunked_at'
                
                if column_name and column_name in existing_columns:
                    logger.info(f"ℹ️  语句 {i} 跳过（列 {column_name} 已存在）")
                    skip_count += 1
                    continue
            
            # 对于 CREATE INDEX 语句，检查列是否存在
            if statement.strip().upper().startswith('CREATE INDEX'):
                # 提取列名
                column_name = None
                if 'structure_json_hash' in statement:
                    column_name = 'structure_json_hash'
                elif 'chunks_json_hash' in statement:
                    column_name = 'chunks_json_hash'
                elif 'chunks_count' in statement:
                    column_name = 'chunks_count'
                
                if column_name and column_name not in existing_columns:
                    logger.warning(f"⚠️ 语句 {i} 跳过（列 {column_name} 不存在，无法创建索引）")
                    skip_count += 1
                    continue
                
            try:
                with pg_client.get_session() as session:
                    logger.info(f"执行语句 {i}/{len(statements)}: {statement[:80]}...")
                    session.execute(text(statement))
                    session.commit()
                    logger.info(f"✅ 语句 {i} 执行成功")
                    success_count += 1
                    
                    # 如果是 ALTER TABLE 添加列，更新 existing_columns
                    if statement.strip().upper().startswith('ALTER TABLE') and 'ADD COLUMN' in statement.upper():
                        for col in ['structure_json_path', 'chunks_json_path', 'structure_json_hash', 
                                   'chunks_json_hash', 'chunks_count', 'chunked_at']:
                            if col in statement:
                                existing_columns.add(col)
                                break
                                
            except Exception as e:
                error_msg = str(e).lower()
                # 检查是否是"已存在"的错误
                if any(keyword in error_msg for keyword in [
                    "already exists",
                    "duplicate key",
                    "duplicate constraint"
                ]):
                    logger.info(f"ℹ️  语句 {i} 跳过（已存在）: {statement[:50]}...")
                    skip_count += 1
                else:
                    logger.error(f"❌ 语句 {i} 执行失败: {e}")
                    logger.error(f"   语句内容: {statement[:200]}")
                    error_count += 1

        logger.info(f"✅ 数据库迁移执行完成: 成功 {success_count}, 跳过 {skip_count}, 失败 {error_count}")

    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {e}", exc_info=True)
        sys.exit(1)

    logger.info("=" * 80)
    logger.info("parsed_documents 表结构更新完成")
    logger.info("=" * 80)
    
    # 验证字段是否添加成功
    logger.info("\n验证字段...")
    try:
        with pg_client.get_session() as session:
            # 检查字段是否存在
            check_sql = """
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
            """
            result = session.execute(text(check_sql))
            columns = [row[0] for row in result]
            
            expected_columns = [
                'structure_json_path',
                'chunks_json_path', 
                'structure_json_hash',
                'chunks_json_hash',
                'chunks_count',
                'chunked_at'
            ]
            
            logger.info(f"找到字段: {columns}")
            
            missing_columns = set(expected_columns) - set(columns)
            if missing_columns:
                logger.warning(f"⚠️  缺少字段: {missing_columns}")
            else:
                logger.info("✅ 所有字段都已成功添加")
                
    except Exception as e:
        logger.warning(f"验证字段时出错: {e}")


if __name__ == "__main__":
    main()
