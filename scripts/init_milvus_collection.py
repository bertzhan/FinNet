# -*- coding: utf-8 -*-
"""
Milvus Collection 初始化脚本
创建 financial_documents Collection（如果不存在）

使用方法:
    python scripts/init_milvus_collection.py
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.storage.vector.milvus_client import get_milvus_client
from src.common.constants import MilvusCollection
from src.common.config import embedding_config
from src.common.logger import get_logger

logger = get_logger(__name__)


def init_milvus_collection():
    """
    初始化 Milvus Collection
    """
    logger.info("开始初始化 Milvus Collection...")
    
    try:
        # 获取 Milvus 客户端
        milvus_client = get_milvus_client()
        
        # 获取向量维度（根据配置的模型）
        dimension = embedding_config.EMBEDDING_DIM
        model_name = embedding_config.EMBEDDING_MODEL
        
        logger.info(f"使用模型: {model_name}, 向量维度: {dimension}")
        
        # Collection 名称
        collection_name = MilvusCollection.DOCUMENTS
        
        # 检查 Collection 是否已存在
        if milvus_client.get_collection(collection_name):
            logger.info(f"Collection 已存在: {collection_name}")
            logger.info("如需重新创建，请先删除现有 Collection")
            return
        
        # 创建 Collection
        logger.info(f"创建 Collection: {collection_name}")
        collection = milvus_client.create_collection(
            collection_name=collection_name,
            dimension=dimension,
            description="金融文档向量集合",
            index_type="IVF_FLAT",
            metric_type="L2",
            nlist=128
        )
        
        logger.info(f"✅ Collection 创建成功: {collection_name}")
        logger.info(f"   向量维度: {dimension}")
        logger.info(f"   索引类型: IVF_FLAT")
        logger.info(f"   距离度量: L2")
        
        # 获取统计信息
        stats = milvus_client.get_collection_stats(collection_name)
        logger.info(f"   Collection 统计: {stats}")
        
    except Exception as e:
        logger.error(f"❌ 初始化失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    init_milvus_collection()
