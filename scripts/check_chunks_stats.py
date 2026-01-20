#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查看 document_chunks 表统计信息
显示分块数量、向量化状态等
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import DocumentChunk, Document
from sqlalchemy import func


def main():
    """主函数"""
    print("=" * 60)
    print("DocumentChunks 表统计信息")
    print("=" * 60)
    print()
    
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 总分块数
            total_chunks = session.query(func.count(DocumentChunk.id)).scalar()
            print(f"📊 总分块数: {total_chunks:,}")
            print()
            
            # 未向量化分块数
            unvectorized = session.query(func.count(DocumentChunk.id)).filter(
                DocumentChunk.vector_id.is_(None)
            ).scalar()
            print(f"⏰ 未向量化分块数: {unvectorized:,}")
            
            # 已向量化分块数
            vectorized = session.query(func.count(DocumentChunk.id)).filter(
                DocumentChunk.vector_id.isnot(None)
            ).scalar()
            print(f"✅ 已向量化分块数: {vectorized:,}")
            
            if total_chunks > 0:
                vectorized_rate = (vectorized / total_chunks) * 100
                print(f"📈 向量化率: {vectorized_rate:.2f}%")
            print()
            
            # 按文档统计
            print("=" * 60)
            print("按文档统计")
            print("=" * 60)
            print()
            
            # 有分块的文档数
            docs_with_chunks = session.query(func.count(func.distinct(DocumentChunk.document_id))).scalar()
            print(f"📄 有分块的文档数: {docs_with_chunks:,}")
            
            # 平均每个文档的分块数
            if docs_with_chunks > 0:
                avg_chunks = total_chunks / docs_with_chunks
                print(f"📊 平均每个文档的分块数: {avg_chunks:.2f}")
            print()
            
            # 按市场统计
            print("=" * 60)
            print("按市场统计")
            print("=" * 60)
            print()
            
            market_stats = session.query(
                Document.market,
                func.count(DocumentChunk.id).label('chunk_count')
            ).join(
                DocumentChunk, Document.id == DocumentChunk.document_id
            ).group_by(Document.market).all()
            
            for market, count in market_stats:
                print(f"  {market}: {count:,} 个分块")
            print()
            
            # 按文档类型统计
            print("=" * 60)
            print("按文档类型统计")
            print("=" * 60)
            print()
            
            doc_type_stats = session.query(
                Document.doc_type,
                func.count(DocumentChunk.id).label('chunk_count')
            ).join(
                DocumentChunk, Document.id == DocumentChunk.document_id
            ).group_by(Document.doc_type).all()
            
            for doc_type, count in doc_type_stats:
                print(f"  {doc_type}: {count:,} 个分块")
            print()
            
            # 向量化状态详情
            if vectorized > 0:
                print("=" * 60)
                print("向量化详情")
                print("=" * 60)
                print()
                
                # 按模型统计
                model_stats = session.query(
                    DocumentChunk.embedding_model,
                    func.count(DocumentChunk.id).label('count')
                ).filter(
                    DocumentChunk.embedding_model.isnot(None)
                ).group_by(DocumentChunk.embedding_model).all()
                
                print("使用的 Embedding 模型:")
                for model, count in model_stats:
                    print(f"  {model}: {count:,} 个分块")
                print()
            
            # 最近向量化的分块
            if vectorized > 0:
                print("=" * 60)
                print("最近向量化的分块（前5个）")
                print("=" * 60)
                print()
                
                recent_chunks = session.query(DocumentChunk).filter(
                    DocumentChunk.vectorized_at.isnot(None)
                ).order_by(
                    DocumentChunk.vectorized_at.desc()
                ).limit(5).all()
                
                for i, chunk in enumerate(recent_chunks, 1):
                    doc = session.query(Document).filter(
                        Document.id == chunk.document_id
                    ).first()
                    print(f"{i}. chunk_id={chunk.id}")
                    print(f"   document_id={chunk.document_id}")
                    print(f"   stock_code={doc.stock_code if doc else 'N/A'}")
                    print(f"   vector_id={chunk.vector_id}")
                    print(f"   embedding_model={chunk.embedding_model}")
                    print(f"   vectorized_at={chunk.vectorized_at}")
                    print()
            
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("=" * 60)
    print("查询完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
