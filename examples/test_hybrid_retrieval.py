# -*- coding: utf-8 -*-
"""
混合检索接口测试
测试移除图检索后的混合检索功能
"""

import requests
import json
import sys
from typing import Dict, Any


BASE_URL = "http://localhost:8000"


def test_hybrid_retrieval_basic():
    """测试基本混合检索功能"""
    print("\n=== 测试1: 基本混合检索（使用默认权重）===")
    
    url = f"{BASE_URL}/api/v1/retrieval/hybrid"
    payload = {
        "query": "平安银行营业收入",
        "filters": {
            "stock_code": "000001",
            "year": 2024,
            "doc_type": ["annual_reports", "quarterly_reports"]
        },
        "top_k": 10
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        print(f"✓ 混合检索成功")
        print(f"  返回结果数: {result.get('total', 0)}")
        print(f"  检索耗时: {result.get('metadata', {}).get('retrieval_time', 0):.3f}s")
        print(f"  检索类型: {result.get('metadata', {}).get('retrieval_type', 'N/A')}")
        
        if result.get('results'):
            print(f"\n  前3个结果:")
            for i, res in enumerate(result['results'][:3], 1):
                print(f"    {i}. 分块ID: {res.get('chunk_id', '')[:36]}...")
                print(f"       分数: {res.get('score', 0):.6f}")
                print(f"       融合方法: {res.get('metadata', {}).get('fusion_method', 'N/A')}")
                print(f"       RRF分数: {res.get('metadata', {}).get('rrf_score', 'N/A')}")
                print(f"       文本预览: {res.get('chunk_text', '')[:80]}...")
                print()
        else:
            print("  警告: 未返回任何结果")
        
        return True
    except requests.exceptions.ConnectionError:
        print(f"✗ 连接失败: 无法连接到 {BASE_URL}")
        print(f"  请确保 API 服务正在运行")
        return False
    except requests.exceptions.Timeout:
        print(f"✗ 请求超时")
        return False
    except requests.exceptions.HTTPError as e:
        print(f"✗ HTTP错误: {e}")
        if e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"  错误详情: {json.dumps(error_detail, indent=2, ensure_ascii=False)}")
            except:
                print(f"  响应内容: {e.response.text[:500]}")
        return False
    except Exception as e:
        print(f"✗ 混合检索失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_hybrid_retrieval_custom_weights():
    """测试自定义权重的混合检索"""
    print("\n=== 测试2: 自定义权重混合检索 ===")
    
    url = f"{BASE_URL}/api/v1/retrieval/hybrid"
    payload = {
        "query": "万科营业收入",
        "filters": {
            "stock_code": "000002",
            "year": 2024,
            "doc_type": ["annual_reports"]
        },
        "top_k": 5,
        "hybrid_weights": {
            "vector": 0.7,
            "fulltext": 0.3
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        print(f"✓ 自定义权重混合检索成功")
        print(f"  返回结果数: {result.get('total', 0)}")
        print(f"  检索耗时: {result.get('metadata', {}).get('retrieval_time', 0):.3f}s")
        
        if result.get('results'):
            print(f"\n  前2个结果:")
            for i, res in enumerate(result['results'][:2], 1):
                print(f"    {i}. 分数: {res.get('score', 0):.6f}")
                print(f"       文本预览: {res.get('chunk_text', '')[:60]}...")
        
        return True
    except Exception as e:
        print(f"✗ 自定义权重混合检索失败: {e}")
        return False


def test_hybrid_retrieval_invalid_graph_weight():
    """测试包含 graph 权重的请求（应该被拒绝）"""
    print("\n=== 测试3: 验证 graph 权重被拒绝 ===")
    
    url = f"{BASE_URL}/api/v1/retrieval/hybrid"
    payload = {
        "query": "平安银行营业收入",
        "top_k": 5,
        "hybrid_weights": {
            "vector": 0.5,
            "fulltext": 0.3,
            "graph": 0.2  # 这个应该被拒绝
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 422:
            print(f"✓ Schema 验证正确拒绝了包含 graph 的权重")
            try:
                error_detail = response.json()
                print(f"  错误详情: {error_detail.get('detail', 'N/A')}")
            except:
                pass
            return True
        else:
            print(f"✗ 预期应该返回 422 错误，但返回了 {response.status_code}")
            print(f"  响应: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_vector_only():
    """测试仅向量检索（权重为1.0）"""
    print("\n=== 测试4: 仅向量检索（fulltext权重为0）===")
    
    url = f"{BASE_URL}/api/v1/retrieval/hybrid"
    payload = {
        "query": "平安银行营业收入",
        "filters": {
            "stock_code": "000001",
            "year": 2024
        },
        "top_k": 5,
        "hybrid_weights": {
            "vector": 1.0,
            "fulltext": 0.0
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        print(f"✓ 仅向量检索成功")
        print(f"  返回结果数: {result.get('total', 0)}")
        print(f"  检索耗时: {result.get('metadata', {}).get('retrieval_time', 0):.3f}s")
        
        return True
    except Exception as e:
        print(f"✗ 仅向量检索失败: {e}")
        return False


def test_fulltext_only():
    """测试仅全文检索（向量权重为0）"""
    print("\n=== 测试5: 仅全文检索（vector权重为0）===")
    
    url = f"{BASE_URL}/api/v1/retrieval/hybrid"
    payload = {
        "query": "万科营业收入",
        "filters": {
            "stock_code": "000002",
            "year": 2024
        },
        "top_k": 5,
        "hybrid_weights": {
            "vector": 0.0,
            "fulltext": 1.0
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        print(f"✓ 仅全文检索成功")
        print(f"  返回结果数: {result.get('total', 0)}")
        print(f"  检索耗时: {result.get('metadata', {}).get('retrieval_time', 0):.3f}s")
        
        return True
    except Exception as e:
        print(f"✗ 仅全文检索失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("=" * 80)
    print("混合检索接口测试")
    print("=" * 80)
    print(f"API地址: {BASE_URL}")
    print()
    
    results = []
    
    # 测试1: 基本混合检索
    results.append(("基本混合检索", test_hybrid_retrieval_basic()))
    
    # 测试2: 自定义权重
    results.append(("自定义权重", test_hybrid_retrieval_custom_weights()))
    
    # 测试3: 验证 graph 权重被拒绝
    results.append(("验证graph权重被拒绝", test_hybrid_retrieval_invalid_graph_weight()))
    
    # 测试4: 仅向量检索
    results.append(("仅向量检索", test_vector_only()))
    
    # 测试5: 仅全文检索
    results.append(("仅全文检索", test_fulltext_only()))
    
    # 汇总结果
    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status}: {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
