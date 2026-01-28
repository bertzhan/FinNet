#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清空向量数据库（Milvus）和 Elasticsearch 数据库

⚠️ 警告：此操作将删除所有向量数据和搜索索引，不可恢复！
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.vector.milvus_client import MilvusClient, get_milvus_client
from src.storage.elasticsearch.elasticsearch_client import ElasticsearchClient, get_elasticsearch_client
from src.common.logger import get_logger

logger = get_logger(__name__)


def clear_milvus(dry_run: bool = True):
    """
    清空 Milvus 向量数据库
    
    Args:
        dry_run: 如果为 True，只检查不删除；如果为 False，实际删除
    """
    logger.info("=" * 80)
    logger.info("清空 Milvus 向量数据库")
    logger.info("=" * 80)
    logger.info(f"模式: {'[DRY RUN] 只检查，不删除' if dry_run else '[实际删除] 将删除所有 Collection'}")
    logger.info("")
    
    try:
        milvus_client = get_milvus_client()
        
        # 列出所有 Collection
        collections = milvus_client.list_collections()
        
        if not collections:
            logger.info("✅ Milvus 中没有 Collection")
            return
        
        logger.info(f"找到 {len(collections)} 个 Collection:")
        for collection_name in collections:
            # 获取 Collection 统计信息
            try:
                stats = milvus_client.get_collection_stats(collection_name)
                row_count = stats.get('row_count', 0)
                logger.info(f"  - {collection_name}: {row_count} 个向量")
            except Exception as e:
                logger.warning(f"  - {collection_name}: 无法获取统计信息 ({e})")
        
        logger.info("")
        
        if dry_run:
            logger.info("⚠️  DRY RUN 模式：未进行实际删除")
            logger.info("如果要实际删除，请运行:")
            logger.info(f"  python {Path(__file__).name} --delete")
        else:
            logger.info("开始删除 Collection...")
            deleted_count = 0
            failed_count = 0
            
            for collection_name in collections:
                try:
                    success = milvus_client.drop_collection(collection_name)
                    if success:
                        deleted_count += 1
                        logger.info(f"✅ 已删除 Collection: {collection_name}")
                    else:
                        failed_count += 1
                        logger.warning(f"⚠️  删除失败: {collection_name}")
                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ 删除异常: {collection_name}, 错误: {e}", exc_info=True)
            
            logger.info("")
            logger.info("=" * 80)
            logger.info("Milvus 清空完成！")
            logger.info("=" * 80)
            logger.info(f"成功删除: {deleted_count} 个 Collection")
            logger.info(f"删除失败: {failed_count} 个 Collection")
            logger.info(f"总计: {len(collections)} 个 Collection")
            
    except Exception as e:
        logger.error(f"清空 Milvus 失败: {e}", exc_info=True)
        raise


