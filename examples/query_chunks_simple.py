#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单查询 document_chunks 表
快速查看分块数量
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import DocumentChunk
from sqlalchemy import func


def main():
    """主函数"""
    print("查询 document_chunks 表...")
    print()
    
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 总分块数
            total = session.query(func.count(DocumentChunk.id)).scalar()
            print(f"✅ 总分块数: {total:,}")
            
            # 未向量化
            unvectorized = session.query(func.count(DocumentChunk.id)).filter(
                DocumentChunk.vector_id.is_(None)
            ).scalar()
            print(f"⏰ 未向量化: {unvectorized:,}")
            
            # 已向量化
            vectorized = session.query(func.count(DocumentChunk.id)).filter(
                DocumentChunk.vector_id.isnot(None)
            ).scalar()
            print(f"✅ 已向量化: {vectorized:,}")
            
            if total > 0:
                rate = (vectorized / total) * 100
                print(f"📈 向量化率: {rate:.2f}%")
            
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
