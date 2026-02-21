#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试完整的 Dagster PDF 解析 Job
验证从扫描到解析到验证的完整流程
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from dagster import RunConfig
from src.processing.compute.dagster.jobs import doc_parse_job


def test_parse_job():
    """测试完整的 PDF 解析 Job"""
    print("=" * 80)
    print("测试: doc_parse_job (完整流程)")
    print("=" * 80)
    print()
    
    # 配置：只解析前3页，小批量测试
    # 使用 ipo_prospectus 类型，确保能找到存在的文档（如 document_id=59）
    config = RunConfig(
        ops={
            "scan_pending_documents_op": {
                "config": {
                    "batch_size": 2,  # 每次处理2个文档
                    "parser_type": "mineru",
                    "limit": 100,  # 增加 limit 以确保能找到存在的文档
                    "doc_type": "ipo_prospectus",  # 只选择 IPO 文档（更可能存在于 MinIO）
                }
            },
            "doc_parse_op": {
                "config": {
                    "batch_size": 2,
                    "parser_type": "mineru",
                    "enable_quarantine": True,
                    "start_page_id": 0,  # 只解析前3页（0, 1, 2）
                    "end_page_id": 2,
                }
            },
            "validate_parse_results_op": {
                "config": {
                    "batch_size": 2,
                    "parser_type": "mineru",
                    "min_success_rate": 0.5,  # 测试时降低成功率要求
                }
            }
        }
    )
    
    try:
        print("开始执行 Job...")
        print()
        
        # 使用 execute_in_process 方法执行 job
        result = doc_parse_job.execute_in_process(run_config=config)
        
        print()
        print("=" * 80)
        print("Job 执行结果")
        print("=" * 80)
        print(f"✅ 执行成功: {result.success}")
        print(f"   运行ID: {result.run_id}")
        
        if result.success:
            print("\n📊 执行统计:")
            # 获取各个 op 的输出
            try:
                scan_output = result.output_for_node("scan_pending_documents_op")
                parse_output = result.output_for_node("doc_parse_op")
                validate_output = result.output_for_node("validate_parse_results_op")
                
                print(f"\n  1. scan_pending_documents_op:")
                if isinstance(scan_output, dict):
                    print(f"     - 总文档数: {scan_output.get('total_documents', 0)}")
                    print(f"     - 批次数: {scan_output.get('total_batches', 0)}")
                
                print(f"\n  2. doc_parse_op:")
                if isinstance(parse_output, dict):
                    print(f"     - 成功解析: {parse_output.get('parsed_count', 0)}")
                    print(f"     - 解析失败: {parse_output.get('failed_count', 0)}")
                    print(f"     - 跳过: {parse_output.get('skipped_count', 0)}")
                
                print(f"\n  3. validate_parse_results_op:")
                if isinstance(validate_output, dict):
                    print(f"     - 验证通过: {validate_output.get('validation_passed', False)}")
                    print(f"     - 成功率: {validate_output.get('success_rate', 0):.2%}")
                    print(f"     - 总文档数: {validate_output.get('total_documents', 0)}")
            except Exception as e:
                print(f"     ⚠️ 无法获取详细输出: {e}")
        else:
            print(f"\n❌ 执行失败:")
            if hasattr(result, 'failure'):
                print(f"   错误: {result.failure}")
        
        return result.success
        
    except Exception as e:
        print(f"\n❌ Job 执行异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("Dagster PDF 解析 Job 完整测试")
    print(f"项目根目录: {project_root}")
    print()
    
    # 检查环境
    import os
    print("检查环境配置...")
    minio_enabled = os.getenv("MINIO_ENDPOINT") is not None
    postgres_enabled = os.getenv("POSTGRES_HOST") is not None
    mineru_api_enabled = os.getenv("MINERU_API_BASE") is not None
    
    print(f"  MinIO: {'✅ 已配置' if minio_enabled else '⚠️  未配置'}")
    print(f"  PostgreSQL: {'✅ 已配置' if postgres_enabled else '⚠️  未配置'}")
    print(f"  MinerU API: {'✅ 已配置' if mineru_api_enabled else '⚠️  未配置（将使用默认）'}")
    print()
    
    if not minio_enabled or not postgres_enabled:
        print("⚠️  警告: 缺少必要的环境配置，测试可能失败")
        print()
    
    # 运行测试
    success = test_parse_job()
    
    print()
    print("=" * 80)
    if success:
        print("✅ 测试通过！Job 执行成功")
    else:
        print("❌ 测试失败！请检查错误信息")
    print("=" * 80)
    
    sys.exit(0 if success else 1)
