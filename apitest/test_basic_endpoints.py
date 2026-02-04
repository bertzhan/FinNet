# -*- coding: utf-8 -*-
"""
测试基础接口
- GET /
- GET /health
"""

import requests
import time
from typing import Dict, Any


BASE_URL = "http://localhost:8000"


def test_root_endpoint() -> Dict[str, Any]:
    """测试根路径接口"""
    test_name = "GET /"
    start_time = time.time()

    try:
        response = requests.get(f"{BASE_URL}/", timeout=10)
        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            return {
                "test_name": test_name,
                "status": "PASS",
                "elapsed_time": f"{elapsed:.3f}s",
                "status_code": response.status_code,
                "error": None
            }
        else:
            return {
                "test_name": test_name,
                "status": "FAIL",
                "elapsed_time": f"{elapsed:.3f}s",
                "status_code": response.status_code,
                "error": f"Unexpected status code: {response.status_code}"
            }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "test_name": test_name,
            "status": "ERROR",
            "elapsed_time": f"{elapsed:.3f}s",
            "status_code": None,
            "error": str(e)
        }


def test_health_endpoint() -> Dict[str, Any]:
    """测试全局健康检查接口"""
    test_name = "GET /health"
    start_time = time.time()

    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok":
                return {
                    "test_name": test_name,
                    "status": "PASS",
                    "elapsed_time": f"{elapsed:.3f}s",
                    "status_code": response.status_code,
                    "error": None
                }
            else:
                return {
                    "test_name": test_name,
                    "status": "FAIL",
                    "elapsed_time": f"{elapsed:.3f}s",
                    "status_code": response.status_code,
                    "error": f"Unexpected status: {data.get('status')}"
                }
        else:
            return {
                "test_name": test_name,
                "status": "FAIL",
                "elapsed_time": f"{elapsed:.3f}s",
                "status_code": response.status_code,
                "error": f"Unexpected status code: {response.status_code}"
            }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "test_name": test_name,
            "status": "ERROR",
            "elapsed_time": f"{elapsed:.3f}s",
            "status_code": None,
            "error": str(e)
        }


def run_tests() -> list:
    """运行所有基础接口测试"""
    results = []

    print("=" * 60)
    print("测试基础接口")
    print("=" * 60)

    # 测试根路径
    print("\n[1/2] 测试 GET /")
    result = test_root_endpoint()
    results.append(result)
    print(f"  状态: {result['status']} | 耗时: {result['elapsed_time']}")
    if result['error']:
        print(f"  错误: {result['error']}")

    # 测试健康检查
    print("\n[2/2] 测试 GET /health")
    result = test_health_endpoint()
    results.append(result)
    print(f"  状态: {result['status']} | 耗时: {result['elapsed_time']}")
    if result['error']:
        print(f"  错误: {result['error']}")

    # 汇总
    passed = sum(1 for r in results if r['status'] == 'PASS')
    total = len(results)
    print(f"\n总计: {passed}/{total} 通过")

    return results


if __name__ == "__main__":
    results = run_tests()

    # 返回退出码
    if all(r['status'] == 'PASS' for r in results):
        exit(0)
    else:
        exit(1)
