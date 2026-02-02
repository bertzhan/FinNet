# -*- coding: utf-8 -*-
"""
检索接口 Schema 测试
只测试 Schema 定义，不导入需要数据库连接的模块
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 80)
print("检索接口 Schema 测试")
print("=" * 80)
print()

# 测试1: Schema 导入和基本验证
print("测试1: Schema 导入和基本验证")
print("-" * 80)

try:
    from src.api.schemas.retrieval import (
        FilterParams,
        VectorRetrievalRequest,
        FulltextRetrievalRequest,
        # GraphRetrievalRequest,  # 已删除：图检索接口已移除
        HybridRetrievalRequest,
        RetrievalResultResponse,
        RetrievalResponse,
        RetrievalHealthResponse
    )
    print("  ✓ 所有 Schema 导入成功")
except Exception as e:
    print(f"  ✗ Schema 导入失败: {e}")
    sys.exit(1)

# 测试2: FilterParams - 单个文档类型
print("\n测试2: FilterParams - 单个文档类型")
print("-" * 80)

try:
    filter1 = FilterParams(
        stock_code="000001",
        year=2023,
        quarter=3,
        doc_type="quarterly_reports",
        market="a_share"
    )
    assert filter1.stock_code == "000001"
    assert filter1.year == 2023
    assert filter1.doc_type == "quarterly_reports"
    print(f"  ✓ FilterParams 创建成功: stock_code={filter1.stock_code}, doc_type={filter1.doc_type}")
except Exception as e:
    print(f"  ✗ 测试失败: {e}")
    sys.exit(1)

# 测试3: FilterParams - 多个文档类型
print("\n测试3: FilterParams - 多个文档类型")
print("-" * 80)

try:
    filter2 = FilterParams(
        stock_code="000001",
        doc_type=["ipo_prospectus", "annual_reports"]
    )
    assert isinstance(filter2.doc_type, list)
    assert len(filter2.doc_type) == 2
    print(f"  ✓ 多个文档类型过滤成功: {filter2.doc_type}")
except Exception as e:
    print(f"  ✗ 测试失败: {e}")
    sys.exit(1)

# 测试4: FilterParams - 无效文档类型（应该抛出异常）
print("\n测试4: FilterParams - 无效文档类型验证")
print("-" * 80)

try:
    try:
        invalid_filter = FilterParams(doc_type="invalid_type_12345")
        print(f"  ✗ 应该抛出异常但没有")
        sys.exit(1)
    except ValueError as e:
        print(f"  ✓ 无效文档类型验证成功: {str(e)[:80]}...")
except Exception as e:
    print(f"  ✗ 测试失败: {e}")
    sys.exit(1)

# 测试5: VectorRetrievalRequest
print("\n测试5: VectorRetrievalRequest")
print("-" * 80)

try:
    request = VectorRetrievalRequest(
        query="平安银行2023年第三季度的营业收入",
        filters=filter1,
        top_k=5
    )
    assert request.query == "平安银行2023年第三季度的营业收入"
    assert request.top_k == 5
    assert request.filters.stock_code == "000001"
    print(f"  ✓ VectorRetrievalRequest 创建成功")
    print(f"    - query: {request.query[:30]}...")
    print(f"    - top_k: {request.top_k}")
    print(f"    - filters.stock_code: {request.filters.stock_code}")
except Exception as e:
    print(f"  ✗ 测试失败: {e}")
    sys.exit(1)

# 测试6: FulltextRetrievalRequest
print("\n测试6: FulltextRetrievalRequest")
print("-" * 80)

try:
    request = FulltextRetrievalRequest(
        query="营业收入 净利润",
        filters=FilterParams(stock_code="000001", doc_type="ipo_prospectus"),
        top_k=10
    )
    assert request.query == "营业收入 净利润"
    assert request.top_k == 10
    print(f"  ✓ FulltextRetrievalRequest 创建成功")
except Exception as e:
    print(f"  ✗ 测试失败: {e}")
    sys.exit(1)

# 测试7: GraphRetrievalRequest (已删除)
# 已删除：图检索接口已移除，替换为 /api/v1/retrieval/graph/children 接口
# print("\n测试7: GraphRetrievalRequest")
# print("-" * 80)
# try:
#     ...
# except Exception as e:
#     print(f"  ✗ 测试失败: {e}")
#     sys.exit(1)

# 测试8: HybridRetrievalRequest
print("\n测试8: HybridRetrievalRequest")
print("-" * 80)

try:
    request = HybridRetrievalRequest(
        query="平安银行营业收入",
        filters=filter2,
        top_k=10,
        hybrid_weights={"vector": 0.5, "fulltext": 0.5}
    )
    assert request.query == "平安银行营业收入"
    assert request.hybrid_weights["vector"] == 0.5
    print(f"  ✓ HybridRetrievalRequest 创建成功")
    print(f"    - weights: {request.hybrid_weights}")
    
    # 测试默认权重
    request2 = HybridRetrievalRequest(
        query="test",
        top_k=5
    )
    assert request2.hybrid_weights is not None
    print(f"  ✓ 默认权重设置成功: {request2.hybrid_weights}")
    
except Exception as e:
    print(f"  ✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试9: RetrievalResultResponse
print("\n测试9: RetrievalResultResponse")
print("-" * 80)

try:
    result = RetrievalResultResponse(
        chunk_id="chunk-123",
        document_id="doc-456",
        chunk_text="这是测试文本内容",
        title="测试标题",
        title_level=1,
        score=0.95,
        metadata={
            "stock_code": "000001",
            "company_name": "平安银行",
            "doc_type": "quarterly_reports",
            "year": 2023,
            "quarter": 3
        }
    )
    assert result.chunk_id == "chunk-123"
    assert result.score == 0.95
    print(f"  ✓ RetrievalResultResponse 创建成功")
    print(f"    - chunk_id: {result.chunk_id}")
    print(f"    - score: {result.score}")
    print(f"    - metadata: {result.metadata.get('stock_code')}")
except Exception as e:
    print(f"  ✗ 测试失败: {e}")
    sys.exit(1)

# 测试10: RetrievalResponse
print("\n测试10: RetrievalResponse")
print("-" * 80)

try:
    response = RetrievalResponse(
        results=[result],
        total=1,
        metadata={
            "retrieval_type": "vector",
            "retrieval_time": 0.123,
            "top_k": 5
        }
    )
    assert response.total == 1
    assert len(response.results) == 1
    print(f"  ✓ RetrievalResponse 创建成功")
    print(f"    - total: {response.total}")
    print(f"    - results count: {len(response.results)}")
    
    # 测试序列化（使用 model_dump 而不是 dict）
    json_data = response.model_dump()
    assert "results" in json_data
    assert "total" in json_data
    assert "metadata" in json_data
    print(f"  ✓ 响应序列化成功")
    
except Exception as e:
    print(f"  ✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试11: RetrievalHealthResponse
print("\n测试11: RetrievalHealthResponse")
print("-" * 80)

try:
    health = RetrievalHealthResponse(
        status="healthy",
        message="Retrieval service is running",
        components={
            "vector_retriever": "ok",
            "fulltext_retriever": "ok",
            "graph_retriever": "ok"
        }
    )
    assert health.status == "healthy"
    assert len(health.components) == 3
    print(f"  ✓ RetrievalHealthResponse 创建成功")
    print(f"    - status: {health.status}")
    print(f"    - components: {len(health.components)}")
except Exception as e:
    print(f"  ✗ 测试失败: {e}")
    sys.exit(1)

# 测试12: 文档类型枚举验证
print("\n测试12: 文档类型枚举验证")
print("-" * 80)

try:
    from src.common.constants import DocType
    
    valid_types = [dt.value for dt in DocType]
    print(f"  ✓ 支持的文档类型数量: {len(valid_types)}")
    
    # 测试所有文档类型都可以用于过滤
    for doc_type_value in valid_types[:5]:  # 只测试前5个
        test_filter = FilterParams(doc_type=doc_type_value)
        assert test_filter.doc_type == doc_type_value
    print(f"  ✓ 文档类型验证通过（测试了前5个）")
    
    # 测试多个文档类型
    multi_filter = FilterParams(doc_type=valid_types[:3])
    assert isinstance(multi_filter.doc_type, list)
    assert len(multi_filter.doc_type) == 3
    print(f"  ✓ 多个文档类型过滤验证通过")
    
except Exception as e:
    print(f"  ✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("所有 Schema 测试通过！✓")
print("=" * 80)
print()
print("总结:")
print("  ✓ Schema 定义正确")
print("  ✓ 文档类型过滤支持（单个和多个）")
print("  ✓ 所有请求/响应模型验证通过")
print("  ✓ 错误处理正确（无效文档类型会抛出异常）")
print()
print("下一步:")
print("  1. 启动 API 服务: python -m src.api.main")
print("  2. 运行完整测试: python examples/test_retrieval_api.py")
