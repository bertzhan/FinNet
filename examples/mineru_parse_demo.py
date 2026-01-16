# -*- coding: utf-8 -*-
"""
MinerU PDF 解析示例
演示如何使用 MinerU 解析器解析 PDF 并上传到 Silver 层
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.processing.ai.pdf_parser import MinerUParser, get_mineru_parser
from src.storage.metadata import get_postgres_client, crud
from src.common.constants import DocumentStatus


def demo_parse_single_document():
    """示例1：解析单个文档"""
    print("=" * 60)
    print("示例1：解析单个文档")
    print("=" * 60)
    
    # 获取一个待解析的文档
    pg_client = get_postgres_client()
    with pg_client.get_session() as session:
        # 查找状态为 crawled 的文档
        docs = crud.get_documents_by_status(
            session=session,
            status=DocumentStatus.CRAWLED.value,
            limit=1
        )
        
        if not docs:
            print("⚠️  没有待解析的文档（状态为 crawled）")
            print("   提示：先运行爬虫任务，爬取一些文档")
            return
        
        doc = docs[0]
        print(f"找到文档: ID={doc.id}, {doc.stock_code} {doc.year} Q{doc.quarter}")
        print(f"MinIO 路径: {doc.minio_object_name}")
        print()
        
        # 创建解析器
        parser = get_mineru_parser()
        
        # 解析文档
        print("开始解析...")
        result = parser.parse_document(doc.id)
        
        if result["success"]:
            print("✅ 解析成功！")
            print(f"   解析任务ID: {result['parse_task_id']}")
            print(f"   Silver 层路径: {result['output_path']}")
            print(f"   文本长度: {result['extracted_text_length']} 字符")
            print(f"   表格数量: {result['extracted_tables_count']}")
            print(f"   图片数量: {result['extracted_images_count']}")
        else:
            print(f"❌ 解析失败: {result.get('error_message', '未知错误')}")
    
    print()


def demo_parse_batch():
    """示例2：批量解析文档"""
    print("=" * 60)
    print("示例2：批量解析文档")
    print("=" * 60)
    
    pg_client = get_postgres_client()
    parser = get_mineru_parser()
    
    with pg_client.get_session() as session:
        # 查找待解析的文档（最多10个）
        docs = crud.get_documents_by_status(
            session=session,
            status=DocumentStatus.CRAWLED.value,
            limit=10
        )
        
        if not docs:
            print("⚠️  没有待解析的文档")
            return
        
        print(f"找到 {len(docs)} 个待解析文档")
        print()
        
        success_count = 0
        fail_count = 0
        
        for i, doc in enumerate(docs, 1):
            print(f"[{i}/{len(docs)}] 解析: {doc.stock_code} {doc.year} Q{doc.quarter}")
            
            result = parser.parse_document(doc.id)
            
            if result["success"]:
                success_count += 1
                print(f"   ✅ 成功 - 文本长度: {result['extracted_text_length']}")
            else:
                fail_count += 1
                print(f"   ❌ 失败 - {result.get('error_message', '未知错误')}")
        
        print()
        print(f"批量解析完成: 成功 {success_count}, 失败 {fail_count}")
    
    print()


def demo_check_parse_status():
    """示例3：检查解析状态"""
    print("=" * 60)
    print("示例3：检查解析状态")
    print("=" * 60)
    
    pg_client = get_postgres_client()
    
    with pg_client.get_session() as session:
        # 统计各状态的文档数量
        crawled_count = len(crud.get_documents_by_status(session, DocumentStatus.CRAWLED.value, limit=1000))
        parsed_count = len(crud.get_documents_by_status(session, DocumentStatus.PARSED.value, limit=1000))
        
        print(f"📊 文档状态统计:")
        print(f"   已爬取（待解析）: {crawled_count}")
        print(f"   已解析: {parsed_count}")
        print()
        
        # 查询最近的解析任务
        from src.storage.metadata.models import ParseTask
        from sqlalchemy import desc
        
        recent_tasks = session.query(ParseTask).order_by(
            desc(ParseTask.created_at)
        ).limit(5).all()
        
        if recent_tasks:
            print("📋 最近的解析任务:")
            for task in recent_tasks:
                status_icon = "✅" if task.success else "❌"
                print(f"   {status_icon} 任务ID={task.id}, 文档ID={task.document_id}")
                print(f"      状态: {task.status}, 解析器: {task.parser_type}")
                if task.success:
                    print(f"      文本长度: {task.extracted_text_length}, "
                          f"表格: {task.extracted_tables_count}, "
                          f"图片: {task.extracted_images_count}")
                if task.error_message:
                    print(f"      错误: {task.error_message[:50]}...")
        else:
            print("   暂无解析任务")
    
    print()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    else:
        mode = "all"
    
    if mode == "single" or mode == "all":
        demo_parse_single_document()
    
    if mode == "batch" or mode == "all":
        demo_parse_batch()
    
    if mode == "status" or mode == "all":
        demo_check_parse_status()
    
    print("=" * 60)
    print("示例运行完成")
    print("=" * 60)
