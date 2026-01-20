#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 Embedding 配置
显示当前使用的模式和配置
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.common.config import embedding_config


def main():
    """主函数"""
    print("=" * 60)
    print("Embedding 配置检查")
    print("=" * 60)
    print()
    
    print("当前配置：")
    print(f"  EMBEDDING_MODE: {embedding_config.EMBEDDING_MODE}")
    print()
    
    if embedding_config.EMBEDDING_MODE == "api":
        print("✅ 使用 API 模式")
        print()
        print("API 配置：")
        print(f"  EMBEDDING_API_URL: {embedding_config.EMBEDDING_API_URL}")
        print(f"  EMBEDDING_API_KEY: {'*' * (len(embedding_config.EMBEDDING_API_KEY) - 4) + embedding_config.EMBEDDING_API_KEY[-4:] if embedding_config.EMBEDDING_API_KEY and len(embedding_config.EMBEDDING_API_KEY) > 4 else '未配置'}")
        print(f"  EMBEDDING_API_MODEL: {embedding_config.EMBEDDING_API_MODEL}")
        print(f"  EMBEDDING_DIM: {embedding_config.EMBEDDING_DIM}")
        print()
        
        if not embedding_config.EMBEDDING_API_URL:
            print("⚠️  警告: EMBEDDING_API_URL 未配置")
        if not embedding_config.EMBEDDING_API_KEY:
            print("⚠️  警告: EMBEDDING_API_KEY 未配置")
    else:
        print("✅ 使用本地模型模式")
        print()
        print("本地模型配置：")
        print(f"  EMBEDDING_MODEL: {embedding_config.EMBEDDING_MODEL}")
        print(f"  EMBEDDING_DIM: {embedding_config.EMBEDDING_DIM}")
        print(f"  EMBEDDING_DEVICE: {embedding_config.EMBEDDING_DEVICE}")
        print(f"  BGE_MODEL_PATH: {embedding_config.BGE_MODEL_PATH}")
        print()
    
    print("=" * 60)
    print("测试实际使用的 Embedder")
    print("=" * 60)
    print()
    
    try:
        from src.processing.ai.embedding.embedder_factory import get_embedder_by_mode
        
        embedder = get_embedder_by_mode()
        
        embedder_type = type(embedder).__name__
        print(f"✅ 实际使用的 Embedder: {embedder_type}")
        
        if embedder_type == "APIEmbedder":
            print(f"   API URL: {embedder.api_url}")
            print(f"   Model: {embedder.model}")
        elif embedder_type == "BGEEmbedder":
            print(f"   模型名称: {embedder.get_model_name()}")
            print(f"   设备: {embedder.device}")
        
        print(f"   向量维度: {embedder.get_model_dim()}")
        print()
        
    except Exception as e:
        print(f"❌ 获取 Embedder 失败: {e}")
        import traceback
        traceback.print_exc()
        print()
    
    print("=" * 60)
    print("如何切换到 API 模式")
    print("=" * 60)
    print()
    print("在 .env 文件中添加：")
    print("  EMBEDDING_MODE=api")
    print("  EMBEDDING_API_URL=https://api.openai.com/v1/embeddings")
    print("  EMBEDDING_API_KEY=your-api-key")
    print("  EMBEDDING_API_MODEL=text-embedding-ada-002")
    print("  EMBEDDING_DIM=1536")
    print()


if __name__ == "__main__":
    main()
