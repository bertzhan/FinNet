# -*- coding: utf-8 -*-
"""
MinIO 对象存储客户端
提供文件上传、下载、删除、列举等操作
"""

from pathlib import Path
from typing import Optional, List, Dict, Any, BinaryIO
from datetime import timedelta
import io

from minio import Minio
from minio.error import S3Error

from src.common.config import minio_config
from src.common.logger import get_logger, LoggerMixin
from src.common.utils import ensure_dir


class MinIOClient(LoggerMixin):
    """
    MinIO 客户端封装
    提供对象存储的所有操作
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket: Optional[str] = None,
        secure: Optional[bool] = None
    ):
        """
        初始化 MinIO 客户端

        Args:
            endpoint: MinIO 端点（默认从配置读取）
            access_key: 访问密钥（默认从配置读取）
            secret_key: 密钥（默认从配置读取）
            bucket: 桶名称（默认从配置读取）
            secure: 是否使用 HTTPS（默认从配置读取）
        """
        self.endpoint = endpoint or minio_config.MINIO_ENDPOINT
        self.access_key = access_key or minio_config.MINIO_ACCESS_KEY
        self.secret_key = secret_key or minio_config.MINIO_SECRET_KEY
        self.bucket = bucket or minio_config.MINIO_BUCKET
        self.secure = secure if secure is not None else minio_config.MINIO_SECURE

        # 记录实际使用的 bucket 名称（用于调试）
        self.logger.info(f"MinIOClient 初始化 - 使用的 bucket: '{self.bucket}' (参数: {bucket}, 配置: {minio_config.MINIO_BUCKET})")

        # 移除协议前缀
        self.endpoint = self.endpoint.replace("http://", "").replace("https://", "")

        # 创建 MinIO 客户端
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )

        # 确保桶存在
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """确保桶存在，不存在则创建"""
        try:
            self.logger.info(f"检查 MinIO bucket '{self.bucket}' 是否存在...")
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                self.logger.info(f"✅ 创建 MinIO bucket: {self.bucket}")
            else:
                self.logger.info(f"✅ MinIO bucket '{self.bucket}' 已存在")
        except S3Error as e:
            self.logger.error(f"❌ 检查/创建 bucket '{self.bucket}' 失败: {e}")
            raise

    def upload_file(
        self,
        object_name: str,
        file_path: Optional[str] = None,
        data: Optional[bytes] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        上传文件到 MinIO

        Args:
            object_name: 对象名称（在 MinIO 中的路径）
            file_path: 本地文件路径（与 data 二选一）
            data: 文件数据（与 file_path 二选一）
            content_type: 内容类型（如 application/pdf）
            metadata: 元数据字典

        Returns:
            是否上传成功

        Example:
            >>> client = MinIOClient()
            >>> client.upload_file("bronze/a_share/test.pdf", file_path="/tmp/test.pdf")
            True
        """
        try:
            # 自动检测内容类型
            if content_type is None and file_path:
                ext = Path(file_path).suffix.lower()
                content_type_map = {
                    '.pdf': 'application/pdf',
                    '.json': 'application/json',
                    '.csv': 'text/csv',
                    '.txt': 'text/plain',
                    '.parquet': 'application/parquet',
                }
                content_type = content_type_map.get(ext, 'application/octet-stream')

            # 上传文件
            if file_path:
                # 检查文件是否存在
                file_path_obj = Path(file_path)
                if not file_path_obj.exists():
                    self.logger.error(f"❌ 文件不存在，无法上传: {file_path}")
                    return False
                
                # 检查文件大小
                file_size = file_path_obj.stat().st_size
                if file_size == 0:
                    self.logger.error(f"❌ 文件大小为0，无法上传: {file_path}")
                    return False
                
                self.logger.info(f"开始上传到 MinIO bucket '{self.bucket}': {object_name} ({file_size} bytes)")
                self.client.fput_object(
                    self.bucket,
                    object_name,
                    file_path,
                    content_type=content_type,
                    metadata=metadata
                )
                self.logger.info(f"✅ 上传成功到 bucket '{self.bucket}': {object_name} ({file_size} bytes)")
            elif data:
                # 从字节数据上传
                data_stream = io.BytesIO(data)
                self.client.put_object(
                    self.bucket,
                    object_name,
                    data_stream,
                    length=len(data),
                    content_type=content_type,
                    metadata=metadata
                )
                self.logger.info(f"上传成功: {object_name} ({len(data)} bytes)")
            else:
                raise ValueError("必须提供 file_path 或 data")

            return True

        except S3Error as e:
            self.logger.error(f"上传失败: {object_name}, 错误: {e}")
            return False
        except Exception as e:
            self.logger.error(f"上传异常: {object_name}, 错误: {e}")
            return False

    def download_file(
        self,
        object_name: str,
        file_path: Optional[str] = None
    ) -> Optional[bytes]:
        """
        从 MinIO 下载文件

        Args:
            object_name: 对象名称（在 MinIO 中的路径）
            file_path: 本地保存路径（可选，如不提供则返回字节数据）

        Returns:
            如果提供 file_path 则返回 None，否则返回文件字节数据

        Example:
            >>> client = MinIOClient()
            >>> # 下载到文件
            >>> client.download_file("bronze/a_share/test.pdf", "/tmp/test.pdf")
            >>> # 下载到内存
            >>> data = client.download_file("bronze/a_share/test.pdf")
        """
        try:
            if file_path:
                # 下载到文件
                ensure_dir(Path(file_path).parent)
                self.client.fget_object(self.bucket, object_name, file_path)
                self.logger.info(f"下载成功: {object_name} -> {file_path}")
                return None
            else:
                # 下载到内存
                response = self.client.get_object(self.bucket, object_name)
                data = response.read()
                response.close()
                response.release_conn()
                self.logger.info(f"下载成功: {object_name} ({len(data)} bytes)")
                return data

        except S3Error as e:
            self.logger.error(f"下载失败: {object_name}, 错误: {e}")
            return None
        except Exception as e:
            self.logger.error(f"下载异常: {object_name}, 错误: {e}")
            return None

    def delete_file(self, object_name: str) -> bool:
        """
        删除文件

        Args:
            object_name: 对象名称

        Returns:
            是否删除成功

        Example:
            >>> client = MinIOClient()
            >>> client.delete_file("bronze/a_share/test.pdf")
            True
        """
        try:
            self.client.remove_object(self.bucket, object_name)
            self.logger.info(f"删除成功: {object_name}")
            return True
        except S3Error as e:
            self.logger.error(f"删除失败: {object_name}, 错误: {e}")
            return False

    def file_exists(self, object_name: str) -> bool:
        """
        检查文件是否存在

        Args:
            object_name: 对象名称

        Returns:
            是否存在

        Example:
            >>> client = MinIOClient()
            >>> client.file_exists("bronze/a_share/test.pdf")
            True
        """
        try:
            self.client.stat_object(self.bucket, object_name)
            return True
        except S3Error:
            return False

    def list_files(
        self,
        prefix: str = "",
        recursive: bool = True,
        max_results: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        列出文件

        Args:
            prefix: 前缀过滤（如 bronze/a_share/）
            recursive: 是否递归列出子目录
            max_results: 最大返回数量

        Returns:
            文件列表，每个文件包含 name、size、last_modified 等信息

        Example:
            >>> client = MinIOClient()
            >>> files = client.list_files(prefix="bronze/a_share/", max_results=10)
            >>> for file in files:
            ...     print(file['name'], file['size'])
        """
        try:
            objects = self.client.list_objects(
                self.bucket,
                prefix=prefix,
                recursive=recursive
            )

            files = []
            for obj in objects:
                files.append({
                    'name': obj.object_name,
                    'size': obj.size,
                    'last_modified': obj.last_modified,
                    'etag': obj.etag,
                    'content_type': obj.content_type,
                    'metadata': obj.metadata
                })

                if max_results and len(files) >= max_results:
                    break

            self.logger.debug(f"列出文件: prefix={prefix}, count={len(files)}")
            return files

        except S3Error as e:
            self.logger.error(f"列出文件失败: {e}")
            return []

    def get_file_info(self, object_name: str) -> Optional[Dict[str, Any]]:
        """
        获取文件信息

        Args:
            object_name: 对象名称

        Returns:
            文件信息字典，包含 size、content_type、metadata 等

        Example:
            >>> client = MinIOClient()
            >>> info = client.get_file_info("bronze/a_share/test.pdf")
            >>> print(info['size'], info['content_type'])
        """
        try:
            stat = self.client.stat_object(self.bucket, object_name)
            return {
                'name': object_name,
                'size': stat.size,
                'last_modified': stat.last_modified,
                'etag': stat.etag,
                'content_type': stat.content_type,
                'metadata': stat.metadata
            }
        except S3Error as e:
            self.logger.error(f"获取文件信息失败: {object_name}, 错误: {e}")
            return None

    def get_presigned_url(
        self,
        object_name: str,
        expires: timedelta = timedelta(hours=1)
    ) -> Optional[str]:
        """
        生成预签名 URL（用于临时访问）

        Args:
            object_name: 对象名称
            expires: 过期时间（默认 1 小时）

        Returns:
            预签名 URL

        Example:
            >>> client = MinIOClient()
            >>> url = client.get_presigned_url("bronze/a_share/test.pdf")
            >>> print(url)  # http://localhost:9000/...?X-Amz-Signature=...
        """
        try:
            url = self.client.presigned_get_object(
                self.bucket,
                object_name,
                expires=expires
            )
            self.logger.debug(f"生成预签名 URL: {object_name}")
            return url
        except S3Error as e:
            self.logger.error(f"生成预签名 URL 失败: {object_name}, 错误: {e}")
            return None

    def copy_file(
        self,
        source_object: str,
        dest_object: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        复制文件

        Args:
            source_object: 源对象名称
            dest_object: 目标对象名称
            metadata: 新的元数据（可选）

        Returns:
            是否复制成功

        Example:
            >>> client = MinIOClient()
            >>> client.copy_file(
            ...     "bronze/a_share/test.pdf",
            ...     "quarantine/validation_failed/bronze/a_share/test.pdf"
            ... )
            True
        """
        try:
            from minio.commonconfig import CopySource

            copy_source = CopySource(self.bucket, source_object)

            self.client.copy_object(
                self.bucket,
                dest_object,
                copy_source,
                metadata=metadata
            )
            self.logger.info(f"复制成功: {source_object} -> {dest_object}")
            return True

        except S3Error as e:
            self.logger.error(f"复制失败: {source_object} -> {dest_object}, 错误: {e}")
            return False

    def move_file(
        self,
        source_object: str,
        dest_object: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        移动文件（复制 + 删除原文件）

        Args:
            source_object: 源对象名称
            dest_object: 目标对象名称
            metadata: 新的元数据（可选）

        Returns:
            是否移动成功

        Example:
            >>> client = MinIOClient()
            >>> client.move_file(
            ...     "bronze/a_share/test.pdf",
            ...     "quarantine/validation_failed/bronze/a_share/test.pdf"
            ... )
            True
        """
        # 先复制
        if not self.copy_file(source_object, dest_object, metadata):
            return False

        # 再删除原文件
        if not self.delete_file(source_object):
            self.logger.warning(f"移动文件时删除原文件失败: {source_object}")
            return False

        self.logger.info(f"移动成功: {source_object} -> {dest_object}")
        return True

    def upload_json(
        self,
        object_name: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        上传 JSON 数据

        Args:
            object_name: 对象名称
            data: JSON 数据（字典）
            metadata: 元数据

        Returns:
            是否上传成功

        Example:
            >>> client = MinIOClient()
            >>> client.upload_json("silver/text_cleaned/test.json", {"key": "value"})
            True
        """
        import json

        try:
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            json_bytes = json_str.encode('utf-8')

            return self.upload_file(
                object_name,
                data=json_bytes,
                content_type='application/json',
                metadata=metadata
            )
        except Exception as e:
            self.logger.error(f"上传 JSON 失败: {object_name}, 错误: {e}")
            return False

    def download_json(self, object_name: str) -> Optional[Dict[str, Any]]:
        """
        下载 JSON 数据

        Args:
            object_name: 对象名称

        Returns:
            JSON 数据（字典）

        Example:
            >>> client = MinIOClient()
            >>> data = client.download_json("silver/text_cleaned/test.json")
            >>> print(data['key'])
        """
        import json

        try:
            data = self.download_file(object_name)
            if data is None:
                return None

            return json.loads(data.decode('utf-8'))
        except Exception as e:
            self.logger.error(f"下载 JSON 失败: {object_name}, 错误: {e}")
            return None
