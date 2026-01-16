# -*- coding: utf-8 -*-
"""
测试 Dagster PDF 解析作业
验证完整的解析流程：从扫描待解析文档到保存到 Silver 层
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.processing.compute.dagster.jobs.parse_jobs import (
    scan_pending_documents_op,
    parse_documents_op,
    validate_parse_results_op,
)
from dagster import build_op_context


def test_scan_pending_documents():
    """测试扫描待解析文档"""
    print("=" * 60)
    print("测试1: 扫描待解析文档")
    print("=" * 60)
    
    config = {
        "batch_size": 5,
        "limit": 10,
    }
    
    context = build_op_context(op_config=config)
    result = scan_pending_documents_op(context)
    
    print(f"扫描结果:")
    print(f"  成功: {result.get('success')}")
    print(f"  总文档数: {result.get('total_documents', 0)}")
    print(f"  批次数: {result.get('total_batches', 0)}")
    
    documents = result.get('documents', [])
    if documents:
        print(f"\n前5个待解析文档:")
        for i, doc in enumerate(documents[:5], 1):
            print(f"  {i}. document_id={doc['document_id']}, "
                  f"stock_code={doc['stock_code']}, "
                  f"doc_type={doc['doc_type']}, "
                  f"path={doc['minio_object_name']}")
    
    return result


def test_parse_documents(scan_result):
    """测试解析文档"""
    print("\n" + "=" * 60)
    print("测试2: 解析文档（只解析前1个文档）")
    print("=" * 60)
    
    # 只解析第一个文档（用于快速测试）
    if scan_result.get('documents'):
        scan_result['documents'] = scan_result['documents'][:1]
        scan_result['total_documents'] = 1
    
    config = {
        "enable_silver_upload": True,
    }
    
    context = build_op_context(op_config=config)
    result = parse_documents_op(context, scan_result)
    
    print(f"解析结果:")
    print(f"  成功: {result.get('success')}")
    print(f"  解析成功: {result.get('parsed_count', 0)}")
    print(f"  解析失败: {result.get('failed_count', 0)}")
    print(f"  跳过: {result.get('skipped_count', 0)}")
    
    failed_docs = result.get('failed_documents', [])
    if failed_docs:
        print(f"\n失败文档:")
        for failed in failed_docs:
            print(f"  - document_id={failed['document_id']}, "
                  f"error={failed['error']}")
    
    return result


def test_validate_results(parse_result):
    """测试验证解析结果"""
    print("\n" + "=" * 60)
    print("测试3: 验证解析结果")
    print("=" * 60)
    
    context = build_op_context()
    result = validate_parse_results_op(context, parse_result)
    
    print(f"验证结果:")
    print(f"  成功: {result.get('success')}")
    print(f"  验证通过: {result.get('validation_passed')}")
    print(f"  成功率: {result.get('success_rate', 0):.2%}")
    print(f"  总文档数: {result.get('total_documents', 0)}")
    print(f"  成功解析: {result.get('parsed_count', 0)}")
    print(f"  解析失败: {result.get('failed_count', 0)}")
    
    return result


if __name__ == '__main__':
    print("Dagster PDF 解析作业测试")
    print("=" * 60)
    print()
    
    try:
        # 1. 扫描待解析文档
        scan_result = test_scan_pending_documents()
        
        if not scan_result.get('success') or not scan_result.get('documents'):
            print("\n⚠️ 没有待解析的文档，测试结束")
            sys.exit(0)
        
        # 2. 解析文档（只解析第一个）
        parse_result = test_parse_documents(scan_result)
        
        # 3. 验证结果
        validate_result = test_validate_results(parse_result)
        
        print("\n" + "=" * 60)
        if validate_result.get('validation_passed'):
            print("✅ 测试通过！解析作业功能正常")
        else:
            print("⚠️ 测试完成，但验证未通过（可能是成功率低于阈值）")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
