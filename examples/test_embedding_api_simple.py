#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试嵌入模型 API
直接测试 API 调用，不依赖配置文件
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))


def test_embedding_api():
    """测试嵌入模型 API"""
    print("=" * 80)
    print("嵌入模型 API 测试")
    print("=" * 80)
    print()
    
    # 1. 检查环境变量配置
    print("1. 检查环境变量配置...")
    api_url = os.getenv("EMBEDDING_API_URL")
    api_key = os.getenv("EMBEDDING_API_KEY")
    api_model = os.getenv("EMBEDDING_API_MODEL", "text-embedding-ada-002")
    
    if not api_url:
        print("❌ EMBEDDING_API_URL 环境变量未设置")
        print("   请设置环境变量：")
        print("   export EMBEDDING_API_URL=https://api.openai.com/v1/embeddings")
        return False
    
    if not api_key:
        print("❌ EMBEDDING_API_KEY 环境变量未设置")
        print("   请设置环境变量：")
        print("   export EMBEDDING_API_KEY=your-api-key")
        return False
    
    print(f"✅ API URL: {api_url}")
    print(f"✅ Model: {api_model}")
    print(f"✅ API Key: {'*' * (len(api_key) - 4) + api_key[-4:] if len(api_key) > 4 else '***'}")
    print()
    
    # 2. 测试直接调用 API
    print("2. 测试直接调用 API...")
    try:
        import requests
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "input": ["这是一个测试文本"],
            "model": api_model
        }
        
        print(f"   请求 URL: {api_url}")
        print(f"   请求 Payload: {payload}")
        print()
        
        response = requests.post(
            api_url,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        print(f"   响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API 调用成功")
            
            if "data" in data and len(data["data"]) > 0:
                embedding = data["data"][0]["embedding"]
                print(f"   向量维度: {len(embedding)}")
                print(f"   向量前5个值: {embedding[:5]}")
            elif "embeddings" in data:
                embeddings = data["embeddings"]
                if len(embeddings) > 0:
                    embedding = embeddings[0]
                    print(f"   向量维度: {len(embedding)}")
                    print(f"   向量前5个值: {embedding[:5]}")
            else:
                print(f"   响应数据: {str(data)[:200]}...")
            
            print()
            return True
        else:
            print(f"❌ API 调用失败")
            print(f"   状态码: {response.status_code}")
            print(f"   响应内容: {response.text[:500]}")
            
            try:
                error_data = response.json()
                if "error" in error_data:
                    error_info = error_data["error"]
                    print(f"   错误信息: {error_info.get('message', 'N/A')}")
                    print(f"   错误代码: {error_info.get('code', 'N/A')}")
            except:
                pass
            
            return False
            
    except requests.exceptions.ConnectionError as e:
        print(f"❌ 连接失败: {e}")
        print(f"   请检查 API URL 是否正确，网络是否正常")
        return False
    except requests.exceptions.Timeout:
        print(f"❌ 请求超时")
        print(f"   请检查网络连接或增加超时时间")
        return False
    except Exception as e:
        print(f"❌ API 调用异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 3. 测试使用 API Embedder
    print("3. 测试使用 API Embedder...")
    try:
        from src.processing.ai.embedding.api_embedder import APIEmbedder
        
        embedder = APIEmbedder(
            api_url=api_url,
            api_key=api_key,
            model=api_model
        )
        
        print(f"✅ API Embedder 初始化成功")
        print(f"   模型名称: {embedder.get_model_name()}")
        print(f"   向量维度: {embedder.dimension}")
        print()
        
        # 测试单个文本向量化
        test_text = "平安银行2024年营业收入"
        print(f"   测试文本: {test_text}")
        vector = embedder.embed_text(test_text)
        print(f"✅ 向量化成功")
        print(f"   向量维度: {len(vector)}")
        print(f"   向量前5个值: {vector[:5]}")
        print()
        
        # 测试批量向量化
        test_texts = ["文本1", "文本2", "文本3"]
        print(f"   测试批量向量化: {len(test_texts)} 个文本")
        vectors = embedder.embed_batch(test_texts)
        print(f"✅ 批量向量化成功")
        print(f"   返回向量数: {len(vectors)}")
        print(f"   每个向量维度: {len(vectors[0]) if vectors else 0}")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ API Embedder 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n使用说明：")
    print("1. 设置环境变量：")
    print("   export EMBEDDING_API_URL=https://api.openai.com/v1/embeddings")
    print("   export EMBEDDING_API_KEY=your-api-key")
    print("   export EMBEDDING_API_MODEL=text-embedding-ada-002  # 可选")
    print()
    print("2. 运行测试：")
    print("   python examples/test_embedding_api_simple.py")
    print()
    print("-" * 80)
    print()
    
    success = test_embedding_api()
    
    if success:
        print("=" * 80)
        print("✅ 所有测试通过！")
        print("=" * 80)
        print()
        print("嵌入模型 API 配置正确，可以正常使用。")
    else:
        print("=" * 80)
        print("❌ 测试失败")
        print("=" * 80)
        print()
        print("请检查：")
        print("1. 环境变量是否正确设置")
        print("2. API URL 是否可访问")
        print("3. API Key 是否有效")
        print("4. 网络连接是否正常")
        sys.exit(1)


if __name__ == "__main__":
    main()
