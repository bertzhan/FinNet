# -*- coding: utf-8 -*-
"""
存储路径管理
按照plan.md规范管理数据存储路径
"""

import os
from typing import Optional
from datetime import datetime
from pathlib import Path

try:
    from .base_crawler import Market, DocType
except ImportError:
    from base_crawler import Market, DocType


class StorageManager:
    """
    存储管理器
    按照plan.md的存储路径规范管理文件存储
    """

    def __init__(self, base_path: str):
        """
        Args:
            base_path: 基础路径（对应s3://company-datalake/或本地路径）
        """
        self.base_path = base_path.rstrip('/')

    def get_bronze_path(self, market: Market, doc_type: DocType, 
                       stock_code: str, year: int, quarter: Optional[str] = None,
                       filename: Optional[str] = None) -> str:
        """
        获取Bronze层存储路径
        
        格式：bronze/{market}/{doc_type}/{year}/{quarter}/{stock_code}/{filename}
        
        Args:
            market: 市场类型
            doc_type: 文档类型
            stock_code: 股票代码
            year: 年份
            quarter: 季度（如 "Q1", "Q2", "Q3", "Q4"，可选）
            filename: 文件名（可选）
            
        Returns:
            完整路径
        """
        if quarter is None:
            quarter = "Q4"  # 默认Q4

        path_parts = [
            self.base_path,
            "bronze",
            market.value,
            doc_type.value,
            str(year),
            quarter,
            stock_code
        ]

        if filename:
            path_parts.append(filename)

        return "/".join(path_parts)

    def get_quarantine_path(self, failure_stage: str, filename: Optional[str] = None) -> str:
        """
        获取隔离区路径
        
        格式：quarantine/{failure_stage}/{filename}
        
        Args:
            failure_stage: 失败阶段（ingestion_failed/validation_failed/content_failed）
            filename: 文件名（可选）
            
        Returns:
            完整路径
        """
        path_parts = [
            self.base_path,
            "quarantine",
            failure_stage
        ]

        if filename:
            path_parts.append(filename)

        return "/".join(path_parts)

    def ensure_dir(self, path: str):
        """
        确保目录存在
        
        Args:
            path: 路径
        """
        dir_path = os.path.dirname(path) if os.path.isfile(path) or '.' in os.path.basename(path) else path
        os.makedirs(dir_path, exist_ok=True)

    def move_to_quarantine(self, source_path: str, failure_stage: str, 
                          reason: Optional[str] = None) -> str:
        """
        将文件移动到隔离区
        
        Args:
            source_path: 源文件路径
            failure_stage: 失败阶段
            reason: 失败原因（可选）
            
        Returns:
            目标路径
        """
        filename = os.path.basename(source_path)
        if reason:
            # 在文件名中添加原因标识
            name, ext = os.path.splitext(filename)
            filename = f"{name}_failed_{reason}{ext}"

        target_path = self.get_quarantine_path(failure_stage, filename)
        self.ensure_dir(target_path)

        # 移动文件
        import shutil
        shutil.move(source_path, target_path)

        return target_path

    def get_silver_path(self, doc_type: str, filename: Optional[str] = None) -> str:
        """
        获取Silver层存储路径
        
        格式：silver/{doc_type}/{filename}
        
        Args:
            doc_type: 文档类型（announcements_parsed/entities/text_cleaned）
            filename: 文件名（可选）
            
        Returns:
            完整路径
        """
        path_parts = [
            self.base_path,
            "silver",
            doc_type
        ]

        if filename:
            path_parts.append(filename)

        return "/".join(path_parts)

    def get_gold_path(self, data_type: str, filename: Optional[str] = None) -> str:
        """
        获取Gold层存储路径
        
        格式：gold/{data_type}/{filename}
        
        Args:
            data_type: 数据类型（company_profiles/financial_metrics/knowledge_graph/time_series）
            filename: 文件名（可选）
            
        Returns:
            完整路径
        """
        path_parts = [
            self.base_path,
            "gold",
            data_type
        ]

        if filename:
            path_parts.append(filename)

        return "/".join(path_parts)
