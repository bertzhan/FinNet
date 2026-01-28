#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通过 API 清空 Milvus 中的所有 Collections
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.vector.milvus_client import get_milvus_client
from src.common.logger import get_logger

logger = get_logger(__name__)


def clear_milvus_collections(dry_run=True):
    """
    清空 Milvus 中的所有 Collections
    
    Args:
        dry_run: 是否为试运行模式
    """
    try:
        logger.info("=" * 80)
        logger.info("清空 Milvus Collections")
        logger.info("=" * 80)
        
        # 获取 Milvus 客户端
        client = get_milvus_client()
        
        # 列出所有 collections
        collections = client.list_collections()
        
        if not collections:
            logger.info("✓ Milvus 中没有任何 Collection，无需清空")
            return True
        
        logger.info(f"\n找到 {len(collections)} 个 Collection(s):")
        for collection_name in collections:
            # 获取统计信息
            stats = client.get_collection_stats(collection_name)
            row_count = stats.get('row_count', 0)
            logger.info(f"  - {collection_name}: {row_count:,} 个向量")
        
        if dry_run:
            logger.warning("\n" + "=" * 80)
            logger.warning("🔍 DRY RUN 模式 - 不会实际删除")
            logger.warning("=" * 80)
            logger.warning(f"将要删除 {len(collections)} 个 Collection(s)")
            logger.warning("=" * 80)
            return False
        
        # 确认删除
        logger.warning("\n" + "=" * 80)
        logger.warning("⚠️  即将删除所有 Collections！")
        logger.warning("=" * 80)
        logger.warning(f"Collection 列表: {collections}")
        logger.warning("=" * 80)
        
        try:
            confirmation = input("\n确认删除所有 Collections？输入 'yes' 继续: ")
            if confirmation.lower() != 'yes':
                logger.info("操作已取消")
                return False
        except Exception:
            logger.error("无法获取用户输入，操作取消")
            return False
        
        # 删除所有 collections
        deleted_count = 0
        failed_count = 0
        
        for collection_name in collections:
            try:
                success = client.drop_collection(collection_name)
                if success:
                    logger.info(f"✓ 已删除: {collection_name}")
                    deleted_count += 1
                else:
                    logger.warning(f"⚠️  删除失败: {collection_name}")
                    failed_count += 1
            except Exception as e:
                logger.error(f"❌ 删除 {collection_name} 失败: {e}")
                failed_count += 1
        
        logger.info("\n" + "=" * 80)
        logger.info("清空完成:")
        logger.info(f"  成功删除: {deleted_count} 个 Collection(s)")
        if failed_count > 0:
            logger.warning(f"  删除失败: {failed_count} 个 Collection(s)")
        logger.info("=" * 80)
        
        return failed_count == 0
        
    except Exception as e:
        logger.error(f"清空 Milvus 失败: {e}", exc_info=True)
        return False


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="通过 API 清空 Milvus Collections")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="试运行模式（不实际删除，默认启用）"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制执行删除（禁用试运行）"
    )
    
    args = parser.parse_args()
    
    # 确定是否为试运行
    dry_run = not args.force
    
    try:
        success = clear_milvus_collections(dry_run=dry_run)
        
        if dry_run:
            logger.info("\n" + "=" * 80)
            logger.info("💡 提示:")
            logger.info("  这是试运行模式，没有实际删除 Collections")
            logger.info("  要执行实际删除，请运行:")
            logger.info("    python scripts/clear_milvus_api.py --force")
            logger.info("=" * 80)
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        logger.warning("\n操作已被用户中断")
        return 1
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
