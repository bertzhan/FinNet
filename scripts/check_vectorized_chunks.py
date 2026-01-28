#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检测已向量化的分块数量（通过查询 PostgreSQL）
这个脚本不依赖 Milvus，只查询 PostgreSQL 数据库中的元数据
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import DocumentChunk, Document
from sqlalchemy import func, and_, case, Integer


def check_vectorized_chunks():
    """检测已向量化的分块数量"""
    
    try:
        pg_client = get_postgres_client()
        
        with pg_client.get_session() as session:
            # 统计总分块数
            total_chunks = session.query(func.count(DocumentChunk.id)).scalar()
            
            # 统计已向量化的分块数（vectorized_at IS NOT NULL）
            vectorized_chunks = session.query(func.count(DocumentChunk.id)).filter(
                DocumentChunk.vectorized_at.isnot(None)
            ).scalar()
            
            # 统计未向量化的分块数（vectorized_at IS NULL）
            unvectorized_chunks = session.query(func.count(DocumentChunk.id)).filter(
                DocumentChunk.vectorized_at.is_(None)
            ).scalar()
            
            # 统计表格分块数量
            table_chunks_total = session.query(func.count(DocumentChunk.id)).filter(
                DocumentChunk.is_table == True
            ).scalar()
            
            table_chunks_vectorized = session.query(func.count(DocumentChunk.id)).filter(
                and_(DocumentChunk.is_table == True, DocumentChunk.vectorized_at.isnot(None))
            ).scalar()
            
            table_chunks_unvectorized = session.query(func.count(DocumentChunk.id)).filter(
                and_(DocumentChunk.is_table == True, DocumentChunk.vectorized_at.is_(None))
            ).scalar()
            
            # 统计文本分块数量（非表格）
            text_chunks_total = session.query(func.count(DocumentChunk.id)).filter(
                DocumentChunk.is_table == False
            ).scalar()
            
            text_chunks_vectorized = session.query(func.count(DocumentChunk.id)).filter(
                and_(DocumentChunk.is_table == False, DocumentChunk.vectorized_at.isnot(None))
            ).scalar()
            
            text_chunks_unvectorized = session.query(func.count(DocumentChunk.id)).filter(
                and_(DocumentChunk.is_table == False, DocumentChunk.vectorized_at.is_(None))
            ).scalar()
            
            # 按 embedding_model 统计
            model_stats = session.query(
                DocumentChunk.embedding_model,
                func.count(DocumentChunk.id).label('count')
            ).filter(
                DocumentChunk.vectorized_at.isnot(None)
            ).group_by(
                DocumentChunk.embedding_model
            ).all()
            
            # 按文档类型统计
            doc_type_stats = session.query(
                Document.doc_type,
                func.count(DocumentChunk.id).label('total'),
                func.sum(
                    case((DocumentChunk.vectorized_at.isnot(None), 1), else_=0)
                ).label('vectorized')
            ).join(
                Document, DocumentChunk.document_id == Document.id
            ).group_by(
                Document.doc_type
            ).all()
            
            # 按市场统计
            market_stats = session.query(
                Document.market,
                func.count(DocumentChunk.id).label('total'),
                func.sum(
                    case((DocumentChunk.vectorized_at.isnot(None), 1), else_=0)
                ).label('vectorized')
            ).join(
                Document, DocumentChunk.document_id == Document.id
            ).group_by(
                Document.market
            ).all()
            
            # 输出统计结果
            print("=" * 80)
            print("分块向量化统计（基于 PostgreSQL 元数据）")
            print("=" * 80)
            print()
            
            print("总体统计:")
            print(f"  总分块数:          {total_chunks:,}")
            print(f"  已向量化:          {vectorized_chunks:,} ({vectorized_chunks/total_chunks*100 if total_chunks > 0 else 0:.1f}%)")
            print(f"  未向量化:          {unvectorized_chunks:,} ({unvectorized_chunks/total_chunks*100 if total_chunks > 0 else 0:.1f}%)")
            print()
            
            print("按分块类型统计:")
            print(f"  文本分块总数:      {text_chunks_total:,}")
            print(f"    已向量化:        {text_chunks_vectorized:,} ({text_chunks_vectorized/text_chunks_total*100 if text_chunks_total > 0 else 0:.1f}%)")
            print(f"    未向量化:        {text_chunks_unvectorized:,} ({text_chunks_unvectorized/text_chunks_total*100 if text_chunks_total > 0 else 0:.1f}%)")
            print()
            print(f"  表格分块总数:      {table_chunks_total:,}")
            print(f"    已向量化:        {table_chunks_vectorized:,} ({table_chunks_vectorized/table_chunks_total*100 if table_chunks_total > 0 else 0:.1f}%)")
            print(f"    未向量化:        {table_chunks_unvectorized:,} ({table_chunks_unvectorized/table_chunks_total*100 if table_chunks_total > 0 else 0:.1f}%)")
            print()
            
            if model_stats:
                print("按 Embedding 模型统计:")
                for model, count in model_stats:
                    model_name = model if model else "(未指定)"
                    print(f"  {model_name}: {count:,}")
                print()
            
            if doc_type_stats:
                print("按文档类型统计:")
                for doc_type, total, vectorized in doc_type_stats:
                    vectorized = vectorized or 0
                    percentage = vectorized / total * 100 if total > 0 else 0
                    print(f"  {doc_type}:")
                    print(f"    总数: {total:,}, 已向量化: {vectorized:,} ({percentage:.1f}%)")
                print()
            
            if market_stats:
                print("按市场统计:")
                for market, total, vectorized in market_stats:
                    vectorized = vectorized or 0
                    percentage = vectorized / total * 100 if total > 0 else 0
                    print(f"  {market}:")
                    print(f"    总数: {total:,}, 已向量化: {vectorized:,} ({percentage:.1f}%)")
                print()
            
            # 数据库连接信息
            print("=" * 80)
            print("PostgreSQL 连接信息:")
            print(f"  连接 URL: {pg_client.database_url}")
            print("=" * 80)
            
            # 提示：如果要检查 Milvus 中的实际向量数量，需要使用另一个脚本
            if vectorized_chunks > 0:
                print()
                print("注意:")
                print("  - 以上统计基于 PostgreSQL 数据库中的 vectorized_at 字段")
                print("  - vectorized_at 不为 NULL 表示该分块已向量化并插入 Milvus")
                print("  - Milvus 使用 chunk_id 作为主键，无需单独的 vector_id 字段")
                print("  - 要检查 Milvus 中的实际向量数量，请运行:")
                print("    python scripts/check_milvus_vectors.py")
                print("=" * 80)
    
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    check_vectorized_chunks()
