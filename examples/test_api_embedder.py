#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 API Embedder
测试 OpenAI 兼容的 Embedding API
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))


def test_api_embedder():
    """测试 API Embedder"""
    print("=" * 60)
    print("测试 API Embedder")
    print("=" * 60)
    print()
    
    # 检查配置
    print("1. 检查配置...")
    from src.common.config import embedding_config
    
    api_url = embedding_config.EMBEDDING_API_URL
    api_key = embedding_config.EMBEDDING_API_KEY
    model = embedding_config.EMBEDDING_API_MODEL
    
    if not api_url:
        print("❌ EMBEDDING_API_URL 未配置")
        print("   请在 .env 文件中设置：")
        print("   EMBEDDING_API_URL=https://api.openai.com/v1/embeddings")
        return False
    
    if not api_key:
        print("❌ EMBEDDING_API_KEY 未配置")
        print("   请在 .env 文件中设置：")
        print("   EMBEDDING_API_KEY=your-api-key")
        return False
    
    print(f"✅ API URL: {api_url}")
    print(f"✅ Model: {model}")
    print(f"✅ API Key: {'*' * (len(api_key) - 4) + api_key[-4:] if len(api_key) > 4 else '***'}")
    print()
    
    # 测试 API Embedder
    print("2. 初始化 API Embedder...")
    try:
        from src.processing.ai.embedding.api_embedder import get_api_embedder
        
        embedder = get_api_embedder()
        
        print(f"✅ API Embedder 初始化成功")
        print(f"   模型名称: {embedder.get_model_name()}")
        print(f"   向量维度: {embedder.dimension}")
        print()
    except Exception as e:
        print(f"❌ API Embedder 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 测试单个文本向量化
    print("3. 测试单个文本向量化...")
    try:
        test_text = "这是一个测试文本，用于验证 API 向量化功能。"
        print(f"测试文本: '{test_text}'")
        print()
        
        vector = embedder.embed_text(test_text)
        
        print(f"✅ 向量化成功")
        print(f"   文本长度: {len(test_text)} 字符")
        print(f"   向量维度: {len(vector)}")
        print(f"   向量前5个值: {vector[:5]}")
        print()
        
        # 更新维度（如果 API 返回的维度不同）
        if len(vector) != embedder.dimension:
            embedder.dimension = len(vector)
            print(f"   更新向量维度: {embedder.dimension}")
            print()
        
    except Exception as e:
        print(f"❌ 向量化失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 测试批量向量化
    print("4. 测试批量向量化...")
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
        
    except Exception as e:
        print(f"❌ 批量向量化失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 测试工厂模式
    print("5. 测试工厂模式...")
    try:
        from src.processing.ai.embedding.embedder_factory import get_embedder_by_mode
        
        # 使用 API 模式
        embedder2 = get_embedder_by_mode(mode="api")
        
        test_vector = embedder2.embed_text("测试")
        
        print(f"✅ 工厂模式测试成功")
        print(f"   向量维度: {len(test_vector)}")
        print()
        
    except Exception as e:
        print(f"❌ 工厂模式测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)
    print()
    
    return True


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("API Embedder 测试")
    print("=" * 60)
    print()
    
    print("使用说明：")
    print("1. 在 .env 文件中配置：")
    print("   EMBEDDING_MODE=api")
    print("   EMBEDDING_API_URL=https://api.openai.com/v1/embeddings")
    print("   EMBEDDING_API_KEY=your-api-key")
    print("   EMBEDDING_API_MODEL=text-embedding-ada-002")
    print()
    print("2. 或者使用自定义配置：")
    print("   from src.processing.ai.embedding.api_embedder import get_api_embedder")
    print("   embedder = get_api_embedder(")
    print("       api_url='https://api.example.com/v1/embeddings',")
    print("       api_key='your-key',")
    print("       model='text-embedding-ada-002'")
    print("   )")
    print()
    print("-" * 60)
    print()
    
    success = test_api_embedder()
    
    if not success:
        print("=" * 60)
        print("❌ 测试失败")
        print("=" * 60)
        print()
        print("请检查：")
        print("1. .env 文件中的 API 配置是否正确")
        print("2. API URL 是否可访问")
        print("3. API Key 是否有效")
        print("4. 网络连接是否正常")
        sys.exit(1)


if __name__ == "__main__":
    main()
