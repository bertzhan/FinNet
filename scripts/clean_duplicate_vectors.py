#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理 Milvus 中的重复向量
当使用 force_revectorize 时，如果没有删除旧向量，会导致同一个 chunk_id 有多个向量
"""

import sys
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.vector.milvus_client import get_milvus_client
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import DocumentChunk
from src.common.constants import MilvusCollection
from src.common.logger import get_logger

logger = get_logger(__name__)


def get_valid_vector_ids_from_postgres() -> Dict[str, str]:
    """
    从 PostgreSQL 获取所有已向量化的 chunk_id 及其对应的 vector_id
    
    Returns:
        字典 {chunk_id: vector_id}
    """
    logger.info("正在从 PostgreSQL 获取有效的向量映射...")
    
    pg_client = get_postgres_client()
    chunk_to_vector = {}
    
    with pg_client.get_session() as session:
        chunks = session.query(
            DocumentChunk.id,
            DocumentChunk.vector_id
        ).filter(
            DocumentChunk.vector_id.isnot(None)
        ).all()
        
        for chunk in chunks:
            chunk_to_vector[str(chunk.id)] = str(chunk.vector_id)
    
    logger.info(f"从 PostgreSQL 获取到 {len(chunk_to_vector)} 个有效的向量映射")
    return chunk_to_vector


def get_all_vectors_from_milvus(collection_name: str) -> List[dict]:
    """
    从 Milvus 获取所有向量
    
    Args:
        collection_name: Collection 名称
        
    Returns:
        包含 id, chunk_id 的字典列表
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
    
    # 查询所有向量
    all_vectors = []
    batch_size = 1000
    offset = 0
    
    logger.info("开始分批查询向量...")
    
    while True:
        try:
            results = collection.query(
                expr="id >= 0",
                output_fields=["id", "chunk_id"],
                limit=batch_size,
                offset=offset
            )
            
            if not results:
                break
            
            all_vectors.extend(results)
            offset += len(results)
            
            logger.info(f"已查询 {offset} 个向量...")
            
            if len(results) < batch_size:
                break
                
        except Exception as e:
            logger.error(f"查询 Milvus 失败 (offset={offset}): {e}")
            break
    
    logger.info(f"从 Milvus 获取到 {len(all_vectors)} 个向量")
    return all_vectors


def find_duplicate_and_invalid_vectors(
    milvus_vectors: List[dict],
    postgres_mapping: Dict[str, str]
) -> tuple[List[int], Dict[str, List[dict]]]:
    """
    查找重复和无效的向量
    
    Args:
        milvus_vectors: Milvus 中的所有向量
        postgres_mapping: PostgreSQL 中的 chunk_id -> vector_id 映射
        
    Returns:
        (要删除的 milvus_id 列表, 重复向量的分组)
    """
    logger.info("正在分析向量重复情况...")
    
    # 按 chunk_id 分组
    chunk_groups = defaultdict(list)
    for vector in milvus_vectors:
        chunk_id = vector.get("chunk_id")
        milvus_id = vector.get("id")
        chunk_groups[chunk_id].append({
            "milvus_id": milvus_id,
            "chunk_id": chunk_id
        })
    
    # 统计
    total_chunks = len(chunk_groups)
    duplicate_chunks = sum(1 for vectors in chunk_groups.values() if len(vectors) > 1)
    
    logger.info(f"统计:")
    logger.info(f"  Milvus 中的向量总数: {len(milvus_vectors):,}")
    logger.info(f"  唯一的 chunk_id 数量: {total_chunks:,}")
    logger.info(f"  有重复向量的 chunk 数量: {duplicate_chunks:,}")
    
    # 查找需要删除的向量
    to_delete = []
    duplicate_details = {}
    
    for chunk_id, vectors in chunk_groups.items():
        if len(vectors) > 1:
            # 有重复，记录详情
            duplicate_details[chunk_id] = vectors
            
            # 获取 PostgreSQL 中记录的有效 vector_id
            valid_vector_id = postgres_mapping.get(chunk_id)
            
            if valid_vector_id:
                # 保留 PostgreSQL 中记录的 vector_id，删除其他的
                for vector in vectors:
                    if str(vector["milvus_id"]) != valid_vector_id:
                        to_delete.append(vector["milvus_id"])
            else:
                # PostgreSQL 中没有记录，保留最新的（ID 最大的），删除其他的
                sorted_vectors = sorted(vectors, key=lambda x: x["milvus_id"], reverse=True)
                for vector in sorted_vectors[1:]:  # 跳过第一个（最新的）
                    to_delete.append(vector["milvus_id"])
    
    logger.info(f"发现 {len(to_delete)} 个重复向量需要删除")
    
    return to_delete, duplicate_details


