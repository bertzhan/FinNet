# -*- coding: utf-8 -*-
"""
检查指定chunk_id的子节点情况
对比PostgreSQL和代码逻辑
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import uuid
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import DocumentChunk


def check_chunk_children(chunk_id_str: str):
    """
    检查指定chunk_id的子节点情况
    
    Args:
        chunk_id_str: 父chunk ID (字符串格式)
    """
    print("=" * 60)
    print("检查Chunk子节点情况")
    print("=" * 60)
    print(f"父Chunk ID: {chunk_id_str}")
    print()
    
    try:
        chunk_id = uuid.UUID(chunk_id_str)
    except ValueError:
        print(f"✗ 无效的UUID格式: {chunk_id_str}")
        return
    
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 1. 检查父chunk是否存在
            print("1. 检查父chunk是否存在...")
            parent_chunk = session.query(DocumentChunk).filter(
                DocumentChunk.id == chunk_id
            ).first()
            
            if not parent_chunk:
                print(f"✗ 父chunk不存在: {chunk_id_str}")
                return
            
            print(f"✓ 父chunk存在:")
            print(f"  - Chunk ID: {parent_chunk.id}")
            print(f"  - Document ID: {parent_chunk.document_id}")
            print(f"  - Title: {parent_chunk.title or 'N/A'}")
            print(f"  - Chunk Index: {parent_chunk.chunk_index}")
            print(f"  - Parent Chunk ID: {parent_chunk.parent_chunk_id or 'None (顶级chunk)'}")
            print()
            
            # 2. 查询所有子chunks（通过parent_chunk_id）
            print("2. 查询PostgreSQL中所有子chunks（通过parent_chunk_id）...")
            child_chunks = session.query(DocumentChunk).filter(
                DocumentChunk.parent_chunk_id == chunk_id
            ).order_by(DocumentChunk.chunk_index).all()
            
            print(f"✓ PostgreSQL中有 {len(child_chunks)} 个子chunks:")
            for i, child in enumerate(child_chunks, 1):
                print(f"  {i}. Chunk ID: {child.id}")
                print(f"      Title: {child.title or 'N/A'}")
                print(f"      Chunk Index: {child.chunk_index}")
                print(f"      Chunk Size: {child.chunk_size}")
            print()
            
            # 3. 检查代码逻辑 - 模拟get_children方法的查询
            print("3. 检查代码逻辑...")
            print("   GraphRetriever.get_children() 使用的Cypher查询:")
            print("   MATCH (parent:Chunk {id: $chunk_id})-[:HAS_CHILD]->(child:Chunk)")
            print("   RETURN child.id as chunk_id, child.title as title, child.chunk_index as chunk_index")
            print("   ORDER BY COALESCE(child.chunk_index, 999999) ASC")
            print()
            print(f"   这个查询应该返回 {len(child_chunks)} 个子节点")
            print()
            
            # 4. 检查是否有重复的chunk_index
            print("4. 检查子chunks的chunk_index...")
            chunk_indices = [c.chunk_index for c in child_chunks]
            if len(chunk_indices) != len(set(chunk_indices)):
                print(f"⚠ 发现重复的chunk_index!")
                from collections import Counter
                counter = Counter(chunk_indices)
                duplicates = {k: v for k, v in counter.items() if v > 1}
                for idx, count in duplicates.items():
                    print(f"  - chunk_index {idx} 出现了 {count} 次")
            else:
                print(f"✓ 所有chunk_index都是唯一的")
            print()
            
            # 5. 检查文档中所有chunks的情况
            print("5. 检查文档中所有chunks的情况...")
            all_chunks = session.query(DocumentChunk).filter(
                DocumentChunk.document_id == parent_chunk.document_id
            ).order_by(DocumentChunk.chunk_index).all()
            
            print(f"✓ 文档中共有 {len(all_chunks)} 个chunks")
            
            # 统计层级结构
            top_level = [c for c in all_chunks if c.parent_chunk_id is None]
            child_level = [c for c in all_chunks if c.parent_chunk_id is not None]
            
            print(f"  - 顶级chunks (parent_chunk_id=None): {len(top_level)}")
            print(f"  - 子chunks (parent_chunk_id不为None): {len(child_level)}")
            print()
            
            # 6. 检查是否有其他chunk也指向这些子chunks（不应该有）
            print("6. 检查数据一致性...")
            for child in child_chunks:
                other_parents = session.query(DocumentChunk).filter(
                    DocumentChunk.id != chunk_id
                ).filter(
                    DocumentChunk.parent_chunk_id == child.id
                ).all()
                if other_parents:
                    print(f"⚠ 子chunk {child.id} 被其他chunk作为parent引用（不应该发生）")
            
            print("✓ 数据一致性检查完成")
            print()
    except Exception as e:
        print(f"✗ 检查失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python examples/check_chunk_children.py <chunk_id>")
        print()
        print("示例:")
        print("  python examples/check_chunk_children.py 006c29fa-5225-4915-8bf2-84964e957187")
        sys.exit(1)
    
    chunk_id = sys.argv[1]
    check_chunk_children(chunk_id)


if __name__ == "__main__":
    main()
