#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 Dagster 文本分块作业
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dagster import execute_job
from src.processing.compute.dagster.jobs.chunk_jobs import chunk_documents_job


def test_chunk_job():
    """测试分块作业"""
    print("=" * 60)
    print("测试 Dagster 文本分块作业")
    print("=" * 60)
    print()
    
    # 配置参数
    config = {
        "ops": {
            "scan_parsed_documents_op": {
                "config": {
                    "batch_size": 2,
                    "limit": 5,  # 只处理5个文档进行测试
                    # "market": "a_share",  # 可选：过滤市场
                    # "doc_type": "quarterly_report",  # 可选：过滤文档类型
                }
            },
            "chunk_documents_op": {
                "config": {
                    "force_rechunk": False,  # 不强制重新分块
                }
            }
        }
    }
    
    print("配置参数:")
    print(f"  - batch_size: {config['ops']['scan_parsed_documents_op']['config']['batch_size']}")
    print(f"  - limit: {config['ops']['scan_parsed_documents_op']['config']['limit']}")
    print(f"  - force_rechunk: {config['ops']['chunk_documents_op']['config']['force_rechunk']}")
    print()
    
    try:
        print("开始执行分块作业...")
        result = execute_job(chunk_documents_job, run_config=config)
        
        print()
        print("=" * 60)
        print("执行结果")
        print("=" * 60)
        print(f"成功: {result.success}")
        
        if result.success:
            print("✅ 作业执行成功！")
            
            # 打印每个步骤的结果
            for step_output in result.step_output_list:
                print(f"\n步骤: {step_output.step_key}")
                if step_output.value:
                    if isinstance(step_output.value, dict):
                        if "chunked_count" in step_output.value:
                            print(f"  成功分块: {step_output.value.get('chunked_count', 0)}")
                            print(f"  失败: {step_output.value.get('failed_count', 0)}")
                            print(f"  跳过: {step_output.value.get('skipped_count', 0)}")
                        elif "total_documents" in step_output.value:
                            print(f"  找到文档数: {step_output.value.get('total_documents', 0)}")
                        elif "validation_passed" in step_output.value:
                            print(f"  验证通过: {step_output.value.get('validation_passed', False)}")
                            print(f"  成功率: {step_output.value.get('success_rate', 0):.2%}")
        else:
            print("❌ 作业执行失败")
            if result.failure_reason:
                print(f"失败原因: {result.failure_reason}")
        
        return result.success
        
    except Exception as e:
        print(f"❌ 执行异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_chunk_job()
    sys.exit(0 if success else 1)
