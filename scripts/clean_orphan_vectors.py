#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理 Milvus 中的孤立向量
孤立向量是指：在 Milvus 中存在，但在 PostgreSQL 元数据中没有对应记录的向量
"""

import sys
from pathlib import Path
from typing import Set, List
import uuid

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.vector.milvus_client import get_milvus_client
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import DocumentChunk
from src.common.constants import MilvusCollection
from src.common.logger import get_logger

logger = get_logger(__name__)


def get_all_chunk_ids_from_postgres() -> Set[str]:
    """
    从 PostgreSQL 获取所有已向量化的 chunk_id
    
    Returns:
        chunk_id 的集合
    """
    logger.info("正在从 PostgreSQL 获取所有已向量化的 chunk_id...")
    
    pg_client = get_postgres_client()
    chunk_ids = set()
    
    with pg_client.get_session() as session:
        # 查询所有有 vectorized_at 的分块（表示已向量化）
        chunks = session.query(DocumentChunk.id).filter(
            DocumentChunk.vectorized_at.isnot(None)
        ).all()
        
        for chunk in chunks:
            chunk_ids.add(str(chunk.id))
    
    logger.info(f"从 PostgreSQL 获取到 {len(chunk_ids)} 个已向量化的 chunk_id")
    return chunk_ids


def get_all_chunk_ids_from_milvus(collection_name: str) -> List[dict]:
    """
    从 Milvus 获取所有向量的 chunk_id
    
    Args:
        collection_name: Collection 名称
        
    Returns:
        包含 chunk_id 的字典列表
    """
    logger.info(f"正在从 Milvus Collection '{collection_name}' 获取所有向量...")
    
    milvus_client = get_milvus_client()
    collection = milvus_client.get_collection(collection_name)
    
    if not collection:
        logger.error(f"Collection 不存在: {collection_name}")
        return []
    
    # 加载 collection
    try:
        collection.load()
    except Exception as e:
        logger.warning(f"加载 Collection 失败: {e}")
    
    # 查询所有向量的 chunk_id
    # 使用分页查询，避免一次性加载过多数据
    all_vectors = []
    batch_size = 1000
    offset = 0
    
    logger.info("开始分批查询向量...")
    
    while True:
        try:
            # 使用 query 获取所有数据
            # chunk_id 是 VARCHAR 主键，使用 chunk_id != "" 查询所有非空记录
            results = collection.query(
                expr='chunk_id != ""',  # 查询所有记录（主键非空）
                output_fields=["chunk_id"],
                limit=batch_size,
                offset=offset
            )
            
            if not results:
                break
            
            all_vectors.extend(results)
            offset += len(results)
            
            logger.info(f"已查询 {offset} 个向量...")
            
            # 如果返回的记录数少于 batch_size，说明已经到末尾
            if len(results) < batch_size:
                break
                
        except Exception as e:
            logger.error(f"查询 Milvus 失败 (offset={offset}): {e}")
            break
    
    logger.info(f"从 Milvus 获取到 {len(all_vectors)} 个向量")
    return all_vectors


def find_orphan_vectors(
    milvus_vectors: List[dict],
    postgres_chunk_ids: Set[str]
) -> List[str]:
    """
    查找孤立的向量（在 Milvus 中但不在 PostgreSQL 中）
    
    Args:
        milvus_vectors: Milvus 中的向量列表
        postgres_chunk_ids: PostgreSQL 中的 chunk_id 集合
        
    Returns:
        孤立向量的 chunk_id 列表（Milvus 主键）
    """
    logger.info("正在查找孤立向量...")
    
    orphan_chunk_ids = []
    
    for vector in milvus_vectors:
        chunk_id = vector.get("chunk_id")
        
        if chunk_id not in postgres_chunk_ids:
            orphan_chunk_ids.append(chunk_id)
    
    logger.info(f"发现 {len(orphan_chunk_ids)} 个孤立向量")
    
    if orphan_chunk_ids:
        logger.info("孤立向量示例（前10个）:")
        for i, chunk_id in enumerate(orphan_chunk_ids[:10], 1):
            logger.info(f"  {i}. Chunk ID: {chunk_id}")
    
    return orphan_chunk_ids


def delete_orphan_vectors(
    collection_name: str,
    orphan_chunk_ids: List[str],
    batch_size: int = 100,
    dry_run: bool = True
) -> int:
    """
    删除孤立向量
    
    Args:
        collection_name: Collection 名称
        orphan_chunk_ids: 要删除的 chunk_id 列表（Milvus 主键）
        batch_size: 批量删除的大小
        dry_run: 是否为试运行（不实际删除）
        
    Returns:
        删除的向量数量
    """
    if not orphan_chunk_ids:
        logger.info("没有孤立向量需要删除")
        return 0
    
    if dry_run:
        logger.warning("=" * 80)
        logger.warning("🔍 DRY RUN 模式 - 不会实际删除向量")
        logger.warning("=" * 80)
        logger.warning(f"将要删除 {len(orphan_chunk_ids)} 个孤立向量")
        return 0
    
    logger.warning("=" * 80)
    logger.warning("⚠️  即将删除孤立向量！")
    logger.warning("=" * 80)
    logger.warning(f"Collection: {collection_name}")
    logger.warning(f"要删除的向量数量: {len(orphan_chunk_ids)}")
    logger.warning("=" * 80)
    
    # 确认删除
    try:
        confirmation = input("确认删除？输入 'yes' 继续: ")
        if confirmation.lower() != 'yes':
            logger.info("操作已取消")
            return 0
    except Exception:
        logger.error("无法获取用户输入，操作取消")
        return 0
    
    milvus_client = get_milvus_client()
    collection = milvus_client.get_collection(collection_name)
    
    if not collection:
        logger.error(f"Collection 不存在: {collection_name}")
        return 0
    
    deleted_count = 0
    
    # 分批删除
    for i in range(0, len(orphan_chunk_ids), batch_size):
        batch = orphan_chunk_ids[i:i + batch_size]
        
        try:
            # 构建删除表达式
            # 格式: chunk_id in ["uuid1", "uuid2", ...]
            ids_str = ", ".join(f'"{chunk_id}"' for chunk_id in batch)
            expr = f"chunk_id in [{ids_str}]"
            
            # 执行删除
            collection.delete(expr)
            collection.flush()
            
            deleted_count += len(batch)
            logger.info(f"已删除 {deleted_count}/{len(orphan_chunk_ids)} 个向量")
            
        except Exception as e:
            logger.error(f"删除向量失败 (batch {i//batch_size + 1}): {e}")
    
    logger.info("=" * 80)
    logger.info(f"✓ 成功删除 {deleted_count} 个孤立向量")
    logger.info("=" * 80)
    
    return deleted_count


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="清理 Milvus 中的孤立向量")
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
    parser.add_argument(
        "--collection",
        default=MilvusCollection.DOCUMENTS,
        help=f"Collection 名称（默认: {MilvusCollection.DOCUMENTS}）"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="批量删除的大小（默认: 100）"
    )
    
    args = parser.parse_args()
    
    # 确定是否为试运行
    dry_run = not args.force
    
    try:
        logger.info("=" * 80)
        logger.info("清理 Milvus 孤立向量工具")
        logger.info("=" * 80)
        logger.info(f"Collection: {args.collection}")
        logger.info(f"批量大小: {args.batch_size}")
        logger.info(f"模式: {'DRY RUN (试运行)' if dry_run else '实际删除'}")
        logger.info("=" * 80)
        logger.info("")
        
        # 1. 从 PostgreSQL 获取所有已向量化的 chunk_id
        postgres_chunk_ids = get_all_chunk_ids_from_postgres()
        
        # 2. 从 Milvus 获取所有向量
        milvus_vectors = get_all_chunk_ids_from_milvus(args.collection)
        
        if not milvus_vectors:
            logger.warning("Milvus 中没有向量，无需清理")
            return
        
        # 3. 查找孤立向量
        orphan_chunk_ids = find_orphan_vectors(milvus_vectors, postgres_chunk_ids)
        
        # 4. 统计信息
        logger.info("")
        logger.info("=" * 80)
        logger.info("统计信息:")
        logger.info(f"  PostgreSQL 中已向量化的分块数: {len(postgres_chunk_ids):,}")
        logger.info(f"  Milvus 中的向量总数: {len(milvus_vectors):,}")
        logger.info(f"  孤立向量数量: {len(orphan_chunk_ids):,} ({len(orphan_chunk_ids)/len(milvus_vectors)*100:.1f}%)")
        logger.info("=" * 80)
        logger.info("")
        
        # 5. 删除孤立向量
        deleted_count = delete_orphan_vectors(
            collection_name=args.collection,
            orphan_chunk_ids=orphan_chunk_ids,
            batch_size=args.batch_size,
            dry_run=dry_run
        )
        
        if dry_run and orphan_chunk_ids:
            logger.info("")
            logger.info("=" * 80)
            logger.info("💡 提示:")
            logger.info("  这是试运行模式，没有实际删除向量")
            logger.info("  要执行实际删除，请运行:")
            logger.info(f"  python {__file__} --force")
            logger.info("=" * 80)
        
    except KeyboardInterrupt:
        logger.warning("\n操作已被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
