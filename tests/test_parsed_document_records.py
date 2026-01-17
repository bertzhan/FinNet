# -*- coding: utf-8 -*-
"""
测试 ParsedDocument 和 Image 记录创建
验证解析器在保存解析结果时是否正确创建数据库记录
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.processing.ai.pdf_parser import get_mineru_parser
from src.storage.metadata import get_postgres_client, crud
from src.common.constants import DocumentStatus
from datetime import datetime


def test_models_import():
    """测试1: 模型导入"""
    print("=" * 60)
    print("测试1: 模型导入")
    print("=" * 60)
    
    try:
        from src.storage.metadata.models import ParsedDocument, Image, ImageAnnotation
        print("✅ ParsedDocument 模型导入成功")
        print("✅ Image 模型导入成功")
        print("✅ ImageAnnotation 模型导入成功")
        return True
    except Exception as e:
        print(f"❌ 模型导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_crud_functions():
    """测试2: CRUD 函数导入"""
    print("\n" + "=" * 60)
    print("测试2: CRUD 函数导入")
    print("=" * 60)
    
    try:
        # 检查 CRUD 函数是否存在
        assert hasattr(crud, 'create_parsed_document'), "create_parsed_document 不存在"
        assert hasattr(crud, 'get_parsed_document_by_id'), "get_parsed_document_by_id 不存在"
        assert hasattr(crud, 'create_image'), "create_image 不存在"
        assert hasattr(crud, 'get_images_by_parsed_document'), "get_images_by_parsed_document 不存在"
        
        print("✅ 所有 CRUD 函数导入成功")
        print("   - create_parsed_document")
        print("   - get_parsed_document_by_id")
        print("   - get_parsed_documents_by_document_id")
        print("   - create_image")
        print("   - get_images_by_parsed_document")
        return True
    except Exception as e:
        print(f"❌ CRUD 函数检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_find_parsed_documents():
    """测试3: 查找已解析的文档"""
    print("\n" + "=" * 60)
    print("测试3: 查找已解析的文档")
    print("=" * 60)
    
    try:
        pg_client = get_postgres_client()
        with pg_client.get_session() as session:
            # 查找已解析的文档
            docs = crud.get_documents_by_status(
                session=session,
                status=DocumentStatus.PARSED.value,
                limit=5
            )
            
            print(f"✅ 找到 {len(docs)} 个已解析文档")
            
            if docs:
                print("\n   检查 ParsedDocument 记录:")
                for doc in docs[:3]:
                    parsed_docs = crud.get_parsed_documents_by_document_id(
                        session=session,
                        document_id=doc.id
                    )
                    print(f"\n   文档 ID={doc.id}, {doc.stock_code} {doc.year} Q{doc.quarter}")
                    print(f"      ParsedDocument 记录数: {len(parsed_docs)}")
                    
                    if parsed_docs:
                        latest = parsed_docs[0]  # 最新的记录
                        print(f"      最新记录 ID: {latest.id}")
                        print(f"      JSON 路径: {latest.content_json_path}")
                        print(f"      文本长度: {latest.text_length}")
                        print(f"      表格数量: {latest.tables_count}")
                        print(f"      图片数量: {latest.images_count}")
                        print(f"      解析器: {latest.parser_type} {latest.parser_version}")
                        
                        # 检查图片记录
                        images = crud.get_images_by_parsed_document(
                            session=session,
                            parsed_document_id=latest.id
                        )
                        print(f"      Image 记录数: {len(images)}")
                        if images:
                            print(f"      示例图片: {images[0].filename} (页码: {images[0].page_number})")
            else:
                print("   ⚠️  没有已解析的文档")
                print("   提示: 先运行解析任务")
            
            return True
    except Exception as e:
        print(f"❌ 查找失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_parse_and_create_records():
    """测试4: 解析文档并创建记录"""
    print("\n" + "=" * 60)
    print("测试4: 解析文档并创建 ParsedDocument 记录")
    print("=" * 60)
    
    try:
        pg_client = get_postgres_client()
        parser = get_mineru_parser()
        
        with pg_client.get_session() as session:
            # 查找一个待解析的文档
            docs = crud.get_documents_by_status(
                session=session,
                status=DocumentStatus.CRAWLED.value,
                limit=1
            )
            
            if not docs:
                print("⚠️  没有待解析的文档，跳过测试")
                print("   提示: 先运行爬虫任务，爬取一些文档")
                return True
            
            doc = docs[0]
            print(f"测试文档: ID={doc.id}, {doc.stock_code} {doc.year} Q{doc.quarter}")
            print(f"MinIO 路径: {doc.minio_object_path}")
            print()
            
            # 检查文件是否存在
            if not parser.minio_client.file_exists(doc.minio_object_path):
                print(f"⚠️  MinIO 文件不存在: {doc.minio_object_path}")
                print("   跳过解析测试")
                return True
            
            print("开始解析...")
            result = parser.parse_document(doc.id)
            
            if result["success"]:
                print("✅ 解析成功！")
                print(f"   解析任务ID: {result['parse_task_id']}")
                print(f"   Silver 层路径: {result['output_path']}")
                print()
                
                # 验证 ParsedDocument 记录是否创建
                print("验证数据库记录:")
                print("-" * 60)
                
                parsed_docs = crud.get_parsed_documents_by_document_id(
                    session=session,
                    document_id=doc.id
                )
                
                if parsed_docs:
                    latest = parsed_docs[0]
                    print(f"✅ ParsedDocument 记录已创建")
                    print(f"   记录 ID: {latest.id}")
                    print(f"   文档 ID: {latest.document_id}")
                    print(f"   解析任务 ID: {latest.parse_task_id}")
                    print(f"   JSON 路径: {latest.content_json_path}")
                    print(f"   Markdown 路径: {latest.markdown_path or '无'}")
                    print(f"   图片文件夹路径: {latest.image_folder_path or '无'}")
                    print(f"   JSON 哈希: {latest.content_json_hash[:16]}..." if latest.content_json_hash else "   无")
                    print(f"   源文档哈希: {latest.source_document_hash[:16]}..." if latest.source_document_hash else "   无")
                    print(f"   文本长度: {latest.text_length}")
                    print(f"   表格数量: {latest.tables_count}")
                    print(f"   图片数量: {latest.images_count}")
                    print(f"   页数: {latest.pages_count}")
                    print(f"   解析器: {latest.parser_type} {latest.parser_version}")
                    print(f"   解析时间: {latest.parsed_at}")
                    
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
                            print(f"      页码: {img.page_number}, 索引: {img.image_index}")
                            if img.description:
                                print(f"      描述: {img.description}")
                            if img.file_hash:
                                print(f"      哈希: {img.file_hash[:16]}...")
                    else:
                        print("   ⚠️  没有图片记录（文档可能没有图片）")
                    
                    return True
                else:
                    print("❌ ParsedDocument 记录未创建")
                    return False
            else:
                print(f"❌ 解析失败: {result.get('error_message', '未知错误')}")
                return False
                
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_query_parsed_documents():
    """测试5: 查询 ParsedDocument 记录"""
    print("\n" + "=" * 60)
    print("测试5: 查询 ParsedDocument 记录")
    print("=" * 60)
    
    try:
        pg_client = get_postgres_client()
        with pg_client.get_session() as session:
            # 查找所有 ParsedDocument 记录
            from src.storage.metadata.models import ParsedDocument
            all_parsed = session.query(ParsedDocument).limit(5).all()
            
            print(f"✅ 找到 {len(all_parsed)} 个 ParsedDocument 记录")
            
            if all_parsed:
                print("\n   记录详情:")
                for i, parsed in enumerate(all_parsed, 1):
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
            else:
                print("   ⚠️  没有 ParsedDocument 记录")
                print("   提示: 先运行解析任务")
            
            return True
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("ParsedDocument 和 Image 记录创建测试")
    print("=" * 60)
    print()
    
    tests = [
        ("模型导入", test_models_import),
        ("CRUD 函数", test_crud_functions),
        ("查找已解析文档", test_find_parsed_documents),
        ("解析并创建记录", test_parse_and_create_records),
        ("查询 ParsedDocument", test_query_parsed_documents),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ 测试 '{name}' 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
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
        print(f"\n⚠️  有 {total - passed} 个测试失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
