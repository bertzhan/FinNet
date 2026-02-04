# -*- coding: utf-8 -*-
"""
测试文档查询接口
POST /api/v1/document/query
"""

import requests
import time
from typing import Dict, Any, List


BASE_URL = "http://localhost:8000"

# 测试数据：三家公司，2024年四个季度
TEST_COMPANIES = [
    {"name": "平安银行", "code": "000001"},
    {"name": "万科A", "code": "000002"},
    {"name": "神州高铁", "code": "000008"},
]

# 测试数据：覆盖四个报告周期
TEST_CASES = [
    {"period": "Q1", "quarter": 1, "doc_type": "quarterly_reports"},
    {"period": "Q2", "quarter": 2, "doc_type": "interim_reports"},  # 半年报
    {"period": "Q3", "quarter": 3, "doc_type": "quarterly_reports"},
    {"period": "Year", "quarter": None, "doc_type": "annual_reports"},  # 年报
]
TEST_YEAR = 2024


def test_document_query(company_code: str, company_name: str, year: int, quarter: int, doc_type: str, period: str) -> Dict[str, Any]:
    """测试文档查询接口"""
    test_name = f"POST /api/v1/document/query"
    start_time = time.time()

    payload = {
        "stock_code": company_code,
        "year": year,
        "quarter": quarter,
        "doc_type": doc_type
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/document/query",
            json=payload,
            timeout=10
        )
        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            document_id = data.get("document_id")
            found = data.get("found", False)

            return {
                "test_name": test_name,
                "company_name": company_name,
                "company_code": company_code,
                "year": year,
                "quarter": quarter if quarter else "Year",
                "period": period,
                "doc_type": doc_type,
                "status": "PASS" if found else "NOT_FOUND",
                "elapsed_time": f"{elapsed:.3f}s",
                "status_code": response.status_code,
                "document_id": document_id,
                "error": None if found else "Document not found"
            }
        else:
            return {
                "test_name": test_name,
                "company_name": company_name,
                "company_code": company_code,
                "year": year,
                "quarter": quarter if quarter else "Year",
                "period": period,
                "doc_type": doc_type,
                "status": "FAIL",
                "elapsed_time": f"{elapsed:.3f}s",
                "status_code": response.status_code,
                "document_id": None,
                "error": f"HTTP {response.status_code}: {response.text[:100]}"
            }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "test_name": test_name,
            "company_name": company_name,
            "company_code": company_code,
            "year": year,
            "quarter": quarter if quarter else "Year",
            "period": period,
            "doc_type": doc_type,
            "status": "ERROR",
            "elapsed_time": f"{elapsed:.3f}s",
            "status_code": None,
            "document_id": None,
            "error": str(e)
        }


def run_tests() -> List[Dict[str, Any]]:
    """运行所有文档查询测试"""
    results = []
    total_tests = len(TEST_COMPANIES) * len(TEST_CASES)

    print("=" * 60)
    print("测试文档查询接口: POST /api/v1/document/query")
    print("=" * 60)
    print(f"测试公司: {', '.join([c['name'] for c in TEST_COMPANIES])}")
    print(f"测试年份: {TEST_YEAR}")
    print(f"测试周期: Q1(季报), Q2(半年报), Q3(季报), 年报")
    print(f"总测试数: {total_tests}")
    print()

    test_count = 0
    for company in TEST_COMPANIES:
        for test_case in TEST_CASES:
            test_count += 1
            period_label = f"{TEST_YEAR}{test_case['period']}"
            print(f"[{test_count}/{total_tests}] 测试 {company['name']} {period_label} ({test_case['doc_type']})")

            result = test_document_query(
                company['code'],
                company['name'],
                TEST_YEAR,
                test_case['quarter'],
                test_case['doc_type'],
                test_case['period']
            )
            results.append(result)

            print(f"  状态: {result['status']} | 耗时: {result['elapsed_time']}")
            if result['document_id']:
                print(f"  文档ID: {result['document_id'][:36]}...")
            if result['error']:
                print(f"  错误: {result['error']}")

    # 汇总
    passed = sum(1 for r in results if r['status'] == 'PASS')
    not_found = sum(1 for r in results if r['status'] == 'NOT_FOUND')
    failed = sum(1 for r in results if r['status'] in ['FAIL', 'ERROR'])

    print(f"\n总计: {passed}/{total_tests} 通过, {not_found} 未找到, {failed} 失败")

    return results


if __name__ == "__main__":
    results = run_tests()

    # 返回退出码（如果有PASS或NOT_FOUND都算成功，只有FAIL/ERROR算失败）
    if any(r['status'] in ['FAIL', 'ERROR'] for r in results):
        exit(1)
    else:
        exit(0)
