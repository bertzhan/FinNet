#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查已解析的文档（包括已分块和未分块的）
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import Document, ParsedDocument


def main():
    """检查已解析的文档"""
    print("=" * 80)
    print("检查已解析的文档")
    print("=" * 80)
    
    pg_client = get_postgres_client()
    
    with pg_client.get_session() as session:
        # 查找所有有 markdown_path 的文档（包括已分块和未分块的）
        query = session.query(ParsedDocument).join(
            Document, ParsedDocument.document_id == Document.id
        ).filter(
            ParsedDocument.markdown_path.isnot(None),
            ParsedDocument.markdown_path != ""
        )
        
        all_parsed = query.limit(20).all()
        
        if not all_parsed:
            print("❌ 没有找到已解析的文档（markdown_path 不为空）")
            return
        
        print(f"✅ 找到 {len(all_parsed)} 个已解析的文档（最多显示20个）\n")
        
        chunked_count = 0
        pending_count = 0
        
        for i, parsed_doc in enumerate(all_parsed, 1):
            doc = session.query(Document).filter(
                Document.id == parsed_doc.document_id
            ).first()
            
            if doc:
                is_chunked = parsed_doc.chunks_count > 0
                status = "✅ 已分块" if is_chunked else "⏳ 待分块"
                
                if is_chunked:
                    chunked_count += 1
                else:
                    pending_count += 1
                
                print(f"{i}. {status}")
                print(f"   Document ID: {doc.id}")
                print(f"   股票代码: {doc.stock_code}")
                print(f"   公司名称: {doc.company_name}")
                print(f"   市场: {doc.market}, 类型: {doc.doc_type}")
                print(f"   Markdown 路径: {parsed_doc.markdown_path}")
                print(f"   Chunks Count: {parsed_doc.chunks_count}")
                if is_chunked:
                    print(f"   分块时间: {parsed_doc.chunked_at}")
                    print(f"   Structure Path: {parsed_doc.structure_json_path}")
                    print(f"   Chunks Path: {parsed_doc.chunks_json_path}")
                print()
        
        print("=" * 80)
        print(f"统计: 已分块={chunked_count}, 待分块={pending_count}, 总计={len(all_parsed)}")
        print("=" * 80)
        
        if chunked_count > 0:
            print("\n💡 提示：如果要强制重新分块已分块的文档，需要在 Dagster UI 中设置：")
            print("   scan_parsed_documents_op.config.force_rechunk = True")
            print("   doc_chunk_op.config.force_rechunk = True")


if __name__ == "__main__":
    main()
