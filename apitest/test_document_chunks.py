# -*- coding: utf-8 -*-
"""
测试文档chunks接口
GET /api/v1/document/{document_id}/chunks
"""

import requests
import time
from typing import Dict, Any, List, Optional
from test_config import BASE_URL, TEST_COMPANIES, TEST_YEAR, TEST_CASES


def get_document_id(company_code: str, year: int, quarter: int, doc_type: str) -> Optional[str]:
    """先查询document_id"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/document/query",
            json={
                "stock_code": company_code,
                "year": year,
                "quarter": quarter,
                "doc_type": doc_type
            },
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("found"):
                return data.get("document_id")
        return None
    except:
        return None


def test_document_chunks(document_id: str, company_name: str, company_code: str, year: int, quarter: int, doc_type: str, period: str) -> Dict[str, Any]:
    """测试文档chunks接口"""
    test_name = f"GET /api/v1/document/{document_id[:8]}.../chunks"
    start_time = time.time()

    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/document/{document_id}/chunks",
            timeout=30
        )
        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            chunks = data.get("chunks", [])
            total = data.get("total", 0)

            return {
                "test_name": test_name,
                "company_name": company_name,
                "company_code": company_code,
                "year": year,
                "quarter": quarter if quarter else "Year",
                "period": period,
                "doc_type": doc_type,
                "status": "PASS",
                "elapsed_time": f"{elapsed:.3f}s",
                "status_code": response.status_code,
                "chunks_count": total,
                "error": None
            }
        elif response.status_code == 404:
            elapsed = time.time() - start_time
            return {
                "test_name": test_name,
                "company_name": company_name,
                "company_code": company_code,
                "year": year,
                "quarter": quarter if quarter else "Year",
                "period": period,
                "doc_type": doc_type,
                "status": "NOT_FOUND",
                "elapsed_time": f"{elapsed:.3f}s",
                "status_code": response.status_code,
                "chunks_count": 0,
                "error": "Document not found"
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
                "chunks_count": 0,
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
            "chunks_count": 0,
            "error": str(e)
        }


def run_tests() -> List[Dict[str, Any]]:
    """运行所有文档chunks测试"""
    results = []
    total_tests = len(TEST_COMPANIES) * len(TEST_CASES)

    print("=" * 60)
    print("测试文档chunks接口: GET /api/v1/document/{document_id}/chunks")
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

            # 先获取document_id
            document_id = get_document_id(
                company['code'],
                TEST_YEAR,
                test_case['quarter'],
                test_case['doc_type']
            )

            if not document_id:
                results.append({
                    "test_name": "GET /api/v1/document/{document_id}/chunks",
                    "company_name": company['name'],
                    "company_code": company['code'],
                    "year": TEST_YEAR,
                    "quarter": test_case['quarter'] if test_case['quarter'] else "Year",
                    "period": test_case['period'],
                    "doc_type": test_case['doc_type'],
                    "status": "SKIP",
                    "elapsed_time": "0.000s",
                    "status_code": None,
                    "chunks_count": 0,
                    "error": "Document ID not found, skipped"
                })
                print(f"  状态: SKIP | 原因: 未找到document_id")
                continue

            result = test_document_chunks(
                document_id,
                company['name'],
                company['code'],
                TEST_YEAR,
                test_case['quarter'],
                test_case['doc_type'],
                test_case['period']
            )
            results.append(result)

            print(f"  状态: {result['status']} | 耗时: {result['elapsed_time']}")
            if result['chunks_count'] > 0:
                print(f"  Chunks数量: {result['chunks_count']}")
            if result['error']:
                print(f"  错误: {result['error']}")

    # 汇总
    passed = sum(1 for r in results if r['status'] == 'PASS')
    skipped = sum(1 for r in results if r['status'] == 'SKIP')
    failed = sum(1 for r in results if r['status'] in ['FAIL', 'ERROR'])

    print(f"\n总计: {passed}/{total_tests} 通过, {skipped} 跳过, {failed} 失败")

    return results


if __name__ == "__main__":
    results = run_tests()

    # 返回退出码
    if any(r['status'] in ['FAIL', 'ERROR'] for r in results):
        exit(1)
    else:
        exit(0)
