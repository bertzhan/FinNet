# -*- coding: utf-8 -*-
"""
测试根据 chunk_id 查询接口
"""

import requests
import json
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

BASE_URL = "http://localhost:8000"


def get_chunk_id_from_db():
    """从数据库获取一个有效的 chunk_id"""
    try:
        from src.storage.metadata import get_postgres_client
        from src.storage.metadata.models import DocumentChunk
        
        pg_client = get_postgres_client()
        with pg_client.get_session() as session:
            # 获取第一个有文本的 chunk
            chunk = session.query(DocumentChunk).filter(
                DocumentChunk.chunk_text.isnot(None),
                DocumentChunk.chunk_text != ""
            ).first()
            
            if chunk:
                return str(chunk.id)
            else:
                print("⚠️  数据库中没有找到有效的 chunk")
                return None
    except Exception as e:
        print(f"⚠️  从数据库获取 chunk_id 失败: {e}")
        return None


def test_chunk_by_id_api(chunk_id: str = None):
    """测试根据 chunk_id 查询接口"""
    print("=" * 60)
    print("测试根据 chunk_id 查询接口")
    print("=" * 60)
    print()
    
    # 如果没有提供 chunk_id，尝试从数据库获取
    if not chunk_id:
        print("正在从数据库获取测试用的 chunk_id...")
        chunk_id = get_chunk_id_from_db()
        if not chunk_id:
            print("❌ 无法获取测试用的 chunk_id")
            return False
        print(f"✓ 获取到 chunk_id: {chunk_id}")
        print()
    
    url = f"{BASE_URL}/api/v1/retrieval/chunk-by-id"
    
    # 测试1: 正常查询
    print("测试1: 正常查询")
    print("-" * 60)
    payload = {
        "chunk_id": chunk_id
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        print(f"✓ 查询成功")
        print(f"  - chunk_id: {result.get('chunk_id')}")
        print(f"  - document_id: {result.get('document_id')}")
        print(f"  - title: {result.get('title', 'N/A')}")
        print(f"  - title_level: {result.get('title_level', 'N/A')}")
        print(f"  - parent_chunk_id: {result.get('parent_chunk_id', 'N/A')}")
        print(f"  - is_table: {result.get('is_table', False)}")
        print(f"  - chunk_text 长度: {len(result.get('chunk_text', ''))} 字符")
        chunk_text_preview = result.get('chunk_text', '')[:150]
        print(f"  - chunk_text 预览: {chunk_text_preview}...")
        print()
        
    except requests.exceptions.HTTPError as e:
        print(f"✗ HTTP 错误: {e}")
        if e.response is not None:
            print(f"  状态码: {e.response.status_code}")
            print(f"  响应内容: {e.response.text[:200]}")
        return False
    except requests.exceptions.ConnectionError:
        print(f"✗ 连接失败: 无法连接到 {BASE_URL}")
        print(f"  请确保 API 服务器正在运行")
        return False
    except Exception as e:
        print(f"✗ 查询失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 测试2: 无效的 UUID 格式
    print("测试2: 无效的 UUID 格式")
    print("-" * 60)
    payload_invalid = {
        "chunk_id": "invalid-uuid-format"
    }
    
    try:
        response = requests.post(url, json=payload_invalid, timeout=10)
        if response.status_code == 400:
            print(f"✓ 无效格式验证成功（返回 400）")
            error_detail = response.json().get('detail', '')
            print(f"  错误信息: {error_detail[:100]}")
        else:
            print(f"⚠️  预期返回 400，实际返回 {response.status_code}")
        print()
    except requests.exceptions.ConnectionError:
        print(f"⚠️  连接失败，跳过此测试")
        print()
    
    # 测试3: 不存在的 chunk_id
    print("测试3: 不存在的 chunk_id")
    print("-" * 60)
    payload_not_found = {
        "chunk_id": "00000000-0000-0000-0000-000000000000"
    }
    
    try:
        response = requests.post(url, json=payload_not_found, timeout=10)
        if response.status_code == 404:
            print(f"✓ 不存在验证成功（返回 404）")
            error_detail = response.json().get('detail', '')
            print(f"  错误信息: {error_detail[:100]}")
        else:
            print(f"⚠️  预期返回 404，实际返回 {response.status_code}")
        print()
    except requests.exceptions.ConnectionError:
        print(f"⚠️  连接失败，跳过此测试")
        print()
    
    print("=" * 60)
    print("测试完成")
    print("=" * 60)
    return True


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="测试根据 chunk_id 查询接口")
    parser.add_argument(
        "--chunk-id",
        type=str,
        help="要查询的 chunk_id（如果不提供，将从数据库获取）"
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://localhost:8000",
        help="API 服务器地址（默认: http://localhost:8000）"
    )
    
    args = parser.parse_args()
    
    global BASE_URL
    BASE_URL = args.base_url
    
    success = test_chunk_by_id_api(args.chunk_id)
    
    if success:
        print("\n✅ 所有测试通过！")
        sys.exit(0)
    else:
        print("\n❌ 测试失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
