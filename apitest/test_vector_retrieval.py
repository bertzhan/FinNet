# -*- coding: utf-8 -*-
"""
测试向量检索接口
POST /api/v1/retrieval/vector
"""

import requests
import time
from typing import Dict, Any, List
from test_config import BASE_URL, TEST_COMPANIES, TEST_YEAR, RETRIEVAL_TEST_CASES

TEST_QUERY = "营业收入和净利润"


def test_vector_retrieval(company_code: str, company_name: str, year: int, quarter: int, doc_type: str, period: str) -> Dict[str, Any]:
    """测试向量检索接口"""
    test_name = "POST /api/v1/retrieval/vector"
    start_time = time.time()

    payload = {
        "query": TEST_QUERY,
        "filters": {
            "stock_code": company_code,
            "year": year,
            "quarter": quarter,
            "doc_type": doc_type
        },
        "top_k": 5
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/retrieval/vector",
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
                "period": period,
                "doc_type": doc_type,
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
                "period": period,
                "doc_type": doc_type,
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
            "period": period,
            "doc_type": doc_type,
            "status": "ERROR",
            "elapsed_time": f"{elapsed:.3f}s",
            "status_code": None,
            "results_count": 0,
            "error": str(e)
        }


def run_tests() -> List[Dict[str, Any]]:
    """运行所有向量检索测试"""
    results = []
    total_tests = len(TEST_COMPANIES) * len(RETRIEVAL_TEST_CASES)

    print("=" * 60)
    print("测试向量检索接口: POST /api/v1/retrieval/vector")
    print("=" * 60)
    print(f"测试公司: {', '.join([c['name'] for c in TEST_COMPANIES])}")
    print(f"测试年份: {TEST_YEAR}")
    print(f"测试周期: Q1(季报), Q2(半年报), Q3(季报)")
    print(f"查询文本: {TEST_QUERY}")
    print(f"总测试数: {total_tests}")
    print()

    test_count = 0
    for company in TEST_COMPANIES:
        for test_case in RETRIEVAL_TEST_CASES:
            test_count += 1
            period_label = f"{TEST_YEAR}{test_case['period']}"
            print(f"[{test_count}/{total_tests}] 测试 {company['name']} {period_label} ({test_case['doc_type']})")

            result = test_vector_retrieval(
                company['code'],
                company['name'],
                TEST_YEAR,
                test_case['quarter'],
                test_case['doc_type'],
                test_case['period']
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
