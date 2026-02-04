# -*- coding: utf-8 -*-
"""
测试检索服务健康检查接口
GET /api/v1/retrieval/health
"""

import requests
import time
from typing import Dict, Any, List


BASE_URL = "http://localhost:8000"


def test_retrieval_health() -> Dict[str, Any]:
    """测试检索服务健康检查接口"""
    test_name = "GET /api/v1/retrieval/health"
    start_time = time.time()

    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/retrieval/health",
            timeout=10
        )
        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "unknown")
            components = data.get("components", {})

            # 检查组件状态
            component_status = {}
            for comp_name, comp_status in components.items():
                if "ok" in str(comp_status).lower():
                    component_status[comp_name] = "OK"
                elif "error" in str(comp_status).lower():
                    component_status[comp_name] = "ERROR"
                else:
                    component_status[comp_name] = comp_status

            return {
                "test_name": test_name,
                "status": "PASS" if status in ["healthy", "degraded"] else "UNHEALTHY",
                "elapsed_time": f"{elapsed:.3f}s",
                "status_code": response.status_code,
                "service_status": status,
                "components": component_status,
                "error": None if status in ["healthy", "degraded"] else f"Service status: {status}"
            }
        else:
            return {
                "test_name": test_name,
                "status": "FAIL",
                "elapsed_time": f"{elapsed:.3f}s",
                "status_code": response.status_code,
                "service_status": "unknown",
                "components": {},
                "error": f"HTTP {response.status_code}: {response.text[:100]}"
            }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "test_name": test_name,
            "status": "ERROR",
            "elapsed_time": f"{elapsed:.3f}s",
            "status_code": None,
            "service_status": "unknown",
            "components": {},
            "error": str(e)
        }


def run_tests() -> List[Dict[str, Any]]:
    """运行健康检查测试"""
    results = []

    print("=" * 60)
    print("测试检索服务健康检查接口: GET /api/v1/retrieval/health")
    print("=" * 60)
    print()

    print("[1/1] 测试检索服务健康检查")
    result = test_retrieval_health()
    results.append(result)

    print(f"  状态: {result['status']} | 耗时: {result['elapsed_time']}")
    print(f"  服务状态: {result['service_status']}")
    if result['components']:
        print(f"  组件状态:")
        for comp_name, comp_status in result['components'].items():
            print(f"    - {comp_name}: {comp_status}")
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
