# -*- coding: utf-8 -*-
"""
测试根据chunk_id查询接口
POST /api/v1/document/chunk-by-id
"""

import requests
import time
from typing import Dict, Any, List, Optional


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


def get_chunk_id_from_vector_search(company_code: str, year: int, quarter: int) -> Optional[str]:
    """通过向量检索获取一个chunk_id"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/retrieval/vector",
            json={
                "query": "营业收入",
                "filters": {
                    "stock_code": company_code,
                    "year": year,
                    "quarter": quarter,
                    "doc_type": DOC_TYPE
                },
                "top_k": 1
            },
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            if results:
                return results[0].get("chunk_id")
        return None
    except:
        return None


def test_chunk_by_id(chunk_id: str, company_name: str, company_code: str, year: int, quarter: int) -> Dict[str, Any]:
    """测试根据chunk_id查询接口"""
    test_name = f"POST /api/v1/document/chunk-by-id"
    start_time = time.time()

    payload = {
        "chunk_id": chunk_id
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/document/chunk-by-id",
            json=payload,
            timeout=10
        )
        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            chunk_text = data.get("chunk_text", "")
            title = data.get("title")

            return {
                "test_name": test_name,
                "company_name": company_name,
                "company_code": company_code,
                "year": year,
                "quarter": quarter,
                "status": "PASS",
                "elapsed_time": f"{elapsed:.3f}s",
                "status_code": response.status_code,
                "chunk_id": chunk_id[:36],
                "chunk_text_length": len(chunk_text),
                "title": title,
                "error": None
            }
        elif response.status_code == 404:
            return {
                "test_name": test_name,
                "company_name": company_name,
                "company_code": company_code,
                "year": year,
                "quarter": quarter,
                "status": "NOT_FOUND",
                "elapsed_time": f"{elapsed:.3f}s",
                "status_code": response.status_code,
                "chunk_id": chunk_id[:36],
                "chunk_text_length": 0,
                "title": None,
                "error": "Chunk not found"
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
                "chunk_id": chunk_id[:36],
                "chunk_text_length": 0,
                "title": None,
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
            "chunk_id": chunk_id[:36] if chunk_id else None,
            "chunk_text_length": 0,
            "title": None,
            "error": str(e)
        }


def run_tests() -> List[Dict[str, Any]]:
    """运行所有chunk-by-id测试"""
    results = []
    total_tests = len(TEST_COMPANIES) * len(TEST_QUARTERS)

    print("=" * 60)
    print("测试根据chunk_id查询接口: POST /api/v1/document/chunk-by-id")
    print("=" * 60)
    print(f"测试公司: {', '.join([c['name'] for c in TEST_COMPANIES])}")
    print(f"测试年份: {TEST_YEAR}")
    print(f"测试季度: Q1, Q2, Q3, Q4")
    print(f"总测试数: {total_tests}")
    print()

    test_count = 0
    for company in TEST_COMPANIES:
        for quarter in TEST_QUARTERS:
            test_count += 1
            print(f"[{test_count}/{total_tests}] 测试 {company['name']} {TEST_YEAR}Q{quarter}")

            # 先获取一个chunk_id
            chunk_id = get_chunk_id_from_vector_search(company['code'], TEST_YEAR, quarter)

            if not chunk_id:
                results.append({
                    "test_name": "POST /api/v1/document/chunk-by-id",
                    "company_name": company['name'],
                    "company_code": company['code'],
                    "year": TEST_YEAR,
                    "quarter": quarter,
                    "status": "SKIP",
                    "elapsed_time": "0.000s",
                    "status_code": None,
                    "chunk_id": None,
                    "chunk_text_length": 0,
                    "title": None,
                    "error": "Chunk ID not found, skipped"
                })
                print(f"  状态: SKIP | 原因: 未找到chunk_id")
                continue

            result = test_chunk_by_id(
                chunk_id,
                company['name'],
                company['code'],
                TEST_YEAR,
                quarter
            )
            results.append(result)

            print(f"  状态: {result['status']} | 耗时: {result['elapsed_time']}")
            if result['chunk_text_length'] > 0:
                print(f"  文本长度: {result['chunk_text_length']} 字符")
            if result['title']:
                print(f"  标题: {result['title'][:50]}...")
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
