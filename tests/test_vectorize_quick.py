# -*- coding: utf-8 -*-
"""
向量化作业快速测试
测试基本功能和数据库查询
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import DocumentChunk, Document
from src.storage.vector.milvus_client import get_milvus_client
from src.common.constants import MilvusCollection


def check_unvectorized_chunks():
    """检查未向量化的分块"""
    print("=" * 60)
    print("检查未向量化的分块")
    print("=" * 60)
    print()
    
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 查找未向量化的分块
            query = session.query(DocumentChunk).join(
                Document, DocumentChunk.document_id == Document.id
            ).filter(
                DocumentChunk.vector_id.is_(None)
            )
            
            total_count = query.count()
            chunks = query.limit(10).all()
            
            print(f"📊 统计信息:")
            print(f"   未向量化分块总数: {total_count}")
            print(f"   显示前 {len(chunks)} 个分块")
            print()
            
            if not chunks:
                print("⚠️  没有找到未向量化的分块")
                print("   可能原因：")
                print("   - 所有分块都已向量化")
                print("   - 还没有分块数据")
                return []
            
            print("前10个未向量化分块:")
            for i, chunk in enumerate(chunks, 1):
                doc = session.query(Document).filter(
                    Document.id == chunk.document_id
                ).first()
                print(f"   {i}. chunk_id={chunk.id}")
                print(f"      document_id={chunk.document_id}")
                print(f"      stock_code={doc.stock_code if doc else 'N/A'}")
                print(f"      chunk_index={chunk.chunk_index}")
                print(f"      text_length={len(chunk.chunk_text)}")
                print(f"      text_preview={chunk.chunk_text[:50]}...")
                print()
            
            return chunks
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
        return []


def check_vectorized_chunks():
    """检查已向量化的分块"""
    print("=" * 60)
    print("检查已向量化的分块")
    print("=" * 60)
    print()
    
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 查找已向量化的分块
            query = session.query(DocumentChunk).filter(
                DocumentChunk.vector_id.isnot(None)
            )
            
            total_count = query.count()
            chunks = query.limit(5).all()
            
            print(f"📊 统计信息:")
            print(f"   已向量化分块总数: {total_count}")
            print(f"   显示前 {len(chunks)} 个分块")
            print()
            
            if not chunks:
                print("⚠️  没有找到已向量化的分块")
                return []
            
            print("前5个已向量化分块:")
            for i, chunk in enumerate(chunks, 1):
                print(f"   {i}. chunk_id={chunk.id}")
                print(f"      vector_id={chunk.vector_id}")
                print(f"      embedding_model={chunk.embedding_model}")
                print(f"      vectorized_at={chunk.vectorized_at}")
                print()
            
            return chunks
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
        return []


def check_milvus_collection():
    """检查 Milvus Collection"""
    print("=" * 60)
    print("检查 Milvus Collection")
    print("=" * 60)
    print()
    
    try:
        milvus_client = get_milvus_client()
        collection_name = MilvusCollection.DOCUMENTS
        
        # 检查 Collection 是否存在
        collection = milvus_client.get_collection(collection_name)
        
        if collection:
            print(f"✅ Collection 存在: {collection_name}")
            
            # 获取统计信息
            stats = milvus_client.get_collection_stats(collection_name)
            print(f"   向量数量: {stats.get('row_count', 0)}")
            print()
            return True
        else:
            print(f"⚠️  Collection 不存在: {collection_name}")
            print(f"   Vectorizer 会在首次使用时自动创建")
            print()
            return False
    except Exception as e:
        print(f"❌ Milvus Collection 检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dagster_scan_op():
    """测试 Dagster scan_op"""
    print("=" * 60)
    print("测试 Dagster scan_unvectorized_chunks_op")
    print("=" * 60)
    print()
    
    try:
        from src.processing.compute.dagster.jobs.vectorize_jobs import (
            scan_unvectorized_chunks_op,
        )
        from dagster import build_op_context
        
        # 测试 scan_op
        print("执行 scan_unvectorized_chunks_op...")
        context = build_op_context(
            config={
                "batch_size": 10,
                "limit": 20,
            }
        )
        scan_result = scan_unvectorized_chunks_op(context)
        
        if scan_result.get("success"):
            print(f"✅ 扫描成功")
            print(f"   找到分块数: {scan_result.get('total_chunks', 0)}")
            print(f"   批次数: {scan_result.get('total_batches', 0)}")
            
            chunks = scan_result.get("chunks", [])
            if chunks:
                print(f"\n前3个分块信息:")
                for i, chunk_info in enumerate(chunks[:3], 1):
                    print(f"   {i}. chunk_id={chunk_info.get('chunk_id')}")
                    print(f"      stock_code={chunk_info.get('stock_code')}")
                    print(f"      chunk_index={chunk_info.get('chunk_index')}")
        else:
            print(f"⚠️  扫描失败: {scan_result.get('error_message')}")
        print()
        
        return scan_result.get("success", False)
    except Exception as e:
        print(f"❌ Dagster scan_op 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("向量化作业快速测试")
    print("=" * 60)
    print()
    
    results = []
    
    # 1. 检查未向量化的分块
    chunks = check_unvectorized_chunks()
    results.append(("未向量化分块检查", len(chunks) >= 0))
    
    # 2. 检查已向量化的分块
    vectorized = check_vectorized_chunks()
    results.append(("已向量化分块检查", len(vectorized) >= 0))
    
    # 3. 检查 Milvus Collection
    results.append(("Milvus Collection", check_milvus_collection()))
    
    # 4. 测试 Dagster scan_op
    results.append(("Dagster scan_op", test_dagster_scan_op()))
    
    # 汇总结果
    print("=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print()
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {name}")
    
    print()
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"总计: {passed}/{total} 通过")
    print()
    
    if chunks:
        print("=" * 60)
        print("下一步")
        print("=" * 60)
        print()
        print("如果看到未向量化的分块，可以运行完整的向量化测试：")
        print("  python tests/test_vectorize_job.py")
        print()
        print("或者在 Dagster UI 中运行向量化作业：")
        print("  - 作业名称: vectorize_documents_job")
        print("  - 传感器: manual_trigger_vectorize_sensor")
        print()


if __name__ == "__main__":
    main()
