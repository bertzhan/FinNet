# -*- coding: utf-8 -*-
"""
添加 documents 表的 chunked_at 和 graphed_at 字段
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


def add_chunked_and_graphed_at_columns():
    """添加 chunked_at 和 graphed_at 字段到 documents 表"""
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 检查字段是否已存在
            check_sql = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'documents' 
                    AND column_name IN ('chunked_at', 'graphed_at')
            """)
            result = session.execute(check_sql)
            existing_columns = {row[0] for row in result.fetchall()}
            
            # 添加 chunked_at 字段
            if 'chunked_at' not in existing_columns:
                logger.info("正在添加 chunked_at 字段...")
                session.execute(text("""
                    ALTER TABLE documents
                        ADD COLUMN chunked_at TIMESTAMP
                """))
                logger.info("✅ chunked_at 字段添加成功")
            else:
                logger.info("✅ chunked_at 字段已存在，跳过添加")
            
            # 添加 graphed_at 字段
            if 'graphed_at' not in existing_columns:
                logger.info("正在添加 graphed_at 字段...")
                session.execute(text("""
                    ALTER TABLE documents
                        ADD COLUMN graphed_at TIMESTAMP
                """))
                logger.info("✅ graphed_at 字段添加成功")
            else:
                logger.info("✅ graphed_at 字段已存在，跳过添加")
            
            # 添加注释
            logger.info("正在添加字段注释...")
            try:
                session.execute(text("""
                    COMMENT ON COLUMN documents.chunked_at IS '分块完成时间（文档分块处理完成的时间戳）'
                """))
                logger.info("✅ chunked_at 注释添加成功")
            except Exception as e:
                logger.warning(f"添加 chunked_at 注释失败（可能已存在）: {e}")
            
            try:
                session.execute(text("""
                    COMMENT ON COLUMN documents.graphed_at IS '图构建完成时间（文档图结构构建完成的时间戳）'
                """))
                logger.info("✅ graphed_at 注释添加成功")
            except Exception as e:
                logger.warning(f"添加 graphed_at 注释失败（可能已存在）: {e}")
            
            session.commit()
            
            # 验证
            result = session.execute(check_sql)
            final_columns = {row[0] for row in result.fetchall()}
            
            if 'chunked_at' in final_columns and 'graphed_at' in final_columns:
                logger.info("✅ 验证通过：chunked_at 和 graphed_at 字段已存在")
                return True
            else:
                missing = {'chunked_at', 'graphed_at'} - final_columns
                logger.error(f"❌ 验证失败：以下字段未找到: {missing}")
                return False
                
    except Exception as e:
        logger.error(f"❌ 添加字段失败: {e}", exc_info=True)
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("添加 documents 表的 chunked_at 和 graphed_at 字段")
    print("=" * 60)
    
    success = add_chunked_and_graphed_at_columns()
    
    if success:
        print("\n✅ 迁移完成！")
        sys.exit(0)
    else:
        print("\n❌ 迁移失败！")
        sys.exit(1)


if __name__ == '__main__':
    main()
