#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库 Schema 迁移脚本
执行以下变更：
1. 删除 document_chunks.vector_id 字段
2. 将 listed_companies.code 设为主键，删除 id 字段
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.common.logger import get_logger
from sqlalchemy import text

logger = get_logger(__name__)


def check_vector_id_migration(session):
    """检查 vector_id 迁移状态"""
    logger.info("=" * 80)
    logger.info("检查 document_chunks.vector_id 迁移状态")
    logger.info("=" * 80)
    
    # 检查列是否存在
    result = session.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'document_chunks' 
          AND column_name = 'vector_id'
    """)).fetchone()
    
    has_vector_id = result is not None
    
    if has_vector_id:
        # 检查数据状态
        result = session.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(vector_id) as has_vector_id,
                COUNT(vectorized_at) as has_vectorized_at
            FROM document_chunks
        """)).fetchone()
        
        logger.info(f"当前状态:")
        logger.info(f"  总分块数: {result[0]:,}")
        logger.info(f"  有 vector_id: {result[1]:,}")
        logger.info(f"  有 vectorized_at: {result[2]:,}")
        
        # 检查需要迁移的记录
        result = session.execute(text("""
            SELECT COUNT(*) 
            FROM document_chunks 
            WHERE vector_id IS NOT NULL AND vectorized_at IS NULL
        """)).fetchone()
        
        need_migration = result[0] if result else 0
        logger.info(f"  需要迁移的记录: {need_migration:,}")
        
        return True, need_migration
    else:
        logger.info("✓ vector_id 字段已不存在，无需迁移")
        return False, 0


def migrate_vector_id(session, dry_run=True):
    """迁移 vector_id 数据并删除字段"""
    logger.info("=" * 80)
    logger.info("迁移 document_chunks.vector_id")
    logger.info("=" * 80)
    
    has_vector_id, need_migration = check_vector_id_migration(session)
    
    if not has_vector_id:
        logger.info("✓ vector_id 字段已不存在，跳过")
        return True
    
    if need_migration > 0:
        if dry_run:
            logger.info(f"🔍 DRY RUN: 将迁移 {need_migration:,} 条记录")
            logger.info("  实际执行时会将 vectorized_at 设置为当前时间")
            return False
        else:
            logger.info(f"正在迁移 {need_migration:,} 条记录...")
            session.execute(text("""
                UPDATE document_chunks 
                SET vectorized_at = COALESCE(vectorized_at, NOW())
                WHERE vector_id IS NOT NULL AND vectorized_at IS NULL
            """))
            session.commit()
            logger.info("✓ 数据迁移完成")
    
    # 删除 vector_id 列
    if dry_run:
        logger.info("🔍 DRY RUN: 将删除 vector_id 列")
        return False
    else:
        logger.info("正在删除 vector_id 列...")
        try:
            session.execute(text("ALTER TABLE document_chunks DROP COLUMN vector_id"))
            session.commit()
            logger.info("✓ vector_id 列已删除")
            return True
        except Exception as e:
            logger.error(f"删除 vector_id 列失败: {e}")
            session.rollback()
            return False


def check_company_code_migration(session):
    """检查 listed_companies.code 主键迁移状态"""
    logger.info("=" * 80)
    logger.info("检查 listed_companies.code 主键迁移状态")
    logger.info("=" * 80)
    
    # 检查主键
    result = session.execute(text("""
        SELECT constraint_name, constraint_type
        FROM information_schema.table_constraints
        WHERE table_name = 'listed_companies'
          AND constraint_type = 'PRIMARY KEY'
    """)).fetchall()
    
    # 检查列
    columns = session.execute(text("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'listed_companies'
        ORDER BY ordinal_position
    """)).fetchall()
    
    has_id_column = any(col[0] == 'id' for col in columns)
    code_is_pk = any('code' in str(constraint) for constraint in result)
    
    logger.info(f"当前状态:")
    logger.info(f"  有 id 列: {has_id_column}")
    logger.info(f"  code 是主键: {code_is_pk}")
    
    if has_id_column:
        # 检查数据
        result = session.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(DISTINCT code) as unique_codes
            FROM listed_companies
        """)).fetchone()
        
        logger.info(f"  总记录数: {result[0]:,}")
        logger.info(f"  唯一 code 数: {result[1]:,}")
        
        if result[0] != result[1]:
            # 检查重复
            result = session.execute(text("""
                SELECT code, COUNT(*) as count
                FROM listed_companies
                GROUP BY code
                HAVING COUNT(*) > 1
                LIMIT 10
            """)).fetchall()
            
            logger.warning(f"⚠️  发现重复的 code:")
            for code, count in result:
                logger.warning(f"    {code}: {count} 条记录")
        
        return True, result[0] != result[1] if result else False
    else:
        logger.info("✓ id 列已不存在，code 已设为主键")
        return False, False


