#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图构建作业测试脚本
测试 graph_jobs 的各个 ops 和完整 job
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

# 延迟导入，避免权限问题
def import_modules():
    """延迟导入模块"""
    from dagster import build_op_context
    from src.processing.compute.dagster.jobs.graph_jobs import (
        scan_chunked_documents_for_graph_op,
        build_graph_op,
        validate_graph_op,
        build_graph_job,
    )
    from src.processing.graph.graph_builder import GraphBuilder
    from src.storage.graph.neo4j_client import get_neo4j_client
    from src.storage.metadata.postgres_client import get_postgres_client
    from src.storage.metadata.models import Document, DocumentChunk
    
    return (
        build_op_context,
        scan_chunked_documents_for_graph_op,
        build_graph_op,
        validate_graph_op,
        build_graph_job,
        GraphBuilder,
        get_neo4j_client,
        get_postgres_client,
        Document,
        DocumentChunk,
    )


def test_scan_vectorized_documents():
    """测试扫描已分块文档的 op"""
    print("=" * 60)
    print("测试: scan_chunked_documents_for_graph_op")
    print("=" * 60)
    print()
    
    build_op_context, scan_chunked_documents_for_graph_op, _, _, _, _, _, _, _, _ = import_modules()
    
    config = {
        "batch_size": 10,
        "limit": 20,
        "force_rebuild": False,
    }
    
    context = build_op_context(config=config)
    
    try:
        result = scan_chunked_documents_for_graph_op(context)
        
        print(f"✅ 扫描完成")
        print(f"   成功: {result.get('success')}")
        print(f"   找到文档数: {result.get('total_documents', 0)}")
        print(f"   批次数量: {result.get('total_batches', 0)}")
        
        if result.get('documents'):
            print(f"\n   前3个文档:")
            for doc in result['documents'][:3]:
                print(f"     - {doc.get('stock_code')} ({doc.get('company_name')}) - {doc.get('doc_type')}")
        
        if not result.get('success'):
            print(f"   错误: {result.get('error_message')}")
        
        print()
        return result
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_build_graph(scan_result):
    """测试构建图的 op"""
    print("=" * 60)
    print("测试: build_graph_op")
    print("=" * 60)
    print()
    
    if not scan_result or not scan_result.get('success') or not scan_result.get('documents'):
        print("⚠️  没有待建图的文档，跳过构建测试")
        return None
    
    build_op_context, _, build_graph_op, _, _, _, _, _, _, _ = import_modules()
    
    config = {
        "force_rebuild": False,
    }
    
    context = build_op_context(config=config)
    
    try:
        result = build_graph_op(context, scan_result)
        
        print(f"✅ 图构建完成")
        print(f"   成功: {result.get('success')}")
        print(f"   处理文档数: {result.get('documents_processed', 0)}")
        print(f"   创建分块节点: {result.get('chunks_created', 0)}")
        print(f"   创建 BELONGS_TO 边: {result.get('belongs_to_edges_created', 0)}")
        print(f"   创建 HAS_CHILD 边: {result.get('has_child_edges_created', 0)}")
        
        if result.get('failed_documents'):
            print(f"   失败文档数: {len(result.get('failed_documents', []))}")
        
        if not result.get('success'):
            print(f"   错误: {result.get('error_message')}")
        
        print()
        return result
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_validate_graph(build_result):
    """测试验证图构建结果的 op"""
    print("=" * 60)
    print("测试: validate_graph_op")
    print("=" * 60)
    print()
    
    if not build_result:
        print("⚠️  没有构建结果，跳过验证测试")
        return None
    
    build_op_context, _, _, validate_graph_op, _, _, _, _, _, _ = import_modules()
    
    context = build_op_context()
    
    try:
        result = validate_graph_op(context, build_result)
        
        print(f"✅ 验证完成")
        print(f"   成功: {result.get('success')}")
        print(f"   验证通过: {result.get('validation_passed')}")
        print(f"   处理文档数: {result.get('documents_processed', 0)}")
        print(f"   创建分块节点: {result.get('chunks_created', 0)}")
        print(f"   创建 BELONGS_TO 边: {result.get('belongs_to_edges_created', 0)}")
        print(f"   创建 HAS_CHILD 边: {result.get('has_child_edges_created', 0)}")
        
        if result.get('graph_stats'):
            stats = result['graph_stats']
            print(f"\n   图统计信息:")
            print(f"     文档节点总数: {stats.get('document_nodes', 0)}")
            print(f"     分块节点总数: {stats.get('chunk_nodes', 0)}")
            print(f"     BELONGS_TO 边总数: {stats.get('belongs_to_edges', 0)}")
            print(f"     HAS_CHILD 边总数: {stats.get('has_child_edges', 0)}")
        
        print()
        return result
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_graph_builder_direct():
    """直接测试 GraphBuilder"""
    print("=" * 60)
    print("测试: GraphBuilder 直接调用")
    print("=" * 60)
    print()
    
    _, _, _, _, _, GraphBuilder, _, _, _, _ = import_modules()
    
    try:
        builder = GraphBuilder()
        
        # 获取图统计信息
        stats = builder.get_graph_stats()
        print(f"✅ 获取图统计信息成功")
        print(f"   文档节点: {stats.get('document_nodes', 0)}")
        print(f"   分块节点: {stats.get('chunk_nodes', 0)}")
        print(f"   BELONGS_TO 边: {stats.get('belongs_to_edges', 0)}")
        print(f"   HAS_CHILD 边: {stats.get('has_child_edges', 0)}")
        print(f"   总节点数: {stats.get('total_nodes', 0)}")
        print(f"   总边数: {stats.get('total_edges', 0)}")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_neo4j_connection():
    """测试 Neo4j 连接"""
    print("=" * 60)
    print("测试: Neo4j 连接")
    print("=" * 60)
    print()
    
    _, _, _, _, _, _, get_neo4j_client, _, _, _ = import_modules()
    
    try:
        client = get_neo4j_client()
        
        # 测试基本查询
        result = client.execute_query("RETURN 1 as test")
        if result:
            print(f"✅ Neo4j 连接成功")
            print(f"   测试查询结果: {result}")
        else:
            print(f"⚠️  Neo4j 连接成功，但查询无结果")
        
        print()
        return True
        
    except Exception as e:
        print(f"❌ Neo4j 连接失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_check_vectorized_documents():
    """检查是否有已分块的文档"""
    print("=" * 60)
    print("检查: 已分块的文档")
    print("=" * 60)
    print()
    
    _, _, _, _, _, _, _, get_postgres_client, Document, DocumentChunk = import_modules()
    
    try:
        pg_client = get_postgres_client()
        
        with pg_client.get_session() as session:
            # 查找有分块的文档（通过 JOIN DocumentChunk）
            from sqlalchemy import distinct
            document_ids = session.query(distinct(Document.id)).join(
                DocumentChunk, Document.id == DocumentChunk.document_id
            ).limit(5).all()
            
            document_ids = [row[0] for row in document_ids]
            chunked_docs = session.query(Document).filter(
                Document.id.in_(document_ids)
            ).all() if document_ids else []
            
            print(f"✅ 查询完成")
            print(f"   已分块文档数（前5个）: {len(chunked_docs)}")
            
            if chunked_docs:
                print(f"\n   文档列表:")
                for doc in chunked_docs:
                    # 检查分块数量
                    chunks_count = session.query(DocumentChunk).filter(
                        DocumentChunk.document_id == doc.id
                    ).count()
                    
                    print(f"     - {doc.stock_code} ({doc.company_name})")
                    print(f"       文档ID: {doc.id}")
                    print(f"       类型: {doc.doc_type}, 年份: {doc.year}, 季度: {doc.quarter}")
                    print(f"       分块数: {chunks_count}")
            else:
                print(f"   ⚠️  没有找到已分块的文档")
                print(f"   提示: 需要先运行分块作业")
            
            print()
            return len(chunked_docs) > 0
            
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("图构建作业测试")
    print("=" * 60)
    print()
    
    results = []
    
    # 1. 测试 Neo4j 连接
    print("1️⃣ 测试 Neo4j 连接...")
    results.append(("Neo4j 连接", test_neo4j_connection()))
    print()
    
    # 2. 测试 GraphBuilder
    print("2️⃣ 测试 GraphBuilder...")
    results.append(("GraphBuilder", test_graph_builder_direct()))
    print()
    
    # 3. 检查已向量化文档
    print("3️⃣ 检查已向量化文档...")
    has_vectorized = test_check_vectorized_documents()
    print()
    
    if not has_vectorized:
        print("⚠️  没有已分块的文档，跳过后续测试")
        print("   提示: 需要先运行分块作业")
        print()
    else:
        # 4. 测试扫描 op
        print("4️⃣ 测试扫描已向量化文档...")
        scan_result = test_scan_vectorized_documents()
        results.append(("扫描文档", scan_result is not None and scan_result.get('success')))
        print()
        
        if scan_result and scan_result.get('documents'):
            # 5. 测试构建图 op
            print("5️⃣ 测试构建图...")
            build_result = test_build_graph(scan_result)
            results.append(("构建图", build_result is not None and build_result.get('success')))
            print()
            
            # 6. 测试验证 op
            print("6️⃣ 测试验证图构建结果...")
            validate_result = test_validate_graph(build_result)
            results.append(("验证结果", validate_result is not None and validate_result.get('validation_passed')))
            print()
        else:
            print("⚠️  没有待建图的文档，跳过构建和验证测试")
            print()
    
    # 汇总
    print("=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print()
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {name}")
    
    print()
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"总计: {passed}/{total} 通过")
    print()
    
    if passed == total:
        print("✅ 所有测试通过！图构建作业功能正常")
    else:
        print("⚠️  部分测试未通过，请检查错误信息")
    print()


if __name__ == "__main__":
    main()
