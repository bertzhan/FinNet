# -*- coding: utf-8 -*-
"""
创建 Elasticsearch 索引
如果索引不存在，则创建它
"""

import sys
from src.storage.elasticsearch import get_elasticsearch_client
from src.common.logger import get_logger

logger = get_logger(__name__)


def create_index_if_not_exists():
    """创建 Elasticsearch 索引（如果不存在）"""
    try:
        es_client = get_elasticsearch_client()
        index_name = "chunks"
        
        # 检查索引是否存在
        full_index_name = f"{es_client.index_prefix}_{index_name}"
        if es_client.client.indices.exists(index=full_index_name):
            logger.info(f"索引已存在: {full_index_name}")
            print(f"✓ 索引已存在: {full_index_name}")
            return True
        
        # 创建索引
        logger.info(f"创建索引: {index_name}")
        print(f"正在创建索引: {full_index_name}...")
        result = es_client.create_index(index_name)
        
        if result:
            logger.info(f"索引创建成功: {full_index_name}")
            print(f"✓ 索引创建成功: {full_index_name}")
            return True
        else:
            logger.error(f"索引创建失败: {full_index_name}")
            print(f"✗ 索引创建失败: {full_index_name}")
            return False
            
    except Exception as e:
        logger.error(f"创建索引时发生错误: {e}", exc_info=True)
        print(f"✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_index_status():
    """检查索引状态"""
    try:
        es_client = get_elasticsearch_client()
        index_name = "chunks"
        full_index_name = f"{es_client.index_prefix}_{index_name}"
        
        # 检查索引是否存在
        exists = es_client.client.indices.exists(index=full_index_name)
        
        if exists:
            # 获取索引统计信息
            stats = es_client.client.indices.stats(index=full_index_name)
            doc_count = stats.get('indices', {}).get(full_index_name, {}).get('total', {}).get('docs', {}).get('count', 0)
            
            print(f"✓ 索引存在: {full_index_name}")
            print(f"  文档数量: {doc_count}")
            
            if doc_count == 0:
                print(f"  ⚠️  索引为空，需要索引数据")
                print(f"  运行以下命令索引数据:")
                print(f"    dagster job execute -j elasticsearch_index_job")
                print(f"  或使用 Python:")
                print(f"    python examples/test_elasticsearch_job_simple.py")
        else:
            print(f"✗ 索引不存在: {full_index_name}")
            print(f"  运行此脚本创建索引:")
            print(f"    python examples/create_elasticsearch_index.py")
        
        return exists
        
    except Exception as e:
        print(f"✗ 检查索引状态时发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="创建或检查 Elasticsearch 索引")
    parser.add_argument(
        "--check",
        action="store_true",
        help="只检查索引状态，不创建"
    )
    
    args = parser.parse_args()
    
    if args.check:
        success = check_index_status()
    else:
        success = create_index_if_not_exists()
        if success:
            print()
            check_index_status()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
