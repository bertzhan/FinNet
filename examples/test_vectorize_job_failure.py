#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
向量化作业失败分析测试脚本
测试 vectorize_documents_job，详细分析分块失败的原因
"""

import sys
import os
import json
import traceback
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import DocumentChunk, Document
from src.processing.ai.embedding.vectorizer import get_vectorizer
from src.processing.ai.embedding.embedder_factory import get_embedder_by_mode
from src.common.config import embedding_config


class FailureAnalyzer:
    """失败分析器"""
    
    def __init__(self):
        self.failure_reasons = []
        self.failed_chunks_detail = []
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """分析文本特征"""
        if not text:
            return {
                "is_empty": True,
                "length": 0,
                "length_bytes": 0,
            }
        
        return {
            "is_empty": False,
            "length": len(text),
            "length_bytes": len(text.encode('utf-8')),
            "is_whitespace_only": text.strip() == "",
            "has_special_chars": any(ord(c) > 127 for c in text),
            "has_control_chars": any(ord(c) < 32 and c not in '\n\r\t' for c in text),
            "line_count": text.count('\n'),
            "preview": text[:200] + "..." if len(text) > 200 else text,
        }
    
    def record_failure(self, chunk_id: str, reason: str, details: Dict[str, Any] = None):
        """记录失败信息"""
        self.failure_reasons.append({
            "chunk_id": chunk_id,
            "reason": reason,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        })
    
    def analyze_failed_chunk(self, chunk: DocumentChunk, doc: Document, error: Exception = None):
        """分析失败的分块"""
        text_analysis = self.analyze_text(chunk.chunk_text)
        
        failure_info = {
            "chunk_id": str(chunk.id),
            "document_id": str(chunk.document_id),
            "chunk_index": chunk.chunk_index,
            "stock_code": doc.stock_code if doc else "N/A",
            "company_name": doc.company_name if doc else "N/A",
            "year": doc.year if doc else None,
            "quarter": doc.quarter if doc else None,
            "text_analysis": text_analysis,
            "error": str(error) if error else None,
            "error_type": type(error).__name__ if error else None,
        }
        
        self.failed_chunks_detail.append(failure_info)
        return failure_info


def test_vectorize_with_detailed_analysis(
    batch_size: int = 32,
    limit: int = 100,
    force_revectorize: bool = False
):
    """测试向量化并详细分析失败原因"""
    print("\n" + "=" * 80)
    print("向量化作业失败分析测试")
    print("=" * 80)
    print(f"\n配置:")
    print(f"  batch_size: {batch_size}")
    print(f"  limit: {limit}")
    print(f"  force_revectorize: {force_revectorize}")
    print(f"  embedding_mode: {embedding_config.EMBEDDING_MODE}")
    print()
    
    analyzer = FailureAnalyzer()
    pg_client = get_postgres_client()
    
    # 步骤1: 扫描未向量化的分块
    print("步骤1: 扫描未向量化的分块...")
    print("-" * 80)
    
    try:
        with pg_client.get_session() as session:
            query = session.query(DocumentChunk).join(
                Document, DocumentChunk.document_id == Document.id
            )
            
            if not force_revectorize:
                query = query.filter(DocumentChunk.vector_id.is_(None))
            
            chunks = query.limit(limit).all()
            
            print(f"✅ 找到 {len(chunks)} 个待向量化的分块")
            
            if not chunks:
                print("⚠️  没有待向量化的分块")
                return
            
            # 提取分块信息
            chunk_list = []
            for chunk in chunks:
                doc = session.query(Document).filter(
                    Document.id == chunk.document_id
                ).first()
                
                if not doc:
                    analyzer.record_failure(
                        str(chunk.id),
                        "关联文档不存在",
                        {"document_id": str(chunk.document_id)}
                    )
                    continue
                
                # 在 session 内提取所有需要的数据，避免 DetachedInstanceError
                chunk_list.append({
                    "chunk_id": str(chunk.id),
                    "chunk_id_uuid": chunk.id,  # 保存 UUID 对象用于后续查询
                    "document_id": str(chunk.document_id),
                    "chunk_index": chunk.chunk_index,
                    "chunk_text": chunk.chunk_text,  # 提取文本
                    "stock_code": doc.stock_code,
                    "company_name": doc.company_name,
                    "market": doc.market,
                    "doc_type": doc.doc_type,
                    "year": doc.year,
                    "quarter": doc.quarter,
                })
            
            print(f"✅ 有效分块数量: {len(chunk_list)}")
            print()
            
    except Exception as e:
        print(f"❌ 扫描失败: {e}")
        traceback.print_exc()
        return
    
    # 步骤2: 测试向量化
    print("步骤2: 执行向量化...")
    print("-" * 80)
    
    try:
        vectorizer = get_vectorizer()
        print(f"✅ Vectorizer 初始化成功")
        print(f"   模型: {vectorizer.embedder.get_model_name()}")
        print(f"   维度: {vectorizer.embedder.get_model_dim()}")
        print()
        
        # 分批处理
        total_batches = (len(chunk_list) + batch_size - 1) // batch_size
        print(f"分为 {total_batches} 个批次处理...")
        print()
        
        all_results = {
            "total_chunks": len(chunk_list),
            "total_batches": total_batches,
            "vectorized_count": 0,
            "failed_count": 0,
            "batch_results": []
        }
        
        for batch_idx in range(0, len(chunk_list), batch_size):
            batch = chunk_list[batch_idx:batch_idx + batch_size]
            batch_num = batch_idx // batch_size + 1
            
            print(f"处理批次 {batch_num}/{total_batches} ({len(batch)} 个分块)...")
            
            # 使用已提取的 chunk_id
            chunk_ids = [item["chunk_id_uuid"] for item in batch]
            
            try:
                # 执行向量化
                result = vectorizer.vectorize_chunks(chunk_ids, force_revectorize=force_revectorize)
                
                batch_result = {
                    "batch_num": batch_num,
                    "chunk_count": len(batch),
                    "vectorized_count": result.get("vectorized_count", 0),
                    "failed_count": result.get("failed_count", 0),
                    "failed_chunks": result.get("failed_chunks", []),
                }
                
                all_results["batch_results"].append(batch_result)
                all_results["vectorized_count"] += batch_result["vectorized_count"]
                all_results["failed_count"] += batch_result["failed_count"]
                
                print(f"  成功: {batch_result['vectorized_count']}, 失败: {batch_result['failed_count']}")
                
                # 分析失败的分块
                if batch_result["failed_chunks"]:
                    print(f"  分析失败的分块...")
                    for failed_chunk_id in batch_result["failed_chunks"]:
                        # 查找对应的 chunk 数据
                        for item in batch:
                            if item["chunk_id"] == failed_chunk_id:
                                # 重新查询 chunk 和 doc 用于分析
                                with pg_client.get_session() as session:
                                    chunk = session.query(DocumentChunk).filter(
                                        DocumentChunk.id == item["chunk_id_uuid"]
                                    ).first()
                                    doc = session.query(Document).filter(
                                        Document.id == uuid.UUID(item["document_id"])
                                    ).first()
                                    
                                    if chunk and doc:
                                        failure_info = analyzer.analyze_failed_chunk(
                                            chunk,
                                            doc
                                        )
                                        print(f"    - chunk_id={failed_chunk_id}")
                                        print(f"      文本长度: {failure_info['text_analysis']['length']}")
                                        print(f"      是否为空: {failure_info['text_analysis'].get('is_empty', False)}")
                                break
                
            except Exception as e:
                print(f"  ❌ 批次 {batch_num} 处理异常: {e}")
                traceback.print_exc()
                
                # 记录整个批次的失败
                for item in batch:
                    # 重新查询 chunk 和 doc 用于分析
                    with pg_client.get_session() as session:
                        chunk = session.query(DocumentChunk).filter(
                            DocumentChunk.id == item["chunk_id_uuid"]
                        ).first()
                        doc = session.query(Document).filter(
                            Document.id == uuid.UUID(item["document_id"])
                        ).first()
                        
                        if chunk and doc:
                            analyzer.analyze_failed_chunk(
                                chunk,
                                doc,
                                error=e
                            )
                    all_results["failed_count"] += 1
            
            print()
        
    except Exception as e:
        print(f"❌ 向量化失败: {e}")
        traceback.print_exc()
        return
    
    # 步骤3: 详细分析失败原因
    print("步骤3: 详细分析失败原因...")
    print("-" * 80)
    
    if analyzer.failed_chunks_detail:
        print(f"\n发现 {len(analyzer.failed_chunks_detail)} 个失败的分块")
        print()
        
        # 按失败原因分类
        failure_categories = {}
        for failure in analyzer.failed_chunks_detail:
            error_type = failure.get("error_type", "Unknown")
            if error_type not in failure_categories:
                failure_categories[error_type] = []
            failure_categories[error_type].append(failure)
        
        print("失败原因分类:")
        for error_type, failures in failure_categories.items():
            print(f"  {error_type}: {len(failures)} 个")
        print()
        
        # 显示前10个失败分块的详细信息
        print("前10个失败分块详情:")
        print()
        for i, failure in enumerate(analyzer.failed_chunks_detail[:10], 1):
            print(f"{i}. chunk_id: {failure['chunk_id']}")
            print(f"   document_id: {failure['document_id']}")
            print(f"   stock_code: {failure['stock_code']}")
            print(f"   chunk_index: {failure['chunk_index']}")
            print(f"   文本分析:")
            text_analysis = failure['text_analysis']
            print(f"     长度: {text_analysis.get('length', 0)} 字符, {text_analysis.get('length_bytes', 0)} 字节")
            print(f"     是否为空: {text_analysis.get('is_empty', False)}")
            print(f"     是否只有空白: {text_analysis.get('is_whitespace_only', False)}")
            print(f"     包含特殊字符: {text_analysis.get('has_special_chars', False)}")
            print(f"     行数: {text_analysis.get('line_count', 0)}")
            if failure.get('error'):
                print(f"   错误: {failure['error']}")
            print(f"   文本预览: {text_analysis.get('preview', '')[:100]}...")
            print()
    else:
        print("✅ 没有发现失败的分块")
    
    # 步骤4: 测试 API Embedder（如果是 API 模式）
    if embedding_config.EMBEDDING_MODE == "api" and analyzer.failed_chunks_detail:
        print("步骤4: 测试 API Embedder（针对失败的分块）...")
        print("-" * 80)
        
        try:
            embedder = get_embedder_by_mode()
            
            # 测试前3个失败分块的文本
            test_count = min(3, len(analyzer.failed_chunks_detail))
            print(f"\n测试前 {test_count} 个失败分块的文本向量化...")
            
            # 重新查询失败分块的完整文本
            with pg_client.get_session() as session:
                for i, failure in enumerate(analyzer.failed_chunks_detail[:test_count], 1):
                    chunk_id = failure['chunk_id']
                    
                    # 查询完整文本
                    chunk_id_uuid = uuid.UUID(failure['chunk_id'])
                    chunk = session.query(DocumentChunk).filter(
                        DocumentChunk.id == chunk_id_uuid
                    ).first()
                    
                    if not chunk:
                        print(f"\n测试 {i}: chunk_id={chunk_id} (分块不存在)")
                        continue
                    
                    text = chunk.chunk_text or ""
                    
                    print(f"\n测试 {i}: chunk_id={chunk_id}")
                    print(f"  文本长度: {len(text)} 字符")
                    print(f"  文本预览: {text[:100]}..." if len(text) > 100 else f"  文本: {text}")
                    
                    try:
                        # 尝试向量化（使用公开方法）
                        vector = embedder.embed_text(text)
                        print(f"  ✅ 向量化成功，维度: {len(vector)}")
                    except Exception as e:
                        print(f"  ❌ 向量化失败: {e}")
                        print(f"     错误类型: {type(e).__name__}")
                        # 如果是 API 模式，尝试批量测试
                        if embedding_config.EMBEDDING_MODE == "api":
                            try:
                                print(f"     尝试批量向量化测试...")
                                vectors = embedder.embed_batch([text])
                                if vectors:
                                    print(f"     ✅ 批量向量化成功，返回 {len(vectors)} 个向量")
                            except Exception as batch_error:
                                print(f"     ❌ 批量向量化也失败: {batch_error}")
                        traceback.print_exc()
        
        except Exception as e:
            print(f"❌ API 测试失败: {e}")
            traceback.print_exc()
    
    # 步骤5: 汇总结果
    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)
    print(f"  总分块数: {all_results['total_chunks']}")
    print(f"  成功向量化: {all_results['vectorized_count']}")
    print(f"  失败数量: {all_results['failed_count']}")
    print(f"  成功率: {all_results['vectorized_count'] / all_results['total_chunks'] * 100:.2f}%" if all_results['total_chunks'] > 0 else "N/A")
    print()
    
    if analyzer.failed_chunks_detail:
        print(f"  失败分块详情: {len(analyzer.failed_chunks_detail)} 个")
        print()
        print("失败原因统计:")
        failure_reasons = {}
        for failure in analyzer.failed_chunks_detail:
            reason = failure.get('error_type', 'Unknown')
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
        
        for reason, count in failure_reasons.items():
            print(f"    {reason}: {count} 个")
    
    print()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="测试向量化作业并分析失败原因")
    parser.add_argument("--batch-size", type=int, default=32, help="批次大小（默认: 32）")
    parser.add_argument("--limit", type=int, default=100, help="最多处理的分块数量（默认: 100）")
    parser.add_argument("--force-revectorize", action="store_true", help="强制重新向量化")
    
    args = parser.parse_args()
    
    try:
        test_vectorize_with_detailed_analysis(
            batch_size=args.batch_size,
            limit=args.limit,
            force_revectorize=args.force_revectorize
        )
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n\n❌ 测试失败: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
