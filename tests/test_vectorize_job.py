# -*- coding: utf-8 -*-
"""
向量化作业测试
测试向量化服务的各个组件和完整流程
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.processing.ai.embedding.bge_embedder import get_embedder
from src.processing.ai.embedding.vectorizer import get_vectorizer
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.storage.metadata.models import DocumentChunk, Document
from src.storage.vector.milvus_client import get_milvus_client
from src.common.constants import MilvusCollection


def test_embedder():
    """测试 Embedder 服务"""
    print("=" * 60)
    print("1. 测试 BGE Embedder 服务")
    print("=" * 60)
    print()
    
    try:
        embedder = get_embedder()
        print(f"✅ Embedder 初始化成功")
        print(f"   模型名称: {embedder.get_model_name()}")
        print(f"   向量维度: {embedder.get_model_dim()}")
        print()
        
        # 测试单个文本向量化
        test_text = "这是一个测试文本"
        print(f"测试单个文本向量化: '{test_text}'")
        vector = embedder.embed_text(test_text)
        print(f"✅ 向量化成功，维度: {len(vector)}")
        print(f"   前5个值: {vector[:5]}")
        print()
        
        # 测试批量向量化
        test_texts = [
            "这是第一个测试文本",
            "这是第二个测试文本",
            "这是第三个测试文本"
        ]
        print(f"测试批量向量化: {len(test_texts)} 个文本")
        vectors = embedder.embed_batch(test_texts)
        print(f"✅ 批量向量化成功，返回 {len(vectors)} 个向量")
        print(f"   每个向量维度: {len(vectors[0]) if vectors else 0}")
        print()
        
        return True
    except Exception as e:
        print(f"❌ Embedder 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_unvectorized_chunks():
    """检查未向量化的分块"""
    print("=" * 60)
    print("2. 检查未向量化的分块")
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
                print(f"      text_preview={chunk.chunk_text[:50]}...")
                print()
            
            return chunks
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
        return []


def test_vectorizer_single(chunk_ids):
    """测试向量化单个分块"""
    print("=" * 60)
    print("3. 测试向量化单个分块")
    print("=" * 60)
    print()
    
    if not chunk_ids:
        print("⚠️  没有可测试的分块，跳过")
        return False
    
    try:
        vectorizer = get_vectorizer()
        print(f"✅ Vectorizer 初始化成功")
        print()
        
        # 测试向量化单个分块
        test_chunk_id = chunk_ids[0].id
        print(f"测试向量化分块: {test_chunk_id}")
        
        result = vectorizer.vectorize_chunks([test_chunk_id])
        
        print(f"✅ 向量化完成")
        print(f"   成功数量: {result.get('vectorized_count', 0)}")
        print(f"   失败数量: {result.get('failed_count', 0)}")
        print(f"   失败分块: {result.get('failed_chunks', [])}")
        print()
        
        # 验证数据库更新
        pg_client = get_postgres_client()
        with pg_client.get_session() as session:
            chunk = session.query(DocumentChunk).filter(
                DocumentChunk.id == test_chunk_id
            ).first()
            
            if chunk and chunk.vector_id:
                print(f"✅ 数据库更新成功")
                print(f"   vector_id: {chunk.vector_id}")
                print(f"   embedding_model: {chunk.embedding_model}")
                print(f"   vectorized_at: {chunk.vectorized_at}")
            else:
                print(f"⚠️  数据库未更新（可能向量化失败）")
        print()
        
        return result.get('vectorized_count', 0) > 0
    except Exception as e:
        print(f"❌ 向量化测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vectorizer_batch(chunk_ids):
    """测试批量向量化"""
    print("=" * 60)
    print("4. 测试批量向量化")
    print("=" * 60)
    print()
    
    if not chunk_ids or len(chunk_ids) < 2:
        print("⚠️  分块数量不足，跳过批量测试")
        return False
    
    try:
        vectorizer = get_vectorizer()
        
        # 测试批量向量化（最多5个）
        test_chunk_ids = [chunk.id for chunk in chunk_ids[:5]]
        print(f"测试批量向量化: {len(test_chunk_ids)} 个分块")
        
        result = vectorizer.vectorize_chunks(test_chunk_ids)
        
        print(f"✅ 批量向量化完成")
        print(f"   成功数量: {result.get('vectorized_count', 0)}")
        print(f"   失败数量: {result.get('failed_count', 0)}")
        print(f"   失败分块: {result.get('failed_chunks', [])}")
        print()
        
        return result.get('vectorized_count', 0) > 0
    except Exception as e:
        print(f"❌ 批量向量化测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_milvus_collection():
    """测试 Milvus Collection"""
    print("=" * 60)
    print("5. 测试 Milvus Collection")
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
        else:
            print(f"⚠️  Collection 不存在: {collection_name}")
            print(f"   Vectorizer 会在首次使用时自动创建")
            print()
        
        return True
    except Exception as e:
        print(f"❌ Milvus Collection 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dagster_ops():
    """测试 Dagster Ops"""
    print("=" * 60)
    print("6. 测试 Dagster 向量化 Ops")
    print("=" * 60)
    print()
    
    try:
        from src.processing.compute.dagster.jobs.vectorize_jobs import (
            scan_unvectorized_chunks_op,
            vectorize_chunks_op,
            validate_vectorize_results_op,
        )
        from dagster import build_op_context
        
        # 测试 scan_op
        print("测试 scan_unvectorized_chunks_op...")
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
        else:
            print(f"⚠️  扫描失败: {scan_result.get('error_message')}")
        print()
        
        # 如果有分块，测试向量化
        if scan_result.get("success") and scan_result.get("total_chunks", 0) > 0:
            print("测试 vectorize_chunks_op...")
            context = build_op_context(
                config={
                    "force_revectorize": False,
                }
            )
            vectorize_result = vectorize_chunks_op(context, scan_result)
            
            if vectorize_result.get("success"):
                print(f"✅ 向量化成功")
                print(f"   成功数量: {vectorize_result.get('vectorized_count', 0)}")
                print(f"   失败数量: {vectorize_result.get('failed_count', 0)}")
            else:
                print(f"⚠️  向量化失败: {vectorize_result.get('error_message')}")
            print()
            
            # 测试验证
            print("测试 validate_vectorize_results_op...")
            context = build_op_context()
            validate_result = validate_vectorize_results_op(context, vectorize_result)
            
            if validate_result.get("success"):
                print(f"✅ 验证完成")
                print(f"   验证通过: {validate_result.get('validation_passed', False)}")
                print(f"   成功率: {validate_result.get('success_rate', 0):.2%}")
            print()
        else:
            print("⚠️  没有分块可测试，跳过向量化 Op 测试")
        print()
        
        return True
    except Exception as e:
        print(f"❌ Dagster Ops 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("向量化作业测试")
    print("=" * 60)
    print()
    
    results = []
    
    # 1. 测试 Embedder
    results.append(("Embedder 服务", test_embedder()))
    
    # 2. 检查未向量化的分块
    chunks = check_unvectorized_chunks()
    
    # 3. 测试 Milvus Collection
    results.append(("Milvus Collection", test_milvus_collection()))
    
    # 4. 测试向量化单个分块
    if chunks:
        results.append(("单个分块向量化", test_vectorizer_single(chunks)))
    
    # 5. 测试批量向量化
    if chunks and len(chunks) >= 2:
        results.append(("批量向量化", test_vectorizer_batch(chunks)))
    
    # 6. 测试 Dagster Ops
    results.append(("Dagster Ops", test_dagster_ops()))
    
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


if __name__ == "__main__":
    main()
