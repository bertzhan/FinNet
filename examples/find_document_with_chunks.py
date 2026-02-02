# -*- coding: utf-8 -*-
"""
查找指定条件的文档，并检查是否有chunks
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.storage.metadata import get_postgres_client, crud
from src.storage.metadata.models import Document
from sqlalchemy import desc
from src.common.logger import get_logger

logger = get_logger(__name__)


def find_document_with_chunks(
    stock_code: str,
    doc_type: str,
    year: int = None
):
    """查找指定条件的文档，并检查是否有chunks"""
    pg_client = get_postgres_client()
    
    print(f"\n{'='*60}")
    print(f"查找文档（有chunks）")
    print(f"{'='*60}")
    print(f"股票代码: {stock_code}")
    print(f"文档类型: {doc_type}")
    if year:
        print(f"年份: {year}")
    print()
    
    with pg_client.get_session() as session:
        # 构建查询
        query = session.query(Document).filter(
            Document.stock_code == stock_code,
            Document.doc_type == doc_type
        )
        
        if year:
            query = query.filter(Document.year == year)
        
        # 按创建时间倒序
        documents = query.order_by(desc(Document.created_at)).all()
        
        if not documents:
            print(f"⚠️  未找到匹配的文档")
            return None
        
        print(f"找到 {len(documents)} 个文档，检查chunks...\n")
        
        # 检查每个文档的chunks
        for i, doc in enumerate(documents, 1):
            chunks = crud.get_document_chunks(session, doc.id)
            chunks_count = len(chunks)
            
            status_icon = "✓" if chunks_count > 0 else "✗"
            
            print(f"{status_icon} {i}. Document ID: {doc.id}")
            print(f"   年份: {doc.year}, 季度: {doc.quarter or 'N/A'}")
            print(f"   状态: {doc.status}")
            print(f"   Chunks数量: {chunks_count}")
            
            if chunks_count > 0:
                print(f"   ✅ 有chunks，可用于测试")
                print()
                print(f"测试命令:")
                print(f"  python examples/test_document_chunks.py --document-id {doc.id}")
                print()
                return str(doc.id)
            print()
        
        print(f"⚠️  所有文档都没有chunks")
        return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="查找指定条件的文档（有chunks）")
    parser.add_argument(
        "--stock-code",
        type=str,
        default="000001",
        help="股票代码（默认: 000001）"
    )
    parser.add_argument(
        "--doc-type",
        type=str,
        default="annual_reports",
        help="文档类型（默认: annual_reports）"
    )
    parser.add_argument(
        "--year",
        type=int,
        help="年份（可选）"
    )
    
    args = parser.parse_args()
    
    try:
        doc_id = find_document_with_chunks(
            stock_code=args.stock_code,
            doc_type=args.doc_type,
            year=args.year
        )
        
        if doc_id:
            print(f"\n{'='*60}")
            print(f"推荐测试文档ID: {doc_id}")
            print(f"{'='*60}\n")
    except Exception as e:
        logger.error(f"查找失败: {e}", exc_info=True)
        sys.exit(1)
