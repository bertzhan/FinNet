# -*- coding: utf-8 -*-
"""
检索接口测试
测试各种检索接口（向量检索、全文检索、图检索、混合检索）
"""

import requests
import json
from typing import Dict, Any


BASE_URL = "http://localhost:8000"


def test_vector_retrieval():
    """测试向量检索接口"""
    print("\n=== 测试向量检索接口 ===")
    
    url = f"{BASE_URL}/api/v1/retrieval/vector"
    payload = {
        "query": "新晨科技2023年第三季度的营业收入",
        "filters": {
            "stock_code": "300542",
            "year": 2023,
            "quarter": 4,
            "doc_type": "quarterly_reports"
        },
        "top_k": 5
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        
        print(f"✓ 向量检索成功")
        print(f"  返回结果数: {result.get('total', 0)}")
        print(f"  检索耗时: {result.get('metadata', {}).get('retrieval_time', 0):.3f}s")
        
        if result.get('results'):
            print(f"  第一个结果:")
            first_result = result['results'][0]
            print(f"    - 分块ID: {first_result.get('chunk_id')[:20]}...")
            print(f"    - 分数: {first_result.get('score', 0):.3f}")
            print(f"    - 文本预览: {first_result.get('chunk_text', '')[:100]}...")
            print(f"    - 元数据: {first_result.get('metadata', {})}")
        
        return True
    except Exception as e:
        print(f"✗ 向量检索失败: {e}")
        return False


def test_fulltext_retrieval():
    """测试全文检索接口"""
    print("\n=== 测试全文检索接口 ===")
    
    url = f"{BASE_URL}/api/v1/retrieval/fulltext"
    payload = {
        "query": "营业收入 净利润",
        "filters": {
            "stock_code": "300542",
            "doc_type": "annual_reports"
        },
        "top_k": 10
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        
        print(f"✓ 全文检索成功")
        print(f"  返回结果数: {result.get('total', 0)}")
        print(f"  检索耗时: {result.get('metadata', {}).get('retrieval_time', 0):.3f}s")
        
        if result.get('results'):
            print(f"  第一个结果:")
            first_result = result['results'][0]
            print(f"    - 分块ID: {first_result.get('chunk_id')[:20]}...")
            print(f"    - 分数: {first_result.get('score', 0):.3f}")
            print(f"    - 文本预览: {first_result.get('chunk_text', '')[:100]}...")
        
        return True
    except Exception as e:
        print(f"✗ 全文检索失败: {e}")
        return False


def test_graph_retrieval_document():
    """测试图检索接口（文档检索）"""
    print("\n=== 测试图检索接口（文档检索） ===")
    
    url = f"{BASE_URL}/api/v1/retrieval/graph"
    payload = {
        "query": "300542",
        "query_type": "document",
        "filters": {
            "stock_code": "300542",
            "year": 2023,
            "doc_type": "annual_reports"
        },
        "top_k": 10
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        
        print(f"✓ 图检索（文档检索）成功")
        print(f"  返回结果数: {result.get('total', 0)}")
        print(f"  检索耗时: {result.get('metadata', {}).get('retrieval_time', 0):.3f}s")
        
        if result.get('results'):
            print(f"  第一个结果:")
            first_result = result['results'][0]
            print(f"    - 分块ID: {first_result.get('chunk_id')[:20]}...")
            print(f"    - 文本预览: {first_result.get('chunk_text', '')[:100]}...")
        
        return True
    except Exception as e:
        print(f"✗ 图检索失败: {e}")
        return False


def test_graph_retrieval_cypher():
    """测试图检索接口（自定义 Cypher 查询）"""
    print("\n=== 测试图检索接口（自定义 Cypher 查询） ===")
    
    url = f"{BASE_URL}/api/v1/retrieval/graph"
    payload = {
        "query_type": "cypher",
        "cypher_query": """
        MATCH (d:Document {stock_code: $stock_code})<-[:BELONGS_TO]-(c:Chunk)
        WHERE d.year = $year
        RETURN c.id as chunk_id
        LIMIT $limit
        """,
        "cypher_parameters": {
            "stock_code": "300542",
            "year": 2023,
            "limit": 5
        },
        "top_k": 5
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        
        print(f"✓ 图检索（Cypher 查询）成功")
        print(f"  返回结果数: {result.get('total', 0)}")
        
        return True
    except Exception as e:
        print(f"✗ 图检索（Cypher 查询）失败: {e}")
        return False


def test_hybrid_retrieval():
    """测试混合检索接口"""
    print("\n=== 测试混合检索接口 ===")
    
    url = f"{BASE_URL}/api/v1/retrieval/hybrid"
    payload = {
        "query": "新晨科技营业收入",
        "filters": {
            "stock_code": "300542",
            "year": 2023,
            "doc_type": ["annual_reports", "quarterly_reports"]
        },
        "top_k": 10,
        "hybrid_weights": {
            "vector": 0.5,
            "fulltext": 0.3,
            "graph": 0.2
        }
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        
        print(f"✓ 混合检索成功")
        print(f"  返回结果数: {result.get('total', 0)}")
        print(f"  检索耗时: {result.get('metadata', {}).get('retrieval_time', 0):.3f}s")
        
        if result.get('results'):
            print(f"  第一个结果:")
            first_result = result['results'][0]
            print(f"    - 分块ID: {first_result.get('chunk_id')[:20]}...")
            print(f"    - 分数: {first_result.get('score', 0):.3f}")
            print(f"    - 融合方法: {first_result.get('metadata', {}).get('fusion_method', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"✗ 混合检索失败: {e}")
        # 混合检索可能因为某些检索器不可用而失败，这是可以接受的
        if "混合检索器" in str(e) or "HybridRetriever" in str(e):
            print(f"  注意: 混合检索器可能未完全实现，这是可选的")
        return False


def test_retrieval_health():
    """测试检索服务健康检查"""
    print("\n=== 测试检索服务健康检查 ===")
    
    url = f"{BASE_URL}/api/v1/retrieval/health"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        result = response.json()
        
        print(f"✓ 健康检查成功")
        print(f"  状态: {result.get('status')}")
        print(f"  消息: {result.get('message')}")
        print(f"  组件状态:")
        for component, status in result.get('components', {}).items():
            print(f"    - {component}: {status}")
        
        return True
    except Exception as e:
        print(f"✗ 健康检查失败: {e}")
        return False


def test_company_name_search():
    """测试根据公司名称搜索股票代码接口"""
    print("\n=== 测试根据公司名称搜索股票代码接口 ===")
    
    url = f"{BASE_URL}/api/v1/retrieval/company-name-search"
    
    # 测试用例1: 完整公司名称
    payload = {
        "company_name": "平安银行",
        "top_k": 10
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        
        print(f"✓ 公司名称搜索成功")
        print(f"  查询公司名称: {result.get('company_name')}")
        print(f"  最可能的股票代码: {result.get('stock_code', 'N/A')}")
        print(f"  检索到的文档数: {result.get('total_documents', 0)}")
        print(f"  检索耗时: {result.get('metadata', {}).get('retrieval_time', 0):.3f}s")
        
        if result.get('all_candidates'):
            print(f"  所有候选股票代码:")
            for candidate in result['all_candidates']:
                print(f"    - {candidate.get('stock_code')}: {candidate.get('votes')} 票 "
                      f"(置信度: {candidate.get('confidence', 0):.1%})")
        
        # 测试用例2: 部分公司名称（模糊匹配）
        print(f"\n  测试部分公司名称匹配...")
        payload2 = {
            "company_name": "平安",
            "top_k": 10
        }
        response2 = requests.post(url, json=payload2)
        response2.raise_for_status()
        result2 = response2.json()
        
        print(f"  ✓ 部分名称搜索成功")
        print(f"    查询公司名称: {result2.get('company_name')}")
        print(f"    最可能的股票代码: {result2.get('stock_code', 'N/A')}")
        print(f"    检索到的文档数: {result2.get('total_documents', 0)}")
        
        return True
    except Exception as e:
        print(f"✗ 公司名称搜索失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_doc_type_filtering():
    """测试文档类型过滤"""
    print("\n=== 测试文档类型过滤 ===")
    
    # 测试单个文档类型
    url = f"{BASE_URL}/api/v1/retrieval/vector"
    payload = {
        "query": "营业收入",
        "filters": {
            "stock_code": "300542",
            "doc_type": "quarterly_reports"  # 单个文档类型
        },
        "top_k": 5
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        print(f"✓ 单个文档类型过滤成功: 返回 {result.get('total', 0)} 个结果")
    except Exception as e:
        print(f"✗ 单个文档类型过滤失败: {e}")
        return False
    
    # 测试多个文档类型
    payload = {
        "query": "公司业务情况",
        "filters": {
            "stock_code": "300542",
            "doc_type": ["ipo_prospectus", "annual_reports"]  # 多个文档类型
        },
        "top_k": 10
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        print(f"✓ 多个文档类型过滤成功: 返回 {result.get('total', 0)} 个结果")
        return True
    except Exception as e:
        print(f"✗ 多个文档类型过滤失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("检索接口测试")
    print("=" * 60)
    
    results = []
    
    # 测试健康检查
    results.append(("健康检查", test_retrieval_health()))
    
    # 测试各种检索接口
    results.append(("向量检索", test_vector_retrieval()))
    results.append(("全文检索", test_fulltext_retrieval()))
    results.append(("图检索（文档）", test_graph_retrieval_document()))
    results.append(("图检索（Cypher）", test_graph_retrieval_cypher()))
    results.append(("混合检索", test_hybrid_retrieval()))
    
    # 测试文档类型过滤
    results.append(("文档类型过滤", test_doc_type_filtering()))
    
    # 测试公司名称搜索
    results.append(("公司名称搜索", test_company_name_search()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status}: {test_name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！")
    else:
        print("⚠️  部分测试失败，请检查日志")


if __name__ == "__main__":
    main()
