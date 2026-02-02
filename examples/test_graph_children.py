# -*- coding: utf-8 -*-
"""
图检索子节点查询接口测试
测试 /api/v1/retrieval/graph/children 接口
"""

import requests
import json
import sys
from typing import Optional, List, Dict, Any


BASE_URL = "http://localhost:8000"


def get_document_chunks(document_id: str) -> Optional[List[Dict[str, Any]]]:
    """
    获取文档的所有chunks，用于获取测试用的chunk_id
    
    Args:
        document_id: 文档ID
        
    Returns:
        chunks列表，如果失败返回None
    """
    url = f"{BASE_URL}/api/v1/document/{document_id}/chunks"
    
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            result = response.json()
            return result.get('chunks', [])
        else:
            print(f"  ⚠ 获取文档chunks失败: {response.status_code}")
            return None
    except Exception as e:
        print(f"  ⚠ 获取文档chunks异常: {e}")
        return None


def find_chunk_with_children(chunks: List[Dict[str, Any]]) -> Optional[str]:
    """
    查找一个有子节点的chunk_id
    
    Args:
        chunks: chunks列表
        
    Returns:
        有子节点的chunk_id，如果没有则返回None
    """
    # 构建parent_chunk_id到chunks的映射
    parent_map = {}
    for chunk in chunks:
        parent_id = chunk.get('parent_chunk_id')
        if parent_id:
            if parent_id not in parent_map:
                parent_map[parent_id] = []
            parent_map[parent_id].append(chunk)
    
    # 返回第一个有子节点的chunk_id
    if parent_map:
        return list(parent_map.keys())[0]
    
    return None


