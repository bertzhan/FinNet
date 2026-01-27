#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG 集成测试脚本
直接运行，不依赖 pytest
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("RAG 集成测试")
print("=" * 80)
print()

# 测试1: 检查服务连接
print("测试1: 检查服务连接")
print("-" * 80)

try:
    from src.storage.metadata.postgres_client import get_postgres_client
    pg_client = get_postgres_client()
    with pg_client.get_session() as session:
        from src.storage.metadata.models import DocumentChunk
        from sqlalchemy import func
        count = session.query(func.count(DocumentChunk.id)).scalar()
        print(f"✅ PostgreSQL 连接成功，DocumentChunk 数量: {count}")
except Exception as e:
    print(f"❌ PostgreSQL 连接失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    from src.storage.vector.milvus_client import get_milvus_client
    client = get_milvus_client()
    collections = client.list_collections()
    print(f"✅ Milvus 连接成功，Collections: {collections}")
    
    # 检查 collection 统计信息
    if "financial_documents" in collections:
        stats = client.get_collection_stats("financial_documents")
        vector_count = stats.get("row_count", 0)
        print(f"   financial_documents 向量数量: {vector_count}")
except Exception as e:
    print(f"❌ Milvus 连接失败: {e}")
    print("   提示: 请确保 Milvus 服务运行并安装 pymilvus: pip install pymilvus")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    from src.common.config import llm_config
    if llm_config.CLOUD_LLM_ENABLED:
        print(f"✅ 云端 LLM 已启用: {llm_config.CLOUD_LLM_API_BASE}")
        if not llm_config.CLOUD_LLM_API_KEY:
            print("   ⚠️  警告: CLOUD_LLM_API_KEY 未配置")
    elif llm_config.LOCAL_LLM_ENABLED:
        print(f"✅ 本地 LLM 已启用: {llm_config.LOCAL_LLM_API_BASE}")
    else:
        print("   ⚠️  警告: 未启用任何 LLM 服务")
except Exception as e:
    print(f"❌ LLM 配置检查失败: {e}")
    import traceback
    traceback.print_exc()

print()

# 测试2: Retriever 初始化
print("测试2: Retriever 初始化")
print("-" * 80)

try:
    from src.application.rag.retriever import Retriever
    retriever = Retriever()
    print(f"✅ Retriever 初始化成功")
    print(f"   Collection: {retriever.collection_name}")
except Exception as e:
    print(f"❌ Retriever 初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# 测试3: 基础检索测试
print("测试3: 基础检索测试")
print("-" * 80)

try:
    results = retriever.retrieve("营业收入", top_k=5)
    print(f"✅ 检索成功，返回 {len(results)} 个结果")
    if results:
        print(f"   第一个结果:")
        print(f"     - chunk_id: {results[0].chunk_id}")
        print(f"     - score: {results[0].score:.4f}")
        print(f"     - text_preview: {results[0].chunk_text[:100]}...")
        print(f"     - metadata: stock_code={results[0].metadata.get('stock_code')}, year={results[0].metadata.get('year')}")
        
        if len(results) > 1:
            print(f"   第二个结果:")
            print(f"     - score: {results[1].score:.4f}")
            print(f"     - text_preview: {results[1].chunk_text[:80]}...")
    else:
        print("   ⚠️  未找到相关结果（可能 Milvus 中没有向量数据）")
except Exception as e:
    print(f"❌ 检索失败: {e}")
    import traceback
    traceback.print_exc()

print()

# 测试4: 带过滤条件的检索
print("测试4: 带过滤条件的检索")
print("-" * 80)

try:
    filters = {"stock_code": "300543", "year": 2023}
    results_filtered = retriever.retrieve("营业收入", top_k=5, filters=filters)
    print(f"✅ 带过滤条件检索成功，返回 {len(results_filtered)} 个结果")
    if results_filtered:
        for i, result in enumerate(results_filtered[:3], 1):
            print(f"   结果 {i}:")
            print(f"     - stock_code: {result.metadata.get('stock_code')}")
            print(f"     - year: {result.metadata.get('year')}")
            print(f"     - quarter: {result.metadata.get('quarter')}")
            print(f"     - score: {result.score:.4f}")
            # 验证过滤条件
            assert result.metadata.get("stock_code") == "300543", "过滤条件验证失败"
            assert result.metadata.get("year") == 2023, "过滤条件验证失败"
    else:
        print("   ⚠️  未找到符合过滤条件的结果")
except Exception as e:
    print(f"❌ 带过滤条件检索失败: {e}")
    import traceback
    traceback.print_exc()

print()

# 测试5: ContextBuilder 测试
print("测试5: ContextBuilder 测试")
print("-" * 80)

try:
    from src.application.rag.context_builder import ContextBuilder
    builder = ContextBuilder(max_length=1000)
    print(f"✅ ContextBuilder 初始化成功")
    
    # 使用之前的检索结果
    if results and len(results) > 0:
        context = builder.build_context(results[:3])
        print(f"✅ 上下文构建成功，长度: {len(context)} 字符")
        print(f"   预览（前200字符）: {context[:200]}...")
        
        # 测试格式化分块
        formatted_chunks = builder.format_chunks(results[:2])
        print(f"✅ 格式化分块成功，分块数: {len(formatted_chunks)}")
        
        # 测试添加元数据
        context_with_metadata = builder.add_metadata(context, results[:3])
        print(f"✅ 添加元数据成功，新长度: {len(context_with_metadata)} 字符")
    else:
        print("   ⚠️  跳过（需要检索结果）")
except Exception as e:
    print(f"❌ ContextBuilder 测试失败: {e}")
    import traceback
    traceback.print_exc()

print()

# 测试6: LLM Service 测试
print("测试6: LLM Service 测试")
print("-" * 80)

try:
    from src.processing.ai.llm.llm_service import get_llm_service
    from src.common.config import llm_config
    
    service = get_llm_service()
    print(f"✅ LLM Service 初始化成功")
    print(f"   Mode: {service.mode}")
    print(f"   Provider: {service.provider}")
    print(f"   API Base: {service.api_base}")
    print(f"   Model: {service.model}")
    
    # 简单测试生成（如果配置了API Key）
    if llm_config.CLOUD_LLM_ENABLED and llm_config.CLOUD_LLM_API_KEY:
        print("   测试文本生成...")
        try:
            answer = service.generate(
                prompt="什么是人工智能？请用一句话回答。",
                system_prompt="你是一个专业的AI助手。",
                temperature=0.7,
                max_tokens=50
            )
            print(f"✅ LLM 生成成功，回答长度: {len(answer)} 字符")
            print(f"   回答: {answer}")
        except Exception as e:
            print(f"   ⚠️  LLM 生成失败: {e}")
            print("   提示: 可能是 API Key 无效或网络问题")
    elif llm_config.LOCAL_LLM_ENABLED:
        print("   测试本地 LLM 生成...")
        try:
            answer = service.generate(
                prompt="你好",
                max_tokens=20
            )
            print(f"✅ 本地 LLM 生成成功，回答长度: {len(answer)} 字符")
            print(f"   回答: {answer[:100]}...")
        except Exception as e:
            print(f"   ⚠️  本地 LLM 生成失败: {e}")
    else:
        print("   ⚠️  跳过实际生成（未配置 API Key）")
except Exception as e:
    print(f"❌ LLM Service 测试失败: {e}")
    import traceback
    traceback.print_exc()

print()

# 测试7: RAG Pipeline 完整流程测试
print("测试7: RAG Pipeline 完整流程测试")
print("-" * 80)

try:
    from src.application.rag.rag_pipeline import RAGPipeline
    from src.common.config import llm_config
    
    pipeline = RAGPipeline()
    print(f"✅ RAG Pipeline 初始化成功")
    
    # 如果配置了LLM API Key，执行完整查询
    if llm_config.CLOUD_LLM_ENABLED and llm_config.CLOUD_LLM_API_KEY:
        print("   执行 RAG 查询...")
        try:
            response = pipeline.query(
                question="2023年的营业收入？",
                top_k=3,
                temperature=0.7,
                max_tokens=150
            )
            print(f"✅ RAG 查询成功")
            print(f"   答案长度: {len(response.answer)} 字符")
            print(f"   来源数量: {len(response.sources)}")
            print(f"   生成时间: {response.metadata.get('generation_time', 0):.2f}s")
            print(f"   模型: {response.metadata.get('model', 'N/A')}")
            print(f"   答案预览: {response.answer[:200]}...")
            
            if response.sources:
                print(f"   引用来源:")
                for i, source in enumerate(response.sources[:3], 1):
                    print(f"     {i}. {source.company_name} ({source.stock_code}) - {source.title or '无标题'}")
                    print(f"        相似度: {source.score:.3f}, 年份: {source.year}")
        except Exception as e:
            print(f"   ⚠️  RAG 查询失败: {e}")
            import traceback
            traceback.print_exc()
    elif llm_config.LOCAL_LLM_ENABLED:
        print("   执行本地 LLM RAG 查询...")
        try:
            response = pipeline.query(
                question="什么是营业收入？",
                top_k=3,
                temperature=0.7,
                max_tokens=100
            )
            print(f"✅ 本地 RAG 查询成功")
            print(f"   答案长度: {len(response.answer)} 字符")
            print(f"   来源数量: {len(response.sources)}")
            print(f"   答案预览: {response.answer[:200]}...")
        except Exception as e:
            print(f"   ⚠️  本地 RAG 查询失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("   ⚠️  跳过完整查询（未配置 LLM API Key）")
except Exception as e:
    print(f"❌ RAG Pipeline 测试失败: {e}")
    import traceback
    traceback.print_exc()

print()

# 测试8: 带过滤条件的完整 RAG 查询
print("测试8: 带过滤条件的完整 RAG 查询")
print("-" * 80)

try:
    if llm_config.CLOUD_LLM_ENABLED and llm_config.CLOUD_LLM_API_KEY:
        print("   执行带过滤条件的 RAG 查询...")
        try:
            response = pipeline.query(
                question="公司2023年营业收入是多少？",
                filters={"stock_code": "300543", "year": 2023, "quarter": 4},
                top_k=5,
                temperature=0.7,
                max_tokens=200
            )
            print(f"✅ 带过滤条件的 RAG 查询成功")
            print(f"   答案长度: {len(response.answer)} 字符")
            print(f"   来源数量: {len(response.sources)}")
            print(f"   答案预览: {response.answer[:250]}...")
            
            # 验证来源是否符合过滤条件
            if response.sources:
                print(f"   验证来源过滤条件:")
                for source in response.sources:
                    assert source.stock_code == "300543", f"过滤失败: stock_code={source.stock_code}"
                    assert source.year == 2023, f"过滤失败: year={source.year}"
                    assert source.quarter == 4, f"过滤失败: quarter={source.quarter}"
                print(f"   ✅ 所有来源都符合过滤条件")
        except Exception as e:
            print(f"   ⚠️  带过滤条件的 RAG 查询失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("   ⚠️  跳过（未配置 LLM API Key）")
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("集成测试完成!")
print("=" * 80)
print()
print("测试总结:")
print("  - 如果所有测试都通过 ✅，说明 RAG 系统运行正常")
print("  - 如果有 ⚠️  警告，可能是配置问题或缺少数据")
print("  - 如果有 ❌ 错误，请检查服务状态和配置")
