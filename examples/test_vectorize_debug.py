#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
向量化调试测试脚本
从 document_chunks 表中获取真实数据，测试向量化并记录详细错误信息
特别关注向量数量不匹配的问题
"""

import sys
import os
import json
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import DocumentChunk, Document
from src.processing.ai.embedding.embedder_factory import get_embedder_by_mode
from src.common.config import embedding_config


def analyze_text(text: str) -> Dict[str, Any]:
    """分析文本特征"""
    return {
        "length": len(text),
        "length_bytes": len(text.encode('utf-8')),
        "is_empty": not text or not text.strip(),
        "is_whitespace_only": text.strip() == "" if text else True,
        "has_special_chars": any(ord(c) > 127 for c in text) if text else False,
        "has_control_chars": any(ord(c) < 32 and c not in '\n\r\t' for c in text) if text else False,
        "line_count": text.count('\n') if text else 0,
        "preview": text[:200] + "..." if len(text) > 200 else text,
    }


def test_api_embedding_detailed(texts: List[str], embedder) -> Dict[str, Any]:
    """详细测试 API embedding，记录所有信息"""
    print("\n" + "=" * 80)
    print("测试 API Embedding（详细模式）")
    print("=" * 80)
    
    result = {
        "input_count": len(texts),
        "texts_analysis": [],
        "api_request": {},
        "api_response": {},
        "embeddings_count": 0,
        "error": None,
        "success": False,
    }
    
    # 分析每个文本
    print("\n📝 输入文本分析:")
    print("-" * 80)
    for i, text in enumerate(texts):
        analysis = analyze_text(text)
        result["texts_analysis"].append(analysis)
        print(f"\n文本 {i+1}:")
        print(f"  长度: {analysis['length']} 字符, {analysis['length_bytes']} 字节")
        print(f"  是否为空: {analysis['is_empty']}")
        print(f"  是否只有空白: {analysis['is_whitespace_only']}")
        print(f"  包含特殊字符: {analysis['has_special_chars']}")
        print(f"  包含控制字符: {analysis['has_control_chars']}")
        print(f"  行数: {analysis['line_count']}")
        print(f"  预览: {analysis['preview']}")
    
    # 准备 API 请求
    payload = {
        "input": texts,
        "model": embedder.model
    }
    result["api_request"] = {
        "url": embedder.api_url,
        "model": embedder.model,
        "input_count": len(texts),
        "payload": payload,
    }
    
    print("\n📤 API 请求信息:")
    print("-" * 80)
    print(f"  URL: {embedder.api_url}")
    print(f"  Model: {embedder.model}")
    print(f"  输入文本数量: {len(texts)}")
    print(f"  请求体大小: {len(json.dumps(payload, ensure_ascii=False))} 字节")
    
    # 调用 API
    try:
        print("\n🔄 调用 API...")
        response = embedder.session.post(
            embedder.api_url,
            json=payload,
            headers=embedder.headers,
            timeout=embedder.timeout
        )
        
        print(f"  HTTP 状态码: {response.status_code}")
        result["api_response"]["status_code"] = response.status_code
        
        if response.status_code != 200:
            result["api_response"]["error"] = response.text
            result["error"] = f"HTTP {response.status_code}: {response.text}"
            print(f"  ❌ 错误: {response.text}")
            return result
        
        # 解析响应
        data = response.json()
        result["api_response"]["raw_data"] = data
        
        print("\n📥 API 响应分析:")
        print("-" * 80)
        print(f"  响应键: {list(data.keys())}")
        
        # 解析向量
        embeddings = None
        if "data" in data:
            embeddings = [item["embedding"] for item in data["data"]]
            print(f"  找到 'data' 字段，包含 {len(embeddings)} 个向量")
        elif "embeddings" in data:
            embeddings = data["embeddings"]
            print(f"  找到 'embeddings' 字段，包含 {len(embeddings)} 个向量")
        else:
            # 兼容其他格式
            if isinstance(data, list):
                embeddings = data
                print(f"  响应是列表格式，包含 {len(embeddings)} 个向量")
            else:
                print(f"  ⚠️  未知响应格式")
                result["error"] = f"未知响应格式: {list(data.keys())}"
                return result
        
        result["embeddings_count"] = len(embeddings) if embeddings else 0
        
        # 检查数量匹配
        print(f"\n✅ 向量数量: {result['embeddings_count']}")
        print(f"   期望数量: {result['input_count']}")
        
        if result["embeddings_count"] != result["input_count"]:
            print(f"\n❌ 向量数量不匹配!")
            print(f"   期望: {result['input_count']}, 实际: {result['embeddings_count']}")
            result["error"] = f"向量数量不匹配: 期望={result['input_count']}, 实际={result['embeddings_count']}"
            
            # 分析哪些文本可能有问题
            print("\n🔍 分析可能的问题文本:")
            if embeddings:
                # 如果返回的向量数量少于输入，可能是某些文本被过滤了
                print(f"  返回的向量数量 ({len(embeddings)}) < 输入文本数量 ({len(texts)})")
                print("  可能原因:")
                print("    - API 过滤了某些文本（如空文本、过长文本）")
                print("    - API 批量处理限制")
                
                # 检查是否有空文本
                empty_indices = [i for i, text in enumerate(texts) if not text or not text.strip()]
                if empty_indices:
                    print(f"    - 发现 {len(empty_indices)} 个空文本（索引: {empty_indices}）")
        else:
            print("✅ 向量数量匹配!")
            result["success"] = True
            
            # 检查向量维度
            if embeddings and len(embeddings) > 0:
                dim = len(embeddings[0])
                print(f"   向量维度: {dim}")
                result["api_response"]["dimension"] = dim
                
                # 检查所有向量维度是否一致
                dims = [len(emb) for emb in embeddings]
                if len(set(dims)) > 1:
                    print(f"  ⚠️  向量维度不一致: {dims}")
                else:
                    print(f"  ✅ 所有向量维度一致: {dim}")
        
    except Exception as e:
        result["error"] = str(e)
        print(f"\n❌ 异常: {e}")
        import traceback
        traceback.print_exc()
    
    return result


def test_chunks_from_database(limit: int = 32):
    """从数据库获取分块并测试向量化"""
    print("\n" + "=" * 80)
    print("从数据库获取分块数据")
    print("=" * 80)
    
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 查询未向量化的分块
            query = session.query(DocumentChunk).join(
                Document, DocumentChunk.document_id == Document.id
            ).filter(
                DocumentChunk.vector_id.is_(None)
            )
            
            total_count = query.count()
            chunks = query.limit(limit).all()
            
            print(f"\n📊 数据库统计:")
            print(f"  未向量化分块总数: {total_count}")
            print(f"  本次测试数量: {len(chunks)}")
            
            if not chunks:
                print("\n⚠️  没有找到未向量化的分块")
                return
            
            # 提取文本
            texts = []
            chunk_info = []
            
            for chunk in chunks:
                doc = session.query(Document).filter(
                    Document.id == chunk.document_id
                ).first()
                
                chunk_text = chunk.chunk_text or ""
                texts.append(chunk_text)
                chunk_info.append({
                    "chunk_id": str(chunk.id),
                    "document_id": str(chunk.document_id),
                    "chunk_index": chunk.chunk_index,
                    "stock_code": doc.stock_code if doc else "N/A",
                    "text_length": len(chunk_text),
                })
            
            print(f"\n✅ 提取了 {len(texts)} 个文本")
            
            # 初始化 Embedder
            print("\n🔧 初始化 Embedder...")
            embedder = get_embedder_by_mode()
            print(f"  模式: {embedding_config.EMBEDDING_MODE}")
            print(f"  模型: {embedder.get_model_name()}")
            print(f"  维度: {embedder.get_model_dim()}")
            
            # 测试向量化
            result = test_api_embedding_detailed(texts, embedder)
            
            # 总结
            print("\n" + "=" * 80)
            print("测试总结")
            print("=" * 80)
            print(f"  输入文本数量: {result['input_count']}")
            print(f"  返回向量数量: {result['embeddings_count']}")
            print(f"  是否成功: {result['success']}")
            if result['error']:
                print(f"  错误信息: {result['error']}")
            
            # 如果有问题，显示问题文本的详细信息
            if not result['success']:
                print("\n🔍 问题文本详情:")
                for i, analysis in enumerate(result['texts_analysis']):
                    if analysis['is_empty'] or analysis['is_whitespace_only']:
                        print(f"\n  文本 {i+1} (可能有问题):")
                        print(f"    chunk_id: {chunk_info[i]['chunk_id']}")
                        print(f"    stock_code: {chunk_info[i]['stock_code']}")
                        print(f"    分析: {json.dumps(analysis, ensure_ascii=False, indent=2)}")
            
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


def test_specific_text_types():
    """测试特定类型的文本"""
    print("\n" + "=" * 80)
    print("测试特定类型的文本")
    print("=" * 80)
    
    # 初始化 Embedder
    embedder = get_embedder_by_mode()
    
    # 测试用例
    test_cases = [
        {
            "name": "正常文本",
            "texts": [
                "这是一个正常的测试文本。",
                "这是另一个正常的测试文本。",
            ]
        },
        {
            "name": "包含空文本",
            "texts": [
                "这是第一个文本。",
                "",  # 空文本
                "这是第三个文本。",
            ]
        },
        {
            "name": "包含空白文本",
            "texts": [
                "这是第一个文本。",
                "   ",  # 只有空白
                "这是第三个文本。",
            ]
        },
        {
            "name": "超长文本",
            "texts": [
                "短文本",
                "A" * 10000,  # 超长文本
                "另一个短文本",
            ]
        },
        {
            "name": "特殊字符",
            "texts": [
                "正常文本",
                "包含特殊字符: ©®™€£¥",
                "另一个正常文本",
            ]
        },
    ]
    
    for test_case in test_cases:
        print(f"\n{'='*80}")
        print(f"测试用例: {test_case['name']}")
        print(f"{'='*80}")
        result = test_api_embedding_detailed(test_case['texts'], embedder)
        
        if not result['success']:
            print(f"\n❌ 测试失败: {result['error']}")
        else:
            print(f"\n✅ 测试成功")


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("向量化调试测试")
    print("=" * 80)
    print("\n本脚本将从 document_chunks 表中获取真实数据，")
    print("测试向量化并记录详细的错误信息，特别关注向量数量不匹配的问题。")
    print()
    
    # 检查配置
    print("📋 当前配置:")
    print(f"  EMBEDDING_MODE: {embedding_config.EMBEDDING_MODE}")
    if embedding_config.EMBEDDING_MODE == "api":
        print(f"  EMBEDDING_API_URL: {embedding_config.EMBEDDING_API_URL}")
        print(f"  EMBEDDING_API_MODEL: {embedding_config.EMBEDDING_API_MODEL}")
    print()
    
    # 1. 测试数据库中的真实数据
    print("\n" + "=" * 80)
    print("步骤 1: 测试数据库中的真实数据")
    print("=" * 80)
    test_chunks_from_database(limit=32)
    
    # 2. 测试特定类型的文本
    print("\n" + "=" * 80)
    print("步骤 2: 测试特定类型的文本")
    print("=" * 80)
    test_specific_text_types()
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