def migrate_company_code_pk(session, dry_run=True):
    """将 listed_companies.code 设为主键"""
    logger.info("=" * 80)
    logger.info("迁移 listed_companies.code 主键")
    logger.info("=" * 80)
    
    has_id_column, has_duplicates = check_company_code_migration(session)
    
    if not has_id_column:
        logger.info("✓ code 已设为主键，跳过")
        return True
    
    if has_duplicates:
        logger.error("❌ 发现重复的 code，请先清理重复数据")
        logger.error("   可以使用以下 SQL 清理（保留最新的记录）:")
        logger.error("""
            DELETE FROM listed_companies
            WHERE id NOT IN (
                SELECT MAX(id)
                FROM listed_companies
                GROUP BY code
            );
        """)
        return False
    
    if dry_run:
        logger.info("🔍 DRY RUN: 将执行以下操作:")
        logger.info("  1. 删除 idx_code 索引（如果存在）")
        logger.info("  2. 删除 id 列")
        logger.info("  3. 设置 code 为主键")
        return False
    else:
        try:
            # 删除索引（如果存在）
            logger.info("正在删除 idx_code 索引...")
            try:
                session.execute(text("DROP INDEX IF EXISTS idx_code"))
                session.commit()
            except Exception as e:
                logger.warning(f"删除索引失败（可能不存在）: {e}")
            
            # 删除 id 列并设置 code 为主键
            logger.info("正在删除 id 列并设置 code 为主键...")
            session.execute(text("""
                ALTER TABLE listed_companies 
                DROP COLUMN id,
                ADD PRIMARY KEY (code)
            """))
            session.commit()
            logger.info("✓ code 已设为主键")
            return True
        except Exception as e:
            logger.error(f"迁移失败: {e}")
            session.rollback()
            return False


def verify_migration(session):
    """验证迁移结果"""
    logger.info("=" * 80)
    logger.info("验证迁移结果")
    logger.info("=" * 80)
    
    # 验证 vector_id
    result = session.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'document_chunks' 
          AND column_name = 'vector_id'
    """)).fetchone()
    
    if result:
        logger.warning("⚠️  document_chunks.vector_id 仍然存在")
    else:
        logger.info("✓ document_chunks.vector_id 已删除")
    
    # 验证 listed_companies
    result = session.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'listed_companies' 
          AND column_name = 'id'
    """)).fetchone()
    
    if result:
        logger.warning("⚠️  listed_companies.id 仍然存在")
    else:
        logger.info("✓ listed_companies.id 已删除")
    
    result = session.execute(text("""
        SELECT constraint_name, constraint_type
        FROM information_schema.table_constraints
        WHERE table_name = 'listed_companies'
          AND constraint_type = 'PRIMARY KEY'
    """)).fetchone()
    
    if result:
        logger.info(f"✓ listed_companies 主键: {result[0]}")
    else:
        logger.warning("⚠️  listed_companies 没有主键")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="数据库 Schema 迁移工具")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="试运行模式（不实际执行，默认启用）"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制执行迁移（禁用试运行）"
    )
    parser.add_argument(
        "--skip-vector-id",
        action="store_true",
        help="跳过 vector_id 迁移"
    )
    parser.add_argument(
        "--skip-company-pk",
        action="store_true",
        help="跳过 company code 主键迁移"
    )
    
    args = parser.parse_args()
    
    dry_run = not args.force
    
    try:
        logger.info("=" * 80)
        logger.info("数据库 Schema 迁移工具")
        logger.info("=" * 80)
        logger.info(f"模式: {'DRY RUN (试运行)' if dry_run else '实际执行'}")
        logger.info("=" * 80)
        logger.info("")
        
        pg_client = get_postgres_client()
        
        with pg_client.get_session() as session:
            # 1. 迁移 vector_id
            if not args.skip_vector_id:
                success = migrate_vector_id(session, dry_run=dry_run)
                if not success and not dry_run:
                    logger.error("vector_id 迁移失败")
                    return 1
                logger.info("")
            
            # 2. 迁移 company code 主键
            if not args.skip_company_pk:
                success = migrate_company_code_pk(session, dry_run=dry_run)
                if not success and not dry_run:
                    logger.error("company code 主键迁移失败")
                    return 1
                logger.info("")
            
            # 3. 验证
            verify_migration(session)
        
        if dry_run:
            logger.info("")
            logger.info("=" * 80)
            logger.info("💡 提示:")
            logger.info("  这是试运行模式，没有实际执行迁移")
            logger.info("  要执行实际迁移，请运行:")
            logger.info("    python scripts/migrate_database_schema.py --force")
            logger.info("=" * 80)
        else:
            logger.info("")
            logger.info("=" * 80)
            logger.info("✅ 迁移完成！")
            logger.info("=" * 80)
        
        return 0
        
    except KeyboardInterrupt:
        logger.warning("\n操作已被用户中断")
        return 1
    except Exception as e:
        logger.error(f"迁移失败: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
