# -*- coding: utf-8 -*-
"""
测试混合检索接口
POST /api/v1/retrieval/hybrid
"""

import requests
import time
from typing import Dict, Any, List


BASE_URL = "http://localhost:8000"

# 测试数据
TEST_COMPANIES = [
    {"name": "平安银行", "code": "000001"},
    {"name": "万科A", "code": "000002"},
    {"name": "神州高铁", "code": "000008"},
]

TEST_QUARTERS = [1, 3]  # Q1和Q3有季报数据，Q2是半年报，Q4在年报中
TEST_YEAR = 2024
DOC_TYPE = "quarterly_reports"
TEST_QUERY = "营业收入和净利润情况"


def test_hybrid_retrieval(company_code: str, company_name: str, year: int, quarter: int) -> Dict[str, Any]:
    """测试混合检索接口"""
    test_name = "POST /api/v1/retrieval/hybrid"
    start_time = time.time()

    payload = {
        "query": TEST_QUERY,
        "filters": {
            "stock_code": company_code,
            "year": year,
            "quarter": quarter,
            "doc_type": DOC_TYPE
        },
        "top_k": 10,
        "hybrid_weights": {
            "vector": 0.5,
            "fulltext": 0.5
        }
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/retrieval/hybrid",
            json=payload,
            timeout=30
        )
        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            total = data.get("total", 0)

            return {
                "test_name": test_name,
                "company_name": company_name,
                "company_code": company_code,
                "year": year,
                "quarter": quarter,
                "status": "PASS" if total > 0 else "NO_RESULTS",
                "elapsed_time": f"{elapsed:.3f}s",
                "status_code": response.status_code,
                "results_count": total,
                "error": None if total > 0 else "No results returned"
            }
        else:
            return {
                "test_name": test_name,
                "company_name": company_name,
                "company_code": company_code,
                "year": year,
                "quarter": quarter,
                "status": "FAIL",
                "elapsed_time": f"{elapsed:.3f}s",
                "status_code": response.status_code,
                "results_count": 0,
                "error": f"HTTP {response.status_code}: {response.text[:100]}"
            }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "test_name": test_name,
            "company_name": company_name,
            "company_code": company_code,
            "year": year,
            "quarter": quarter,
            "status": "ERROR",
            "elapsed_time": f"{elapsed:.3f}s",
            "status_code": None,
            "results_count": 0,
            "error": str(e)
        }


def run_tests() -> List[Dict[str, Any]]:
    """运行所有混合检索测试"""
    results = []
    total_tests = len(TEST_COMPANIES) * len(TEST_QUARTERS)

    print("=" * 60)
    print("测试混合检索接口: POST /api/v1/retrieval/hybrid")
    print("=" * 60)
    print(f"测试公司: {', '.join([c['name'] for c in TEST_COMPANIES])}")
    print(f"测试年份: {TEST_YEAR}")
    print(f"测试季度: Q1, Q2, Q3, Q4")
    print(f"查询文本: {TEST_QUERY}")
    print(f"总测试数: {total_tests}")
    print()

    test_count = 0
    for company in TEST_COMPANIES:
        for quarter in TEST_QUARTERS:
            test_count += 1
            print(f"[{test_count}/{total_tests}] 测试 {company['name']} {TEST_YEAR}Q{quarter}")

            result = test_hybrid_retrieval(
                company['code'],
                company['name'],
                TEST_YEAR,
                quarter
            )
            results.append(result)

            print(f"  状态: {result['status']} | 耗时: {result['elapsed_time']}")
            if result['results_count'] > 0:
                print(f"  结果数量: {result['results_count']}")
            if result['error']:
                print(f"  错误: {result['error']}")

    # 汇总
    passed = sum(1 for r in results if r['status'] == 'PASS')
    no_results = sum(1 for r in results if r['status'] == 'NO_RESULTS')
    failed = sum(1 for r in results if r['status'] in ['FAIL', 'ERROR'])

    print(f"\n总计: {passed}/{total_tests} 通过, {no_results} 无结果, {failed} 失败")

    return results


if __name__ == "__main__":
    results = run_tests()

    # 返回退出码
    if any(r['status'] in ['FAIL', 'ERROR'] for r in results):
        exit(1)
    else:
        exit(0)
