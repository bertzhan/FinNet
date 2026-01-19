#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断分块作业问题
检查为什么分块作业没有生成新文件
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.storage.metadata.models import Document, ParsedDocument
from src.storage.object_store.minio_client import MinIOClient


def check_pending_chunks():
    """检查待分块的文档"""
    print("=" * 80)
    print("1. 检查待分块的文档")
    print("=" * 80)
    
    pg_client = get_postgres_client()
    
    with pg_client.get_session() as session:
        # 查找有 markdown_path 但未分块的文档
        query = session.query(ParsedDocument).join(
            Document, ParsedDocument.document_id == Document.id
        ).filter(
            ParsedDocument.markdown_path.isnot(None),
            ParsedDocument.markdown_path != "",
            ParsedDocument.chunks_count == 0
        )
        
        parsed_docs = query.limit(10).all()
        
        if not parsed_docs:
            print("❌ 没有找到待分块的文档")
            print("   可能原因：")
            print("   - 所有文档都已分块（chunks_count > 0）")
            print("   - 没有已解析的文档（markdown_path 为空）")
            return []
        
        print(f"✅ 找到 {len(parsed_docs)} 个待分块的文档（最多显示10个）\n")
        
        for i, parsed_doc in enumerate(parsed_docs, 1):
            doc = session.query(Document).filter(
                Document.id == parsed_doc.document_id
            ).first()
            
            if doc:
                print(f"{i}. Document ID: {doc.id}")
                print(f"   股票代码: {doc.stock_code}")
                print(f"   公司名称: {doc.company_name}")
                print(f"   市场: {doc.market}, 类型: {doc.doc_type}")
                print(f"   Markdown 路径: {parsed_doc.markdown_path}")
                print(f"   Chunks Count: {parsed_doc.chunks_count}")
                print()
        
        return parsed_docs


def check_minio_files(parsed_doc):
    """检查 MinIO 中的文件"""
    print("=" * 80)
    print("2. 检查 MinIO 中的文件")
    print("=" * 80)
    
    minio_client = MinIOClient()
    markdown_path = parsed_doc.markdown_path
    
    if not markdown_path:
        print("❌ Markdown 路径为空")
        return
    
    # 提取目录
    markdown_dir = "/".join(markdown_path.split("/")[:-1])
    
    files_to_check = [
        markdown_path,
        f"{markdown_dir}/structure.json",
        f"{markdown_dir}/structure.txt",
        f"{markdown_dir}/chunks.json",
    ]
    
    print(f"检查路径: {markdown_dir}\n")
    
    for file_path in files_to_check:
        exists = minio_client.file_exists(file_path)
        status = "✅" if exists else "❌"
        print(f"{status} {file_path}")
        
        if exists:
            # 获取文件信息
            info = minio_client.get_file_info(file_path)
            if info:
                print(f"   大小: {info['size']:,} bytes")
                print(f"   修改时间: {info['last_modified']}")
    
    print()


def check_chunked_documents():
    """检查已分块的文档"""
    print("=" * 80)
    print("3. 检查最近分块的文档")
    print("=" * 80)
    
    pg_client = get_postgres_client()
    
    with pg_client.get_session() as session:
        # 查找最近分块的文档
        query = session.query(ParsedDocument).join(
            Document, ParsedDocument.document_id == Document.id
        ).filter(
            ParsedDocument.chunks_count > 0
        ).order_by(
            ParsedDocument.chunked_at.desc()
        ).limit(5)
        
        parsed_docs = query.all()
        
        if not parsed_docs:
            print("❌ 没有找到已分块的文档")
            return
        
        print(f"✅ 找到 {len(parsed_docs)} 个已分块的文档（最近5个）\n")
        
        for i, parsed_doc in enumerate(parsed_docs, 1):
            doc = session.query(Document).filter(
                Document.id == parsed_doc.document_id
            ).first()
            
            if doc:
                print(f"{i}. Document ID: {doc.id}")
                print(f"   股票代码: {doc.stock_code}")
                print(f"   Chunks Count: {parsed_doc.chunks_count}")
                print(f"   分块时间: {parsed_doc.chunked_at}")
                print(f"   Structure Path: {parsed_doc.structure_json_path}")
                print(f"   Chunks Path: {parsed_doc.chunks_json_path}")
                print()


def check_database_stats():
    """检查数据库统计信息"""
    print("=" * 80)
    print("4. 数据库统计信息")
    print("=" * 80)
    
    pg_client = get_postgres_client()
    
    with pg_client.get_session() as session:
        # 统计已解析的文档
        total_parsed = session.query(ParsedDocument).filter(
            ParsedDocument.markdown_path.isnot(None),
            ParsedDocument.markdown_path != ""
        ).count()
        
        # 统计已分块的文档
        total_chunked = session.query(ParsedDocument).filter(
            ParsedDocument.chunks_count > 0
        ).count()
        
        # 统计待分块的文档
        total_pending = session.query(ParsedDocument).join(
            Document, ParsedDocument.document_id == Document.id
        ).filter(
            ParsedDocument.markdown_path.isnot(None),
            ParsedDocument.markdown_path != "",
            ParsedDocument.chunks_count == 0
        ).count()
        
        print(f"已解析的文档总数: {total_parsed}")
        print(f"已分块的文档总数: {total_chunked}")
        print(f"待分块的文档总数: {total_pending}")
        print()


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("分块作业诊断工具")
    print("=" * 80 + "\n")
    
    # 1. 检查待分块的文档
    pending_docs = check_pending_chunks()
    
    # 2. 检查数据库统计
    check_database_stats()
    
    # 3. 如果有待分块的文档，检查 MinIO 文件
    if pending_docs:
        print("\n检查第一个待分块文档的 MinIO 文件...")
        check_minio_files(pending_docs[0])
    
    # 4. 检查已分块的文档
    check_chunked_documents()
    
    print("=" * 80)
    print("诊断完成")
    print("=" * 80)
    print("\n建议：")
    print("1. 如果 '待分块的文档总数' 为 0，说明所有文档都已分块")
    print("2. 如果有待分块文档但没有生成文件，请检查 Dagster 作业日志")
    print("3. 使用 force_rechunk=True 可以强制重新分块已分块的文档")
    print()


if __name__ == "__main__":
    main()
