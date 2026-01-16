# -*- coding: utf-8 -*-
"""
MinerU 解析器本地测试示例
使用 MinIO 中实际存在的文件进行测试
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.processing.ai.pdf_parser import get_mineru_parser
from src.storage.metadata import get_postgres_client, crud
from src.storage.object_store.minio_client import MinIOClient
from src.common.constants import DocumentStatus, Market, DocType


def find_test_document():
    """查找一个可以用于测试的文档"""
    print("=" * 60)
    print("查找测试文档")
    print("=" * 60)
    
    # 方法1: 从数据库查找
    try:
        pg_client = get_postgres_client()
        with pg_client.get_session() as session:
            # 查找状态为 crawled 的 PDF 文档
            docs = crud.get_documents_by_status(
                session=session,
                status=DocumentStatus.CRAWLED.value,
                limit=10
            )
            
            print(f"\n从数据库找到 {len(docs)} 个待解析文档")
            
            # 检查 MinIO 中是否存在
            minio_client = MinIOClient()
            for doc in docs:
                if doc.minio_object_name and minio_client.file_exists(doc.minio_object_name):
                    print(f"\n✅ 找到可用文档:")
                    print(f"   ID: {doc.id}")
                    print(f"   股票代码: {doc.stock_code}")
                    print(f"   年份: {doc.year}, 季度: {doc.quarter}")
                    print(f"   MinIO 路径: {doc.minio_object_name}")
                    print(f"   文档类型: {doc.doc_type}")
                    return doc
            
            print("\n⚠️  数据库中的文档在 MinIO 中不存在")
    except Exception as e:
        print(f"❌ 从数据库查找失败: {e}")
    
    # 方法2: 直接从 MinIO 查找 PDF 文件
    print("\n从 MinIO 直接查找 PDF 文件...")
    try:
        minio_client = MinIOClient()
        objects = list(minio_client.client.list_objects(
            minio_client.bucket,
            prefix="bronze/a_share/ipo_prospectus/",
            recursive=True
        ))
        
        # 找一个 PDF 文件
        for obj in objects:
            if obj.object_name.endswith('.pdf'):
                print(f"\n✅ 找到 PDF 文件:")
                print(f"   MinIO 路径: {obj.object_name}")
                print(f"   大小: {obj.size} bytes")
                
                # 尝试从路径提取信息
                parts = obj.object_name.split('/')
                if len(parts) >= 4:
                    stock_code = parts[3]
                    print(f"   股票代码: {stock_code}")
                
                return {
                    'minio_path': obj.object_name,
                    'stock_code': parts[3] if len(parts) >= 4 else 'unknown',
                    'size': obj.size
                }
        
        print("⚠️  没有找到 PDF 文件")
    except Exception as e:
        print(f"❌ 从 MinIO 查找失败: {e}")
    
    return None


def test_parse_with_mineru(doc_info):
    """使用 MinerU 解析文档"""
    print("\n" + "=" * 60)
    print("测试 MinerU 解析")
    print("=" * 60)
    
    # 检查 MinerU 是否安装
    try:
        import mineru
        print("✅ MinerU 已安装")
    except ImportError:
        print("❌ MinerU 未安装")
        print("\n请先安装 MinerU:")
        print("  pip install mineru")
        print("\n或者配置 MINERU_API_BASE 使用 API 方式:")
        print("  export MINERU_API_BASE=http://localhost:8000")
        return False
    
    # 如果有数据库文档 ID，使用完整流程
    if isinstance(doc_info, dict) and 'id' in doc_info:
        doc_id = doc_info['id']
        print(f"\n使用文档 ID {doc_id} 进行解析...")
        
        try:
            parser = get_mineru_parser()
            result = parser.parse_document(doc_id)
            
            if result["success"]:
                print("\n✅ 解析成功！")
                print(f"   解析任务ID: {result.get('parse_task_id')}")
                print(f"   Silver 层路径: {result.get('output_path')}")
                print(f"   文本长度: {result.get('extracted_text_length', 0)} 字符")
                print(f"   表格数量: {result.get('extracted_tables_count', 0)}")
                print(f"   图片数量: {result.get('extracted_images_count', 0)}")
                return True
            else:
                print(f"\n❌ 解析失败: {result.get('error_message', '未知错误')}")
                return False
        except Exception as e:
            print(f"\n❌ 解析异常: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # 如果没有数据库文档，只能测试下载和解析功能
    elif isinstance(doc_info, dict) and 'minio_path' in doc_info:
        print(f"\n⚠️  只有 MinIO 路径，无法使用完整流程")
        print(f"   MinIO 路径: {doc_info['minio_path']}")
        print("\n提示: 需要先创建数据库记录才能使用 parse_document()")
        print("      或者可以手动下载文件并测试 MinerU 解析功能")
        return False
    
    else:
        print("⚠️  没有可用的文档信息")
        return False


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("MinerU 解析器本地测试")
    print("=" * 60)
    print()
    
    # 查找测试文档
    doc_info = find_test_document()
    
    if not doc_info:
        print("\n" + "=" * 60)
        print("测试总结")
        print("=" * 60)
        print("⚠️  没有找到可用的测试文档")
        print("\n建议:")
        print("1. 先运行爬虫任务，爬取一些文档到 MinIO")
        print("2. 确保文档已记录到数据库")
        print("3. 确保 MinerU 已安装或配置了 API")
        return
    
    # 测试解析
    if isinstance(doc_info, dict) and 'id' in doc_info:
        success = test_parse_with_mineru(doc_info)
    else:
        # 检查 MinerU 安装
        try:
            import mineru
            print("\n✅ MinerU 已安装，但需要数据库文档记录才能完整测试")
            print("   建议: 先运行爬虫任务创建文档记录")
        except ImportError:
            print("\n❌ MinerU 未安装")
            print("   安装命令: pip install mineru")
        success = False
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    if success:
        print("✅ 测试通过！")
    else:
        print("⚠️  测试未完成")
        print("\n下一步:")
        print("1. 确保 MinerU 已安装: pip install mineru")
        print("2. 确保有数据库文档记录（运行爬虫任务）")
        print("3. 重新运行测试")


if __name__ == '__main__':
    main()
