# -*- coding: utf-8 -*-
"""
爬虫配置管理
"""

import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class CrawlerConfig:
    """爬虫配置"""
    # 基础路径
    data_root: str = "/data/finnet"
    
    # 爬虫配置
    workers: int = 6
    old_pdf_dir: Optional[str] = None
    
    # 验证配置
    enable_validation: bool = True
    auto_quarantine: bool = True
    
    # 存储配置
    use_minio: bool = False
    minio_endpoint: Optional[str] = None
    minio_access_key: Optional[str] = None
    minio_secret_key: Optional[str] = None
    minio_bucket: str = "finnet-datalake"
    minio_upload_on_download: bool = True  # 是否在下载时立即上传
    minio_upload_retry: int = 0  # 上传失败重试次数（默认0，仅记录）
    
    @classmethod
    def from_env(cls) -> "CrawlerConfig":
        """
        从环境变量加载配置
        
        环境变量：
        - FINNET_DATA_ROOT: 数据根目录
        - CRAWLER_WORKERS: 并行进程数
        - CRAWLER_OLD_PDF_DIR: 旧PDF目录
        - CRAWLER_ENABLE_VALIDATION: 是否启用验证
        - CRAWLER_AUTO_QUARANTINE: 是否自动隔离失败数据
        - MINIO_ENDPOINT: MinIO端点
        - MINIO_ACCESS_KEY: MinIO访问密钥
        - MINIO_SECRET_KEY: MinIO密钥
        - MINIO_BUCKET: MinIO桶名
        - MINIO_UPLOAD_ON_DOWNLOAD: 是否在下载时立即上传（默认true）
        - MINIO_UPLOAD_RETRY: 上传失败重试次数（默认0）
        """
        return cls(
            data_root=os.getenv("FINNET_DATA_ROOT", "/data/finnet"),
            workers=int(os.getenv("CRAWLER_WORKERS", "6")),
            old_pdf_dir=os.getenv("CRAWLER_OLD_PDF_DIR"),
            enable_validation=os.getenv("CRAWLER_ENABLE_VALIDATION", "true").lower() == "true",
            auto_quarantine=os.getenv("CRAWLER_AUTO_QUARANTINE", "true").lower() == "true",
            use_minio=os.getenv("USE_MINIO", "false").lower() == "true",
            minio_endpoint=os.getenv("MINIO_ENDPOINT"),
            minio_access_key=os.getenv("MINIO_ACCESS_KEY"),
            minio_secret_key=os.getenv("MINIO_SECRET_KEY"),
            minio_bucket=os.getenv("MINIO_BUCKET", "finnet-datalake"),
            minio_upload_on_download=os.getenv("MINIO_UPLOAD_ON_DOWNLOAD", "true").lower() == "true",
            minio_upload_retry=int(os.getenv("MINIO_UPLOAD_RETRY", "0")),
        )


# 全局配置实例
config = CrawlerConfig.from_env()
