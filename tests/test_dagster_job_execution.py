# -*- coding: utf-8 -*-
"""
测试 Dagster Job 执行
直接运行 Dagster job 验证完整流程
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
from src.storage.metadata import get_postgres_client, crud


def test_parse_pdf_job():
    """测试 PDF 解析 Job"""
    print("=" * 60)
    print("测试 Dagster PDF 解析 Job")
    print("=" * 60)
    print()
    
    # 配置
    config = {
        "ops": {
            "scan_pending_documents_op": {
                "config": {
                    "batch_size": 2,
                    "limit": 5,
                }
            },
            "parse_documents_op": {
                "config": {
                    "enable_silver_upload": True,
                    "start_page_id": 0,
                    "end_page_id": 2,  # 只解析前3页（快速测试）
                }
            }
        }
    }
    
    print("配置:")
    print(f"  batch_size: {config['ops']['scan_pending_documents_op']['config']['batch_size']}")
    print(f"  limit: {config['ops']['scan_pending_documents_op']['config']['limit']}")
    print(f"  页面范围: 0-2 (前3页)")
    print()
    
    try:
        print("开始执行 Job 步骤...")
        
        # 步骤1: 扫描待解析文档
        print("\n步骤1: 扫描待解析文档")
        scan_config = config['ops']['scan_pending_documents_op']['config']
        scan_context = build_op_context(op_config=scan_config)
        scan_result = scan_pending_documents_op(scan_context)
        
        print(f"  成功: {scan_result.get('success')}")
        print(f"  总文档数: {scan_result.get('total_documents', 0)}")
        
        if not scan_result.get('success') or not scan_result.get('documents'):
            print("\n⚠️  没有待解析的文档，Job 结束")
            return True
        
        # 步骤2: 解析文档（只解析第一个文档用于测试）
        print("\n步骤2: 解析文档")
        test_doc = scan_result['documents'][0]
        print(f"  测试文档: document_id={test_doc['document_id']}, {test_doc['stock_code']}")
        
        test_scan_result = {
            **scan_result,
            'documents': [test_doc],
            'total_documents': 1,
        }
        
        parse_config = config['ops']['parse_documents_op']['config']
        parse_context = build_op_context(op_config=parse_config)
        parse_result = parse_documents_op(parse_context, test_scan_result)
        
        print(f"  成功: {parse_result.get('success')}")
        print(f"  解析成功: {parse_result.get('parsed_count', 0)}")
        print(f"  解析失败: {parse_result.get('failed_count', 0)}")
        
        # 步骤3: 验证解析结果
        print("\n步骤3: 验证解析结果")
        validate_context = build_op_context()
        validate_result = validate_parse_results_op(validate_context, parse_result)
        
        print(f"  成功: {validate_result.get('success')}")
        
        print("\n" + "=" * 60)
        print("Job 执行结果")
        print("=" * 60)
        
        if parse_result.get('success') and parse_result.get('parsed_count', 0) > 0:
            print("✅ Job 执行成功！")
            
            # 验证数据库记录
            print("\n" + "=" * 60)
            print("验证数据库记录")
            print("=" * 60)
            
            pg_client = get_postgres_client()
            with pg_client.get_session() as session:
                # 查询最新的 ParsedDocument 记录
                from src.storage.metadata.models import ParsedDocument
                latest_parsed = session.query(ParsedDocument).order_by(
                    ParsedDocument.parsed_at.desc()
                ).limit(3).all()
                
                if latest_parsed:
                    print(f"\n✅ 找到 {len(latest_parsed)} 个最新的 ParsedDocument 记录:")
                    for i, parsed in enumerate(latest_parsed, 1):
                        print(f"\n  {i}. 记录 ID: {parsed.id}")
                        print(f"     文档 ID: {parsed.document_id}")
                        print(f"     JSON 路径: {parsed.content_json_path}")
                        print(f"     文本长度: {parsed.text_length}")
                        print(f"     图片数量: {parsed.images_count}")
                        print(f"     解析时间: {parsed.parsed_at}")
                        
                        # 获取图片记录
                        images = crud.get_images_by_parsed_document(
                            session=session,
                            parsed_document_id=parsed.id
                        )
                        print(f"     图片记录数: {len(images)}")
                else:
                    print("\n⚠️  没有 ParsedDocument 记录")
                    print("   提示: 可能没有成功解析的文档，或者文件不存在")
            
            return True
        else:
            print("❌ Job 执行失败")
            print(f"错误: {result.failure_data}")
            return False
            
    except Exception as e:
        print(f"\n❌ Job 执行异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    success = test_parse_pdf_job()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ 测试完成！")
    else:
        print("❌ 测试失败")
    print("=" * 60)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
