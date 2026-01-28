#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通过 Milvus API 删除向量数据库数据
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from pymilvus import connections, utility, MilvusException
except ImportError:
    print("❌ 错误: 未安装 pymilvus")
    print("   请运行: pip install pymilvus")
    sys.exit(1)

from src.common.config import milvus_config


def list_collections():
    """列出所有 Collections"""
    try:
        collections = utility.list_collections()
        return collections
    except MilvusException as e:
        print(f"❌ 列出 Collections 失败: {e}")
        return []


def get_collection_info(collection_name: str):
    """获取 Collection 信息"""
    try:
        from pymilvus import Collection
        collection = Collection(collection_name)
        num_entities = collection.num_entities
        return {
            "name": collection_name,
            "num_entities": num_entities
        }
    except Exception as e:
        print(f"  ⚠️  获取 Collection 信息失败: {e}")
        return None


def drop_collection(collection_name: str):
    """删除 Collection"""
    try:
        utility.drop_collection(collection_name)
        return True
    except MilvusException as e:
        print(f"  ❌ 删除失败: {e}")
        return False


def delete_all_collections(confirm: bool = False):
    """删除所有 Collections"""
    print("=" * 80)
    print("通过 Milvus API 删除向量数据库数据")
    print("=" * 80)
    print()
    
    # 连接 Milvus
    print("1. 连接 Milvus...")
    try:
        connections.connect(
            alias="default",
            host=milvus_config.MILVUS_HOST,
            port=str(milvus_config.MILVUS_PORT),
            user=milvus_config.MILVUS_USER,
            password=milvus_config.MILVUS_PASSWORD
        )
        print(f"✅ 连接成功: {milvus_config.MILVUS_HOST}:{milvus_config.MILVUS_PORT}")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False
    
    print()
    
    # 列出所有 Collections
    print("2. 列出所有 Collections...")
    collections = list_collections()
    
    if not collections:
        print("  没有找到任何 Collection")
        connections.disconnect("default")
        return True
    
    print(f"  找到 {len(collections)} 个 Collections:")
    print()
    
    # 显示每个 Collection 的信息
    collection_info = []
    for col_name in collections:
        info = get_collection_info(col_name)
        if info:
            print(f"  - {col_name}: {info['num_entities']:,} 个向量")
            collection_info.append(info)
        else:
            print(f"  - {col_name}: (无法获取信息)")
            collection_info.append({"name": col_name, "num_entities": 0})
    
    print()
    
    # 确认删除
    if not confirm:
        total_entities = sum(info['num_entities'] for info in collection_info)
        print(f"⚠️  警告：将删除 {len(collections)} 个 Collections，共 {total_entities:,} 个向量")
        print()
        response = input("确认删除所有 Collections? (yes/no): ")
        if response.lower() != 'yes':
            print("取消操作")
            connections.disconnect("default")
            return False
    
    # 删除所有 Collections
    print()
    print("3. 删除 Collections...")
    print("-" * 80)
    
    success_count = 0
    failed_count = 0
    
    for col_name in collections:
        print(f"  正在删除: {col_name}...", end=" ")
        if drop_collection(col_name):
            print("✅")
            success_count += 1
        else:
            print("❌")
            failed_count += 1
    
    print()
    print("-" * 80)
    print(f"删除完成: 成功 {success_count} 个，失败 {failed_count} 个")
    
    # 断开连接
    connections.disconnect("default")
    
    print()
    print("=" * 80)
    print("✅ 操作完成！")
    print("=" * 80)
    
    return success_count > 0


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="通过 Milvus API 删除向量数据库数据")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="自动确认删除（不询问）"
    )
    
    args = parser.parse_args()
    
    try:
        success = delete_all_collections(confirm=args.yes)
        sys.exit(0 if success else 1)
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
