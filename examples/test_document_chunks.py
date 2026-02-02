# -*- coding: utf-8 -*-
"""
文档Chunks查询接口测试
根据document_id获取该文档的所有chunk列表
"""

import requests
import json
import sys
from typing import Optional


BASE_URL = "http://localhost:8000"


def test_document_chunks(document_id: str) -> bool:
    """
    测试文档Chunks查询接口
    
    Args:
        document_id: 文档ID（UUID字符串）
        
    Returns:
        是否测试成功
    """
    print(f"\n{'='*60}")
    print(f"测试文档Chunks查询接口")
    print(f"{'='*60}")
    print(f"文档ID: {document_id}")
    print()
    
    url = f"{BASE_URL}/api/v1/document/{document_id}/chunks"
    
    try:
        print("发送请求...")
        response = requests.get(url, timeout=30)
        
        # 检查 HTTP 状态码
        if response.status_code == 404:
            print(f"✗ 文档不存在: {response.status_code}")
            result = response.json()
            print(f"  错误详情: {result.get('detail', 'Unknown error')}")
            return False
        elif response.status_code == 400:
            print(f"✗ 请求格式错误: {response.status_code}")
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
        print(f"查询结果:")
        print(f"  - 文档ID: {result.get('document_id')}")
        print(f"  - Chunk总数: {result.get('total', 0)}")
        print()
        
        chunks = result.get('chunks', [])
        if chunks:
            print(f"Chunk列表 (显示前10个):")
            for i, chunk in enumerate(chunks[:10], 1):
                chunk_id = chunk.get('chunk_id', 'N/A')
                title = chunk.get('title', 'N/A') or '(无标题)'
                title_level = chunk.get('title_level', 'N/A')
                parent_chunk_id = chunk.get('parent_chunk_id', 'N/A') or '(无父chunk)'
                print(f"  {i}. Chunk ID: {chunk_id}")
                print(f"     标题: {title}")
                print(f"     标题层级: {title_level}")
                print(f"     父Chunk ID: {parent_chunk_id}")
                print()
            
            if len(chunks) > 10:
                print(f"  ... 还有 {len(chunks) - 10} 个chunks未显示")
                print()
            
            # 统计信息
            chunks_with_title = sum(1 for c in chunks if c.get('title'))
            chunks_with_parent = sum(1 for c in chunks if c.get('parent_chunk_id'))
            chunks_with_title_level = sum(1 for c in chunks if c.get('title_level') is not None)
            top_level_chunks = len(chunks) - chunks_with_parent
            
            # 统计title_level分布
            title_levels = {}
            for c in chunks:
                level = c.get('title_level')
                if level is not None:
                    title_levels[level] = title_levels.get(level, 0) + 1
            
            print(f"统计信息:")
            print(f"  - 有标题的chunks: {chunks_with_title}/{len(chunks)}")
            print(f"  - 有标题层级的chunks: {chunks_with_title_level}/{len(chunks)}")
            print(f"  - 有父chunk的chunks: {chunks_with_parent}/{len(chunks)}")
            print(f"  - 顶级chunks: {top_level_chunks}/{len(chunks)}")
            if title_levels:
                print(f"  - 标题层级分布:")
                for level in sorted(title_levels.keys()):
                    print(f"      Level {level}: {title_levels[level]} chunks")
            print()
            
            print(f"  ✅ 成功获取 {len(chunks)} 个chunks")
        else:
            print(f"  ⚠️  该文档没有chunks")
        
        print()
        
        return True
        
    except requests.exceptions.ConnectionError:
        print(f"✗ 连接失败: 无法连接到 API 服务 ({BASE_URL})")
        print(f"  请确保 FinNet API 服务正在运行")
        return False
    except requests.exceptions.Timeout:
        print(f"✗ 请求超时: API 服务响应时间过长")
        return False
    except json.JSONDecodeError as e:
        print(f"✗ JSON 解析失败: {e}")
        print(f"  响应内容: {response.text[:200]}")
        return False
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_document_id_by_query(
    stock_code: str,
    year: int,
    quarter: Optional[int],
    doc_type: str
) -> Optional[str]:
    """
    通过查询接口获取document_id
    
    Args:
        stock_code: 股票代码
        year: 年份
        quarter: 季度（可选）
        doc_type: 文档类型
        
    Returns:
        document_id（如果找到），否则返回None
    """
    url = f"{BASE_URL}/api/v1/document/query"
    payload = {
        "stock_code": stock_code,
        "year": year,
        "doc_type": doc_type
    }
    
    if quarter is not None:
        payload["quarter"] = quarter
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if result.get('found'):
                return result.get('document_id')
    except Exception:
        pass
    
    return None


