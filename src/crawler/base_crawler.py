# -*- coding: utf-8 -*-
"""
爬虫基类接口
定义统一的爬虫接口，支持A股、港股、美股三大市场
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from enum import Enum
from dataclasses import dataclass


class Market(Enum):
    """市场类型枚举"""
    A_SHARE = "zh_stock"  # A股（中文股票市场）
    HK_STOCK = "hk_stock"  # 港股
    US_STOCK = "us_stock"  # 美股


class DocType(Enum):
    """文档类型枚举"""
    ANNUAL_REPORT = "annual_reports"  # 年报
    QUARTERLY_REPORT = "quarterly_reports"  # 季报
    INTERIM_REPORT = "interim_reports"  # 半年报
    IPO_PROSPECTUS = "ipo_prospectus"  # 招股说明书
    ANNOUNCEMENT = "announcements"  # 公告


@dataclass
class CrawlTask:
    """爬取任务"""
    stock_code: str  # 股票代码
    company_name: str  # 公司名称
    year: int  # 年份
    quarter: Optional[int] = None  # 季度 (1-4)，None表示年报
    doc_type: DocType = DocType.QUARTERLY_REPORT  # 文档类型
    market: Market = Market.A_SHARE  # 市场类型


@dataclass
class CrawlResult:
    """爬取结果"""
    success: bool  # 是否成功
    task: CrawlTask  # 任务信息
    file_path: Optional[str] = None  # 文件路径（成功时）
    file_size: Optional[int] = None  # 文件大小（字节）
    error_message: Optional[str] = None  # 错误信息（失败时）
    metadata: Optional[Dict] = None  # 元数据（发布日期、文件URL等）


class BaseCrawler(ABC):
    """
    爬虫基类
    所有市场爬虫都应继承此类并实现抽象方法
    """

    def __init__(self, market: Market, output_root: str):
        """
        Args:
            market: 市场类型
            output_root: 输出根目录（Bronze层路径）
        """
        self.market = market
        self.output_root = output_root

    @abstractmethod
    def crawl(self, task: CrawlTask) -> CrawlResult:
        """
        执行单个爬取任务
        
        Args:
            task: 爬取任务
            
        Returns:
            爬取结果
        """
        pass

    @abstractmethod
    def crawl_batch(self, tasks: List[CrawlTask]) -> List[CrawlResult]:
        """
        批量爬取
        
        Args:
            tasks: 任务列表
            
        Returns:
            结果列表
        """
        pass

    @abstractmethod
    def validate_result(self, result: CrawlResult) -> Tuple[bool, Optional[str]]:
        """
        验证爬取结果
        
        Args:
            result: 爬取结果
            
        Returns:
            (是否通过验证, 错误信息)
        """
        pass

    def get_storage_path(self, task: CrawlTask, filename: str) -> str:
        """
        根据plan.md规范生成存储路径
        
        路径格式：bronze/{market}/{doc_type}/{year}/{quarter}/{stock_code}/{filename}
        
        Args:
            task: 爬取任务
            filename: 文件名
            
        Returns:
            完整存储路径
        """
        year = task.year
        # 季度：从任务中获取，如果没有则默认为Q4
        quarter = f"Q{task.quarter}" if task.quarter else "Q4"
        
        # 构建路径（去掉key=value格式，直接使用值）
        path_parts = [
            self.output_root,
            "bronze",
            self.market.value,
            task.doc_type.value,
            str(year),
            quarter,
            task.stock_code,
            filename
        ]
        
        return "/".join(path_parts)

    def get_metadata(self, task: CrawlTask, publish_date: Optional[str] = None) -> Dict:
        """
        生成元数据字典
        
        Args:
            task: 爬取任务
            publish_date: 发布日期（ISO格式，可选）
            
        Returns:
            元数据字典
        """
        metadata = {
            "stock_code": task.stock_code,
            "company_name": task.company_name,
            "market": self.market.value,
            "doc_type": task.doc_type.value,
            "year": task.year,
            "quarter": task.quarter,
            "crawl_time": datetime.now().isoformat(),
        }
        if publish_date:
            metadata["publish_date"] = publish_date
        return metadata
