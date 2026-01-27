#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 Neo4j Schema 重置功能
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.graph.neo4j_client import get_neo4j_client
from src.common.logger import get_logger

logger = get_logger(__name__)


def test_reset_schema():
    """测试重置 Neo4j schema"""
    print("=" * 60)
    print("Neo4j Schema 重置测试")
    print("=" * 60)
    print()
    
    try:
        # 获取 Neo4j 客户端
        client = get_neo4j_client()
        
        # 1. 获取重置前的统计信息
        print("1️⃣ 获取重置前的统计信息...")
        doc_count_before = client.get_node_count('Document')
        chunk_count_before = client.get_node_count('Chunk')
        contains_count_before = client.get_relationship_count('CONTAINS')
        parent_count_before = client.get_relationship_count('HAS_PARENT')
        total_nodes_before = client.get_node_count()
        total_edges_before = client.get_relationship_count()
        
        print(f"   文档节点: {doc_count_before}")
        print(f"   分块节点: {chunk_count_before}")
        print(f"   CONTAINS 边: {contains_count_before}")
        print(f"   HAS_PARENT 边: {parent_count_before}")
        print(f"   总节点数: {total_nodes_before}")
        print(f"   总边数: {total_edges_before}")
        print()
        
        # 2. 确认重置
        if total_nodes_before > 0 or total_edges_before > 0:
            print("⚠️  警告：数据库中有数据，重置将删除所有数据！")
            confirm = input("确认继续重置吗？(yes/no): ")
            if confirm.lower() != 'yes':
                print("操作已取消")
                return
        print()
        
        # 3. 执行重置
        print("2️⃣ 执行 schema 重置...")
        result = client.reset_schema()
        
        if not result.get('success'):
            print(f"   ❌ 重置失败: {result.get('error_message')}")
            return
        
        print(f"   ✅ 重置成功")
        print(f"   删除节点: {result.get('nodes_deleted', 0)}")
        print(f"   删除边: {result.get('relationships_deleted', 0)}")
        print(f"   删除约束: {result.get('constraints_deleted', 0)}")
        print(f"   删除索引: {result.get('indexes_deleted', 0)}")
        print()
        
        # 4. 验证重置结果
        print("3️⃣ 验证重置结果...")
        doc_count_after = client.get_node_count('Document')
        chunk_count_after = client.get_node_count('Chunk')
        contains_count_after = client.get_relationship_count('CONTAINS')
        parent_count_after = client.get_relationship_count('HAS_PARENT')
        total_nodes_after = client.get_node_count()
        total_edges_after = client.get_relationship_count()
        
        print(f"   文档节点: {doc_count_after} (之前: {doc_count_before})")
        print(f"   分块节点: {chunk_count_after} (之前: {chunk_count_before})")
        print(f"   CONTAINS 边: {contains_count_after} (之前: {contains_count_before})")
        print(f"   HAS_PARENT 边: {parent_count_after} (之前: {parent_count_before})")
        print(f"   总节点数: {total_nodes_after} (之前: {total_nodes_before})")
        print(f"   总边数: {total_edges_after} (之前: {total_edges_before})")
        print()
        
        # 5. 重新创建约束和索引
        print("4️⃣ 重新创建约束和索引...")
        client.create_constraints_and_indexes()
        print("   ✅ 约束和索引创建完成")
        print()
        
        # 6. 验证约束和索引
        print("5️⃣ 验证约束和索引...")
        try:
            constraints = client.execute_query("SHOW CONSTRAINTS")
            indexes = client.execute_query("SHOW INDEXES")
            print(f"   约束数量: {len(constraints)}")
            print(f"   索引数量: {len(indexes)}")
            print("   ✅ 约束和索引验证完成")
        except Exception as e:
            print(f"   ⚠️  验证失败: {e}")
        print()
        
        print("=" * 60)
        print("✅ Schema 重置测试完成")
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_reset_schema()