def test_with_document_query():
    """先通过查询接口获取document_id，然后测试chunks接口"""
    print(f"\n{'='*60}")
    print(f"完整测试流程：查询文档 -> 获取Chunks")
    print(f"{'='*60}")
    
    # 先查询一个文档
    print("\n步骤1: 查询文档ID...")
    document_id = get_document_id_by_query(
        stock_code="000001",
        year=2024,
        quarter=3,
        doc_type="quarterly_reports"
    )
    
    if not document_id:
        print("✗ 未找到测试文档，尝试其他参数...")
        # 尝试年度报告
        document_id = get_document_id_by_query(
            stock_code="000001",
            year=2024,
            quarter=None,
            doc_type="annual_reports"
        )
    
    if not document_id:
        print("✗ 无法找到测试文档，请手动提供document_id")
        return False
    
    print(f"✓ 找到文档ID: {document_id}")
    
    # 测试chunks接口
    print("\n步骤2: 获取文档Chunks...")
    return test_document_chunks(document_id)


def main():
    """主函数"""
    import argparse
    
    global BASE_URL
    
    parser = argparse.ArgumentParser(description="测试文档Chunks查询接口")
    parser.add_argument(
        "--document-id",
        type=str,
        help="文档ID（UUID字符串），如果不提供则先通过查询接口获取"
    )
    parser.add_argument(
        "--stock-code",
        type=str,
        help="股票代码（用于查询document_id）"
    )
    parser.add_argument(
        "--year",
        type=int,
        help="年份（用于查询document_id）"
    )
    parser.add_argument(
        "--quarter",
        type=int,
        help="季度（1-4），用于查询document_id"
    )
    parser.add_argument(
        "--doc-type",
        type=str,
        help="文档类型（用于查询document_id）"
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=BASE_URL,
        help=f"API 基础 URL（默认: {BASE_URL}）"
    )
    
    args = parser.parse_args()
    
    # 更新 BASE_URL
    BASE_URL = args.base_url
    
    # 检查 API 服务是否可访问
    try:
        health_url = f"{BASE_URL}/health"
        response = requests.get(health_url, timeout=5)
        if response.status_code == 200:
            print(f"✓ API 服务可访问: {BASE_URL}")
        else:
            print(f"⚠️  API 服务响应异常: {response.status_code}")
    except Exception as e:
        print(f"✗ 无法连接到 API 服务: {e}")
        print(f"  请确保 FinNet API 服务正在运行")
        sys.exit(1)
    
    # 运行测试
    if args.document_id:
        # 直接使用提供的document_id
        success = test_document_chunks(args.document_id)
    elif args.stock_code and args.year and args.doc_type:
        # 先查询document_id，然后测试chunks
        document_id = get_document_id_by_query(
            stock_code=args.stock_code,
            year=args.year,
            quarter=args.quarter,
            doc_type=args.doc_type
        )
        if document_id:
            success = test_document_chunks(document_id)
        else:
            print(f"✗ 未找到匹配的文档")
            success = False
    else:
        # 默认测试：先查询，再测试chunks
        print("未指定document_id，使用默认参数查询文档...")
        success = test_with_document_query()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
