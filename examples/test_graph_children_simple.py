# -*- coding: utf-8 -*-
"""
图检索子节点查询接口简单测试
直接测试 GraphRetriever.get_children() 方法（不依赖API服务）
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.application.rag.graph_retriever import GraphRetriever


def test_get_children(chunk_id: str, recursive: bool = True, max_depth: int = None):
    """
    测试 GraphRetriever.get_children() 方法
    
    Args:
        chunk_id: 父分块ID
        recursive: 是否递归查询所有子节点
        max_depth: 最大递归深度（仅在 recursive=True 时有效）
    """
    print("=" * 60)
    print("测试 GraphRetriever.get_children() 方法")
    print("=" * 60)
    print(f"父Chunk ID: {chunk_id}")
    print(f"递归查询: {recursive}")
    if recursive and max_depth:
        print(f"最大深度: {max_depth}")
    print()
    
    try:
        # 创建图检索器
        retriever = GraphRetriever()
        
        # 查询子节点
        print("查询子节点...")
        children = retriever.get_children(chunk_id, recursive=recursive, max_depth=max_depth)
        
        print(f"✓ 查询完成")
        print()
        print(f"查询结果:")
        print(f"  - 子节点总数: {len(children)}")
        print()
        
        if children:
            print(f"子节点列表 (显示前20个):")
            for i, child in enumerate(children[:20], 1):
                child_chunk_id = child.get('chunk_id', 'N/A')
                title = child.get('title', 'N/A')
                print(f"  {i}. Chunk ID: {child_chunk_id}")
                print(f"     标题: {title if title else '(无标题)'}")
            if len(children) > 20:
                print(f"  ... 还有 {len(children) - 20} 个子节点")
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
        print("用法: python examples/test_graph_children_simple.py <chunk_id> [recursive] [max_depth]")
        print()
        print("示例:")
        print("  # 递归查询所有子节点（默认）")
        print("  python examples/test_graph_children_simple.py 123e4567-e89b-12d3-a456-426614174000")
        print()
        print("  # 只查询直接子节点")
        print("  python examples/test_graph_children_simple.py 123e4567-e89b-12d3-a456-426614174000 false")
        print()
        print("  # 递归查询，限制最大深度为3")
        print("  python examples/test_graph_children_simple.py 123e4567-e89b-12d3-a456-426614174000 true 3")
        print()
        print("💡 提示: 可以通过以下方式获取chunk_id:")
        print("  1. 查询文档chunks接口: GET /api/v1/document/{document_id}/chunks")
        print("  2. 从数据库查询: SELECT id FROM document_chunks LIMIT 1;")
        sys.exit(1)
    
    chunk_id = sys.argv[1]
    recursive = True
    max_depth = None
    
    # 解析可选参数
    if len(sys.argv) > 2:
        recursive_str = sys.argv[2].lower()
        recursive = recursive_str in ['true', '1', 'yes', 'y']
    if len(sys.argv) > 3:
        try:
            max_depth = int(sys.argv[3])
        except ValueError:
            print(f"⚠ 无效的 max_depth 参数: {sys.argv[3]}，将使用默认值")
    
    # 如果指定了参数，只测试一种模式
    if len(sys.argv) > 2:
        success = test_get_children(chunk_id, recursive=recursive, max_depth=max_depth)
        sys.exit(0 if success else 1)
    else:
        # 默认测试所有模式
        print("\n" + "="*60)
        print("测试1: 递归查询所有子节点")
        print("="*60)
        success1 = test_get_children(chunk_id, recursive=True)
        
        print("\n" + "="*60)
        print("测试2: 只查询直接子节点")
        print("="*60)
        success2 = test_get_children(chunk_id, recursive=False)
        
        print("\n" + "="*60)
        print("测试3: 递归查询（限制深度为3）")
        print("="*60)
        success3 = test_get_children(chunk_id, recursive=True, max_depth=3)
        
        sys.exit(0 if (success1 and success2 and success3) else 1)


if __name__ == "__main__":
    main()
