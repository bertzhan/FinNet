#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检测 Milvus 向量数据库中的向量数量
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.vector.milvus_client import get_milvus_client
from src.common.constants import MilvusCollection
from src.common.logger import get_logger

logger = get_logger(__name__)


def check_milvus_vectors():
    """检测 Milvus 中所有 collection 的向量数量"""
    
    try:
        # 获取 Milvus 客户端
        client = get_milvus_client()
        
        # 列出所有 collections
        collections = client.list_collections()
        
        if not collections:
            logger.info("Milvus 中没有任何 collection")
            return
        
        logger.info("=" * 80)
        logger.info("Milvus 向量数据库统计")
        logger.info("=" * 80)
        
        total_vectors = 0
        
        for collection_name in collections:
            # 获取 collection 统计信息
            stats = client.get_collection_stats(collection_name)
            row_count = stats.get('row_count', 0)
            total_vectors += row_count
            
            logger.info(f"\nCollection: {collection_name}")
            logger.info(f"  向量数量: {row_count:,}")
            
            # 获取 collection 详细信息
            collection = client.get_collection(collection_name)
            if collection:
                # 获取 schema 信息
                schema = collection.schema
                logger.info(f"  字段数量: {len(schema.fields)}")
                
                # 找到 embedding 字段的维度
                for field in schema.fields:
                    if field.dtype.name == 'FLOAT_VECTOR':
                        logger.info(f"  向量维度: {field.params.get('dim', 'N/A')}")
                        break
        
        logger.info("\n" + "=" * 80)
        logger.info(f"总向量数量: {total_vectors:,}")
        logger.info("=" * 80)
        
        # 详细检查主要 collection
        main_collection = MilvusCollection.DOCUMENTS
        if main_collection in collections:
            logger.info(f"\n主要 Collection 详细信息: {main_collection}")
            logger.info("=" * 80)
            
            collection = client.get_collection(main_collection)
            if collection:
                # 尝试加载 collection（如果未加载）
                try:
                    collection.load()
                    logger.info("✓ Collection 已加载到内存")
                except Exception as e:
                    logger.warning(f"加载 Collection 失败: {e}")
                
                # 获取索引信息
                try:
                    indexes = collection.indexes
                    if indexes:
                        logger.info("\n索引信息:")
                        for idx in indexes:
                            logger.info(f"  字段: {idx.field_name}")
                            logger.info(f"  索引类型: {idx.params.get('index_type', 'N/A')}")
                            logger.info(f"  度量类型: {idx.params.get('metric_type', 'N/A')}")
                    else:
                        logger.warning("  没有索引")
                except Exception as e:
                    logger.warning(f"获取索引信息失败: {e}")
        
        # 连接信息
        logger.info("\n" + "=" * 80)
        logger.info("Milvus 连接信息:")
        logger.info(f"  主机: {client.host}")
        logger.info(f"  端口: {client.port}")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"检测 Milvus 向量失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    check_milvus_vectors()
