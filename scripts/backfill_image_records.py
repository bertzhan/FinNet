#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为已解析的文档补充 Image 记录
用于修复没有创建 Image 记录的历史数据
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import ParsedDocument, Image
from src.storage.metadata import crud
from src.storage.object_store.minio_client import MinIOClient
from src.common.logger import get_logger

logger = get_logger(__name__)


def backfill_images_for_parsed_document(parsed_doc_id: int):
    """为指定的 ParsedDocument 补充 Image 记录"""
    logger.info(f"=" * 80)
    logger.info(f"为 ParsedDocument {parsed_doc_id} 补充 Image 记录")
    logger.info(f"=" * 80)

    pg_client = get_postgres_client()
    minio_client = MinIOClient()

    with pg_client.get_session() as session:
        # 获取 ParsedDocument 记录
        parsed_doc = session.query(ParsedDocument).filter(
            ParsedDocument.id == parsed_doc_id
        ).first()

        if not parsed_doc:
            logger.error(f"ParsedDocument 不存在: id={parsed_doc_id}")
            return False

        logger.info(f"ParsedDocument 信息:")
        logger.info(f"  document_id: {parsed_doc.document_id}")
        logger.info(f"  images_count: {parsed_doc.images_count}")
        logger.info(f"  image_folder_path: {parsed_doc.image_folder_path}")

        # 检查是否已有 Image 记录
        existing_images_count = session.query(Image).filter(
            Image.parsed_document_id == parsed_doc_id
        ).count()

        if existing_images_count > 0:
            logger.warning(f"已存在 {existing_images_count} 条 Image 记录，跳过")
            return False

        # 获取 MinIO 中的图片文件列表
        if not parsed_doc.image_folder_path:
            logger.warning("image_folder_path 为空，跳过")
            return False

        try:
            objects = list(minio_client.client.list_objects(
                'finnet-datalake',
                prefix=parsed_doc.image_folder_path
            ))

            image_files = [obj for obj in objects if obj.object_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'))]

            logger.info(f"在 MinIO 中找到 {len(image_files)} 个图片文件")

            if not image_files:
                logger.warning("未找到图片文件")
                return False

            # 创建 Image 记录
            created_count = 0
            for idx, img_obj in enumerate(image_files):
                try:
                    filename = img_obj.object_name.split('/')[-1]
                    file_path = img_obj.object_name
                    file_size = img_obj.size

                    # 创建 Image 记录（基本信息，没有详细元数据）
                    image = crud.create_image(
                        session=session,
                        parsed_document_id=parsed_doc_id,
                        document_id=parsed_doc.document_id,
                        image_index=idx,
                        filename=filename,
                        file_path=file_path,
                        page_number=0,  # 未知页码
                        file_hash=None,  # 后续可以计算
                        bbox=None,
                        description=None,
                        width=None,
                        height=None,
                        file_size=file_size
                    )
                    created_count += 1

                    if (idx + 1) % 50 == 0:
                        logger.info(f"已创建 {created_count}/{len(image_files)} 条记录...")

                except Exception as e:
                    logger.error(f"创建 Image 记录失败 (index={idx}, file={filename}): {e}")
                    continue

            session.commit()
            logger.info(f"✅ 成功创建 {created_count} 条 Image 记录")
            return True

        except Exception as e:
            logger.error(f"补充 Image 记录失败: {e}", exc_info=True)
            session.rollback()
            return False


def main():
    """主函数"""
    logger.info("=" * 80)
    logger.info("开始补充历史 ParsedDocument 的 Image 记录")
    logger.info("=" * 80)

    pg_client = get_postgres_client()

    with pg_client.get_session() as session:
        # 查找所有没有 Image 记录的 ParsedDocument
        parsed_docs = session.query(ParsedDocument).filter(
            ParsedDocument.images_count > 0
        ).all()

        logger.info(f"找到 {len(parsed_docs)} 个 ParsedDocument 记录")

        success_count = 0
        failed_count = 0
        skipped_count = 0

        for parsed_doc in parsed_docs:
            # 检查是否已有 Image 记录
            existing_count = session.query(Image).filter(
                Image.parsed_document_id == parsed_doc.id
            ).count()

            if existing_count > 0:
                logger.info(f"ParsedDocument {parsed_doc.id} 已有 {existing_count} 条 Image 记录，跳过")
                skipped_count += 1
                continue

            logger.info(f"\n处理 ParsedDocument {parsed_doc.id}...")
            result = backfill_images_for_parsed_document(parsed_doc.id)

            if result:
                success_count += 1
            else:
                failed_count += 1

    logger.info("\n" + "=" * 80)
    logger.info("补充完成")
    logger.info(f"  成功: {success_count}")
    logger.info(f"  失败: {failed_count}")
    logger.info(f"  跳过: {skipped_count}")
    logger.info(f"  总计: {success_count + failed_count + skipped_count}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
