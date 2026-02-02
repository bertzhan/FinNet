# -*- coding: utf-8 -*-
"""
向量检索接口测试
测试向量检索功能
"""

import requests
import json
import sys
from typing import Dict, Any


BASE_URL = "http://localhost:8000"


def test_vector_retrieval_pingan():
    """测试平安银行向量检索"""
    print("\n=== 测试1: 平安银行向量检索（2024年）===")
    
    url = f"{BASE_URL}/api/v1/retrieval/vector"
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
        
        print(f"✓ 向量检索成功")
        print(f"  返回结果数: {result.get('total', 0)}")
        print(f"  检索耗时: {result.get('metadata', {}).get('retrieval_time', 0):.3f}s")
        print(f"  检索类型: {result.get('metadata', {}).get('retrieval_type', 'N/A')}")
        
        if result.get('results'):
            print(f"\n  前5个结果:")
            for i, res in enumerate(result['results'][:5], 1):
                print(f"    {i}. 分块ID: {res.get('chunk_id', '')[:36]}...")
                print(f"       分数: {res.get('score', 0):.6f}")
                print(f"       标题: {res.get('title', 'N/A')}")
                print(f"       文本预览: {res.get('chunk_text', '')[:80]}...")
                print(f"       元数据: stock_code={res.get('metadata', {}).get('stock_code', 'N/A')}, "
                      f"year={res.get('metadata', {}).get('year', 'N/A')}, "
                      f"doc_type={res.get('metadata', {}).get('doc_type', 'N/A')}")
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
        print(f"✗ 向量检索失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vector_retrieval_wanke():
    """测试万科向量检索"""
    print("\n=== 测试2: 万科向量检索（2024年）===")
    
    url = f"{BASE_URL}/api/v1/retrieval/vector"
    payload = {
        "query": "万科营业收入",
        "filters": {
            "stock_code": "000002",
            "year": 2024,
            "doc_type": ["annual_reports"]
        },
        "top_k": 5
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        print(f"✓ 向量检索成功")
        print(f"  返回结果数: {result.get('total', 0)}")
        print(f"  检索耗时: {result.get('metadata', {}).get('retrieval_time', 0):.3f}s")
        
        if result.get('results'):
            print(f"\n  前3个结果:")
            for i, res in enumerate(result['results'][:3], 1):
                print(f"    {i}. 分数: {res.get('score', 0):.6f}")
                print(f"       标题: {res.get('title', 'N/A')}")
                print(f"       文本预览: {res.get('chunk_text', '')[:60]}...")
                print()
        
        return True
    except Exception as e:
        print(f"✗ 向量检索失败: {e}")
        return False


def test_vector_retrieval_with_quarter():
    """测试带季度过滤的向量检索"""
    print("\n=== 测试3: 平安银行向量检索（2024年Q4）===")
    
    url = f"{BASE_URL}/api/v1/retrieval/vector"
    payload = {
        "query": "平安银行营业收入",
        "filters": {
            "stock_code": "000001",
            "year": 2024,
            "quarter": 4,
            "doc_type": "quarterly_reports"
        },
        "top_k": 5
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        print(f"✓ 向量检索成功")
        print(f"  返回结果数: {result.get('total', 0)}")
        print(f"  检索耗时: {result.get('metadata', {}).get('retrieval_time', 0):.3f}s")
        
        if result.get('results'):
            print(f"\n  前2个结果:")
            for i, res in enumerate(result['results'][:2], 1):
                print(f"    {i}. 分数: {res.get('score', 0):.6f}")
                print(f"       季度: {res.get('metadata', {}).get('quarter', 'N/A')}")
                print(f"       文本预览: {res.get('chunk_text', '')[:60]}...")
        
        return True
    except Exception as e:
        print(f"✗ 向量检索失败: {e}")
        return False


def test_vector_retrieval_no_filters():
    """测试无过滤条件的向量检索"""
    print("\n=== 测试4: 无过滤条件的向量检索 ===")
    
    url = f"{BASE_URL}/api/v1/retrieval/vector"
    payload = {
        "query": "营业收入",
        "top_k": 5
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        print(f"✓ 向量检索成功")
        print(f"  返回结果数: {result.get('total', 0)}")
        print(f"  检索耗时: {result.get('metadata', {}).get('retrieval_time', 0):.3f}s")
        
        if result.get('results'):
            print(f"\n  前2个结果:")
            for i, res in enumerate(result['results'][:2], 1):
                print(f"    {i}. 分数: {res.get('score', 0):.6f}")
                print(f"       公司: {res.get('metadata', {}).get('company_name', 'N/A')}")
                print(f"       文本预览: {res.get('chunk_text', '')[:60]}...")
        
        return True
    except Exception as e:
        print(f"✗ 向量检索失败: {e}")
        return False


def test_vector_retrieval_semantic_query():
    """测试语义查询（非关键词匹配）"""
    print("\n=== 测试5: 语义查询测试 ===")
    
    url = f"{BASE_URL}/api/v1/retrieval/vector"
    payload = {
        "query": "公司的主要收入来源是什么",
        "filters": {
            "stock_code": "000001",
            "year": 2024
        },
        "top_k": 5
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        print(f"✓ 语义查询成功")
        print(f"  返回结果数: {result.get('total', 0)}")
        print(f"  检索耗时: {result.get('metadata', {}).get('retrieval_time', 0):.3f}s")
        
        if result.get('results'):
            print(f"\n  前2个结果:")
            for i, res in enumerate(result['results'][:2], 1):
                print(f"    {i}. 分数: {res.get('score', 0):.6f}")
                print(f"       文本预览: {res.get('chunk_text', '')[:60]}...")
        
        return True
    except Exception as e:
        print(f"✗ 语义查询失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("=" * 80)
    print("向量检索接口测试")
    print("=" * 80)
    print(f"API地址: {BASE_URL}")
    print()
    
    results = []
    
    # 测试1: 平安银行向量检索
    results.append(("平安银行向量检索", test_vector_retrieval_pingan()))
    
    # 测试2: 万科向量检索
    results.append(("万科向量检索", test_vector_retrieval_wanke()))
    
    # 测试3: 带季度过滤
    results.append(("带季度过滤", test_vector_retrieval_with_quarter()))
    
    # 测试4: 无过滤条件
    results.append(("无过滤条件", test_vector_retrieval_no_filters()))
    
    # 测试5: 语义查询
    results.append(("语义查询", test_vector_retrieval_semantic_query()))
    
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
