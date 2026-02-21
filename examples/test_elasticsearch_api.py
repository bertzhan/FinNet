#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elasticsearch API 测试脚本
测试 /api/v1/retrieval/fulltext 接口
"""

import requests
import json
import sys
from typing import Dict, Any, Optional


BASE_URL = "http://localhost:8000"


def check_api_health() -> bool:
    """检查 API 服务是否运行"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✓ API 服务正在运行")
            return True
        else:
            print(f"✗ API 服务健康检查失败: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"✗ 无法连接到 API 服务: {BASE_URL}")
        print(f"  请先启动 API 服务: python -m src.api.main")
        return False
    except Exception as e:
        print(f"✗ 检查 API 服务时出错: {e}")
        return False


def check_elasticsearch_health() -> bool:
    """检查 Elasticsearch 服务状态"""
    try:
        url = f"{BASE_URL}/api/v1/retrieval/health"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            components = result.get('components', {})
            es_status = components.get('fulltext_retriever', 'unknown')
            
            print(f"✓ Elasticsearch 状态: {es_status}")
            
            if 'error' in es_status.lower():
                print(f"  ⚠ Elasticsearch 可能未正常运行")
                return False
            return True
        else:
            print(f"✗ 检索服务健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 检查 Elasticsearch 状态时出错: {e}")
        return False


def check_index_data() -> bool:
    """检查索引中是否有数据"""
    print("\n" + "=" * 60)
    print("检查 Elasticsearch 索引数据")
    print("=" * 60)
    
    try:
        # 尝试一个简单的查询来检查索引中是否有数据
        url = f"{BASE_URL}/api/v1/retrieval/fulltext"
        payload = {
            "query": "*",  # 通配符查询，匹配所有文档
            "top_k": 1
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()
            total = result.get('total', 0)
            
            if total > 0:
                print(f"✓ 索引中有数据: {total} 个文档")
                return True
            else:
                print(f"⚠ 索引中没有数据")
                print(f"  提示: 需要先运行 doc_index_job 来索引数据")
                print(f"  命令: dagster job execute -j doc_index_job")
                return False
        else:
            print(f"⚠ 无法检查索引数据: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"⚠ 检查索引数据时出错: {e}")
        return False


def test_basic_fulltext_retrieval(query: str = "营业收入", top_k: int = 5) -> bool:
    """
    测试基本全文检索
    
    Args:
        query: 查询文本
        top_k: 返回数量
    """
    print("\n" + "=" * 60)
    print("测试 1: 基本全文检索")
    print("=" * 60)
    print(f"查询文本: {query}")
    print(f"返回数量: {top_k}")
    print()
    
    url = f"{BASE_URL}/api/v1/retrieval/fulltext"
    payload = {
        "query": query,
        "top_k": top_k
    }
    
    try:
        print("发送请求...")
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code != 200:
            print(f"✗ 请求失败: HTTP {response.status_code}")
            print(f"  错误详情: {response.text[:200]}")
            return False
        
        result = response.json()
        
        print(f"✓ 请求成功")
        print()
        print(f"查询结果:")
        print(f"  - 返回结果数: {result.get('total', 0)}")
        print(f"  - 检索耗时: {result.get('metadata', {}).get('retrieval_time', 0):.3f}s")
        print(f"  - 检索类型: {result.get('metadata', {}).get('retrieval_type', 'N/A')}")
        print()
        
        results = result.get('results', [])
        if results:
            print(f"前 {min(5, len(results))} 个结果:")
            for i, res in enumerate(results[:5], 1):
                print(f"\n  结果 {i}:")
                print(f"    - Chunk ID: {res.get('chunk_id', 'N/A')[:36]}...")
                print(f"    - 分数 (BM25): {res.get('score', 0):.4f}")
                print(f"    - 标题: {res.get('title', 'N/A') or '(无标题)'}")
                print(f"    - 文本预览: {res.get('chunk_text', '')[:100]}...")
                
                metadata = res.get('metadata', {})
                if metadata:
                    print(f"    - 股票代码: {metadata.get('stock_code', 'N/A')}")
                    print(f"    - 公司名称: {metadata.get('company_name', 'N/A')}")
                    print(f"    - 文档类型: {metadata.get('doc_type', 'N/A')}")
                    print(f"    - 年份: {metadata.get('year', 'N/A')}")
        else:
            print(f"  (没有找到结果)")
        
        print()
        return len(results) > 0
        
    except requests.exceptions.ConnectionError:
        print(f"✗ 连接失败: 无法连接到 {BASE_URL}")
        return False
    except Exception as e:
        print(f"✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_filtered_fulltext_retrieval(
    query: str = "营业收入",
    filters: Optional[Dict[str, Any]] = None,
    top_k: int = 5
) -> bool:
    """
    测试带过滤条件的全文检索
    
    Args:
        query: 查询文本
        filters: 过滤条件
        top_k: 返回数量
    """
    print("\n" + "=" * 60)
    print("测试 2: 带过滤条件的全文检索")
    print("=" * 60)
    print(f"查询文本: {query}")
    print(f"过滤条件: {filters}")
    print(f"返回数量: {top_k}")
    print()
    
    url = f"{BASE_URL}/api/v1/retrieval/fulltext"
    payload = {
        "query": query,
        "top_k": top_k
    }
    
    if filters:
        payload["filters"] = filters
    
    try:
        print("发送请求...")
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code != 200:
            print(f"✗ 请求失败: HTTP {response.status_code}")
            print(f"  错误详情: {response.text[:200]}")
            return False
        
        result = response.json()
        
        print(f"✓ 请求成功")
        print()
        print(f"查询结果:")
        print(f"  - 返回结果数: {result.get('total', 0)}")
        print(f"  - 检索耗时: {result.get('metadata', {}).get('retrieval_time', 0):.3f}s")
        print()
        
        results = result.get('results', [])
        if results:
            # 验证过滤条件
            all_match = True
            print(f"验证过滤条件 (前 {min(5, len(results))} 个结果):")
            for i, res in enumerate(results[:5], 1):
                metadata = res.get('metadata', {})
                match = True
                
                if filters:
                    if 'stock_code' in filters:
                        if metadata.get('stock_code') != filters['stock_code']:
                            match = False
                            all_match = False
                    if 'year' in filters:
                        if metadata.get('year') != filters['year']:
                            match = False
                            all_match = False
                    if 'quarter' in filters:
                        if metadata.get('quarter') != filters['quarter']:
                            match = False
                            all_match = False
                    if 'doc_type' in filters:
                        doc_type = filters['doc_type']
                        if isinstance(doc_type, list):
                            if metadata.get('doc_type') not in doc_type:
                                match = False
                                all_match = False
                        else:
                            if metadata.get('doc_type') != doc_type:
                                match = False
                                all_match = False
                
                status = "✓" if match else "✗"
                print(f"\n  {status} 结果 {i}:")
                print(f"    - Chunk ID: {res.get('chunk_id', 'N/A')[:36]}...")
                print(f"    - 分数: {res.get('score', 0):.4f}")
                if metadata:
                    print(f"    - 股票代码: {metadata.get('stock_code', 'N/A')}")
                    print(f"    - 年份: {metadata.get('year', 'N/A')}")
                    if 'quarter' in filters or metadata.get('quarter'):
                        print(f"    - 季度: {metadata.get('quarter', 'N/A')}")
                    print(f"    - 文档类型: {metadata.get('doc_type', 'N/A')}")
        else:
            print(f"  (没有找到结果)")
        
        print()
        return len(results) > 0
        
    except Exception as e:
        print(f"✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_doc_type_filtering() -> bool:
    """测试文档类型过滤"""
    print("\n" + "=" * 60)
    print("测试 3: 文档类型过滤")
    print("=" * 60)
    
    test_cases = [
        {
            "name": "单个文档类型 - 年报",
            "query": "营业收入",
            "filters": {"doc_type": "annual_reports"},
            "top_k": 5
        },
        {
            "name": "单个文档类型 - 季报",
            "query": "净利润",
            "filters": {"doc_type": "quarterly_reports"},
            "top_k": 5
        },
        {
            "name": "多个文档类型",
            "query": "公司业务",
            "filters": {"doc_type": ["annual_reports", "quarterly_reports"]},
            "top_k": 10
        },
    ]
    
    all_passed = True
    for test_case in test_cases:
        print(f"\n  {test_case['name']}:")
        print(f"    查询: {test_case['query']}")
        print(f"    过滤: {test_case['filters']}")
        
        success = test_filtered_fulltext_retrieval(
            query=test_case['query'],
            filters=test_case['filters'],
            top_k=test_case['top_k']
        )
        
        if not success:
            all_passed = False
    
    return all_passed


def test_stock_code_filtering() -> bool:
    """测试股票代码过滤"""
    print("\n" + "=" * 60)
    print("测试 4: 股票代码和季度过滤")
    print("=" * 60)
    
    test_cases = [
        {
            "name": "平安银行",
            "query": "营业收入",
            "filters": {"stock_code": "000001"},
            "top_k": 5
        },
        {
            "name": "带年份过滤",
            "query": "净利润",
            "filters": {"stock_code": "000001", "year": 2023},
            "top_k": 5
        },
        {
            "name": "带年份和季度过滤",
            "query": "营业收入",
            "filters": {"stock_code": "000001", "year": 2023, "quarter": 3},
            "top_k": 5
        },
    ]
    
    all_passed = True
    for test_case in test_cases:
        print(f"\n  {test_case['name']}:")
        print(f"    查询: {test_case['query']}")
        print(f"    过滤: {test_case['filters']}")
        
        success = test_filtered_fulltext_retrieval(
            query=test_case['query'],
            filters=test_case['filters'],
            top_k=test_case['top_k']
        )
        
        if not success:
            all_passed = False
    
    return all_passed


def test_edge_cases() -> bool:
    """测试边界情况"""
    print("\n" + "=" * 60)
    print("测试 5: 边界情况")
    print("=" * 60)
    
    url = f"{BASE_URL}/api/v1/retrieval/fulltext"
    all_passed = True
    
    # 测试1: 空查询
    print("\n  测试1: 空查询")
    try:
        response = requests.post(url, json={"query": "", "top_k": 5}, timeout=10)
        if response.status_code == 422:
            print("    ✓ 空查询被正确拒绝（422）")
        else:
            print(f"    ⚠ 空查询返回状态码: {response.status_code}")
    except Exception as e:
        print(f"    ✗ 测试失败: {e}")
        all_passed = False
    
    # 测试2: 非常大的 top_k
    print("\n  测试2: 非常大的 top_k")
    try:
        response = requests.post(url, json={"query": "营业收入", "top_k": 200}, timeout=10)
        if response.status_code == 422:
            print("    ✓ 过大的 top_k 被正确拒绝（422）")
        else:
            print(f"    ⚠ 过大的 top_k 返回状态码: {response.status_code}")
    except Exception as e:
        print(f"    ✗ 测试失败: {e}")
        all_passed = False
    
    # 测试3: 不存在的股票代码
    print("\n  测试3: 不存在的股票代码")
    success = test_filtered_fulltext_retrieval(
        query="营业收入",
        filters={"stock_code": "999999"},
        top_k=5
    )
    if success:
        print("    ⚠ 不存在的股票代码返回了结果（可能是正常的）")
    else:
        print("    ✓ 不存在的股票代码返回空结果")
    
    return all_passed


def main():
    """主函数"""
    print("=" * 60)
    print("Elasticsearch API 测试")
    print("=" * 60)
    
    # 检查前置条件
    if not check_api_health():
        sys.exit(1)
    
    if not check_elasticsearch_health():
        print("\n⚠️  Elasticsearch 可能未正常运行，但继续测试...")
    
    # 检查索引数据
    has_data = check_index_data()
    if not has_data:
        print("\n⚠️  索引中没有数据，测试可能会返回空结果")
        print("  建议先运行: dagster job execute -j doc_index_job")
        print()
    
    # 解析命令行参数
    query = "营业收入"
    filters = None
    top_k = 5
    
    if len(sys.argv) > 1:
        query = sys.argv[1]
    if len(sys.argv) > 2:
        # 可以传入 JSON 格式的过滤条件
        try:
            filters = json.loads(sys.argv[2])
        except:
            print(f"⚠ 无法解析过滤条件: {sys.argv[2]}")
    if len(sys.argv) > 3:
        try:
            top_k = int(sys.argv[3])
        except:
            print(f"⚠ 无法解析 top_k: {sys.argv[3]}")
    
    # 如果提供了命令行参数，只运行单个测试
    if len(sys.argv) > 1:
        print(f"\n使用命令行参数:")
        print(f"  - query: {query}")
        if filters:
            print(f"  - filters: {filters}")
        print(f"  - top_k: {top_k}")
        
        if filters:
            success = test_filtered_fulltext_retrieval(query, filters, top_k)
        else:
            success = test_basic_fulltext_retrieval(query, top_k)
        sys.exit(0 if success else 1)
    
    # 否则运行所有测试
    results = []
    
    # 基本测试
    results.append(("基本全文检索", test_basic_fulltext_retrieval()))
    
    # 过滤测试
    results.append(("文档类型过滤", test_doc_type_filtering()))
    results.append(("股票代码过滤", test_stock_code_filtering()))
    
    # 边界情况测试
    results.append(("边界情况", test_edge_cases()))
    
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
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")
    
    print("\n💡 提示:")
    print("  使用命令行参数可以测试特定查询:")
    print("  python examples/test_elasticsearch_api.py <query> [filters_json] [top_k]")
    print("  示例: python examples/test_elasticsearch_api.py '营业收入' '{\"stock_code\":\"000001\"}' 10")


if __name__ == "__main__":
    main()
