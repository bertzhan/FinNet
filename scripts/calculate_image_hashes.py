#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为 images 表中的记录计算文件哈希值
"""

import sys
import hashlib
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import Image
from src.storage.object_store.minio_client import MinIOClient
from src.common.logger import get_logger

logger = get_logger(__name__)


def calculate_file_hash(data: bytes) -> str:
    """计算文件的 SHA256 哈希值"""
    return hashlib.sha256(data).hexdigest()


def update_image_hashes(limit: int = None):
    """
    更新 images 表中的文件哈希值

    Args:
        limit: 限制处理的记录数量，None 表示处理全部
    """
    logger.info("=" * 80)
    logger.info("开始计算 images 表的文件哈希值")
    logger.info("=" * 80)

    pg_client = get_postgres_client()
    minio_client = MinIOClient()

    with pg_client.get_session() as session:
        # 查询所有没有哈希值的图片记录
        query = session.query(Image).filter(Image.file_hash.is_(None))

        if limit:
            query = query.limit(limit)

        images = query.all()
        total_count = len(images)

        logger.info(f"找到 {total_count} 条需要计算哈希的记录")

        if total_count == 0:
            logger.info("没有需要处理的记录")
            return

        success_count = 0
        failed_count = 0

        for idx, image in enumerate(images, 1):
            try:
                # 从 MinIO 下载文件
                file_data = minio_client.download_file(image.file_path)

                if not file_data:
                    logger.warning(f"[{idx}/{total_count}] 无法下载文件: {image.file_path}")
                    failed_count += 1
                    continue

                # 计算哈希值
                file_hash = calculate_file_hash(file_data)

                # 更新数据库
                image.file_hash = file_hash
                success_count += 1

                if idx % 50 == 0:
                    logger.info(f"进度: {idx}/{total_count} ({idx*100//total_count}%), 成功: {success_count}, 失败: {failed_count}")
                    session.commit()  # 批量提交

            except Exception as e:
                logger.error(f"[{idx}/{total_count}] 处理失败 (image_id={image.id}, file={image.filename}): {e}")
                failed_count += 1
                continue

        # 最后一次提交
        session.commit()

        logger.info("=" * 80)
        logger.info("计算完成")
        logger.info(f"  总计: {total_count}")
        logger.info(f"  成功: {success_count}")
        logger.info(f"  失败: {failed_count}")
        logger.info("=" * 80)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="为 images 表计算文件哈希值")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="限制处理的记录数量（用于测试）"
    )

    args = parser.parse_args()

    update_image_hashes(limit=args.limit)


if __name__ == "__main__":
    main()
