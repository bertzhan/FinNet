#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重建 Milvus Collection 脚本
解决向量维度不匹配问题

⚠️  警告：此操作将删除所有现有向量数据！
需要重新运行向量化作业来重新填充数据。

使用方法:
    python scripts/recreate_milvus_collection.py
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pymilvus import utility, connections
from src.storage.vector.milvus_client import get_milvus_client
from src.common.constants import MilvusCollection
from src.common.logger import get_logger

logger = get_logger(__name__)


def recreate_milvus_collection():
    """
    重建 Milvus Collection（使用正确的向量维度）
    """
    logger.info("=" * 80)
    logger.info("重建 Milvus Collection")
    logger.info("=" * 80)
    
    # 获取 Milvus 客户端
    milvus_client = get_milvus_client()
    
    collection_name = MilvusCollection.DOCUMENTS
    
    # 获取 API 返回的实际向量维度
    logger.info("检测 API 返回的向量维度...")
    try:
        from src.processing.ai.embedding.embedder_factory import get_embedder_by_mode
        embedder = get_embedder_by_mode()
        actual_dim = embedder.get_model_dim()
        logger.info(f"API 返回的向量维度: {actual_dim}")
    except Exception as e:
        logger.error(f"无法获取向量维度: {e}")
        return False
    
    # 检查现有 Collection
    existing_collection = milvus_client.get_collection(collection_name)
    if existing_collection:
        # 获取现有维度
        schema = existing_collection.schema
        current_dim = None
        for field in schema.fields:
            if field.name == "embedding":
                current_dim = field.params.get('dim')
                break
        
        logger.info(f"现有 Collection 维度: {current_dim}")
        
        if current_dim == actual_dim:
            logger.info(f"✅ 维度已匹配 ({actual_dim})，无需重建")
            return True
        
        # 获取现有数据量
        existing_collection.flush()
        entity_count = existing_collection.num_entities
        logger.warning(f"⚠️  现有 Collection 包含 {entity_count} 条向量数据")
        logger.warning(f"⚠️  维度不匹配: 现有={current_dim}, 需要={actual_dim}")
        
        # 确认删除
        confirm = input(f"\n确认删除现有 Collection 并重建？(yes/no): ").strip().lower()
        if confirm != 'yes':
            logger.info("操作已取消")
            return False
        
        # 删除现有 Collection
        logger.info(f"删除现有 Collection: {collection_name}...")
        utility.drop_collection(collection_name)
        logger.info(f"✅ Collection 已删除")
    
    # 创建新 Collection
    logger.info(f"\n创建新 Collection: {collection_name}")
    logger.info(f"  向量维度: {actual_dim}")
    logger.info(f"  索引类型: IVF_FLAT")
    logger.info(f"  距离度量: L2")
    
    try:
        collection = milvus_client.create_collection(
            collection_name=collection_name,
            dimension=actual_dim,
            description="金融文档向量集合",
            index_type="IVF_FLAT",
            metric_type="L2",
            nlist=128
        )
        logger.info(f"✅ Collection 创建成功")
    except Exception as e:
        logger.error(f"创建 Collection 失败: {e}")
        return False
    
    # 验证新 Collection
    new_collection = milvus_client.get_collection(collection_name)
    if new_collection:
        schema = new_collection.schema
        for field in schema.fields:
            if field.name == "embedding":
                new_dim = field.params.get('dim')
                logger.info(f"验证: 新 Collection 维度 = {new_dim}")
                if new_dim == actual_dim:
                    logger.info("✅ 维度匹配，重建成功！")
                else:
                    logger.error(f"❌ 维度仍不匹配: {new_dim} != {actual_dim}")
                    return False
                break
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("下一步: 运行向量化作业重新生成向量数据")
    logger.info("  命令: dagster job launch -j vectorize_documents_job")
    logger.info("=" * 80)
    
    return True


def main():
    """主函数"""
    success = recreate_milvus_collection()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
