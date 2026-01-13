# -*- coding: utf-8 -*-
"""
MinIO对象存储集成
实现文件上传到MinIO的功能
"""

import os
from typing import Optional
from pathlib import Path

try:
    from minio import Minio
    from minio.error import S3Error
    MINIO_AVAILABLE = True
except ImportError:
    MINIO_AVAILABLE = False


class MinIOStorage:
    """
    MinIO对象存储管理器
    实现文件上传、下载、删除等功能
    """

    def __init__(self, endpoint: str, access_key: str, secret_key: str, 
                 bucket: str, secure: bool = False):
        """
        Args:
            endpoint: MinIO端点（如：localhost:9000）
            access_key: 访问密钥
            secret_key: 密钥
            bucket: 桶名
            secure: 是否使用HTTPS（默认False）
        """
        if not MINIO_AVAILABLE:
            raise ImportError(
                "minio库未安装，请运行: pip install minio"
            )
        
        self.endpoint = endpoint.replace("http://", "").replace("https://", "")
        self.bucket = bucket
        self.client = Minio(
            self.endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        
        # 确保桶存在
        self._ensure_bucket()

    def _ensure_bucket(self):
        """确保桶存在，如果不存在则创建"""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                print(f"✅ 创建MinIO桶: {self.bucket}")
            else:
                print(f"✅ MinIO桶已存在: {self.bucket}")
        except S3Error as e:
            print(f"⚠️  检查/创建桶失败: {e}")

    def upload_file(self, local_path: str, object_name: str, 
                   content_type: Optional[str] = None) -> bool:
        """
        上传文件到MinIO
        
        Args:
            local_path: 本地文件路径
            object_name: 对象名称（在MinIO中的路径）
            content_type: 内容类型（如：application/pdf）
            
        Returns:
            是否上传成功
        """
        if not os.path.exists(local_path):
            print(f"❌ 文件不存在: {local_path}")
            return False
        
        try:
            # 自动检测内容类型
            if content_type is None:
                ext = Path(local_path).suffix.lower()
                content_type_map = {
                    '.pdf': 'application/pdf',
                    '.json': 'application/json',
                    '.csv': 'text/csv',
                    '.txt': 'text/plain',
                }
                content_type = content_type_map.get(ext, 'application/octet-stream')
            
            # 上传文件
            self.client.fput_object(
                self.bucket,
                object_name,
                local_path,
                content_type=content_type
            )
            print(f"✅ 上传成功: {object_name}")
            return True
            
        except S3Error as e:
            print(f"❌ 上传失败: {e}")
            return False
        except Exception as e:
            print(f"❌ 上传异常: {e}")
            return False

    def download_file(self, object_name: str, local_path: str) -> bool:
        """
        从MinIO下载文件
        
        Args:
            object_name: 对象名称（在MinIO中的路径）
            local_path: 本地保存路径
            
        Returns:
            是否下载成功
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            self.client.fget_object(self.bucket, object_name, local_path)
            print(f"✅ 下载成功: {object_name} -> {local_path}")
            return True
            
        except S3Error as e:
            print(f"❌ 下载失败: {e}")
            return False
        except Exception as e:
            print(f"❌ 下载异常: {e}")
            return False

    def file_exists(self, object_name: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            object_name: 对象名称
            
        Returns:
            是否存在
        """
        try:
            self.client.stat_object(self.bucket, object_name)
            return True
        except S3Error:
            return False

    def delete_file(self, object_name: str) -> bool:
        """
        删除文件
        
        Args:
            object_name: 对象名称
            
        Returns:
            是否删除成功
        """
        try:
            self.client.remove_object(self.bucket, object_name)
            print(f"✅ 删除成功: {object_name}")
            return True
        except S3Error as e:
            print(f"❌ 删除失败: {e}")
            return False

    def list_files(self, prefix: str = "") -> list:
        """
        列出文件
        
        Args:
            prefix: 前缀过滤
            
        Returns:
            文件列表
        """
        try:
            objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=True)
            return [obj.object_name for obj in objects]
        except S3Error as e:
            print(f"❌ 列出文件失败: {e}")
            return []


def create_minio_storage_from_config(config) -> Optional[MinIOStorage]:
    """
    从配置创建MinIO存储实例
    
    Args:
        config: CrawlerConfig实例
        
    Returns:
        MinIOStorage实例，如果配置未启用则返回None
    """
    if not config.use_minio:
        return None
    
    if not config.minio_endpoint or not config.minio_access_key or not config.minio_secret_key:
        print("⚠️  MinIO配置不完整，跳过MinIO存储")
        return None
    
    try:
        return MinIOStorage(
            endpoint=config.minio_endpoint,
            access_key=config.minio_access_key,
            secret_key=config.minio_secret_key,
            bucket=config.minio_bucket,
            secure=config.minio_endpoint.startswith("https://")
        )
    except Exception as e:
        print(f"⚠️  创建MinIO存储失败: {e}")
        return None
