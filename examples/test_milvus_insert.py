#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 Milvus 向量插入
诊断向量维度和格式问题
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))


def test_milvus_insert():
    """测试 Milvus 向量插入"""
    print("=" * 80)
    print("Milvus 向量插入测试")
    print("=" * 80)
    print()
    
    # 1. 检查配置
    print("1. 检查配置...")
    from src.common.config import embedding_config
    
    embedding_mode = embedding_config.EMBEDDING_MODE
    embedding_dim = embedding_config.EMBEDDING_DIM
    
    print(f"   EMBEDDING_MODE: {embedding_mode}")
    print(f"   EMBEDDING_DIM: {embedding_dim}")
    print()
    
    # 2. 检查 Milvus Collection
    print("2. 检查 Milvus Collection...")
    try:
        from src.storage.vector.milvus_client import get_milvus_client
        from src.common.constants import MilvusCollection
        
        milvus_client = get_milvus_client()
        collection = milvus_client.get_collection(MilvusCollection.DOCUMENTS)
        
        if collection:
            print(f"✅ Collection 存在: {MilvusCollection.DOCUMENTS}")
            
            # 获取 Schema
            schema = collection.schema
            print(f"   Schema 字段:")
            for field in schema.fields:
                if field.name == "embedding":
                    print(f"     - {field.name}: {field.dtype}, dim={field.params.get('dim', 'N/A')}")
                else:
                    print(f"     - {field.name}: {field.dtype}")
            
            # 获取向量维度
            for field in schema.fields:
                if field.name == "embedding":
                    collection_dim = field.params.get('dim')
                    print(f"\n   Collection 向量维度: {collection_dim}")
                    if collection_dim != embedding_dim:
                        print(f"   ⚠️  警告: Collection 维度 ({collection_dim}) != 配置维度 ({embedding_dim})")
                    break
        else:
            print(f"❌ Collection 不存在: {MilvusCollection.DOCUMENTS}")
            return False
        
    except Exception as e:
        print(f"❌ Milvus 检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()
    
    # 3. 测试 Embedder
    print("3. 测试 Embedder...")
    try:
        from src.processing.ai.embedding.embedder_factory import get_embedder_by_mode
        
        embedder = get_embedder_by_mode()
        
        print(f"   Embedder 类型: {type(embedder).__name__}")
        print(f"   模型维度: {embedder.get_model_dim()}")
        
        # 测试单个文本
        test_text = "这是一个测试文本"
        vector = embedder.embed_text(test_text)
        
        print(f"   单个向量类型: {type(vector)}")
        print(f"   单个向量长度: {len(vector)}")
        print(f"   单个向量前5个值: {vector[:5]}")
        
        # 测试批量
        test_texts = ["文本1", "文本2", "文本3"]
        vectors = embedder.embed_batch(test_texts)
        
        print(f"\n   批量向量化:")
        print(f"   输入文本数: {len(test_texts)}")
        print(f"   返回类型: {type(vectors)}")
        print(f"   返回数量: {len(vectors)}")
        if vectors and len(vectors) > 0:
            print(f"   第一个向量类型: {type(vectors[0])}")
            print(f"   第一个向量长度: {len(vectors[0]) if hasattr(vectors[0], '__len__') else 'N/A'}")
            
            # 检查是否被展平
            if isinstance(vectors[0], (int, float)):
                print(f"   ❌ 向量被展平了！第一个元素是 {type(vectors[0])}")
            else:
                print(f"   ✅ 向量格式正确（二维列表）")
        
    except Exception as e:
        print(f"❌ Embedder 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()
    
    # 4. 测试 Milvus 插入
    print("4. 测试 Milvus 插入（小批量）...")
    try:
        import uuid
        
        # 生成测试数据
        num_test_vectors = 3
        test_vectors = embedder.embed_batch([f"测试文本{i}" for i in range(num_test_vectors)])
        
        # 验证向量格式
        print(f"   测试向量数量: {len(test_vectors)}")
        print(f"   测试向量类型: {type(test_vectors)}")
        if test_vectors and len(test_vectors) > 0:
            print(f"   第一个向量类型: {type(test_vectors[0])}")
            print(f"   第一个向量维度: {len(test_vectors[0]) if hasattr(test_vectors[0], '__len__') else 'N/A'}")
        
        # 生成测试 ID
        test_chunk_ids = [str(uuid.uuid4()) for _ in range(num_test_vectors)]
        test_document_ids = [str(uuid.uuid4()) for _ in range(num_test_vectors)]
        
        # 尝试插入
        print(f"\n   尝试插入 {num_test_vectors} 个测试向量...")
        
        vector_ids = milvus_client.insert_vectors(
            collection_name=MilvusCollection.DOCUMENTS,
            embeddings=test_vectors,
            document_ids=test_document_ids,
            chunk_ids=test_chunk_ids,
            stock_codes=["000001"] * num_test_vectors,
            company_names=["测试公司"] * num_test_vectors,
            doc_types=["test"] * num_test_vectors,
            years=[2024] * num_test_vectors,
            quarters=[1] * num_test_vectors
        )
        
        print(f"✅ 插入成功！返回 {len(vector_ids)} 个 ID")
        
        # 删除测试数据
        print(f"\n   清理测试数据...")
        collection.delete(f"chunk_id in {test_chunk_ids}")
        collection.flush()
        print(f"✅ 测试数据已清理")
        
    except Exception as e:
        print(f"❌ Milvus 插入测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()
    print("=" * 80)
    print("✅ 所有测试通过！")
    print("=" * 80)
    return True


def main():
    """主函数"""
    success = test_milvus_insert()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
