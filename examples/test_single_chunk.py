#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试单个分块的向量化
用于调试特定分块的失败原因
"""

import sys
import uuid
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import DocumentChunk, Document
from src.processing.ai.embedding.embedder_factory import get_embedder_by_mode
from src.common.config import embedding_config


def test_single_chunk(chunk_id_str: str):
    """测试单个分块的向量化"""
    print("=" * 80)
    print(f"测试分块: {chunk_id_str}")
    print("=" * 80)
    print()
    
    chunk_id = uuid.UUID(chunk_id_str)
    pg_client = get_postgres_client()
    
    # 查询分块信息
    with pg_client.get_session() as session:
        chunk = session.query(DocumentChunk).filter(
            DocumentChunk.id == chunk_id
        ).first()
        
        if not chunk:
            print(f"❌ 分块不存在: {chunk_id_str}")
            return
        
        doc = session.query(Document).filter(
            Document.id == chunk.document_id
        ).first()
        
        print("📋 分块信息:")
        print(f"  chunk_id: {chunk.id}")
        print(f"  document_id: {chunk.document_id}")
        print(f"  chunk_index: {chunk.chunk_index}")
        print(f"  stock_code: {doc.stock_code if doc else 'N/A'}")
        print(f"  company_name: {doc.company_name if doc else 'N/A'}")
        print(f"  vector_id: {chunk.vector_id}")
        print()
        
        # 分析文本
        text = chunk.chunk_text or ""
        print("📝 文本分析:")
        print(f"  长度: {len(text)} 字符")
        print(f"  字节长度: {len(text.encode('utf-8'))} 字节")
        print(f"  是否为空: {not text or not text.strip()}")
        print(f"  是否只有空白: {text.strip() == '' if text else True}")
        print(f"  行数: {text.count(chr(10))}")
        print()
        
        # 检查特殊字符
        special_chars = []
        for i, char in enumerate(text):
            code = ord(char)
            if code > 127 or (code < 32 and char not in '\n\r\t'):
                special_chars.append((i, char, code, f"U+{code:04X}"))
        
        if special_chars:
            print(f"  ⚠️  发现 {len(special_chars)} 个特殊字符:")
            for pos, char, code, hex_code in special_chars[:10]:  # 只显示前10个
                print(f"    位置 {pos}: '{char}' (Unicode: {hex_code}, 十进制: {code})")
            if len(special_chars) > 10:
                print(f"    ... 还有 {len(special_chars) - 10} 个特殊字符")
        print()
        
        # 显示文本内容
        print("📄 文本内容:")
        print("-" * 80)
        print(repr(text))  # 使用 repr 显示所有字符
        print("-" * 80)
        print()
        print("📄 文本内容（可读格式）:")
        print("-" * 80)
        print(text)
        print("-" * 80)
        print()
        
        # 测试向量化
        print("🔄 测试向量化...")
        print("-" * 80)
        
        try:
            embedder = get_embedder_by_mode()
            print(f"✅ Embedder 初始化成功")
            print(f"   模式: {embedding_config.EMBEDDING_MODE}")
            print(f"   模型: {embedder.get_model_name()}")
            print(f"   维度: {embedder.get_model_dim()}")
            print()
            
            # 测试单个文本向量化
            print("测试单个文本向量化...")
            try:
                vector = embedder.embed_text(text)
                print(f"✅ 单个文本向量化成功")
                print(f"   向量维度: {len(vector)}")
                print(f"   向量前5个值: {vector[:5]}")
                print()
            except Exception as e:
                print(f"❌ 单个文本向量化失败: {e}")
                print(f"   错误类型: {type(e).__name__}")
                import traceback
                traceback.print_exc()
                print()
            
            # 测试批量向量化（只包含这一个文本）
            print("测试批量向量化（单个文本）...")
            try:
                vectors = embedder.embed_batch([text])
                print(f"✅ 批量向量化成功")
                print(f"   返回向量数量: {len(vectors)}")
                if vectors:
                    print(f"   向量维度: {len(vectors[0])}")
                    print(f"   向量前5个值: {vectors[0][:5]}")
                print()
            except Exception as e:
                print(f"❌ 批量向量化失败: {e}")
                print(f"   错误类型: {type(e).__name__}")
                import traceback
                traceback.print_exc()
                print()
            
            # 如果是 API 模式，测试 API 调用
            if embedding_config.EMBEDDING_MODE == "api":
                print("测试 API 直接调用...")
                print("-" * 80)
                try:
                    if hasattr(embedder, '_call_api'):
                        response = embedder._call_api([text])
                        print(f"✅ API 调用成功")
                        print(f"   返回向量数量: {len(response)}")
                        if response:
                            print(f"   向量维度: {len(response[0])}")
                except Exception as e:
                    print(f"❌ API 调用失败: {e}")
                    print(f"   错误类型: {type(e).__name__}")
                    import traceback
                    traceback.print_exc()
                print()
        
        except Exception as e:
            print(f"❌ Embedder 初始化失败: {e}")
            import traceback
            traceback.print_exc()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="测试单个分块的向量化")
    parser.add_argument("chunk_id", help="分块ID (UUID)")
    
    args = parser.parse_args()
    
    try:
        test_single_chunk(args.chunk_id)
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
