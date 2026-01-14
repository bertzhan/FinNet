#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
删除 MinIO bucket
用于删除旧的 company-datalake bucket
"""

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common.config import minio_config
from src.common.logger import get_logger

logger = get_logger(__name__)

def delete_bucket(bucket_name: str, force: bool = False):
    """
    删除 MinIO bucket
    
    Args:
        bucket_name: bucket 名称
        force: 是否强制删除（即使 bucket 不为空）
    """
    try:
        from minio import Minio
        from minio.error import S3Error
    except ImportError:
        logger.error("minio 库未安装，请运行: pip install minio")
        return False
    
    # 从配置读取 MinIO 连接信息
    endpoint = minio_config.MINIO_ENDPOINT.replace("http://", "").replace("https://", "")
    access_key = minio_config.MINIO_ACCESS_KEY
    secret_key = minio_config.MINIO_SECRET_KEY
    secure = minio_config.MINIO_SECURE
    
    try:
        # 创建 MinIO 客户端
        client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        
        # 检查 bucket 是否存在
        if not client.bucket_exists(bucket_name):
            logger.warning(f"Bucket '{bucket_name}' 不存在")
            return False
        
        # 如果 force=False，检查 bucket 是否为空
        if not force:
            try:
                objects = list(client.list_objects(bucket_name, recursive=True))
                object_count = sum(1 for _ in objects)
                if object_count > 0:
                    logger.error(f"Bucket '{bucket_name}' 不为空，包含 {object_count} 个对象")
                    logger.info("如果要强制删除（包括所有对象），请使用 --force 参数")
                    return False
            except Exception as e:
                logger.warning(f"检查 bucket 内容时出错: {e}")
        
        # 如果 force=True，先删除所有对象
        if force:
            logger.info(f"强制删除模式：先删除 bucket '{bucket_name}' 中的所有对象...")
            try:
                objects = list(client.list_objects(bucket_name, recursive=True))
                object_count = 0
                for obj in objects:
                    try:
                        client.remove_object(bucket_name, obj.object_name)
                        object_count += 1
                        if object_count % 100 == 0:
                            logger.info(f"已删除 {object_count} 个对象...")
                    except Exception as e:
                        logger.warning(f"删除对象 '{obj.object_name}' 失败: {e}")
                
                logger.info(f"已删除 {object_count} 个对象")
            except Exception as e:
                logger.error(f"删除对象时出错: {e}")
                return False
        
        # 删除 bucket
        logger.info(f"正在删除 bucket '{bucket_name}'...")
        client.remove_bucket(bucket_name)
        logger.info(f"✅ 成功删除 bucket '{bucket_name}'")
        return True
        
    except S3Error as e:
        logger.error(f"删除 bucket 失败: {e}")
        return False
    except Exception as e:
        logger.error(f"操作异常: {e}", exc_info=True)
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="删除 MinIO bucket")
    parser.add_argument(
        "bucket_name",
        nargs="?",
        default="company-datalake",
        help="要删除的 bucket 名称（默认: company-datalake）"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制删除（即使 bucket 不为空，会先删除所有对象）"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="跳过确认提示（谨慎使用）"
    )
    
    args = parser.parse_args()
    
    bucket_name = args.bucket_name
    
    print("=" * 60)
    print("删除 MinIO Bucket")
    print("=" * 60)
    print(f"\nBucket 名称: {bucket_name}")
    print(f"MinIO 端点: {minio_config.MINIO_ENDPOINT}")
    print(f"强制删除: {'是' if args.force else '否'}")
    
    if not args.confirm:
        print("\n⚠️  警告: 此操作将删除 bucket 及其所有内容！")
        if args.force:
            print("⚠️  强制删除模式: 将删除 bucket 中的所有对象！")
        
        response = input(f"\n确认要删除 bucket '{bucket_name}' 吗？(yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("操作已取消")
            return
    
    print("\n开始删除...")
    success = delete_bucket(bucket_name, force=args.force)
    
    if success:
        print("\n✅ 删除成功")
    else:
        print("\n❌ 删除失败，请查看上面的错误信息")
        sys.exit(1)


if __name__ == "__main__":
    main()