def clear_elasticsearch(dry_run: bool = True):
    """
    清空 Elasticsearch 数据库
    
    Args:
        dry_run: 如果为 True，只检查不删除；如果为 False，实际删除
    """
    logger.info("")
    logger.info("=" * 80)
    logger.info("清空 Elasticsearch 数据库")
    logger.info("=" * 80)
    logger.info(f"模式: {'[DRY RUN] 只检查，不删除' if dry_run else '[实际删除] 将删除所有索引'}")
    logger.info("")
    
    try:
        es_client = get_elasticsearch_client()
        
        # 列出所有索引（包括带前缀的）
        try:
            # 获取所有索引
            all_indices = es_client.client.indices.get(index="*")
            
            # 过滤出用户索引（排除系统索引，以 . 开头的）
            index_prefix = es_client.index_prefix
            user_indices = [
                index_name for index_name in all_indices.keys()
                if not index_name.startswith(".")  # 排除系统索引
            ]
            
            if not user_indices:
                logger.info("✅ Elasticsearch 中没有用户索引")
                return
            
            logger.info(f"找到 {len(user_indices)} 个索引（前缀: {index_prefix}_）:")
            for index_name in user_indices:
                try:
                    # 获取索引统计信息
                    stats = es_client.client.indices.stats(index=index_name)
                    doc_count = stats['indices'][index_name]['total']['docs']['count']
                    size = stats['indices'][index_name]['total']['store']['size_in_bytes']
                    size_mb = size / (1024 * 1024)
                    logger.info(f"  - {index_name}: {doc_count} 个文档, {size_mb:.2f} MB")
                except Exception as e:
                    logger.warning(f"  - {index_name}: 无法获取统计信息 ({e})")
            
            logger.info("")
            
            if dry_run:
                logger.info("⚠️  DRY RUN 模式：未进行实际删除")
                logger.info("如果要实际删除，请运行:")
                logger.info(f"  python {Path(__file__).name} --delete")
            else:
                logger.info("开始删除索引...")
                deleted_count = 0
                failed_count = 0
                
                for index_name in user_indices:
                    try:
                        # 提取不带前缀的索引名
                        if index_name.startswith(f"{index_prefix}_"):
                            short_name = index_name[len(f"{index_prefix}_"):]
                        else:
                            short_name = index_name
                        
                        success = es_client.delete_index(short_name)
                        if success:
                            deleted_count += 1
                            logger.info(f"✅ 已删除索引: {index_name}")
                        else:
                            failed_count += 1
                            logger.warning(f"⚠️  删除失败: {index_name}")
                    except Exception as e:
                        failed_count += 1
                        logger.error(f"❌ 删除异常: {index_name}, 错误: {e}", exc_info=True)
                
                logger.info("")
                logger.info("=" * 80)
                logger.info("Elasticsearch 清空完成！")
                logger.info("=" * 80)
                logger.info(f"成功删除: {deleted_count} 个索引")
                logger.info(f"删除失败: {failed_count} 个索引")
                logger.info(f"总计: {len(user_indices)} 个索引")
                
        except Exception as e:
            logger.error(f"获取索引列表失败: {e}", exc_info=True)
            raise
            
    except Exception as e:
        logger.error(f"清空 Elasticsearch 失败: {e}", exc_info=True)
        raise


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="清空向量数据库（Milvus）和 Elasticsearch 数据库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
⚠️  警告：此操作将删除所有向量数据和搜索索引，不可恢复！

示例:
  # 检查模式（只查看，不删除）
  python scripts/clear_vector_and_search_databases.py
  
  # 实际删除
  python scripts/clear_vector_and_search_databases.py --delete
  
  # 只清空 Milvus
  python scripts/clear_vector_and_search_databases.py --delete --milvus-only
  
  # 只清空 Elasticsearch
  python scripts/clear_vector_and_search_databases.py --delete --elasticsearch-only
        """
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="实际删除（默认只检查不删除）"
    )
    parser.add_argument(
        "--milvus-only",
        action="store_true",
        help="只清空 Milvus，不清空 Elasticsearch"
    )
    parser.add_argument(
        "--elasticsearch-only",
        action="store_true",
        help="只清空 Elasticsearch，不清空 Milvus"
    )
    
    args = parser.parse_args()
    
    if args.milvus_only and args.elasticsearch_only:
        logger.error("❌ 不能同时指定 --milvus-only 和 --elasticsearch-only")
        sys.exit(1)
    
    try:
        dry_run = not args.delete
        
        if not args.elasticsearch_only:
            clear_milvus(dry_run=dry_run)
        
        if not args.milvus_only:
            clear_elasticsearch(dry_run=dry_run)
        
        if dry_run:
            logger.info("")
            logger.info("=" * 80)
            logger.info("检查完成！")
            logger.info("=" * 80)
            logger.info("使用 --delete 参数来实际删除数据")
        else:
            logger.info("")
            logger.info("=" * 80)
            logger.info("✅ 所有操作完成！")
            logger.info("=" * 80)
            
    except Exception as e:
        logger.error(f"\n❌ 执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
