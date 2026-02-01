# -*- coding: utf-8 -*-
"""
检查股票代码对应的公司名称
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud


def check_stock_code(stock_code: str):
    """检查股票代码对应的公司名称"""
    print(f"=" * 60)
    print(f"检查股票代码: {stock_code}")
    print(f"=" * 60)
    
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 1. 检查 listed_companies 表
            print("\n1. 检查 listed_companies 表:")
            company = crud.get_listed_company_by_code(session, stock_code)
            if company:
                print(f"   ✅ 找到: {company.code} - {company.name}")
            else:
                print(f"   ❌ 未找到")
            
            # 2. 检查 documents 表
            print("\n2. 检查 documents 表:")
            from src.storage.metadata.models import Document
            documents = session.query(Document).filter(
                Document.stock_code == stock_code
            ).limit(5).all()
            
            if documents:
                print(f"   ✅ 找到 {len(documents)} 个文档:")
                company_names = set()
                for doc in documents:
                    company_names.add(doc.company_name or "未知")
                    print(f"      - {doc.company_name} ({doc.stock_code}) - {doc.doc_type}")
                print(f"\n   公司名称集合: {company_names}")
            else:
                print(f"   ❌ 未找到文档")
            
            # 3. 检查 document_chunks 表
            print("\n3. 检查 document_chunks 表:")
            from src.storage.metadata.models import DocumentChunk
            chunks = session.query(DocumentChunk).join(
                Document, DocumentChunk.document_id == Document.id
            ).filter(
                Document.stock_code == stock_code
            ).limit(5).all()
            
            if chunks:
                print(f"   ✅ 找到 {len(chunks)} 个分块")
                company_names = set()
                for chunk in chunks:
                    doc = chunk.document
                    company_names.add(doc.company_name or "未知")
                print(f"   公司名称集合: {company_names}")
            else:
                print(f"   ❌ 未找到分块")
                
    except Exception as e:
        print(f"\n❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="检查股票代码对应的公司名称")
    parser.add_argument("--stock-code", type=str, required=True, help="股票代码")
    args = parser.parse_args()
    
    check_stock_code(args.stock_code)
