# -*- coding: utf-8 -*-
"""
测试公司名称搜索接口
POST /api/v1/document/company-code-search
"""

import requests
import time
from typing import Dict, Any, List


BASE_URL = "http://localhost:8000"

# 测试数据
TEST_COMPANIES = [
    {"name": "平安银行", "code": "000001"},
    {"name": "万科A", "code": "000002"},
    {"name": "万科", "code": "000002"},  # 测试简称
    {"name": "神州高铁", "code": "000008"},
]


def test_company_code_search(company_name: str, expected_code: str = None) -> Dict[str, Any]:
    """测试公司名称搜索接口"""
    test_name = "POST /api/v1/document/company-code-search"
    start_time = time.time()

    payload = {
        "company_name": company_name
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/document/company-code-search",
            json=payload,
            timeout=10
        )
        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            stock_code = data.get("stock_code")
            message = data.get("message")

            # 判断测试是否通过
            if stock_code:
                # 如果有期望的代码，检查是否匹配
                if expected_code:
                    status = "PASS" if stock_code == expected_code else "MISMATCH"
                    error = None if status == "PASS" else f"Expected {expected_code}, got {stock_code}"
                else:
                    status = "PASS"
                    error = None
            else:
                # 没有找到股票代码
                if message:
                    status = "MULTIPLE_CANDIDATES"
                    error = f"Multiple matches: {message[:100]}..."
                else:
                    status = "NOT_FOUND"
                    error = "Stock code not found"

            return {
                "test_name": test_name,
                "company_name": company_name,
                "expected_code": expected_code,
                "stock_code": stock_code,
                "status": status,
                "elapsed_time": f"{elapsed:.3f}s",
                "status_code": response.status_code,
                "error": error
            }
        else:
            return {
                "test_name": test_name,
                "company_name": company_name,
                "expected_code": expected_code,
                "stock_code": None,
                "status": "FAIL",
                "elapsed_time": f"{elapsed:.3f}s",
                "status_code": response.status_code,
                "error": f"HTTP {response.status_code}: {response.text[:100]}"
            }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "test_name": test_name,
            "company_name": company_name,
            "expected_code": expected_code,
            "stock_code": None,
            "status": "ERROR",
            "elapsed_time": f"{elapsed:.3f}s",
            "status_code": None,
            "error": str(e)
        }


def run_tests() -> List[Dict[str, Any]]:
    """运行所有公司名称搜索测试"""
    results = []
    total_tests = len(TEST_COMPANIES)

    print("=" * 60)
    print("测试公司名称搜索接口: POST /api/v1/document/company-code-search")
    print("=" * 60)
    print(f"总测试数: {total_tests}")
    print()

    test_count = 0
    for company in TEST_COMPANIES:
        test_count += 1
        print(f"[{test_count}/{total_tests}] 测试搜索 '{company['name']}'")

        result = test_company_code_search(
            company['name'],
            company['code']
        )
        results.append(result)

        print(f"  状态: {result['status']} | 耗时: {result['elapsed_time']}")
        if result['stock_code']:
            print(f"  股票代码: {result['stock_code']}")
        if result['error']:
            print(f"  错误: {result['error']}")

    # 汇总
    passed = sum(1 for r in results if r['status'] == 'PASS')
    failed = sum(1 for r in results if r['status'] in ['FAIL', 'ERROR', 'MISMATCH'])
    other = sum(1 for r in results if r['status'] in ['NOT_FOUND', 'MULTIPLE_CANDIDATES'])

    print(f"\n总计: {passed}/{total_tests} 通过, {other} 其他, {failed} 失败")

    return results


if __name__ == "__main__":
    results = run_tests()

    # 返回退出码
    if any(r['status'] in ['FAIL', 'ERROR'] for r in results):
        exit(1)
    else:
        exit(0)
