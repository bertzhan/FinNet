# -*- coding: utf-8 -*-
"""
MinerU API 解析测试脚本
测试通过 API 接口解析 PDF 是否成功
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.processing.ai.pdf_parser import get_mineru_parser
from src.storage.object_store.minio_client import MinIOClient
import tempfile


def test_api_connection():
    """测试1: API 连接测试"""
    print("=" * 60)
    print("测试1: API 连接测试")
    print("=" * 60)
    
    try:
        parser = get_mineru_parser()
        print(f"✅ 解析器初始化成功")
        print(f"   API 地址: {parser.api_base}")
        print(f"   使用 API 模式: {parser.use_api}")
        return True
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_find_pdf_in_minio():
    """测试2: 查找 MinIO 中的 PDF 文件"""
    print("\n" + "=" * 60)
    print("测试2: 查找 MinIO 中的 PDF 文件")
    print("=" * 60)
    
    try:
        minio_client = MinIOClient()
        objects = list(minio_client.client.list_objects(
            minio_client.bucket,
            prefix="bronze/a_share/ipo_prospectus/",
            recursive=True
        ))
        
        # 找一个较小的 PDF 文件（便于快速测试）
        pdf_object = None
        for obj in objects:
            if obj.object_name.endswith('.pdf') and obj.size < 5 * 1024 * 1024:  # 小于 5MB
                pdf_object = obj
                break
        
        if not pdf_object:
            print("⚠️  没有找到合适的 PDF 文件（小于 5MB）")
            # 尝试找一个稍大的文件
            for obj in objects:
                if obj.object_name.endswith('.pdf'):
                    pdf_object = obj
                    break
        
        if not pdf_object:
            print("❌ MinIO 中没有找到 PDF 文件")
            return None
        
        print(f"✅ 找到 PDF 文件:")
        print(f"   路径: {pdf_object.object_name}")
        print(f"   大小: {pdf_object.size / 1024 / 1024:.2f} MB")
        return pdf_object
        
    except Exception as e:
        print(f"❌ 查找失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_download_and_parse(pdf_object):
    """测试3: 下载 PDF 并使用 API 解析"""
    print("\n" + "=" * 60)
    print("测试3: 下载 PDF 并使用 API 解析")
    print("=" * 60)
    
    if not pdf_object:
        print("⚠️  跳过测试（没有 PDF 文件）")
        return False
    
    try:
        parser = get_mineru_parser()
        minio_client = MinIOClient()
        
        # 下载 PDF 到临时文件
        temp_dir = tempfile.mkdtemp(prefix="mineru_api_test_")
        temp_pdf_path = os.path.join(temp_dir, Path(pdf_object.object_name).name)
        
        print(f"下载 PDF 到临时文件...")
        minio_client.download_file(
            object_name=pdf_object.object_name,
            file_path=temp_pdf_path
        )
        print(f"✅ PDF 已下载: {temp_pdf_path}")
        print(f"   文件大小: {os.path.getsize(temp_pdf_path)} bytes")
        
        # 使用 API 解析
        print(f"\n调用 MinerU API 解析...")
        print(f"   API 地址: {parser.api_base}")
        print(f"   这可能需要一些时间，请耐心等待...")
        
        parse_result = parser._parse_with_api(temp_pdf_path)
        
        # 清理临时文件
        try:
            os.remove(temp_pdf_path)
            os.rmdir(temp_dir)
        except:
            pass
        
        if parse_result.get("success"):
            print(f"\n✅ API 解析成功！")
            print(f"   文本长度: {parse_result.get('text_length', 0)} 字符")
            print(f"   表格数量: {parse_result.get('tables_count', 0)}")
            print(f"   图片数量: {parse_result.get('images_count', 0)}")
            
            # 显示部分文本预览
            text_preview = parse_result.get('text', '')[:200]
            if text_preview:
                print(f"\n   文本预览（前200字符）:")
                print(f"   {text_preview}...")
            
            return True
        else:
            error_msg = parse_result.get('error_message', '未知错误')
            print(f"\n❌ API 解析失败: {error_msg}")
            return False
            
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_parse_flow():
    """测试4: 完整解析流程（如果有数据库文档）"""
    print("\n" + "=" * 60)
    print("测试4: 完整解析流程测试")
    print("=" * 60)
    
    try:
        from src.storage.metadata import get_postgres_client, crud
        from src.common.constants import DocumentStatus
        
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
                print("⚠️  数据库中没有待解析的文档（状态为 crawled）")
                print("   提示: 先运行爬虫任务，爬取一些文档")
                return True
            
            doc = docs[0]
            print(f"找到文档: ID={doc.id}, {doc.stock_code}")
            print(f"MinIO 路径: {doc.minio_object_name}")
            
            # 检查文件是否存在
            if not parser.minio_client.file_exists(doc.minio_object_name):
                print(f"⚠️  MinIO 文件不存在: {doc.minio_object_name}")
                print("   跳过完整流程测试")
                return True
            
            print(f"\n开始完整解析流程...")
            result = parser.parse_document(doc.id, save_to_silver=False)  # 先不保存到 Silver，只测试解析
            
            if result["success"]:
                print(f"\n✅ 完整流程测试成功！")
                print(f"   解析任务ID: {result.get('parse_task_id')}")
                print(f"   文本长度: {result.get('extracted_text_length', 0)} 字符")
                print(f"   表格数量: {result.get('extracted_tables_count', 0)}")
                print(f"   图片数量: {result.get('extracted_images_count', 0)}")
                return True
            else:
                print(f"\n❌ 完整流程测试失败: {result.get('error_message', '未知错误')}")
                return False
                
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("MinerU API 解析测试")
    print("=" * 60)
    print()
    
    tests = [
        ("API 连接", test_api_connection),
        ("查找 PDF 文件", lambda: test_find_pdf_in_minio() is not None),
    ]
    
    results = []
    pdf_object = None
    
    # 运行前两个测试
    for name, test_func in tests:
        try:
            if name == "查找 PDF 文件":
                pdf_object = test_find_pdf_in_minio()
                result = pdf_object is not None
            else:
                result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ 测试 '{name}' 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 运行 API 解析测试
    if pdf_object:
        try:
            result = test_download_and_parse(pdf_object)
            results.append(("API 解析", result))
        except Exception as e:
            print(f"\n❌ 测试 'API 解析' 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append(("API 解析", False))
    else:
        results.append(("API 解析", None))
    
    # 运行完整流程测试
    try:
        result = test_full_parse_flow()
        results.append(("完整流程", result))
    except Exception as e:
        print(f"\n❌ 测试 '完整流程' 异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("完整流程", False))
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    for name, result in results:
        if result is None:
            status = "⚠️  跳过"
        elif result:
            status = "✅ 通过"
        else:
            status = "❌ 失败"
        print(f"{status} - {name}")
    
    total = len([r for r in results if r[1] is not None])
    passed = sum(1 for _, r in results if r is True)
    
    print(f"\n总计: {passed}/{total} 通过 ({passed*100//total if total > 0 else 0}%)")
    
    if passed == total and total > 0:
        print("\n🎉 所有测试通过！MinerU API 解析功能正常")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败或跳过")
        return 1


if __name__ == '__main__':
    sys.exit(main())
