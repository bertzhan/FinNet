# -*- coding: utf-8 -*-
"""
检查并索引数据到 Elasticsearch
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import Document, DocumentChunk
from src.storage.elasticsearch import get_elasticsearch_client
from datetime import datetime


def check_data():
    """检查 PostgreSQL 中是否有已分块的数据"""
    print("=" * 60)
    print("检查 PostgreSQL 中的数据")
    print("=" * 60)
    
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 查找已分块的文档
            chunks = session.query(DocumentChunk).join(
                Document, DocumentChunk.document_id == Document.id
            ).filter(
                DocumentChunk.chunk_text.isnot(None),
                DocumentChunk.chunk_text != ""
            ).limit(10).all()
            
            if not chunks:
                print("❌ PostgreSQL 中没有已分块的数据")
                print("   提示: 请先运行分块作业生成分块数据")
                return False
            
            print(f"✅ 找到 {len(chunks)} 个已分块的数据（显示前10个）\n")
            
            # 统计公司名称
            company_names = {}
            for chunk in chunks:
                doc = chunk.document
                company_name = doc.company_name or "未知"
                stock_code = doc.stock_code or "未知"
                key = f"{company_name}({stock_code})"
                company_names[key] = company_names.get(key, 0) + 1
            
            print("公司名称统计:")
            for company, count in sorted(company_names.items(), key=lambda x: x[1], reverse=True):
                print(f"  - {company}: {count} 个分块")
            
            # 检查是否已索引到 Elasticsearch
            indexed_count = sum(1 for chunk in chunks if chunk.es_indexed_at is not None)
            print(f"\n已索引到 Elasticsearch: {indexed_count}/{len(chunks)}")
            
            return True
            
    except Exception as e:
        print(f"❌ 检查数据时发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_elasticsearch():
    """检查 Elasticsearch 索引状态"""
    print("\n" + "=" * 60)
    print("检查 Elasticsearch 索引状态")
    print("=" * 60)
    
    try:
        es_client = get_elasticsearch_client()
        index_name = "chunks"
        full_index_name = f"{es_client.index_prefix}_{index_name}"
        
        # 检查索引是否存在
        exists = es_client.client.indices.exists(index=full_index_name)
        
        if not exists:
            print(f"❌ 索引不存在: {full_index_name}")
            print(f"   运行以下命令创建索引:")
            print(f"     PYTHONPATH={project_root} python examples/create_elasticsearch_index.py")
            return False
        
        # 获取索引统计信息
        stats = es_client.client.indices.stats(index=full_index_name)
        doc_count = stats.get('indices', {}).get(full_index_name, {}).get('total', {}).get('docs', {}).get('count', 0)
        
        print(f"✅ 索引存在: {full_index_name}")
        print(f"   文档数量: {doc_count}")
        
        if doc_count == 0:
            print(f"\n⚠️  索引为空，需要索引数据")
            print(f"   运行以下命令索引数据:")
            print(f"     dagster job execute -j elasticsearch_index_job")
            print(f"   或使用 Python:")
            print(f"     PYTHONPATH={project_root} python examples/test_elasticsearch_job_simple.py")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 检查 Elasticsearch 时发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n检查数据状态...\n")
    
    # 检查 PostgreSQL 数据
    has_data = check_data()
    
    # 检查 Elasticsearch 索引
    has_indexed = check_elasticsearch()
    
    print("\n" + "=" * 60)
    print("总结")
    print("=" * 60)
    
    if not has_data:
        print("❌ PostgreSQL 中没有数据，请先运行数据采集和分块作业")
    elif not has_indexed:
        print("⚠️  有数据但未索引到 Elasticsearch，请运行索引作业")
    else:
        print("✅ 数据已准备就绪，可以测试接口")
    
    print()


if __name__ == "__main__":
    main()
