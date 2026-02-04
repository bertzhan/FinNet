# -*- coding: utf-8 -*-
"""
运行所有API测试并生成报告
"""

import sys
import csv
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


# 测试脚本列表（按执行顺序）
TEST_SCRIPTS = [
    {
        "name": "基础接口测试",
        "script": "test_basic_endpoints.py",
        "category": "Basic"
    },
    {
        "name": "文档查询接口测试",
        "script": "test_document_query.py",
        "category": "Document API"
    },
    {
        "name": "文档Chunks接口测试",
        "script": "test_document_chunks.py",
        "category": "Document API"
    },
    {
        "name": "公司名称搜索接口测试",
        "script": "test_company_code_search.py",
        "category": "Document API"
    },
    {
        "name": "Chunk详情查询接口测试",
        "script": "test_chunk_by_id.py",
        "category": "Document API"
    },
    {
        "name": "向量检索接口测试",
        "script": "test_vector_retrieval.py",
        "category": "Retrieval API"
    },
    {
        "name": "全文检索接口测试",
        "script": "test_fulltext_retrieval.py",
        "category": "Retrieval API"
    },
    {
        "name": "图检索子节点接口测试",
        "script": "test_graph_children.py",
        "category": "Retrieval API"
    },
    {
        "name": "混合检索接口测试",
        "script": "test_hybrid_retrieval.py",
        "category": "Retrieval API"
    },
    {
        "name": "检索服务健康检查测试",
        "script": "test_retrieval_health.py",
        "category": "Retrieval API"
    },
]


def run_single_test(script_path: Path) -> tuple:
    """
    运行单个测试脚本

    Returns:
        (exit_code, output)
    """
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )
        return result.returncode, result.stdout
    except subprocess.TimeoutExpired:
        return 1, "测试超时（超过5分钟）"
    except Exception as e:
        return 1, f"运行测试时发生错误: {str(e)}"


def parse_test_results(output: str) -> Dict[str, Any]:
    """
    解析测试输出，提取统计信息

    Returns:
        {
            "total": int,
            "passed": int,
            "failed": int,
            "other": int
        }
    """
    lines = output.split('\n')

    # 查找汇总行，例如 "总计: 5/12 通过"
    for line in lines:
        if '总计:' in line or '总计：' in line:
            # 提取数字
            import re
            match = re.search(r'(\d+)/(\d+)', line)
            if match:
                passed = int(match.group(1))
                total = int(match.group(2))

                # 查找其他状态
                failed = 0
                other = 0
                if '失败' in line:
                    fail_match = re.search(r'(\d+)\s*失败', line)
                    if fail_match:
                        failed = int(fail_match.group(1))

                # 其他状态（跳过、未找到、无结果等）
                other = total - passed - failed

                return {
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "other": other
                }

    # 如果无法解析，返回默认值
    return {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "other": 0
    }


def generate_csv_report(results: List[Dict[str, Any]], output_path: Path):
    """生成CSV格式的测试报告"""
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)

        # 写入标题行
        writer.writerow([
            '测试时间',
            '测试类别',
            '测试名称',
            '测试脚本',
            '状态',
            '总测试数',
            '通过数',
            '失败数',
            '其他'
        ])

        # 写入数据行
        for result in results:
            writer.writerow([
                result['timestamp'],
                result['category'],
                result['name'],
                result['script'],
                result['status'],
                result['stats']['total'],
                result['stats']['passed'],
                result['stats']['failed'],
                result['stats']['other']
            ])


def main():
    """主函数"""
    print("=" * 80)
    print("FinNet API 全面测试")
    print("=" * 80)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试脚本数: {len(TEST_SCRIPTS)}")
    print()

    # 获取当前目录
    current_dir = Path(__file__).parent

    # 测试结果
    all_results = []

    # 运行每个测试
    for idx, test_info in enumerate(TEST_SCRIPTS, 1):
        print(f"\n[{idx}/{len(TEST_SCRIPTS)}] 运行: {test_info['name']}")
        print("-" * 80)

        script_path = current_dir / test_info['script']

        if not script_path.exists():
            print(f"⚠️  测试脚本不存在: {script_path}")
            all_results.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'category': test_info['category'],
                'name': test_info['name'],
                'script': test_info['script'],
                'status': 'SKIP',
                'stats': {'total': 0, 'passed': 0, 'failed': 0, 'other': 0}
            })
            continue

        # 运行测试
        exit_code, output = run_single_test(script_path)

        # 显示输出
        print(output)

        # 解析结果
        stats = parse_test_results(output)

        # 确定状态
        if exit_code == 0:
            status = 'PASS'
        else:
            status = 'FAIL'

        # 保存结果
        all_results.append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'category': test_info['category'],
            'name': test_info['name'],
            'script': test_info['script'],
            'status': status,
            'stats': stats
        })

        print(f"\n状态: {status}")

    # 生成汇总
    print("\n" + "=" * 80)
    print("测试汇总")
    print("=" * 80)

    total_scripts = len(all_results)
    passed_scripts = sum(1 for r in all_results if r['status'] == 'PASS')
    failed_scripts = sum(1 for r in all_results if r['status'] == 'FAIL')
    skipped_scripts = sum(1 for r in all_results if r['status'] == 'SKIP')

    total_tests = sum(r['stats']['total'] for r in all_results)
    passed_tests = sum(r['stats']['passed'] for r in all_results)
    failed_tests = sum(r['stats']['failed'] for r in all_results)
    other_tests = sum(r['stats']['other'] for r in all_results)

    print(f"\n测试脚本统计:")
    print(f"  - 总脚本数: {total_scripts}")
    print(f"  - 通过: {passed_scripts}")
    print(f"  - 失败: {failed_scripts}")
    print(f"  - 跳过: {skipped_scripts}")

    print(f"\n测试用例统计:")
    print(f"  - 总测试数: {total_tests}")
    print(f"  - 通过: {passed_tests}")
    print(f"  - 失败: {failed_tests}")
    print(f"  - 其他（跳过/未找到/无结果）: {other_tests}")

    print(f"\n详细结果:")
    for result in all_results:
        status_icon = "✓" if result['status'] == 'PASS' else ("✗" if result['status'] == 'FAIL' else "⊘")
        print(f"  {status_icon} {result['name']}: {result['stats']['passed']}/{result['stats']['total']} 通过")

    # 生成CSV报告
    csv_path = current_dir / "test_results.csv"
    generate_csv_report(all_results, csv_path)
    print(f"\n测试报告已生成: {csv_path}")

    # 结束时间
    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # 返回退出码
    if failed_scripts > 0:
        print(f"\n⚠️  {failed_scripts} 个测试脚本失败")
        sys.exit(1)
    else:
        print(f"\n✅ 所有测试脚本通过！")
        sys.exit(0)


if __name__ == "__main__":
    main()
