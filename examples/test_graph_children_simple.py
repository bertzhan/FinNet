# -*- coding: utf-8 -*-
"""
图检索子节点查询接口简单测试
直接测试 GraphRetriever.get_children() 方法（不依赖API服务）
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.application.rag.graph_retriever import GraphRetriever


def test_get_children(chunk_id: str):
    """
    测试 GraphRetriever.get_children() 方法
    
    Args:
        chunk_id: 父分块ID
    """
    print("=" * 60)
    print("测试 GraphRetriever.get_children() 方法")
    print("=" * 60)
    print(f"父Chunk ID: {chunk_id}")
    print()
    
    try:
        # 创建图检索器
        retriever = GraphRetriever()
        
        # 查询子节点
        print("查询子节点...")
        children = retriever.get_children(chunk_id)
        
        print(f"✓ 查询完成")
        print()
        print(f"查询结果:")
        print(f"  - 子节点总数: {len(children)}")
        print()
        
        if children:
            print(f"子节点列表:")
            for i, child in enumerate(children[:10], 1):
                chunk_id = child.get('chunk_id', 'N/A')
                title = child.get('title', 'N/A')
                print(f"  {i}. Chunk ID: {chunk_id}")
                print(f"     标题: {title if title else '(无标题)'}")
            if len(children) > 10:
                print(f"  ... 还有 {len(children) - 10} 个子节点")
        else:
            print(f"  (该chunk没有子节点)")
        
        print()
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python examples/test_graph_children_simple.py <chunk_id>")
        print()
        print("示例:")
        print("  python examples/test_graph_children_simple.py 123e4567-e89b-12d3-a456-426614174000")
        print()
        print("💡 提示: 可以通过以下方式获取chunk_id:")
        print("  1. 查询文档chunks接口: GET /api/v1/document/{document_id}/chunks")
        print("  2. 从数据库查询: SELECT id FROM document_chunks LIMIT 1;")
        sys.exit(1)
    
    chunk_id = sys.argv[1]
    success = test_get_children(chunk_id)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