def delete_vectors_by_ids(
    collection_name: str,
    milvus_ids: List[int],
    batch_size: int = 100,
    dry_run: bool = True
) -> int:
    """
    根据 Milvus ID 删除向量
    
    Args:
        collection_name: Collection 名称
        milvus_ids: 要删除的 Milvus ID 列表
        batch_size: 批量删除的大小
        dry_run: 是否为试运行
        
    Returns:
        删除的向量数量
    """
    if not milvus_ids:
        logger.info("没有向量需要删除")
        return 0
    
    if dry_run:
        logger.warning("=" * 80)
        logger.warning("🔍 DRY RUN 模式 - 不会实际删除向量")
        logger.warning("=" * 80)
        logger.warning(f"将要删除 {len(milvus_ids)} 个重复向量")
        return 0
    
    logger.warning("=" * 80)
    logger.warning("⚠️  即将删除重复向量！")
    logger.warning("=" * 80)
    logger.warning(f"Collection: {collection_name}")
    logger.warning(f"要删除的向量数量: {len(milvus_ids)}")
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
    for i in range(0, len(milvus_ids), batch_size):
        batch = milvus_ids[i:i + batch_size]
        
        try:
            # 构建删除表达式
            ids_str = ", ".join(str(id) for id in batch)
            expr = f"id in [{ids_str}]"
            
            # 执行删除
            collection.delete(expr)
            collection.flush()
            
            deleted_count += len(batch)
            logger.info(f"已删除 {deleted_count}/{len(milvus_ids)} 个向量")
            
        except Exception as e:
            logger.error(f"删除向量失败 (batch {i//batch_size + 1}): {e}")
    
    logger.info("=" * 80)
    logger.info(f"✓ 成功删除 {deleted_count} 个重复向量")
    logger.info("=" * 80)
    
    return deleted_count


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="清理 Milvus 中的重复向量")
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
    parser.add_argument(
        "--show-details",
        action="store_true",
        help="显示重复向量的详细信息"
    )
    
    args = parser.parse_args()
    
    # 确定是否为试运行
    dry_run = not args.force
    
    try:
        logger.info("=" * 80)
        logger.info("清理 Milvus 重复向量工具")
        logger.info("=" * 80)
        logger.info(f"Collection: {args.collection}")
        logger.info(f"批量大小: {args.batch_size}")
        logger.info(f"模式: {'DRY RUN (试运行)' if dry_run else '实际删除'}")
        logger.info("=" * 80)
        logger.info("")
        
        # 1. 从 PostgreSQL 获取有效的向量映射
        postgres_mapping = get_valid_vector_ids_from_postgres()
        
        # 2. 从 Milvus 获取所有向量
        milvus_vectors = get_all_vectors_from_milvus(args.collection)
        
        if not milvus_vectors:
            logger.warning("Milvus 中没有向量")
            return
        
        # 3. 查找重复和无效的向量
        to_delete, duplicate_details = find_duplicate_and_invalid_vectors(
            milvus_vectors,
            postgres_mapping
        )
        
        # 4. 显示详细信息
        if args.show_details and duplicate_details:
            logger.info("")
            logger.info("=" * 80)
            logger.info(f"重复向量详情（前 20 个）:")
            logger.info("=" * 80)
            
            for i, (chunk_id, vectors) in enumerate(list(duplicate_details.items())[:20], 1):
                valid_vector_id = postgres_mapping.get(chunk_id)
                logger.info(f"\n{i}. Chunk ID: {chunk_id}")
                logger.info(f"   重复数量: {len(vectors)}")
                logger.info(f"   PostgreSQL 记录的 vector_id: {valid_vector_id or '(无)'}")
                logger.info(f"   Milvus 中的向量 IDs:")
                for vector in vectors:
                    milvus_id = vector["milvus_id"]
                    is_valid = str(milvus_id) == valid_vector_id
                    status = "✓ 保留" if is_valid else "✗ 删除"
                    logger.info(f"     - {milvus_id} {status}")
        
        # 5. 统计信息
        logger.info("")
        logger.info("=" * 80)
        logger.info("统计信息:")
        logger.info(f"  Milvus 中的向量总数: {len(milvus_vectors):,}")
        logger.info(f"  PostgreSQL 中已向量化的分块数: {len(postgres_mapping):,}")
        logger.info(f"  重复向量数量: {len(to_delete):,}")
        logger.info(f"  删除后预计向量数: {len(milvus_vectors) - len(to_delete):,}")
        logger.info("=" * 80)
        logger.info("")
        
        # 6. 删除重复向量
        deleted_count = delete_vectors_by_ids(
            collection_name=args.collection,
            milvus_ids=to_delete,
            batch_size=args.batch_size,
            dry_run=dry_run
        )
        
        if dry_run and to_delete:
            logger.info("")
            logger.info("=" * 80)
            logger.info("💡 提示:")
            logger.info("  这是试运行模式，没有实际删除向量")
            logger.info("  要查看详细信息，请运行:")
            logger.info(f"  python {__file__} --dry-run --show-details")
            logger.info("")
            logger.info("  要执行实际删除，请运行:")
            logger.info(f"  python {__file__} --force")
            logger.info("=" * 80)
        elif deleted_count > 0:
            logger.info("")
            logger.info("建议:")
            logger.info("  删除完成后，建议重新检查向量数量:")
            logger.info("  python scripts/check_milvus_direct.sh")
            logger.info("  python scripts/check_vectorized_chunks.py")
        
    except KeyboardInterrupt:
        logger.warning("\n操作已被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
