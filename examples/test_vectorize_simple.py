#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的向量化测试脚本
直接测试向量化功能，不依赖复杂配置
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

# 设置环境变量（如果.env文件有权限问题）
# 这些值可以从实际配置中获取
os.environ.setdefault('PROJECT_ROOT', str(project_root))


def test_embedder_basic():
    """测试 Embedder 基本功能"""
    print("=" * 60)
    print("测试 BGE Embedder")
    print("=" * 60)
    print()
    
    try:
        from src.processing.ai.embedding.bge_embedder import get_embedder
        
        print("正在初始化 Embedder...")
        embedder = get_embedder()
        
        print(f"✅ Embedder 初始化成功")
        print(f"   模型名称: {embedder.get_model_name()}")
        print(f"   向量维度: {embedder.get_model_dim()}")
        print()
        
        # 测试单个文本
        print("测试单个文本向量化...")
        test_text = "这是一个测试文本，用于验证向量化功能是否正常工作。"
        vector = embedder.embed_text(test_text)
        print(f"✅ 向量化成功")
        print(f"   文本长度: {len(test_text)} 字符")
        print(f"   向量维度: {len(vector)}")
        print(f"   向量前5个值: {vector[:5]}")
        print()
        
        # 测试批量向量化
        print("测试批量向量化...")
        test_texts = [
            "这是第一个测试文本",
            "这是第二个测试文本",
            "这是第三个测试文本",
            "这是第四个测试文本",
            "这是第五个测试文本",
        ]
        vectors = embedder.embed_batch(test_texts)
        print(f"✅ 批量向量化成功")
        print(f"   输入文本数: {len(test_texts)}")
        print(f"   输出向量数: {len(vectors)}")
        print(f"   每个向量维度: {len(vectors[0]) if vectors else 0}")
        print()
        
        return True
    except Exception as e:
        print(f"❌ Embedder 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vectorizer_basic():
    """测试 Vectorizer 基本功能"""
    print("=" * 60)
    print("测试 Vectorizer")
    print("=" * 60)
    print()
    
    try:
        from src.processing.ai.embedding.vectorizer import get_vectorizer
        from src.storage.metadata.postgres_client import get_postgres_client
        from src.storage.metadata.models import DocumentChunk
        
        print("正在初始化 Vectorizer...")
        vectorizer = get_vectorizer()
        print(f"✅ Vectorizer 初始化成功")
        print()
        
        # 查找未向量化的分块
        print("查找未向量化的分块...")
        pg_client = get_postgres_client()
        with pg_client.get_session() as session:
            chunks = session.query(DocumentChunk).filter(
                DocumentChunk.vector_id.is_(None)
            ).limit(3).all()
            
            if not chunks:
                print("⚠️  没有找到未向量化的分块")
                print("   所有分块都已向量化，或还没有分块数据")
                return True
            
            print(f"✅ 找到 {len(chunks)} 个未向量化的分块")
            chunk_ids = [chunk.id for chunk in chunks]
            print(f"   分块IDs: {[str(cid) for cid in chunk_ids[:3]]}")
            print()
            
            # 测试向量化
            print("测试向量化这些分块...")
            result = vectorizer.vectorize_chunks(chunk_ids)
            
            print(f"✅ 向量化完成")
            print(f"   成功数量: {result.get('vectorized_count', 0)}")
            print(f"   失败数量: {result.get('failed_count', 0)}")
            if result.get('failed_chunks'):
                print(f"   失败分块: {result.get('failed_chunks')}")
            print()
            
            # 验证数据库更新
            print("验证数据库更新...")
            updated_chunks = session.query(DocumentChunk).filter(
                DocumentChunk.id.in_(chunk_ids),
                DocumentChunk.vector_id.isnot(None)
            ).all()
            
            print(f"✅ 数据库更新验证")
            print(f"   已更新分块数: {len(updated_chunks)}")
            for chunk in updated_chunks[:2]:
                print(f"   - chunk_id={chunk.id}, vector_id={chunk.vector_id}, model={chunk.embedding_model}")
            print()
            
            return True
    except Exception as e:
        print(f"❌ Vectorizer 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_milvus_basic():
    """测试 Milvus 基本功能"""
    print("=" * 60)
    print("测试 Milvus")
    print("=" * 60)
    print()
    
    try:
        from src.storage.vector.milvus_client import get_milvus_client
        from src.common.constants import MilvusCollection
        
        print("正在连接 Milvus...")
        milvus_client = get_milvus_client()
        collection_name = MilvusCollection.DOCUMENTS
        
        # 检查 Collection
        collection = milvus_client.get_collection(collection_name)
        
        if collection:
            print(f"✅ Collection 存在: {collection_name}")
            stats = milvus_client.get_collection_stats(collection_name)
            print(f"   向量数量: {stats.get('row_count', 0)}")
        else:
            print(f"⚠️  Collection 不存在: {collection_name}")
            print(f"   Vectorizer 会在首次使用时自动创建")
        
        print()
        return True
    except Exception as e:
        print(f"❌ Milvus 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("向量化功能简单测试")
    print("=" * 60)
    print()
    
    results = []
    
    # 1. 测试 Embedder
    print("开始测试 Embedder...")
    results.append(("Embedder", test_embedder_basic()))
    print()
    
    # 2. 测试 Milvus
    print("开始测试 Milvus...")
    results.append(("Milvus", test_milvus_basic()))
    print()
    
    # 3. 测试 Vectorizer
    print("开始测试 Vectorizer...")
    results.append(("Vectorizer", test_vectorizer_basic()))
    print()
    
    # 汇总
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
    
    if passed == total:
        print("✅ 所有测试通过！向量化功能正常工作")
    else:
        print("⚠️  部分测试未通过，请检查错误信息")
    print()


if __name__ == "__main__":
    main()
