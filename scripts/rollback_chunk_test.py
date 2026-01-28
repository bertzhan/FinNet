#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回退 test_chunk_job_simple.py 测试产生的数据库更改

回退内容：
1. 删除 DocumentChunk 记录
2. 重置 ParsedDocument 的分块相关字段
3. 重置 Document 的 chunked_at 字段
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.storage.metadata.models import Document, ParsedDocument, DocumentChunk
from src.common.logger import get_logger

logger = get_logger(__name__)


def rollback_chunk_test(dry_run: bool = True, document_id: str = None, hours_back: int = 24):
    """
    回退分块测试的更改
    
    Args:
        dry_run: 如果为 True，只检查不回退；如果为 False，实际回退
        document_id: 指定要回退的文档ID（可选，如果不指定则查找最近分块的文档）
        hours_back: 查找最近多少小时内分块的文档（默认24小时）
    """
    logger.info("=" * 80)
    logger.info("回退分块测试的数据库更改")
    logger.info("=" * 80)
    logger.info(f"模式: {'[DRY RUN] 只检查，不回退' if dry_run else '[实际回退] 将删除分块数据'}")
    if document_id:
        logger.info(f"指定文档ID: {document_id}")
    else:
        logger.info(f"查找最近 {hours_back} 小时内分块的文档")
    logger.info("")
    
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 查找要回退的文档
            if document_id:
                # 使用指定的文档ID
                doc = crud.get_document_by_id(session, document_id)
                if not doc:
                    logger.error(f"文档不存在: document_id={document_id}")
                    return False
                docs_to_rollback = [doc]
            else:
                # 查找最近分块的文档
                cutoff_time = datetime.now() - timedelta(hours=hours_back)
                docs_to_rollback = session.query(Document).filter(
                    Document.chunked_at.isnot(None),
                    Document.chunked_at >= cutoff_time
                ).all()
            
            if not docs_to_rollback:
                logger.info("✅ 没有找到需要回退的文档")
                return True
            
            logger.info(f"找到 {len(docs_to_rollback)} 个需要回退的文档\n")
            
            # 显示详细信息
            for i, doc in enumerate(docs_to_rollback, 1):
                logger.info(f"文档 {i}:")
                logger.info(f"  - Document ID: {doc.id}")
                logger.info(f"  - 股票代码: {doc.stock_code}")
                logger.info(f"  - 公司名称: {doc.company_name}")
                logger.info(f"  - chunked_at: {doc.chunked_at}")
                
                # 查找 ParsedDocument
                parsed_doc = crud.get_latest_parsed_document(session, doc.id)
                if parsed_doc:
                    logger.info(f"  - ParsedDocument ID: {parsed_doc.id}")
                    logger.info(f"  - chunks_count: {parsed_doc.chunks_count}")
                    logger.info(f"  - structure_json_path: {parsed_doc.structure_json_path}")
                    logger.info(f"  - chunks_json_path: {parsed_doc.chunks_json_path}")
                    logger.info(f"  - chunked_at: {parsed_doc.chunked_at}")
                    
                    # 查找 DocumentChunk 数量
                    chunks = session.query(DocumentChunk).filter(
                        DocumentChunk.document_id == doc.id
                    ).all()
                    logger.info(f"  - DocumentChunk 记录数: {len(chunks)}")
                else:
                    logger.warning(f"  - ⚠️  未找到 ParsedDocument")
                
                logger.info("")
            
            if dry_run:
                logger.info("=" * 80)
                logger.info("⚠️  DRY RUN 模式：未进行实际回退")
                logger.info("=" * 80)
                logger.info("如果要实际回退，请运行:")
                logger.info(f"  python {Path(__file__).name} --rollback")
                if document_id:
                    logger.info(f"  python {Path(__file__).name} --rollback --document-id {document_id}")
            else:
                logger.info("开始回退...")
                rolled_back_count = 0
                failed_count = 0
                
                for doc in docs_to_rollback:
                    try:
                        # 1. 删除 DocumentChunk 记录
                        chunks_deleted = crud.delete_document_chunks(session, doc.id)
                        logger.info(f"✅ 已删除 {chunks_deleted} 个 DocumentChunk 记录: document_id={doc.id}")
                        
                        # 2. 重置 ParsedDocument 的分块相关字段
                        parsed_doc = crud.get_latest_parsed_document(session, doc.id)
                        if parsed_doc:
                            parsed_doc.structure_json_path = None
                            parsed_doc.chunks_json_path = None
                            parsed_doc.structure_json_hash = None
                            parsed_doc.chunks_json_hash = None
                            parsed_doc.chunks_count = 0
                            parsed_doc.chunked_at = None
                            session.flush()
                            logger.info(f"✅ 已重置 ParsedDocument 分块信息: parsed_document_id={parsed_doc.id}")
                        
                        # 3. 重置 Document 的 chunked_at
                        doc.chunked_at = None
                        session.flush()
                        logger.info(f"✅ 已重置 Document chunked_at: document_id={doc.id}")
                        
                        rolled_back_count += 1
                        
                    except Exception as e:
                        failed_count += 1
                        logger.error(f"❌ 回退失败: document_id={doc.id}, 错误: {e}", exc_info=True)
                
                # 提交事务
                session.commit()
                
                logger.info("")
                logger.info("=" * 80)
                logger.info("回退完成！")
                logger.info("=" * 80)
                logger.info(f"成功回退: {rolled_back_count} 个文档")
                logger.info(f"回退失败: {failed_count} 个文档")
                logger.info(f"总计: {len(docs_to_rollback)} 个文档")
                
                return True
                
    except Exception as e:
        logger.error(f"回退失败: {e}", exc_info=True)
        return False


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="回退分块测试的数据库更改")
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="实际回退（默认只检查不回退）"
    )
    parser.add_argument(
        "--document-id",
        type=str,
        default=None,
        help="指定要回退的文档ID（可选）"
    )
    parser.add_argument(
        "--hours-back",
        type=int,
        default=24,
        help="查找最近多少小时内分块的文档（默认24小时）"
    )
    
    args = parser.parse_args()
    
    try:
        success = rollback_chunk_test(
            dry_run=not args.rollback,
            document_id=args.document_id,
            hours_back=args.hours_back
        )
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"\n❌ 执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
