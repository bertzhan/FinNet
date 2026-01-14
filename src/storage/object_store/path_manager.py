# -*- coding: utf-8 -*-
"""
对象存储路径管理器
遵循 plan.md 5.2 存储路径规范，生成 Bronze/Silver/Gold/Application 路径
"""

from pathlib import Path
from typing import Optional

from src.common.constants import Market, DocType, DataLayer, QuarantineReason
from src.common.utils import quarter_to_string


class PathManager:
    """
    路径管理器
    按照 plan.md 5.2 规范生成对象存储路径
    """

    def __init__(self, bucket: str = "finnet-datalake"):
        """
        Args:
            bucket: MinIO 桶名称
        """
        self.bucket = bucket

    def get_bronze_path(
        self,
        market: Market,
        doc_type: DocType,
        stock_code: str,
        year: Optional[int] = None,
        quarter: Optional[int] = None,
        filename: Optional[str] = None
    ) -> str:
        """
        获取 Bronze 层路径（原始数据）

        路径格式：
        - 常规文档：bronze/{market}/{doc_type}/{year}/{quarter}/{stock_code}/{filename}
        - IPO文档：bronze/{market}/{doc_type}/{stock_code}/{filename}

        Args:
            market: 市场类型
            doc_type: 文档类型
            stock_code: 股票代码
            year: 年份（IPO类型不需要）
            quarter: 季度 (1-4)，可选（IPO类型不需要）
            filename: 文件名，可选

        Returns:
            对象存储路径

        Example:
            >>> pm = PathManager()
            >>> pm.get_bronze_path(Market.A_SHARE, DocType.QUARTERLY_REPORT, "000001", 2023, 3, "000001_2023_Q3.pdf")
            'bronze/a_share/quarterly_reports/2023/Q3/000001/000001_2023_Q3.pdf'
            >>> pm.get_bronze_path(Market.A_SHARE, DocType.IPO_PROSPECTUS, "000001", filename="000001_IPO.pdf")
            'bronze/a_share/ipo_prospectus/000001/000001_IPO.pdf'
        """
        # 构建路径组件
        components = [
            DataLayer.BRONZE.value,
            market.value,
            doc_type.value
        ]

        # IPO类型不需要年份和季度
        if doc_type == DocType.IPO_PROSPECTUS:
            # IPO路径：bronze/{market}/{doc_type}/{stock_code}/{filename}
            components.append(stock_code)
        else:
            # 常规文档路径：bronze/{market}/{doc_type}/{year}/{quarter}/{stock_code}/{filename}
            if year is None:
                raise ValueError(f"year is required for doc_type {doc_type}")
            components.append(str(year))

            # 添加季度（如果提供）
            if quarter is not None and quarter != 2 and quarter != 4:
                components.append(quarter_to_string(quarter))

            # 添加股票代码
            components.append(stock_code)

        # 添加文件名（如果提供）
        if filename:
            components.append(filename)

        return "/".join(components)

    def get_silver_path(
        self,
        market: Market,
        doc_type: DocType,
        stock_code: str,
        year: int,
        quarter: Optional[int] = None,
        filename: Optional[str] = None,
        subdir: Optional[str] = None
    ) -> str:
        """
        获取 Silver 层路径（清洗数据）

        路径格式：silver/{subdir}/{market}/{doc_type}/{year}/{quarter}/{stock_code}/{filename}

        Args:
            market: 市场类型
            doc_type: 文档类型
            stock_code: 股票代码
            year: 年份
            quarter: 季度，可选
            filename: 文件名，可选
            subdir: 子目录（如 text_cleaned, entities）

        Returns:
            对象存储路径

        Example:
            >>> pm = PathManager()
            >>> pm.get_silver_path(Market.A_SHARE, DocType.QUARTERLY_REPORT, "000001", 2023, 3,
            ...                    "000001_2023_Q3_parsed.json", "text_cleaned")
            'silver/text_cleaned/a_share/quarterly_reports/2023/Q3/000001/000001_2023_Q3_parsed.json'
        """
        components = [DataLayer.SILVER.value]

        # 添加子目录（如果提供）
        if subdir:
            components.append(subdir)

        components.extend([
            market.value,
            doc_type.value,
            str(year)
        ])

        if quarter is not None:
            components.append(quarter_to_string(quarter))

        components.append(stock_code)

        if filename:
            components.append(filename)

        return "/".join(components)

    def get_gold_path(
        self,
        category: str,
        market: Optional[Market] = None,
        stock_code: Optional[str] = None,
        filename: Optional[str] = None
    ) -> str:
        """
        获取 Gold 层路径（聚合数据）

        路径格式：gold/{category}/{market}/{stock_code}/{filename}

        Args:
            category: 数据类别（company_profiles, financial_metrics, knowledge_graph, time_series）
            market: 市场类型，可选
            stock_code: 股票代码，可选
            filename: 文件名，可选

        Returns:
            对象存储路径

        Example:
            >>> pm = PathManager()
            >>> pm.get_gold_path("company_profiles", Market.A_SHARE, "000001", "profile.json")
            'gold/company_profiles/a_share/000001/profile.json'
        """
        components = [DataLayer.GOLD.value, category]

        if market:
            components.append(market.value)

        if stock_code:
            components.append(stock_code)

        if filename:
            components.append(filename)

        return "/".join(components)

    def get_application_path(
        self,
        app_type: str,
        subdir: Optional[str] = None,
        filename: Optional[str] = None
    ) -> str:
        """
        获取 Application 层路径（AI 应用数据）

        路径格式：application/{app_type}/{subdir}/{filename}

        Args:
            app_type: 应用类型（training_corpus, sft_datasets, rlhf_datasets, vector_store, rag_documents）
            subdir: 子目录，可选
            filename: 文件名，可选

        Returns:
            对象存储路径

        Example:
            >>> pm = PathManager()
            >>> pm.get_application_path("training_corpus", "chinese", "corpus_2023.jsonl")
            'application/training_corpus/chinese/corpus_2023.jsonl'
        """
        components = [DataLayer.APPLICATION.value, app_type]

        if subdir:
            components.append(subdir)

        if filename:
            components.append(filename)

        return "/".join(components)

    def get_quarantine_path(
        self,
        reason: QuarantineReason,
        original_path: str
    ) -> str:
        """
        获取隔离区路径（验证失败数据）

        路径格式：quarantine/{reason}/{original_path}

        Args:
            reason: 隔离原因
            original_path: 原始文件路径

        Returns:
            隔离区路径

        Example:
            >>> pm = PathManager()
            >>> pm.get_quarantine_path(QuarantineReason.VALIDATION_FAILED,
            ...                        "bronze/a_share/quarterly_reports/2023/Q3/000001/test.pdf")
            'quarantine/validation_failed/bronze/a_share/quarterly_reports/2023/Q3/000001/test.pdf'
        """
        return f"{DataLayer.QUARANTINE.value}/{reason.value}/{original_path}"

    def parse_bronze_path(self, path: str) -> dict:
        """
        解析 Bronze 层路径，提取元数据

        Args:
            path: Bronze 层路径

        Returns:
            元数据字典

        Example:
            >>> pm = PathManager()
            >>> pm.parse_bronze_path("bronze/a_share/quarterly_reports/2023/Q3/000001/test.pdf")
            {
                'layer': 'bronze',
                'market': 'a_share',
                'doc_type': 'quarterly_reports',
                'year': 2023,
                'quarter': 3,
                'stock_code': '000001',
                'filename': 'test.pdf'
            }
        """
        parts = path.split("/")

        if len(parts) < 6:
            raise ValueError(f"Invalid Bronze path format: {path}")

        metadata = {
            "layer": parts[0],
            "market": parts[1],
            "doc_type": parts[2],
            "year": int(parts[3])
        }

        # 解析季度
        if parts[4].startswith("Q"):
            metadata["quarter"] = int(parts[4][1:])
            metadata["stock_code"] = parts[5]
            if len(parts) > 6:
                metadata["filename"] = parts[6]
        else:
            # 没有季度信息（如年报）
            metadata["quarter"] = None
            metadata["stock_code"] = parts[4]
            if len(parts) > 5:
                metadata["filename"] = parts[5]

        return metadata
