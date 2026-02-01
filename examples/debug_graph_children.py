# -*- coding: utf-8 -*-
"""
调试图检索子节点查询
检查Neo4j中实际有多少个子节点
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.graph.neo4j_client import get_neo4j_client


def debug_children(chunk_id: str):
    """
    调试查询子节点
    
    Args:
        chunk_id: 父分块ID
    """
    print("=" * 60)
    print("调试图检索子节点查询")
    print("=" * 60)
    print(f"父Chunk ID: {chunk_id}")
    print()
    
    neo4j_client = get_neo4j_client()
    
    # 1. 检查节点是否存在
    print("1. 检查父节点是否存在...")
    check_node_cypher = """
    MATCH (parent:Chunk {id: $chunk_id})
    RETURN parent.id as chunk_id, parent.title as title, parent.chunk_index as chunk_index
    """
    node_result = neo4j_client.execute_query(check_node_cypher, {"chunk_id": chunk_id})
    if not node_result:
        print(f"✗ 父节点不存在: {chunk_id}")
        return
    else:
        node = node_result[0]
        print(f"✓ 父节点存在:")
        print(f"  - Chunk ID: {node.get('chunk_id')}")
        print(f"  - Title: {node.get('title', 'N/A')}")
        print(f"  - Chunk Index: {node.get('chunk_index', 'N/A')}")
    print()
    
    # 2. 查询所有直接子节点（当前使用的查询）
    print("2. 查询所有直接子节点（当前查询）...")
    current_cypher = """
    MATCH (parent:Chunk {id: $chunk_id})-[:HAS_CHILD]->(child:Chunk)
    RETURN child.id as chunk_id, child.title as title, child.chunk_index as chunk_index
    ORDER BY child.chunk_index
    """
    current_results = neo4j_client.execute_query(current_cypher, {"chunk_id": chunk_id})
    print(f"✓ 查询到 {len(current_results)} 个子节点:")
    for i, child in enumerate(current_results, 1):
        print(f"  {i}. Chunk ID: {child.get('chunk_id')}")
        print(f"      Title: {child.get('title', 'N/A')}")
        print(f"      Chunk Index: {child.get('chunk_index', 'N/A')}")
    print()
    
    # 3. 检查是否有其他关系
    print("3. 检查父节点的所有出边关系...")
    all_relationships_cypher = """
    MATCH (parent:Chunk {id: $chunk_id})-[r]->(target)
    RETURN type(r) as relationship_type, labels(target) as target_labels, 
           target.id as target_id, target.title as target_title
    ORDER BY type(r), target.chunk_index
    """
    all_rels = neo4j_client.execute_query(all_relationships_cypher, {"chunk_id": chunk_id})
    print(f"✓ 父节点有 {len(all_rels)} 条出边关系:")
    for i, rel in enumerate(all_rels, 1):
        rel_type = rel.get('relationship_type')
        target_labels = rel.get('target_labels', [])
        target_id = rel.get('target_id')
        target_title = rel.get('target_title', 'N/A')
        print(f"  {i}. 关系类型: {rel_type}")
        print(f"     目标标签: {target_labels}")
        print(f"     目标ID: {target_id}")
        print(f"     目标标题: {target_title}")
    print()
    
    # 4. 检查是否有反向关系（子节点指向父节点）
    print("4. 检查是否有反向关系（子节点指向父节点）...")
    reverse_cypher = """
    MATCH (child:Chunk)-[r]->(parent:Chunk {id: $chunk_id})
    RETURN type(r) as relationship_type, child.id as child_id, child.title as child_title
    ORDER BY child.chunk_index
    """
    reverse_rels = neo4j_client.execute_query(reverse_cypher, {"chunk_id": chunk_id})
    if reverse_rels:
        print(f"✓ 找到 {len(reverse_rels)} 条反向关系:")
        for i, rel in enumerate(reverse_rels, 1):
            print(f"  {i}. 关系类型: {rel.get('relationship_type')}")
            print(f"     子节点ID: {rel.get('child_id')}")
            print(f"     子节点标题: {rel.get('child_title', 'N/A')}")
    else:
        print("  (没有反向关系)")
    print()
    
    # 5. 检查数据库中该文档的所有chunks（通过parent_chunk_id）
    print("5. 检查PostgreSQL中该chunk的所有子chunks（通过parent_chunk_id）...")
    try:
        from src.storage.metadata.postgres_client import get_postgres_client
        from src.storage.metadata.models import DocumentChunk
        import uuid
        
        pg_client = get_postgres_client()
        with pg_client.get_session() as session:
            # 先找到父chunk的document_id
            parent_chunk_uuid = uuid.UUID(chunk_id)
            parent_chunk = session.query(DocumentChunk).filter(
                DocumentChunk.id == parent_chunk_uuid
            ).first()
            
            if parent_chunk:
                print(f"✓ 父chunk信息:")
                print(f"  - Document ID: {parent_chunk.document_id}")
                print(f"  - Chunk Index: {parent_chunk.chunk_index}")
                print(f"  - Title: {parent_chunk.title}")
                print()
                
                # 查找所有子chunks
                child_chunks = session.query(DocumentChunk).filter(
                    DocumentChunk.parent_chunk_id == parent_chunk_uuid
                ).order_by(DocumentChunk.chunk_index).all()
                
                print(f"✓ PostgreSQL中有 {len(child_chunks)} 个子chunks:")
                for i, child in enumerate(child_chunks, 1):
                    print(f"  {i}. Chunk ID: {child.id}")
                    print(f"      Title: {child.title or 'N/A'}")
                    print(f"      Chunk Index: {child.chunk_index}")
                
                # 检查哪些在Neo4j中
                print()
                print("6. 检查哪些子chunks在Neo4j中有HAS_CHILD关系...")
                neo4j_child_ids = {str(r.get('chunk_id')) for r in current_results}
                pg_child_ids = {str(c.id) for c in child_chunks}
                
                missing_in_neo4j = pg_child_ids - neo4j_child_ids
                if missing_in_neo4j:
                    print(f"⚠ PostgreSQL中有 {len(missing_in_neo4j)} 个子chunks在Neo4j中没有HAS_CHILD关系:")
                    for child_id in missing_in_neo4j:
                        child = next((c for c in child_chunks if str(c.id) == child_id), None)
                        if child:
                            print(f"  - Chunk ID: {child_id}")
                            print(f"    Title: {child.title or 'N/A'}")
                            print(f"    Chunk Index: {child.chunk_index}")
                else:
                    print("✓ 所有PostgreSQL中的子chunks都在Neo4j中有HAS_CHILD关系")
            else:
                print(f"✗ 在PostgreSQL中找不到父chunk: {chunk_id}")
    except Exception as e:
        print(f"⚠ 检查PostgreSQL时出错: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 60)


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python examples/debug_graph_children.py <chunk_id>")
        print()
        print("示例:")
        print("  python examples/debug_graph_children.py 032b99ea-dd6f-47f1-8c77-8de013b6ba41")
        sys.exit(1)
    
    chunk_id = sys.argv[1]
    debug_children(chunk_id)


if __name__ == "__main__":
    main()
