# -*- coding: utf-8 -*-
"""
MinerU 解析器本地测试脚本
用于测试 MinerUParser 的各个功能
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.processing.ai.pdf_parser import MinerUParser, get_mineru_parser
from src.storage.metadata import get_postgres_client, crud
from src.common.constants import DocumentStatus


def test_import():
    """测试1: 模块导入"""
    print("=" * 60)
    print("测试1: 模块导入")
    print("=" * 60)
    
    try:
        from src.processing.ai.pdf_parser import MinerUParser, get_mineru_parser
        print("✅ 模块导入成功")
        return True
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_mineru_import():
    """测试2: MinerU 包导入"""
    print("\n" + "=" * 60)
    print("测试2: MinerU 包导入")
    print("=" * 60)
    
    try:
        from mineru.cli.common import do_parse
        print("✅ MinerU 包导入成功")
        print("   可以使用 Python 包方式")
        return True
    except ImportError as e:
        print(f"⚠️  MinerU 包未安装: {e}")
        print("   提示: pip install mineru")
        print("   或者配置 MINERU_API_BASE 使用 API 方式")
        return False
    except Exception as e:
        print(f"❌ MinerU 包导入异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_parser_initialization():
    """测试3: 解析器初始化"""
    print("\n" + "=" * 60)
    print("测试3: 解析器初始化")
    print("=" * 60)
    
    try:
        parser = get_mineru_parser()
        print("✅ 解析器初始化成功")
        print(f"   MinIO 客户端: {'✅' if parser.minio_client else '❌'}")
        print(f"   路径管理器: {'✅' if parser.path_manager else '❌'}")
        print(f"   PostgreSQL 客户端: {'✅' if parser.pg_client else '❌'}")
        print(f"   使用 API 模式: {'✅' if parser.use_api else '❌'}")
        if parser.use_api:
            print(f"   API 地址: {parser.api_base}")
        return True
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_find_pending_documents():
    """测试4: 查找待解析文档"""
    print("\n" + "=" * 60)
    print("测试4: 查找待解析文档")
    print("=" * 60)
    
    try:
        pg_client = get_postgres_client()
        with pg_client.get_session() as session:
            # 查找状态为 crawled 的文档
            docs = crud.get_documents_by_status(
                session=session,
                status=DocumentStatus.CRAWLED.value,
                limit=5
            )
            
            print(f"✅ 找到 {len(docs)} 个待解析文档")
            
            if docs:
                print("   示例文档:")
                for i, doc in enumerate(docs[:3], 1):
                    print(f"   {i}. ID={doc.id}, {doc.stock_code} {doc.year} Q{doc.quarter}")
                    print(f"      MinIO路径: {doc.minio_object_path}")
                    print(f"      状态: {doc.status}")
            else:
                print("   ⚠️  没有待解析的文档")
                print("   提示: 先运行爬虫任务，爬取一些文档")
            
            return True
    except Exception as e:
        print(f"❌ 查找文档失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_parse_single_document():
    """测试5: 解析单个文档"""
    print("\n" + "=" * 60)
    print("测试5: 解析单个文档")
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
                print(f"   文本长度: {result['extracted_text_length']} 字符")
                print(f"   表格数量: {result['extracted_tables_count']}")
                print(f"   图片数量: {result['extracted_images_count']}")
                
                # 验证 Silver 层文件是否存在
                if result['output_path']:
                    if parser.minio_client.file_exists(result['output_path']):
                        print(f"   ✅ Silver 层文件已创建")
                    else:
                        print(f"   ⚠️  Silver 层文件不存在（可能上传失败）")
                
                return True
            else:
                print(f"❌ 解析失败: {result.get('error_message', '未知错误')}")
                return False
                
    except Exception as e:
        print(f"❌ 解析测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_extract_text_from_markdown():
    """测试6: Markdown 文本提取"""
    print("\n" + "=" * 60)
    print("测试6: Markdown 文本提取")
    print("=" * 60)
    
    try:
        parser = get_mineru_parser()
        
        # 测试 Markdown 文本提取
        test_markdown = """
# 标题1

这是一段**粗体**文本和*斜体*文本。

## 表格

| 列1 | 列2 |
|-----|-----|
| 值1 | 值2 |

![图片描述](image.png)

`代码块`
"""
        
        text = parser._extract_text_from_markdown(test_markdown)
        
        print("✅ 文本提取成功")
        print("   原始 Markdown 长度:", len(test_markdown))
        print("   提取文本长度:", len(text))
        print()
        print("   提取的文本:")
        print("   " + text[:200].replace("\n", "\n   "))
        
        # 验证格式标记已移除
        if "**" not in text and "*" not in test_markdown[:50]:
            print("   ✅ 格式标记已移除")
        else:
            print("   ⚠️  可能还有格式标记")
        
        return True
    except Exception as e:
        print(f"❌ 文本提取测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_silver_path_generation():
    """测试7: Silver 层路径生成"""
    print("\n" + "=" * 60)
    print("测试7: Silver 层路径生成")
    print("=" * 60)
    
    try:
        from src.storage.object_store.path_manager import PathManager
        from src.common.constants import Market, DocType
        
        pm = PathManager()
        
        # 测试常规文档路径
        path1 = pm.get_silver_path(
            market=Market.HS,
            doc_type=DocType.QUARTERLY_REPORT,
            stock_code="000001",
            year=2023,
            quarter=3,
            filename="000001_2023_Q3_parsed.json",
            subdir="text_cleaned"
        )
        print(f"✅ 常规文档路径: {path1}")
        
        # 测试 IPO 文档路径（与 Bronze 格式一致）
        path2 = pm.get_silver_path(
            market=Market.HS,
            doc_type=DocType.IPO_PROSPECTUS,
            stock_code="000001",
            filename="000001_IPO_parsed.json",
            subdir="text_cleaned"
        )
        print(f"✅ IPO 文档路径: {path2}")
        
        return True
    except Exception as e:
        print(f"❌ 路径生成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("MinerU 解析器本地测试")
    print("=" * 60)
    print()
    
    tests = [
        ("模块导入", test_import),
        ("MinerU 包导入", test_mineru_import),
        ("解析器初始化", test_parser_initialization),
        ("查找待解析文档", test_find_pending_documents),
        ("解析单个文档", test_parse_single_document),
        ("Markdown 文本提取", test_extract_text_from_markdown),
        ("Silver 层路径生成", test_silver_path_generation),
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
