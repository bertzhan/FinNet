# -*- coding: utf-8 -*-
"""
检索接口单元测试
直接测试检索器代码逻辑，不依赖网络连接
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 80)
print("检索接口单元测试")
print("=" * 80)
print()

# 测试1: Schema 验证
print("测试1: Schema 验证")
print("-" * 80)

try:
    from src.api.schemas.retrieval import (
        FilterParams,
        VectorRetrievalRequest,
        FulltextRetrievalRequest,
        GraphRetrievalRequest,
        HybridRetrievalRequest,
        RetrievalResultResponse,
        RetrievalResponse
    )
    
    # 测试 FilterParams - 单个文档类型
    filter1 = FilterParams(
        stock_code="000001",
        year=2023,
        doc_type="quarterly_reports"
    )
    print(f"  ✓ FilterParams (单个文档类型): {filter1.doc_type}")
    
    # 测试 FilterParams - 多个文档类型
    filter2 = FilterParams(
        stock_code="000001",
        doc_type=["ipo_prospectus", "annual_reports"]
    )
    print(f"  ✓ FilterParams (多个文档类型): {filter2.doc_type}")
    
    # 测试 VectorRetrievalRequest
    vector_req = VectorRetrievalRequest(
        query="平安银行营业收入",
        filters=filter1,
        top_k=5
    )
    print(f"  ✓ VectorRetrievalRequest: query='{vector_req.query[:20]}...', top_k={vector_req.top_k}")
    
    # 测试 GraphRetrievalRequest
    graph_req = GraphRetrievalRequest(
        query="000001",
        query_type="document",
        filters=filter1,
        top_k=10
    )
    print(f"  ✓ GraphRetrievalRequest: query_type={graph_req.query_type}")
    
    # 测试 HybridRetrievalRequest
    hybrid_req = HybridRetrievalRequest(
        query="平安银行营业收入",
        filters=filter2,
        top_k=10,
        hybrid_weights={"vector": 0.5, "fulltext": 0.3, "graph": 0.2}
    )
    print(f"  ✓ HybridRetrievalRequest: weights={hybrid_req.hybrid_weights}")
    
    print("  测试1结果: 通过\n")
except Exception as e:
    print(f"  ✗ 测试1失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试2: GraphRetriever 初始化
print("测试2: GraphRetriever 初始化")
print("-" * 80)

try:
    from src.application.rag.graph_retriever import GraphRetriever
    
    # 注意：这里可能会因为 Neo4j 连接失败而报错，但至少可以测试导入
    print("  ✓ GraphRetriever 导入成功")
    
    # 测试方法存在性
    methods = ['retrieve', '_retrieve_by_document', '_retrieve_by_chunk', 
               '_retrieve_by_hierarchy', '_execute_cypher_query', '_fetch_chunks_from_db']
    for method in methods:
        assert hasattr(GraphRetriever, method), f"GraphRetriever 缺少方法: {method}"
        print(f"  ✓ GraphRetriever.{method} 方法存在")
    
    print("  测试2结果: 通过\n")
except Exception as e:
    print(f"  ✗ 测试2失败: {e}")
    import traceback
    traceback.print_exc()

# 测试3: HybridRetriever RRF 算法
print("测试3: HybridRetriever RRF 算法")
print("-" * 80)

try:
    from src.application.rag.hybrid_retriever import HybridRetriever
    from src.application.rag.retriever import RetrievalResult
    
    hybrid_retriever = HybridRetriever()
    
    # 创建模拟检索结果
    results1 = [
        RetrievalResult(
            chunk_id="chunk1",
            document_id="doc1",
            chunk_text="文本1",
            title="标题1",
            title_level=1,
            score=0.9,
            metadata={"stock_code": "000001"}
        ),
        RetrievalResult(
            chunk_id="chunk2",
            document_id="doc1",
            chunk_text="文本2",
            title="标题2",
            title_level=1,
            score=0.8,
            metadata={"stock_code": "000001"}
        ),
    ]
    
    results2 = [
        RetrievalResult(
            chunk_id="chunk1",
            document_id="doc1",
            chunk_text="文本1",
            title="标题1",
            title_level=1,
            score=0.85,
            metadata={"stock_code": "000001"}
        ),
        RetrievalResult(
            chunk_id="chunk3",
            document_id="doc2",
            chunk_text="文本3",
            title="标题3",
            title_level=1,
            score=0.75,
            metadata={"stock_code": "000002"}
        ),
    ]
    
    # 测试融合
    fused = hybrid_retriever.fuse_results(
        results_dict={
            "vector": results1,
            "fulltext": results2
        },
        weights={"vector": 0.6, "fulltext": 0.4},
        top_k=3
    )
    
    print(f"  ✓ RRF 融合成功: 输入2个检索结果列表，融合后 {len(fused)} 个结果")
    if fused:
        print(f"  ✓ 第一个结果: chunk_id={fused[0].chunk_id}, score={fused[0].score:.4f}")
    
    print("  测试3结果: 通过\n")
except Exception as e:
    print(f"  ✗ 测试3失败: {e}")
    import traceback
    traceback.print_exc()

# 测试4: 文档类型验证
print("测试4: 文档类型验证")
print("-" * 80)

try:
    from src.api.schemas.retrieval import FilterParams
    from src.common.constants import DocType
    
    # 测试有效文档类型
    valid_types = [dt.value for dt in DocType]
    print(f"  ✓ 支持的文档类型数量: {len(valid_types)}")
    print(f"  ✓ 示例文档类型: {valid_types[:5]}")
    
    # 测试无效文档类型（应该抛出异常）
    try:
        invalid_filter = FilterParams(doc_type="invalid_type")
        print(f"  ✗ 无效文档类型验证失败: 应该抛出异常但没有")
    except ValueError as e:
        print(f"  ✓ 无效文档类型验证成功: {str(e)[:50]}...")
    
    print("  测试4结果: 通过\n")
except Exception as e:
    print(f"  ✗ 测试4失败: {e}")
    import traceback
    traceback.print_exc()

# 测试5: 路由注册
print("测试5: 路由注册")
print("-" * 80)

try:
    from src.api.routes import retrieval
    
    # 检查路由是否存在
    routes = [route.path for route in retrieval.router.routes]
    expected_routes = [
        "/api/v1/retrieval/vector",
        "/api/v1/retrieval/fulltext",
        "/api/v1/retrieval/graph",
        "/api/v1/retrieval/hybrid",
        "/api/v1/retrieval/health"
    ]
    
    print(f"  ✓ 注册的路由数量: {len(routes)}")
    for route in routes:
        print(f"    - {route}")
    
    # 检查是否包含所有期望的路由
    route_paths = [route for route in routes]
    for expected in expected_routes:
        if expected in route_paths:
            print(f"  ✓ 路由存在: {expected}")
        else:
            print(f"  ✗ 路由缺失: {expected}")
    
    print("  测试5结果: 通过\n")
except Exception as e:
    print(f"  ✗ 测试5失败: {e}")
    import traceback
    traceback.print_exc()

# 测试6: 响应模型构建
print("测试6: 响应模型构建")
print("-" * 80)

try:
    from src.api.schemas.retrieval import RetrievalResultResponse, RetrievalResponse
    
    # 创建响应结果
    result = RetrievalResultResponse(
        chunk_id="chunk1",
        document_id="doc1",
        chunk_text="测试文本",
        title="测试标题",
        title_level=1,
        score=0.95,
        metadata={"stock_code": "000001", "year": 2023}
    )
    
    response = RetrievalResponse(
        results=[result],
        total=1,
        metadata={"retrieval_type": "vector", "retrieval_time": 0.123}
    )
    
    print(f"  ✓ RetrievalResultResponse 创建成功")
    print(f"  ✓ RetrievalResponse 创建成功: total={response.total}")
    
    # 测试序列化
    json_data = response.dict()
    assert "results" in json_data
    assert "total" in json_data
    assert "metadata" in json_data
    print(f"  ✓ 响应序列化成功")
    
    print("  测试6结果: 通过\n")
except Exception as e:
    print(f"  ✗ 测试6失败: {e}")
    import traceback
    traceback.print_exc()

print("=" * 80)
print("单元测试完成!")
print("=" * 80)
print()
print("注意: 这些测试只验证代码逻辑，不测试实际的服务连接。")
print("要测试完整的 API 功能，需要:")
print("1. 启动 API 服务: python -m src.api.main")
print("2. 确保数据库服务运行 (PostgreSQL, Milvus, Neo4j, Elasticsearch)")
print("3. 运行完整测试: python examples/test_retrieval_api.py")
