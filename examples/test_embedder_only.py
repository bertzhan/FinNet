#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
仅测试 Embedder 功能（不依赖 Milvus）
直接测试 BGE Embedder，避免导入 vectorizer
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))


def test_imports():
    """测试依赖导入"""
    print("=" * 60)
    print("1. 测试依赖导入")
    print("=" * 60)
    print()
    
    try:
        import torch
        print(f"✅ PyTorch: {torch.__version__}")
    except ImportError as e:
        print(f"❌ PyTorch 导入失败: {e}")
        return False
    
    try:
        import transformers
        print(f"✅ Transformers: {transformers.__version__}")
    except ImportError as e:
        print(f"❌ Transformers 导入失败: {e}")
        return False
    
    try:
        import sentence_transformers
        print(f"✅ Sentence-Transformers: {sentence_transformers.__version__}")
    except ImportError as e:
        print(f"❌ Sentence-Transformers 导入失败: {e}")
        return False
    
    print()
    return True


def test_embedder_init():
    """测试 Embedder 初始化"""
    print("=" * 60)
    print("2. 测试 Embedder 初始化")
    print("=" * 60)
    print()
    
    try:
        # 直接导入 BGEEmbedder，避免导入 vectorizer（需要 pymilvus）
        from src.processing.ai.embedding.bge_embedder import BGEEmbedder
        
        print("正在初始化 Embedder（首次会下载模型，可能需要几分钟）...")
        print("模型路径: BAAI/bge-large-zh-v1.5")
        print()
        
        embedder = BGEEmbedder(device="cpu")
        
        print(f"✅ Embedder 初始化成功")
        print(f"   模型名称: {embedder.get_model_name()}")
        print(f"   向量维度: {embedder.get_model_dim()}")
        print(f"   设备: {embedder.device}")
        print()
        
        return embedder
    except Exception as e:
        print(f"❌ Embedder 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_single_embedding(embedder):
    """测试单个文本向量化"""
    print("=" * 60)
    print("3. 测试单个文本向量化")
    print("=" * 60)
    print()
    
    if embedder is None:
        print("⚠️  跳过测试（Embedder 未初始化）")
        return False
    
    try:
        test_text = "这是一个测试文本，用于验证向量化功能是否正常工作。"
        print(f"测试文本: '{test_text}'")
        print()
        
        vector = embedder.embed_text(test_text)
        
        print(f"✅ 向量化成功")
        print(f"   文本长度: {len(test_text)} 字符")
        print(f"   向量维度: {len(vector)}")
        print(f"   向量前5个值: {vector[:5]}")
        print(f"   向量后5个值: {vector[-5:]}")
        print()
        
        return True
    except Exception as e:
        print(f"❌ 向量化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_embedding(embedder):
    """测试批量向量化"""
    print("=" * 60)
    print("4. 测试批量向量化")
    print("=" * 60)
    print()
    
    if embedder is None:
        print("⚠️  跳过测试（Embedder 未初始化）")
        return False
    
    try:
        test_texts = [
            "这是第一个测试文本",
            "这是第二个测试文本",
            "这是第三个测试文本",
        ]
        
        print(f"测试批量向量化: {len(test_texts)} 个文本")
        print()
        
        vectors = embedder.embed_batch(test_texts)
        
        print(f"✅ 批量向量化成功")
        print(f"   输入文本数: {len(test_texts)}")
        print(f"   输出向量数: {len(vectors)}")
        print(f"   每个向量维度: {len(vectors[0]) if vectors else 0}")
        print()
        
        # 验证向量相似度（应该相似）
        if len(vectors) >= 2:
            import numpy as np
            v1 = np.array(vectors[0])
            v2 = np.array(vectors[1])
            similarity = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
            print(f"   前两个向量相似度: {similarity:.4f}")
            print()
        
        return True
    except Exception as e:
        print(f"❌ 批量向量化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("Embedder 功能测试（不依赖 Milvus）")
    print("=" * 60)
    print()
    
    results = []
    
    # 1. 测试导入
    if not test_imports():
        print("❌ 依赖导入失败，请检查安装")
        return
    
    # 2. 测试初始化
    embedder = test_embedder_init()
    results.append(("Embedder 初始化", embedder is not None))
    
    # 3. 测试单个向量化
    if embedder:
        results.append(("单个文本向量化", test_single_embedding(embedder)))
    
    # 4. 测试批量向量化
    if embedder:
        results.append(("批量向量化", test_batch_embedding(embedder)))
    
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
        print("✅ 所有测试通过！Embedder 功能正常")
        print()
        print("注意：此测试不包含 Milvus 相关功能")
        print("如需测试完整向量化流程，请先安装 pymilvus：")
        print("  pip install pymilvus")
        print()
        print("然后运行：")
        print("  python examples/test_vectorize_simple.py")
    else:
        print("⚠️  部分测试未通过，请检查错误信息")
    print()


if __name__ == "__main__":
    main()
