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
            >>> pm.get_bronze_path(Market.HS, DocType.QUARTERLY_REPORT, "000001", 2023, 3, "000001_2023_Q3.pdf")
            'bronze/hs_stock/quarterly_reports/2023/Q3/000001/000001_2023_Q3.pdf'
            >>> pm.get_bronze_path(Market.HS, DocType.IPO_PROSPECTUS, "000001", filename="000001_IPO.pdf")
            'bronze/hs_stock/ipo_prospectus/000001/000001_IPO.pdf'
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

    def get_us_stock_bronze_path(
        self,
        stock_code: str,
        year: int,
        period: str,
        filename: str = "document.htm"
    ) -> str:
        """
        获取美股 Bronze 层路径（SEC 财报专用格式）

        路径格式：bronze/us_stock/{stock_code}/{year}/{period}/{filename}

        Args:
            stock_code: 股票代码（如 AAPL）
            year: 年份
            period: 报告期，取值 {Q1, Q2, Q3, FY}
                    10-K、20-F、40-F 使用 FY；10-Q 使用 Q1/Q2/Q3
            filename: 文件名（默认 document.htm，图片为 document_image-001.gif 等）

        Returns:
            对象存储路径

        Example:
            >>> pm = PathManager()
            >>> pm.get_us_stock_bronze_path("AAPL", 2025, "FY", "document.htm")
            'bronze/us_stock/AAPL/2025/FY/document.htm'
        """
        return "/".join([
            DataLayer.BRONZE.value,
            Market.US_STOCK.value,
            stock_code,
            str(year),
            period,
            filename
        ])

    def get_hs_bronze_path(
        self,
        stock_code: str,
        year: Optional[int] = None,
        period: Optional[str] = None,
        filename: str = "document.pdf"
    ) -> str:
        """
        获取A股 Bronze 层路径（与US格式一致：stock_code 优先）

        路径格式：
        - 定期报告：bronze/hs_stock/{stock_code}/{year}/{period}/{filename}
        - IPO招股书：bronze/hs_stock/{stock_code}/ipo/{filename}

        Args:
            stock_code: 股票代码
            year: 年份（IPO类型不需要）
            period: 报告期 Q1/Q2/Q3/FY（IPO类型不需要）
            filename: 文件名

        Returns:
            对象存储路径

        Example:
            >>> pm = PathManager()
            >>> pm.get_hs_bronze_path("000001", 2023, "Q3", "document.pdf")
            'bronze/hs_stock/000001/2023/Q3/document.pdf'
            >>> pm.get_hs_bronze_path("000001", period="ipo", filename="000001_IPO.pdf")
            'bronze/hs_stock/000001/ipo/000001_IPO.pdf'
        """
        components = [
            DataLayer.BRONZE.value,
            Market.HS.value,
            stock_code
        ]
        if period == "ipo":
            components.append("ipo")
        elif year is not None and period:
            components.extend([str(year), period])
        components.append(filename)
        return "/".join(components)

    def get_hk_stock_bronze_path(
        self,
        stock_code: str,
        year: int,
        period: str,
        filename: str = "document.pdf"
    ) -> str:
        """
        获取港股 Bronze 层路径（与US格式一致：stock_code 优先）

        路径格式：bronze/hk_stock/{stock_code}/{year}/{period}/{filename}

        Args:
            stock_code: 股票代码（如 00700）
            year: 年份
            period: 报告期 Q1/Q2/Q3/FY
            filename: 文件名（默认 document.pdf）

        Returns:
            对象存储路径

        Example:
            >>> pm = PathManager()
            >>> pm.get_hk_stock_bronze_path("00700", 2023, "FY", "document.pdf")
            'bronze/hk_stock/00700/2023/FY/document.pdf'
        """
        return "/".join([
            DataLayer.BRONZE.value,
            Market.HK_STOCK.value,
            stock_code,
            str(year),
            period,
            filename
        ])

    def get_silver_path(
        self,
        market: Market,
        doc_type: DocType,
        stock_code: str,
        year: Optional[int] = None,
        quarter: Optional[int] = None,
        filename: Optional[str] = None,
        subdir: Optional[str] = None
    ) -> str:
        """
        获取 Silver 层路径（清洗数据）

        三市场与 Bronze 一致：silver/{subdir}/{market}/{stock_code}/{year}/{period}/{filename}
        IPO：silver/{subdir}/{market}/{stock_code}/ipo/{filename}

        Args:
            market: 市场类型
            doc_type: 文档类型
            stock_code: 股票代码
            year: 年份
            quarter: 季度，可选
            filename: 文件名，可选
            subdir: 子目录（如 mineru, text_cleaned）

        Returns:
            对象存储路径
        """
        components = [DataLayer.SILVER.value]
        if subdir:
            components.append(subdir)
        components.append(market.value)

        # 三市场与 Bronze 格式一致：stock_code 优先
        if market in (Market.HS, Market.HK_STOCK, Market.US_STOCK):
            components.append(stock_code)
            if doc_type == DocType.IPO_PROSPECTUS or doc_type == DocType.HK_IPO_PROSPECTUS:
                components.append("ipo")
            else:
                if year is None:
                    raise ValueError(f"year is required for doc_type {doc_type}")
                period = "FY" if (quarter is None or quarter == 4) else f"Q{quarter}"
                components.extend([str(year), period])
            if filename:
                components.append(filename)
        else:
            # 其他市场沿用旧格式
            components.extend([doc_type.value, str(year)])
            if quarter is not None:
                components.append(quarter_to_string(quarter))
            components.append(stock_code)
            if filename:
                components.append(filename)

        return "/".join(components)

    def get_silver_base_path(
        self,
        market: Market,
        doc_type: DocType,
        stock_code: str,
        year: Optional[int] = None,
        quarter: Optional[int] = None,
        subdir: str = "mineru"
    ) -> str:
        """
        获取 Silver 层基础目录路径（用于 mineru 等多文件上传）

        格式与 Bronze 一致：silver/{subdir}/{market}/{stock_code}/{year}/{period}/ 或 .../ipo/
        """
        return self.get_silver_path(
            market=market,
            doc_type=doc_type,
            stock_code=stock_code,
            year=year,
            quarter=quarter,
            subdir=subdir
        )

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
            >>> pm.get_gold_path("company_profiles", Market.HS, "000001", "profile.json")
            'gold/company_profiles/hs_stock/000001/profile.json'
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
            ...                        "bronze/hs_stock/quarterly_reports/2023/Q3/000001/test.pdf")
            'quarantine/validation_failed/bronze/hs_stock/quarterly_reports/2023/Q3/000001/test.pdf'
        """
        return f"{DataLayer.QUARANTINE.value}/{reason.value}/{original_path}"

    def get_silver_structure_path(
        self,
        market: Optional[Market] = None,
        doc_type: Optional[DocType] = None,
        stock_code: Optional[str] = None,
        year: Optional[int] = None,
        quarter: Optional[int] = None,
        base_filename: Optional[str] = None,
        markdown_path: Optional[str] = None
    ) -> str:
        """
        生成 structure.json 文件的 Silver 层路径
        
        路径格式（基于 markdown_path）：
        - 从 markdown_path 提取目录，生成 structure.json 路径
        - 例如: silver/mineru/hs_stock/300542/2023/FY/document.md
        - -> silver/mineru/hs_stock/300542/2023/FY/structure.json
        
        如果提供 markdown_path，则优先使用（推荐方式）
        否则使用传统的参数方式（向后兼容）
        
        Args:
            market: 市场类型（markdown_path 未提供时必需）
            doc_type: 文档类型（markdown_path 未提供时必需）
            stock_code: 股票代码（markdown_path 未提供时必需）
            year: 年份（markdown_path 未提供时可能需要）
            quarter: 季度（markdown_path 未提供时可选）
            base_filename: 基础文件名（markdown_path 未提供时可选）
            markdown_path: Markdown 文件路径（推荐使用）
            
        Returns:
            structure.json 文件路径
        """
        # 优先使用 markdown_path（新方式）
        if markdown_path:
            # 从 markdown_path 提取目录，生成 structure.json 路径
            markdown_dir = "/".join(markdown_path.split("/")[:-1])  # 去掉文件名，保留目录
            return f"{markdown_dir}/structure.json"
        
        # 向后兼容：使用传统参数方式
        if market is None or doc_type is None or stock_code is None:
            raise ValueError("market, doc_type, stock_code are required when markdown_path is not provided")
        if base_filename is None:
            if doc_type in (DocType.IPO_PROSPECTUS, DocType.HK_IPO_PROSPECTUS):
                base_filename = f"{stock_code}_IPO"
            elif quarter is not None:
                base_filename = f"{stock_code}_{year}_Q{quarter}"
            else:
                base_filename = f"{stock_code}_{year}"
        
        filename = f"{base_filename}_structure.json"
        if year is None and doc_type not in (DocType.IPO_PROSPECTUS, DocType.HK_IPO_PROSPECTUS):
            raise ValueError(f"year is required for doc_type {doc_type}")
        return self.get_silver_path(
            market=market,
            doc_type=doc_type,
            stock_code=stock_code,
            year=year,
            quarter=quarter,
            filename=filename,
            subdir="text_cleaned"
        )
    
    def get_silver_chunks_path(
        self,
        market: Optional[Market] = None,
        doc_type: Optional[DocType] = None,
        stock_code: Optional[str] = None,
        year: Optional[int] = None,
        quarter: Optional[int] = None,
        base_filename: Optional[str] = None,
        markdown_path: Optional[str] = None
    ) -> str:
        """
        生成 chunks.json 文件的 Silver 层路径
        
        路径格式（基于 markdown_path）：
        - 从 markdown_path 提取目录，生成 chunks.json 路径
        - 例如: silver/mineru/hs_stock/300542/2023/FY/document.md
        - -> silver/mineru/hs_stock/300542/2023/FY/chunks.json
        
        如果提供 markdown_path，则优先使用（推荐方式）
        否则使用传统的参数方式（向后兼容）
        
        Args:
            market: 市场类型（markdown_path 未提供时必需）
            doc_type: 文档类型（markdown_path 未提供时必需）
            stock_code: 股票代码（markdown_path 未提供时必需）
            year: 年份（markdown_path 未提供时可能需要）
            quarter: 季度（markdown_path 未提供时可选）
            base_filename: 基础文件名（markdown_path 未提供时可选）
            markdown_path: Markdown 文件路径（推荐使用）
            
        Returns:
            chunks.json 文件路径
        """
        # 优先使用 markdown_path（新方式）
        if markdown_path:
            # 从 markdown_path 提取目录，生成 chunks.json 路径
            markdown_dir = "/".join(markdown_path.split("/")[:-1])  # 去掉文件名，保留目录
            return f"{markdown_dir}/chunks.json"
        
        # 向后兼容：使用传统参数方式
        if market is None or doc_type is None or stock_code is None:
            raise ValueError("market, doc_type, stock_code are required when markdown_path is not provided")
        if base_filename is None:
            if doc_type in (DocType.IPO_PROSPECTUS, DocType.HK_IPO_PROSPECTUS):
                base_filename = f"{stock_code}_IPO"
            elif quarter is not None:
                base_filename = f"{stock_code}_{year}_Q{quarter}"
            else:
                base_filename = f"{stock_code}_{year}"
        
        filename = f"{base_filename}_chunks.json"
        if year is None and doc_type not in (DocType.IPO_PROSPECTUS, DocType.HK_IPO_PROSPECTUS):
            raise ValueError(f"year is required for doc_type {doc_type}")
        return self.get_silver_path(
            market=market,
            doc_type=doc_type,
            stock_code=stock_code,
            year=year,
            quarter=quarter,
            filename=filename,
            subdir="text_cleaned"
        )

    def parse_bronze_path(self, path: str) -> dict:
        """
        解析 Bronze 层路径，提取元数据

        支持格式：
        - 旧A股：bronze/hs_stock/{doc_type}/{year}/{quarter}/{stock_code}/{filename}
        - 新A股/US：bronze/{market}/{stock_code}/{year}/{period}/{filename}
        - A股IPO：bronze/hs_stock/{stock_code}/ipo/{filename}

        Args:
            path: Bronze 层路径

        Returns:
            元数据字典
        """
        parts = path.split("/")

        if len(parts) < 5:
            raise ValueError(f"Invalid Bronze path format: {path}")

        metadata = {"layer": parts[0], "market": parts[1]}

        # 新格式：bronze/{market}/{stock_code}/{year}/{period}/{filename} 或 bronze/{market}/{stock_code}/ipo/{filename}
        doc_types = ("quarterly_reports", "interim_reports", "annual_reports", "ipo_prospectus")
        if parts[1] in ("hs_stock", "us_stock", "hk_stock") and parts[2] not in doc_types:
            metadata["stock_code"] = parts[2]
            if len(parts) >= 4 and parts[3] == "ipo":
                metadata["doc_type"] = "ipo_prospectus"
                metadata["year"] = None
                metadata["quarter"] = None
                metadata["filename"] = parts[4] if len(parts) > 4 else None
            elif len(parts) >= 6 and parts[3].isdigit():
                metadata["year"] = int(parts[3])
                period = parts[4]
                metadata["quarter"] = int(period[1:]) if period.startswith("Q") else (4 if period == "FY" else None)
                metadata["doc_type"] = "interim_reports" if metadata["quarter"] == 2 else (
                    "annual_reports" if period == "FY" else "quarterly_reports"
                )
                metadata["filename"] = parts[5] if len(parts) > 5 else None
            else:
                raise ValueError(f"Invalid Bronze path format: {path}")
        else:
            # 旧格式：bronze/{market}/{doc_type}/{year}/{quarter}/{stock_code}/{filename}
            metadata["doc_type"] = parts[2]
            metadata["year"] = int(parts[3])
            if parts[4].startswith("Q"):
                metadata["quarter"] = int(parts[4][1:])
                metadata["stock_code"] = parts[5]
                metadata["filename"] = parts[6] if len(parts) > 6 else None
            else:
                metadata["quarter"] = None
                metadata["stock_code"] = parts[4]
                metadata["filename"] = parts[5] if len(parts) > 5 else None

        return metadata
