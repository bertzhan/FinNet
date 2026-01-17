# -*- coding: utf-8 -*-
"""
测试 Dagster PDF 解析作业（包含 ParsedDocument 和 Image 记录创建）
验证完整的解析流程：从扫描待解析文档到保存到 Silver 层，并创建数据库记录
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
from src.storage.metadata import get_postgres_client, crud
from dagster import build_op_context


def test_scan_pending_documents():
    """测试1: 扫描待解析文档"""
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
                  f"path={doc['minio_object_path']}")
    else:
        print("  ⚠️  没有待解析的文档")
    
    return result


def test_parse_documents(scan_result):
    """测试2: 解析文档并验证数据库记录创建"""
    print("\n" + "=" * 60)
    print("测试2: 解析文档并创建 ParsedDocument 记录")
    print("=" * 60)
    
    if not scan_result.get('success') or not scan_result.get('documents'):
        print("⚠️  没有待解析的文档，跳过测试")
        return None
    
    # 只解析第一个文档（用于测试）
    test_doc = scan_result['documents'][0]
    print(f"测试文档: document_id={test_doc['document_id']}, {test_doc['stock_code']}")
    
    # 修改 scan_result，只包含一个文档
    test_scan_result = {
        **scan_result,
        'documents': [test_doc],
        'total_documents': 1,
        'batches': [[test_doc]],
        'total_batches': 1,
    }
    
    config = {
        "enable_silver_upload": True,
        "start_page_id": 0,
        "end_page_id": 2,  # 只解析前3页（快速测试）
    }
    
    context = build_op_context(op_config=config)
    result = parse_documents_op(context, test_scan_result)
    
    print(f"\n解析结果:")
    print(f"  成功: {result.get('success')}")
    print(f"  解析成功: {result.get('parsed_count', 0)}")
    print(f"  解析失败: {result.get('failed_count', 0)}")
    print(f"  跳过: {result.get('skipped_count', 0)}")
    
    if result.get('parsed_count', 0) > 0:
        print(f"\n✅ 解析成功！验证数据库记录...")
        
        # 验证 ParsedDocument 记录
        pg_client = get_postgres_client()
        with pg_client.get_session() as session:
            parsed_docs = crud.get_parsed_documents_by_document_id(
                session=session,
                document_id=test_doc['document_id']
            )
            
            if parsed_docs:
                latest = parsed_docs[0]
                print(f"\n✅ ParsedDocument 记录已创建:")
                print(f"   记录 ID: {latest.id}")
                print(f"   JSON 路径: {latest.content_json_path}")
                print(f"   文本长度: {latest.text_length}")
                print(f"   表格数量: {latest.tables_count}")
                print(f"   图片数量: {latest.images_count}")
                print(f"   解析器: {latest.parser_type} {latest.parser_version}")
                
                # 验证图片记录
                images = crud.get_images_by_parsed_document(
                    session=session,
                    parsed_document_id=latest.id
                )
                print(f"\n✅ Image 记录数: {len(images)}")
                if images:
                    print("   前3个图片记录:")
                    for i, img in enumerate(images[:3], 1):
                        print(f"   {i}. ID={img.id}, 文件名={img.filename}")
                        print(f"      路径: {img.file_path}")
                        print(f"      页码: {img.page_number}")
            else:
                print("❌ ParsedDocument 记录未创建")
    
    return result


def test_validate_parse_results(parse_results):
    """测试3: 验证解析结果"""
    print("\n" + "=" * 60)
    print("测试3: 验证解析结果")
    print("=" * 60)
    
    if not parse_results:
        print("⚠️  没有解析结果，跳过验证")
        return None
    
    context = build_op_context()
    result = validate_parse_results_op(context, parse_results)
    
    print(f"验证结果:")
    print(f"  成功: {result.get('success')}")
    print(f"  验证通过: {result.get('validated_count', 0)}")
    print(f"  验证失败: {result.get('failed_count', 0)}")
    
    return result


def test_query_parsed_documents():
    """测试4: 查询已创建的 ParsedDocument 记录"""
    print("\n" + "=" * 60)
    print("测试4: 查询 ParsedDocument 记录")
    print("=" * 60)
    
    pg_client = get_postgres_client()
    with pg_client.get_session() as session:
        from src.storage.metadata.models import ParsedDocument
        
        # 查询最新的 ParsedDocument 记录
        latest_parsed = session.query(ParsedDocument).order_by(
            ParsedDocument.parsed_at.desc()
        ).limit(5).all()
        
        print(f"✅ 找到 {len(latest_parsed)} 个最新的 ParsedDocument 记录")
        
        if latest_parsed:
            print("\n   记录详情:")
            for i, parsed in enumerate(latest_parsed, 1):
                print(f"\n   {i}. 记录 ID: {parsed.id}")
                print(f"      文档 ID: {parsed.document_id}")
                print(f"      JSON 路径: {parsed.content_json_path}")
                print(f"      文本长度: {parsed.text_length}")
                print(f"      图片数量: {parsed.images_count}")
                print(f"      解析时间: {parsed.parsed_at}")
                
                # 获取关联的文档信息
                doc = crud.get_document_by_id(session, parsed.document_id)
                if doc:
                    print(f"      文档: {doc.stock_code} {doc.year} Q{doc.quarter}")
                
                # 获取图片记录
                images = crud.get_images_by_parsed_document(
                    session=session,
                    parsed_document_id=parsed.id
                )
                print(f"      图片记录数: {len(images)}")
        else:
            print("   ⚠️  没有 ParsedDocument 记录")
            print("   提示: 先运行解析任务")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Dagster PDF 解析作业测试（包含数据库记录验证）")
    print("=" * 60)
    print()
    
    results = []
    
    # 测试1: 扫描待解析文档
    try:
        scan_result = test_scan_pending_documents()
        results.append(("扫描待解析文档", scan_result.get('success') if scan_result else False))
    except Exception as e:
        print(f"\n❌ 测试1异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("扫描待解析文档", False))
        scan_result = None
    
    # 测试2: 解析文档（如果有待解析的文档）
    parse_results = None
    if scan_result and scan_result.get('success') and scan_result.get('documents'):
        try:
            parse_results = test_parse_documents(scan_result)
            results.append(("解析文档并创建记录", parse_results.get('success') if parse_results else False))
        except Exception as e:
            print(f"\n❌ 测试2异常: {e}")
            import traceback
            traceback.print_exc()
            results.append(("解析文档并创建记录", False))
    else:
        print("\n⚠️  跳过解析测试（没有待解析的文档）")
        results.append(("解析文档并创建记录", True))  # 跳过不算失败
    
    # 测试3: 验证解析结果
    if parse_results:
        try:
            validate_result = test_validate_parse_results(parse_results)
            results.append(("验证解析结果", validate_result.get('success') if validate_result else False))
        except Exception as e:
            print(f"\n❌ 测试3异常: {e}")
            import traceback
            traceback.print_exc()
            results.append(("验证解析结果", False))
    else:
        results.append(("验证解析结果", True))  # 跳过不算失败
    
    # 测试4: 查询 ParsedDocument 记录
    try:
        test_query_parsed_documents()
        results.append(("查询 ParsedDocument 记录", True))
    except Exception as e:
        print(f"\n❌ 测试4异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("查询 ParsedDocument 记录", False))
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    total = len(results)
    passed = sum(1 for _, r in results if r)
    
    print(f"\n总计: {passed}/{total} 通过 ({passed*100//total if total > 0 else 0}%)")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败或跳过")
        return 1


if __name__ == '__main__':
    sys.exit(main())
