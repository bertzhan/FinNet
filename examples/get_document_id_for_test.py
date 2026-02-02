# -*- coding: utf-8 -*-
"""
辅助脚本：从数据库获取document_id用于测试
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.storage.metadata import get_postgres_client, crud
from src.common.logger import get_logger

logger = get_logger(__name__)


def get_document_ids(limit: int = 10):
    """获取一些document_id用于测试"""
    pg_client = get_postgres_client()
    
    print(f"\n{'='*60}")
    print(f"从数据库获取Document ID用于测试")
    print(f"{'='*60}\n")
    
    with pg_client.get_session() as session:
        from src.storage.metadata.models import Document
        from sqlalchemy import desc
        
        # 获取最近的一些文档
        documents = session.query(Document).order_by(
            desc(Document.created_at)
        ).limit(limit).all()
        
        if not documents:
            print("⚠️  数据库中没有文档记录")
            return
        
        print(f"找到 {len(documents)} 个文档:\n")
        
        for i, doc in enumerate(documents, 1):
            # 检查是否有chunks
            chunks = crud.get_document_chunks(session, doc.id)
            chunks_count = len(chunks)
            
            print(f"{i}. Document ID: {doc.id}")
            print(f"   股票代码: {doc.stock_code}")
            print(f"   公司名称: {doc.company_name}")
            print(f"   文档类型: {doc.doc_type}")
            print(f"   年份: {doc.year}, 季度: {doc.quarter or 'N/A'}")
            print(f"   Chunks数量: {chunks_count}")
            print()
        
        # 推荐一个有chunks的文档
        doc_with_chunks = None
        for doc in documents:
            chunks = crud.get_document_chunks(session, doc.id)
            if len(chunks) > 0:
                doc_with_chunks = doc
                break
        
        if doc_with_chunks:
            print(f"\n{'='*60}")
            print(f"推荐测试文档（有chunks）:")
            print(f"{'='*60}")
            print(f"Document ID: {doc_with_chunks.id}")
            print(f"股票代码: {doc_with_chunks.stock_code}")
            print(f"公司名称: {doc_with_chunks.company_name}")
            print(f"文档类型: {doc_with_chunks.doc_type}")
            print(f"年份: {doc_with_chunks.year}, 季度: {doc_with_chunks.quarter or 'N/A'}")
            
            chunks = crud.get_document_chunks(session, doc_with_chunks.id)
            print(f"Chunks数量: {len(chunks)}")
            print()
            print(f"测试命令:")
            print(f"  python examples/test_document_chunks.py --document-id {doc_with_chunks.id}")
            print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="从数据库获取document_id用于测试")
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="返回的文档数量（默认: 10）"
    )
    
    args = parser.parse_args()
    
    try:
        get_document_ids(limit=args.limit)
    except Exception as e:
        logger.error(f"获取document_id失败: {e}", exc_info=True)
        sys.exit(1)
