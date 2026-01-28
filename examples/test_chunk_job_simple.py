#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试 Dagster 文本分块作业
直接测试分块服务，不依赖 Dagster
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.processing.text import get_text_chunker
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud


def test_chunker_directly():
    """直接测试分块服务"""
    print("=" * 60)
    print("测试文本分块服务（直接调用）")
    print("=" * 60)
    print()
    
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 查找一个已解析的文档
            from src.storage.metadata.models import ParsedDocument, Document
            
            parsed_doc = session.query(ParsedDocument).join(
                Document, ParsedDocument.document_id == Document.id
            ).filter(
                ParsedDocument.markdown_path.isnot(None),
                ParsedDocument.markdown_path != "",
                ParsedDocument.chunks_count == 0  # 未分块的文档
            ).first()
            
            if not parsed_doc:
                print("⚠️  没有找到待分块的文档")
                print("   提示: 请先运行解析作业生成 Markdown 文件")
                return False
            
            doc = session.query(Document).filter(
                Document.id == parsed_doc.document_id
            ).first()
            
            if not doc:
                print("⚠️  文档不存在")
                return False
            
            print(f"找到待分块文档:")
            print(f"  - Document ID: {doc.id}")
            print(f"  - 股票代码: {doc.stock_code}")
            print(f"  - 公司名称: {doc.company_name}")
            print(f"  - 市场: {doc.market}")
            print(f"  - 文档类型: {doc.doc_type}")
            print(f"  - Markdown 路径: {parsed_doc.markdown_path}")
            print()
            
            # 执行分块
            print("开始分块...")
            chunker = get_text_chunker()
            result = chunker.chunk_document(doc.id)
            
            print()
            print("=" * 60)
            print("分块结果")
            print("=" * 60)
            
            if result.get("success"):
                print("✅ 分块成功！")
                print(f"  - 分块数量: {result.get('chunks_count', 0)}")
                print(f"  - Structure 路径: {result.get('structure_path', 'N/A')}")
                print(f"  - Chunks 路径: {result.get('chunks_path', 'N/A')}")
                print(f"  - 耗时: {result.get('duration', 0):.2f} 秒")
                
                # 保存分块结果到本地
                print()
                print("=" * 60)
                print("保存分块结果到本地")
                print("=" * 60)
                
                # 创建本地保存目录
                output_dir = Path("downloads/chunks") / str(doc.id)
                output_dir.mkdir(parents=True, exist_ok=True)
                
                # 下载并保存 structure.json
                structure_path = result.get('structure_path')
                if structure_path:
                    try:
                        structure_data = chunker.minio_client.download_file(structure_path)
                        if structure_data:
                            local_structure_path = output_dir / "structure.json"
                            with open(local_structure_path, 'wb') as f:
                                f.write(structure_data)
                            print(f"✅ Structure JSON 已保存到: {local_structure_path}")
                        else:
                            print(f"⚠️  无法下载 Structure JSON: {structure_path}")
                    except Exception as e:
                        print(f"⚠️  下载 Structure JSON 失败: {e}")
                
                # 下载并保存 chunks.json
                chunks_path = result.get('chunks_path')
                if chunks_path:
                    try:
                        chunks_data = chunker.minio_client.download_file(chunks_path)
                        if chunks_data:
                            local_chunks_path = output_dir / "chunks.json"
                            with open(local_chunks_path, 'wb') as f:
                                f.write(chunks_data)
                            print(f"✅ Chunks JSON 已保存到: {local_chunks_path}")
                            
                            # 解析并显示分块信息
                            import json
                            chunks_json = json.loads(chunks_data.decode('utf-8'))
                            total_chunks = chunks_json.get('total_chunks', 0)
                            print(f"  - 总分块数: {total_chunks}")
                            
                            # 显示前3个分块的标题
                            chunks_list = chunks_json.get('chunks', [])
                            if chunks_list:
                                print(f"  - 前3个分块标题:")
                                for i, chunk in enumerate(chunks_list[:3], 1):
                                    title = chunk.get('title', 'N/A')
                                    content_length = chunk.get('content_length', 0)
                                    print(f"    {i}. {title} ({content_length} 字符)")
                        else:
                            print(f"⚠️  无法下载 Chunks JSON: {chunks_path}")
                    except Exception as e:
                        print(f"⚠️  下载 Chunks JSON 失败: {e}")
                
                # 下载并保存 markdown 文件（如果存在）
                if parsed_doc.markdown_path:
                    try:
                        markdown_data = chunker.minio_client.download_file(parsed_doc.markdown_path)
                        if markdown_data:
                            local_markdown_path = output_dir / "document.md"
                            with open(local_markdown_path, 'wb') as f:
                                f.write(markdown_data)
                            print(f"✅ Markdown 已保存到: {local_markdown_path}")
                    except Exception as e:
                        print(f"⚠️  下载 Markdown 失败: {e}")
                
                print()
                print(f"📁 所有文件已保存到: {output_dir.absolute()}")
                
                return True
            else:
                print("❌ 分块失败")
                print(f"  错误: {result.get('error_message', '未知错误')}")
                return False
                
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_chunker_directly()
    sys.exit(0 if success else 1)
