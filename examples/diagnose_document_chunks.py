# -*- coding: utf-8 -*-
"""
诊断文档为什么没有chunks
检查文档的解析和分块状态
"""

import sys
from pathlib import Path
import uuid

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.storage.metadata import get_postgres_client, crud
from src.storage.metadata.models import Document, ParsedDocument, DocumentChunk, ParseTask
from src.common.logger import get_logger

logger = get_logger(__name__)


def diagnose_document(document_id: str):
    """诊断文档的chunks状态"""
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        print(f"✗ 无效的document_id格式: {document_id}")
        return
    
    pg_client = get_postgres_client()
    
    print(f"\n{'='*60}")
    print(f"诊断文档Chunks状态")
    print(f"{'='*60}")
    print(f"Document ID: {document_id}\n")
    
    with pg_client.get_session() as session:
        # 1. 检查文档是否存在
        document = crud.get_document_by_id(session, document_id)
        if not document:
            print(f"✗ 文档不存在")
            return
        
        print(f"✓ 文档存在")
        print(f"  股票代码: {document.stock_code}")
        print(f"  公司名称: {document.company_name}")
        print(f"  文档类型: {document.doc_type}")
        print(f"  年份: {document.year}, 季度: {document.quarter or 'N/A'}")
        print(f"  状态: {document.status}")
        print(f"  创建时间: {document.created_at}")
        print()
        
        # 2. 检查解析状态
        print(f"{'='*60}")
        print(f"解析状态检查")
        print(f"{'='*60}\n")
        
        parsed_docs = session.query(ParsedDocument).filter(
            ParsedDocument.document_id == doc_uuid
        ).order_by(ParsedDocument.parsed_at.desc()).all()
        
        if not parsed_docs:
            print(f"⚠️  文档尚未解析（没有ParsedDocument记录）")
            print(f"   建议: 需要先运行解析任务（parse job）")
            print()
        else:
            latest_parsed = parsed_docs[0]
            print(f"✓ 找到 {len(parsed_docs)} 个解析记录（显示最新的）")
            print(f"  ParsedDocument ID: {latest_parsed.id}")
            print(f"  解析时间: {latest_parsed.parsed_at}")
            print(f"  解析器类型: {latest_parsed.parser_type}")
            print(f"  状态: {latest_parsed.status}")
            print(f"  文本长度: {latest_parsed.text_length}")
            print(f"  页数: {latest_parsed.pages_count}")
            print(f"  表格数量: {latest_parsed.tables_count}")
            print(f"  图片数量: {latest_parsed.images_count}")
            print(f"  记录的Chunks数量: {latest_parsed.chunks_count}")
            print(f"  分块时间: {latest_parsed.chunked_at or '未分块'}")
            print()
            
            if latest_parsed.chunks_count == 0:
                print(f"⚠️  ParsedDocument记录的chunks_count为0")
                print(f"   建议: 需要运行分块任务（chunk job）")
                print()
        
        # 3. 检查实际的chunks
        print(f"{'='*60}")
        print(f"Chunks检查")
        print(f"{'='*60}\n")
        
        chunks = crud.get_document_chunks(session, document_id)
        chunks_count = len(chunks)
        
        print(f"实际Chunks数量: {chunks_count}")
        
        if chunks_count == 0:
            print(f"⚠️  数据库中没有chunks记录")
            print()
            
            # 检查分块任务状态
            print(f"{'='*60}")
            print(f"分块任务检查")
            print(f"{'='*60}\n")
            
            # 检查是否有分块相关的任务记录
            # 注意：这里可能需要查看chunk job的执行记录
            
            # 总结
            print(f"{'='*60}")
            print(f"诊断总结")
            print(f"{'='*60}\n")
            
            if not parsed_docs:
                print(f"问题: 文档尚未解析")
                print(f"解决步骤:")
                print(f"  1. 运行解析任务（parse job）")
                print(f"  2. 等待解析完成")
                print(f"  3. 然后运行分块任务（chunk job）")
            elif latest_parsed.chunks_count == 0:
                print(f"问题: 文档已解析但未分块")
                print(f"解决步骤:")
                print(f"  1. 运行分块任务（chunk job）")
                print(f"  2. 等待分块完成")
            else:
                print(f"问题: ParsedDocument记录显示有chunks，但实际数据库中没有")
                print(f"解决步骤:")
                print(f"  1. 检查分块任务是否成功执行")
                print(f"  2. 检查是否有错误日志")
                print(f"  3. 可能需要重新运行分块任务")
        else:
            print(f"✓ 找到 {chunks_count} 个chunks")
            print()
            
            # 显示前5个chunks的信息
            print(f"前5个chunks示例:")
            for i, chunk in enumerate(chunks[:5], 1):
                print(f"  {i}. Chunk ID: {chunk.id}")
                print(f"     索引: {chunk.chunk_index}")
                print(f"     标题: {chunk.title or '(无标题)'}")
                print(f"     父Chunk: {chunk.parent_chunk_id or '(无父chunk)'}")
                print(f"     文本长度: {len(chunk.chunk_text) if chunk.chunk_text else 0}")
                print()
        
        # 4. 检查解析任务
        print(f"{'='*60}")
        print(f"解析任务检查")
        print(f"{'='*60}\n")
        
        parse_tasks = session.query(ParseTask).filter(
            ParseTask.document_id == doc_uuid
        ).order_by(ParseTask.created_at.desc()).all()
        
        if parse_tasks:
            print(f"找到 {len(parse_tasks)} 个解析任务（显示最新的）")
            latest_task = parse_tasks[0]
            print(f"  任务ID: {latest_task.id}")
            print(f"  状态: {latest_task.status}")
            print(f"  创建时间: {latest_task.created_at}")
            print(f"  开始时间: {latest_task.started_at or '未开始'}")
            print(f"  完成时间: {latest_task.completed_at or '未完成'}")
            if latest_task.error_message:
                print(f"  错误信息: {latest_task.error_message[:200]}")
            print()
        else:
            print(f"⚠️  没有找到解析任务记录")
            print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="诊断文档为什么没有chunks")
    parser.add_argument(
        "document_id",
        type=str,
        help="文档ID（UUID字符串）"
    )
    
    args = parser.parse_args()
    
    try:
        diagnose_document(args.document_id)
    except Exception as e:
        logger.error(f"诊断失败: {e}", exc_info=True)
        sys.exit(1)
