#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理 Milvus 存储空间
提供多种清理选项
"""

import sys
import argparse
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.vector.milvus_client import get_milvus_client
from src.common.constants import MilvusCollection


def list_collections():
    """列出所有 Collections"""
    try:
        client = get_milvus_client()
        collections = client.list_collections()
        
        if not collections:
            print("没有找到任何 Collection")
            return []
        
        print(f"找到 {len(collections)} 个 Collections:")
        for i, col_name in enumerate(collections, 1):
            print(f"  {i}. {col_name}")
        
        return collections
    except Exception as e:
        print(f"❌ 列出 Collections 失败: {e}")
        return []


def get_collection_stats(collection_name: str):
    """获取 Collection 统计信息"""
    try:
        client = get_milvus_client()
        collection = client.get_collection(collection_name)
        if collection is None:
            print(f"  Collection 不存在: {collection_name}")
            return None
        
        # 获取实体数量
        num_entities = collection.num_entities
        print(f"  Collection: {collection_name}")
        print(f"  实体数量: {num_entities:,}")
        
        return {
            "name": collection_name,
            "num_entities": num_entities
        }
    except Exception as e:
        print(f"  ❌ 获取统计信息失败: {e}")
        return None


def drop_collection(collection_name: str, confirm: bool = False):
    """删除 Collection"""
    if not confirm:
        response = input(f"确认删除 Collection '{collection_name}'? (yes/no): ")
        if response.lower() != 'yes':
            print("取消删除")
            return False
    
    try:
        client = get_milvus_client()
        success = client.drop_collection(collection_name)
        if success:
            print(f"✅ Collection '{collection_name}' 已删除")
            return True
        else:
            print(f"❌ 删除 Collection '{collection_name}' 失败")
            return False
    except Exception as e:
        print(f"❌ 删除 Collection 失败: {e}")
        return False


def clean_milvus_storage(args):
    """清理 Milvus 存储"""
    print("=" * 80)
    print("清理 Milvus 存储空间")
    print("=" * 80)
    print()
    
    # 列出所有 Collections
    collections = list_collections()
    if not collections:
        print("\n没有可清理的 Collections")
        return
    
    print()
    
    # 显示统计信息
    if args.stats:
        print("Collection 统计信息:")
        print("-" * 80)
        for col_name in collections:
            get_collection_stats(col_name)
            print()
    
    # 删除指定的 Collection
    if args.drop:
        for col_name in args.drop:
            if col_name in collections:
                drop_collection(col_name, args.yes)
            else:
                print(f"⚠️  Collection '{col_name}' 不存在")
    
    # 交互式删除
    if args.interactive:
        print("\n交互式删除模式:")
        print("-" * 80)
        for col_name in collections:
            if col_name == MilvusCollection.DOCUMENTS and not args.force:
                print(f"\n⚠️  跳过系统 Collection: {col_name} (使用 --force 强制删除)")
                continue
            
            get_collection_stats(col_name)
            drop_collection(col_name, args.yes)
            print()


def main():
    parser = argparse.ArgumentParser(description="清理 Milvus 存储空间")
    parser.add_argument(
        "--stats",
        action="store_true",
        help="显示 Collection 统计信息"
    )
    parser.add_argument(
        "--drop",
        nargs="+",
        metavar="COLLECTION",
        help="删除指定的 Collection(s)"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="交互式删除模式"
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="自动确认删除（不询问）"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="允许删除系统 Collection"
    )
    
    args = parser.parse_args()
    
    # 如果没有指定任何操作，显示帮助
    if not (args.stats or args.drop or args.interactive):
        parser.print_help()
        return
    
    try:
        clean_milvus_storage(args)
    except KeyboardInterrupt:
        print("\n\n操作已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 操作失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