def test_graph_children(
    chunk_id: str, 
    recursive: bool = True, 
    max_depth: Optional[int] = None,
    expected_success: bool = True
) -> bool:
    """
    测试图检索子节点查询接口
    
    Args:
        chunk_id: 父分块ID
        recursive: 是否递归查询所有子节点
        max_depth: 最大递归深度（仅在 recursive=True 时有效）
        expected_success: 是否期望成功
        
    Returns:
        是否测试成功
    """
    print(f"\n{'='*60}")
    print(f"测试图检索子节点查询接口")
    print(f"{'='*60}")
    print(f"父Chunk ID: {chunk_id}")
    print(f"递归查询: {recursive}")
    if recursive and max_depth:
        print(f"最大深度: {max_depth}")
    print()
    
    url = f"{BASE_URL}/api/v1/retrieval/graph/children"
    payload = {
        "chunk_id": chunk_id,
        "recursive": recursive
    }
    if max_depth is not None:
        payload["max_depth"] = max_depth
    
    try:
        print("发送请求...")
        response = requests.post(url, json=payload, timeout=30)
        
        # 检查 HTTP 状态码
        if response.status_code == 400:
            print(f"✗ 请求格式错误: {response.status_code}")
            result = response.json()
            print(f"  错误详情: {result.get('detail', 'Unknown error')}")
            return not expected_success  # 如果期望失败，则返回True
        elif response.status_code == 500:
            print(f"✗ 服务器错误: {response.status_code}")
            result = response.json()
            print(f"  错误详情: {result.get('detail', 'Unknown error')}")
            return False
        elif response.status_code != 200:
            print(f"✗ HTTP 错误: {response.status_code}")
            print(f"  响应内容: {response.text[:200]}")
            return False
        
        result = response.json()
        
        # 显示结果
        print(f"✓ 请求成功")
        print()
        metadata = result.get('metadata', {})
        print(f"查询结果:")
        print(f"  - 父Chunk ID: {metadata.get('parent_chunk_id')}")
        print(f"  - 子节点总数: {result.get('total', 0)}")
        print(f"  - 查询耗时: {metadata.get('query_time', 0):.3f}s")
        print(f"  - 递归查询: {metadata.get('recursive', 'N/A')}")
        if metadata.get('max_depth') is not None:
            print(f"  - 最大深度: {metadata.get('max_depth')}")
        print()
        
        children = result.get('children', [])
        if children:
            print(f"子节点列表 (显示前10个):")
            for i, child in enumerate(children[:10], 1):
                chunk_id = child.get('chunk_id', 'N/A')
                title = child.get('title', 'N/A')
                print(f"  {i}. Chunk ID: {chunk_id[:36]}...")
                print(f"     标题: {title if title else '(无标题)'}")
            if len(children) > 10:
                print(f"  ... 还有 {len(children) - 10} 个子节点")
        else:
            print(f"  (该chunk没有子节点)")
        
        print()
        return True
        
    except requests.exceptions.ConnectionError:
        print(f"✗ 连接失败: 无法连接到 {BASE_URL}")
        print(f"  请确保API服务正在运行")
        return False
    except Exception as e:
        print(f"✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("图检索子节点查询接口测试")
    print("=" * 60)
    
    # 检查API服务是否运行
    try:
        health_url = f"{BASE_URL}/health"
        response = requests.get(health_url, timeout=5)
        if response.status_code != 200:
            print(f"✗ API服务健康检查失败: {response.status_code}")
            sys.exit(1)
        print("✓ API服务正在运行")
    except requests.exceptions.ConnectionError:
        print(f"✗ 无法连接到API服务: {BASE_URL}")
        print(f"  请先启动API服务: python -m src.api.main")
        sys.exit(1)
    
    # 测试1: 使用命令行参数提供的chunk_id
    if len(sys.argv) > 1:
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
        
        print(f"\n使用命令行参数:")
        print(f"  - chunk_id: {chunk_id}")
        print(f"  - recursive: {recursive}")
        if max_depth:
            print(f"  - max_depth: {max_depth}")
        
        # 测试递归查询
        print("\n" + "="*60)
        print("测试1: 递归查询所有子节点")
        print("="*60)
        success1 = test_graph_children(chunk_id, recursive=True, max_depth=max_depth)
        
        # 测试直接子节点查询
        print("\n" + "="*60)
        print("测试2: 只查询直接子节点")
        print("="*60)
        success2 = test_graph_children(chunk_id, recursive=False)
        
        # 如果指定了max_depth，测试限制深度的递归查询
        if max_depth:
            print("\n" + "="*60)
            print(f"测试3: 递归查询（限制深度为 {max_depth}）")
            print("="*60)
            success3 = test_graph_children(chunk_id, recursive=True, max_depth=max_depth)
            sys.exit(0 if (success1 and success2 and success3) else 1)
        else:
            sys.exit(0 if (success1 and success2) else 1)
    
    # 测试2: 尝试从文档获取chunk_id
    print("\n尝试从文档获取测试用的chunk_id...")
    
    # 尝试获取一个文档的chunks
    # 这里使用一个示例document_id，实际使用时应该从数据库获取
    test_document_id = None
    
    # 如果提供了document_id作为第二个参数
    if len(sys.argv) > 2:
        test_document_id = sys.argv[2]
    else:
        # 尝试使用一些常见的测试document_id
        # 实际使用时应该从数据库查询
        print("  ⚠ 未提供document_id，尝试使用示例chunk_id...")
        print("  💡 提示: 使用 python examples/test_graph_children.py <chunk_id> [recursive] [max_depth] 直接测试")
        print("  💡 或: python examples/test_graph_children.py <chunk_id> <document_id> 从文档获取chunk_id")
        print("  💡 示例: python examples/test_graph_children.py <chunk_id> true 3  # 递归查询，最大深度3")
        
        # 测试无效chunk_id（边界情况）
        print("\n" + "="*60)
        print("测试边界情况: 无效的chunk_id")
        print("="*60)
        test_graph_children("invalid-chunk-id", expected_success=False)
        
        # 测试不存在的chunk_id
        print("\n" + "="*60)
        print("测试边界情况: 不存在的chunk_id")
        print("="*60)
        test_graph_children("00000000-0000-0000-0000-000000000000", expected_success=True)
        
        sys.exit(0)
    
    # 从文档获取chunks
    chunks = get_document_chunks(test_document_id)
    if not chunks:
        print(f"✗ 无法获取文档chunks，请检查document_id是否正确")
        sys.exit(1)
    
    print(f"✓ 获取到 {len(chunks)} 个chunks")
    
    # 查找有子节点的chunk
    parent_chunk_id = find_chunk_with_children(chunks)
    
    if parent_chunk_id:
        print(f"✓ 找到有子节点的chunk: {parent_chunk_id}")
        # 测试递归查询
        print("\n" + "="*60)
        print("测试1: 递归查询所有子节点")
        print("="*60)
        success1 = test_graph_children(parent_chunk_id, recursive=True)
        
        # 测试直接子节点查询
        print("\n" + "="*60)
        print("测试2: 只查询直接子节点")
        print("="*60)
        success2 = test_graph_children(parent_chunk_id, recursive=False)
        
        sys.exit(0 if (success1 and success2) else 1)
    else:
        print(f"⚠ 未找到有子节点的chunk，使用第一个chunk进行测试...")
        if chunks:
            first_chunk_id = chunks[0].get('chunk_id')
            if first_chunk_id:
                # 测试递归查询
                print("\n" + "="*60)
                print("测试1: 递归查询所有子节点")
                print("="*60)
                success1 = test_graph_children(first_chunk_id, recursive=True)
                
                # 测试直接子节点查询
                print("\n" + "="*60)
                print("测试2: 只查询直接子节点")
                print("="*60)
                success2 = test_graph_children(first_chunk_id, recursive=False)
                
                sys.exit(0 if (success1 and success2) else 1)
        
        print(f"✗ 无法找到有效的chunk_id进行测试")
        sys.exit(1)


if __name__ == "__main__":
    main()
