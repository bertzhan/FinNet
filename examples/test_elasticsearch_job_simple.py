#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试 Elasticsearch 索引功能
直接测试 Elasticsearch 客户端和索引功能，不依赖 Dagster
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.elasticsearch import get_elasticsearch_client
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import Document, DocumentChunk


def test_elasticsearch_connection():
    """测试 Elasticsearch 连接"""
    print("=" * 60)
    print("测试 Elasticsearch 连接")
    print("=" * 60)
    print()
    
    try:
        es_client = get_elasticsearch_client()
        print("✅ Elasticsearch 客户端初始化成功")
        
        # 测试 ping
        if es_client.client.ping():
            print("✅ Elasticsearch 服务连接正常")
            return True
        else:
            print("❌ Elasticsearch ping 失败")
            return False
            
    except Exception as e:
        print(f"❌ Elasticsearch 连接失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_create_index():
    """测试创建索引"""
    print()
    print("=" * 60)
    print("测试创建索引")
    print("=" * 60)
    print()
    
    try:
        es_client = get_elasticsearch_client()
        
        # 创建测试索引
        index_name = "chunks"
        result = es_client.create_index(index_name)
        
        if result:
            print(f"✅ 索引 '{index_name}' 创建成功")
            return True
        else:
            print(f"❌ 索引 '{index_name}' 创建失败")
            return False
            
    except Exception as e:
        print(f"❌ 创建索引失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_index_sample_chunks():
    """测试索引示例分块"""
    print()
    print("=" * 60)
    print("测试索引示例分块")
    print("=" * 60)
    print()
    
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 查找已分块的文档
            chunks = session.query(DocumentChunk).join(
                Document, DocumentChunk.document_id == Document.id
            ).filter(
                DocumentChunk.chunk_text.isnot(None),
                DocumentChunk.chunk_text != ""
            ).limit(5).all()
            
            if not chunks:
                print("⚠️  没有找到已分块的文档")
                print("   提示: 请先运行分块作业生成分块数据")
                return False
            
            print(f"找到 {len(chunks)} 个分块，准备索引...")
            
            es_client = get_elasticsearch_client()
            index_name = "chunks"
            
            # 准备文档数据
            documents = []
            for chunk in chunks:
                doc = session.query(Document).filter(Document.id == chunk.document_id).first()
                if not doc:
                    continue
                
                es_doc = {
                    "id": str(chunk.id),
                    "document_id": str(chunk.document_id),
                    "chunk_index": chunk.chunk_index,
                    "chunk_text": chunk.chunk_text[:500],  # 限制长度用于测试
                    "title": chunk.title or "",
                    "title_level": chunk.title_level,
                    "chunk_size": chunk.chunk_size,
                    "is_table": chunk.is_table or False,
                    "stock_code": doc.stock_code,
                    "company_name": doc.company_name,
                    "market": doc.market,
                    "doc_type": doc.doc_type,
                    "year": doc.year,
                    "quarter": doc.quarter,
                    "publish_date": doc.publish_date.isoformat() if doc.publish_date else None,
                }
                documents.append(es_doc)
            
            print(f"准备索引 {len(documents)} 个文档...")
            
            # 批量索引
            result = es_client.bulk_index_documents(
                index_name=index_name,
                documents=documents,
                document_id_field="id"
            )
            
            success_count = result.get("success_count", 0)
            failed_count = result.get("failed_count", 0)
            
            print()
            print("索引结果:")
            print(f"  - 成功: {success_count}")
            print(f"  - 失败: {failed_count}")
            
            if success_count > 0:
                print("✅ 索引成功！")
                
                # 刷新索引
                es_client.refresh_index(index_name)
                print("✅ 索引已刷新")
                
                return True
            else:
                print("❌ 索引失败")
                if result.get("failed_items"):
                    print("失败项:")
                    for item in result.get("failed_items", [])[:5]:
                        print(f"  - {item}")
                return False
                
    except Exception as e:
        print(f"❌ 索引测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_search():
    """测试搜索功能"""
    print()
    print("=" * 60)
    print("测试搜索功能")
    print("=" * 60)
    print()
    
    try:
        es_client = get_elasticsearch_client()
        index_name = "chunks"
        
        # 简单搜索测试
        query = {
            "match_all": {}
        }
        
        print("执行搜索查询...")
        results = es_client.search(
            index_name=index_name,
            query=query,
            size=5
        )
        
        hits = results.get("hits", {}).get("hits", [])
        total = results.get("hits", {}).get("total", {}).get("value", 0)
        
        print(f"✅ 搜索成功！找到 {total} 个结果")
        print(f"   显示前 {len(hits)} 个结果:")
        print()
        
        for i, hit in enumerate(hits, 1):
            source = hit.get("_source", {})
            print(f"{i}. 分块 ID: {hit.get('_id')}")
            print(f"   股票代码: {source.get('stock_code')}")
            print(f"   公司名称: {source.get('company_name')}")
            print(f"   文本预览: {source.get('chunk_text', '')[:100]}...")
            print()
        
        return True
        
    except Exception as e:
        print(f"❌ 搜索测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_filter_search():
    """测试带过滤条件的搜索"""
    print()
    print("=" * 60)
    print("测试带过滤条件的搜索")
    print("=" * 60)
    print()
    
    try:
        es_client = get_elasticsearch_client()
        index_name = "chunks"
        
        pg_client = get_postgres_client()
        with pg_client.get_session() as session:
            # 获取一个股票代码用于测试
            doc = session.query(Document).first()
            if not doc:
                print("⚠️  没有找到文档数据")
                return False
            
            stock_code = doc.stock_code
            print(f"使用股票代码 '{stock_code}' 进行过滤搜索...")
            
            # 带过滤条件的搜索
            query = {
                "bool": {
                    "must": [
                        {"match_all": {}}
                    ],
                    "filter": [
                        {"term": {"stock_code": stock_code}}
                    ]
                }
            }
            
            results = es_client.search(
                index_name=index_name,
                query=query,
                size=3
            )
            
            hits = results.get("hits", {}).get("hits", [])
            total = results.get("hits", {}).get("total", {}).get("value", 0)
            
            print(f"✅ 过滤搜索成功！找到 {total} 个结果（股票代码: {stock_code}）")
            print(f"   显示前 {len(hits)} 个结果:")
            print()
            
            for i, hit in enumerate(hits, 1):
                source = hit.get("_source", {})
                print(f"{i}. 分块索引: {source.get('chunk_index')}")
                print(f"   文本预览: {source.get('chunk_text', '')[:80]}...")
                print()
            
            return True
            
    except Exception as e:
        print(f"❌ 过滤搜索测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print()
    print("=" * 60)
    print("Elasticsearch 功能测试")
    print("=" * 60)
    print()
    
    results = []
    
    # 1. 测试连接
    results.append(("连接测试", test_elasticsearch_connection()))
    
    # 2. 测试创建索引
    results.append(("创建索引", test_create_index()))
    
    # 3. 测试索引数据
    results.append(("索引数据", test_index_sample_chunks()))
    
    # 4. 测试搜索
    results.append(("搜索功能", test_search()))
    
    # 5. 测试过滤搜索
    results.append(("过滤搜索", test_filter_search()))
    
    # 汇总结果
    print()
    print("=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print()
    
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    print()
    if all_passed:
        print("🎉 所有测试通过！")
    else:
        print("⚠️  部分测试失败，请检查错误信息")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
