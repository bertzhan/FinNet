# -*- coding: utf-8 -*-
"""
SEC EDGAR API 客户端（用于获取公司和财报数据）
适配自 SEC-Filings-ETL/services/sec_api.py

性能优化：
- 共享HTTP客户端（连接池和HTTP/2）
- 增强的限流（429响应处理）
"""
import json
from datetime import datetime, date
from typing import Dict, List, Optional, Union
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from src.common.logger import get_logger
from src.common.config import sec_config
from src.ingestion.us_stock.crawlers.utils.rate_limiter import SECRateLimiter
from src.ingestion.us_stock.crawlers.utils.http_client import get_http_client

logger = get_logger(__name__)


def _to_date_or_none(value: Optional[Union[str, date]]) -> Optional[date]:
    """
    将日期字符串或日期对象转换为日期对象

    支持的ISO格式：
    - YYYY-MM-DD (例如："2025-03-31")
    - YYYYMMDD (例如："20250331")

    Args:
        value: 日期字符串、日期对象或None

    Returns:
        日期对象，如果转换失败或输入为None/空则返回None
    """
    if value is None or value == "":
        return None

    # 已经是日期对象
    if isinstance(value, date):
        return value

    # 字符串转换
    if not isinstance(value, str):
        return None

    # 尝试ISO格式（带破折号：YYYY-MM-DD）
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        pass

    # 尝试紧凑格式（YYYYMMDD）
    try:
        return datetime.strptime(value, '%Y%m%d').date()
    except (ValueError, TypeError):
        pass

    # 转换失败
    logger.warning(f"无法解析日期: {value}", extra={"value": value})
    return None


class SECAPIClient:
    """
    SEC EDGAR API交互客户端

    性能特性：
    - 共享HTTP客户端（连接池、HTTP/2）
    - 增强的限流（429处理）
    """

    BASE_URL = "https://www.sec.gov"
    DATA_URL = "https://data.sec.gov"

    def __init__(self, use_cache: bool = False):
        """
        初始化SEC API客户端

        Args:
            use_cache: 启用缓存（暂未实现，预留）
        """
        self.rate_limiter = SECRateLimiter(requests_per_second=sec_config.SEC_RATE_LIMIT)
        self.client = get_http_client()

        user_agent = sec_config.SEC_USER_AGENT
        if not user_agent or user_agent == "":
            logger.warning("SEC_USER_AGENT未配置，使用默认值")
            user_agent = "FinNet Research noreply@example.com"

        self.headers = {
            "User-Agent": user_agent,
            "Accept": "application/json"
        }

        logger.info(
            f"SEC API客户端已初始化: {sec_config.SEC_RATE_LIMIT} req/s",
            extra={
                "user_agent": user_agent,
                "rps": sec_config.SEC_RATE_LIMIT,
                "http2": True
            }
        )

    def _make_request(self, url: str, stream: bool = False) -> httpx.Response:
        """
        发起限流的HTTP请求到SEC（使用共享客户端）

        Args:
            url: 完整URL
            stream: 是否流式响应

        Returns:
            响应对象

        Raises:
            httpx.HTTPError: 请求失败时
        """
        self.rate_limiter.wait()

        try:
            response = self.client.get(url, headers=self.headers)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            # 处理429 Too Many Requests
            if e.response.status_code == 429:
                retry_after = e.response.headers.get('Retry-After')
                retry_after_seconds = int(retry_after) if retry_after else None
                self.rate_limiter.handle_429(retry_after_seconds)
                logger.warning(
                    f"收到429响应: {url}",
                    extra={
                        "url": url,
                        "retry_after": retry_after_seconds
                    }
                )
            raise

    def fetch_company_tickers(self) -> Dict[str, Dict]:
        """
        从SEC获取所有公司代码

        Returns:
            CIK到公司信息的映射字典：
            {
                "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
                ...
            }
        """
        url = f"{self.BASE_URL}/files/company_tickers.json"
        logger.info(f"获取公司列表: {url}")

        response = self._make_request(url)
        data = response.json()

        logger.info(f"公司列表已获取，数量: {len(data)}")
        return data

    def fetch_company_submissions(self, cik: str) -> Dict:
        """
        获取公司的所有提交记录

        Args:
            cik: 公司CIK（将被补零到10位）

        Returns:
            包含财报元数据的提交JSON数据
        """
        # SEC API要求CIK补零到10位
        cik_padded = cik.zfill(10)
        url = f"{self.DATA_URL}/submissions/CIK{cik_padded}.json"

        logger.debug(
            f"获取提交记录: CIK={cik}",
            extra={
                "cik": cik,
                "cik_padded": cik_padded,
                "url": url
            }
        )

        response = self._make_request(url)
        data = response.json()

        return data

    def download_file(self, url: str, output_path: str, chunk_size: int = 262144) -> int:
        """
        从SEC下载文件到本地路径（使用共享客户端）

        Args:
            url: 下载URL
            output_path: 本地保存路径
            chunk_size: 下载块大小（默认256KB）

        Returns:
            文件大小（字节）
        """
        self.rate_limiter.wait()

        logger.debug(f"下载文件: {url} -> {output_path}")

        try:
            with self.client.stream("GET", url, headers=self.headers) as response:
                response.raise_for_status()

                total_size = 0
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_bytes(chunk_size=chunk_size):
                        f.write(chunk)
                        total_size += len(chunk)

            logger.debug(f"文件已下载: {total_size} 字节")
            return total_size

        except httpx.HTTPStatusError as e:
            # 处理429 Too Many Requests
            if e.response.status_code == 429:
                retry_after = e.response.headers.get('Retry-After')
                retry_after_seconds = int(retry_after) if retry_after else None
                self.rate_limiter.handle_429(retry_after_seconds)
                logger.warning(
                    f"下载时收到429响应: {url}",
                    extra={
                        "url": url,
                        "retry_after": retry_after_seconds
                    }
                )
            raise

    def construct_document_url(self, cik: str, accession: str, filename: str) -> str:
        """
        构造特定文档的URL

        Args:
            cik: 公司CIK
            accession: Accession编号（格式：0001234567-23-000123）
            filename: 文档文件名

        Returns:
            文档的完整URL

        Example:
            https://www.sec.gov/Archives/edgar/data/320193/000032019323000123/aapl-20230930.htm
        """
        # 从accession编号中删除破折号用于URL路径
        accession_clean = accession.replace('-', '')
        cik_clean = cik.lstrip('0')  # 删除前导零

        url = f"{self.BASE_URL}/Archives/edgar/data/{cik_clean}/{accession_clean}/{filename}"
        return url

    def construct_primary_html_url(self, cik: str, accession: str, primary_document: Optional[str] = None) -> str:
        """
        构造主HTML文档或index回退的URL

        Args:
            cik: 公司CIK（例如："0001766600"或"1766600"）
            accession: Accession编号（格式：0001234567-23-000123）
            primary_document: 主文档文件名（例如："sndl-20241231.htm"）
                            如果为None或空，返回index.html URL

        Returns:
            主文档或index.html的完整URL

        Examples:
            >>> construct_primary_html_url("0001766600", "0000950170-25-040545", "sndl-20241231.htm")
            'https://www.sec.gov/Archives/edgar/data/1766600/000095017025040545/sndl-20241231.htm'
        """
        # 标准化CIK：删除前导零
        cik_no_zeros = cik.lstrip('0')

        # 标准化accession：删除破折号
        acc_no_dashes = accession.replace('-', '')

        # 确定文件名：如果有primary_document则使用，否则使用index.html
        if primary_document and primary_document.strip():
            filename = primary_document
        else:
            filename = 'index.html'

        url = f"{self.BASE_URL}/Archives/edgar/data/{cik_no_zeros}/{acc_no_dashes}/{filename}"
        return url

    def parse_filings(
        self,
        submissions_data: Dict,
        form_types: List[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        从提交数据中解析财报

        Args:
            submissions_data: 来自fetch_company_submissions的数据
            form_types: 要包含的表单类型列表（例如：['10-K', '10-Q']）
            start_date: 过滤此日期或之后的财报
            end_date: 过滤此日期或之前的财报

        Returns:
            包含相关元数据的财报字典列表
        """
        filings = []

        recent_filings = submissions_data.get('filings', {}).get('recent', {})
        if not recent_filings:
            return filings

        # 解析最近的财报
        for i in range(len(recent_filings.get('accessionNumber', []))):
            form = recent_filings['form'][i]

            # 按表单类型过滤
            if form not in form_types:
                continue

            # 将filing_date转换为日期对象
            filing_date_str = recent_filings['filingDate'][i]
            filing_date = _to_date_or_none(filing_date_str)

            if filing_date is None:
                logger.warning(f"跳过无效日期的财报: {recent_filings['accessionNumber'][i]}")
                continue

            # 按日期范围过滤
            if start_date and filing_date < start_date.date():
                continue
            if end_date and filing_date > end_date.date():
                continue

            # 将report_date转换为日期对象（可能为None）
            report_date_str = recent_filings.get('reportDate', [None] * len(recent_filings['accessionNumber']))[i]
            report_date = _to_date_or_none(report_date_str)

            filing = {
                'accession_number': recent_filings['accessionNumber'][i],
                'form_type': form,
                'filing_date': filing_date,
                'report_date': report_date,
                'primary_document': recent_filings['primaryDocument'][i],
                'is_amendment': form.endswith('/A')
            }

            filings.append(filing)

        logger.debug(f"已解析财报数: {len(filings)}")
        return filings

    def get_primary_document_from_index(self, cik: str, accession: str) -> Optional[str]:
        """
        从filing index页面获取主文档文件名

        当SEC API的submissions数据中primaryDocument字段为空时，
        通过访问filing的index页面来获取实际的主文档文件名。

        Args:
            cik: 公司CIK（可以带前导零）
            accession: Accession编号（格式：0000950170-25-040545）

        Returns:
            主文档文件名，如"sndl-20241231.htm"，如果找不到则返回None

        Example:
            >>> client.get_primary_document_from_index("1766600", "0000950170-25-040545")
            "sndl-20241231.htm"
        """
        accession_clean = accession.replace('-', '')
        cik_clean = cik.lstrip('0')
        index_url = f"{self.BASE_URL}/Archives/edgar/data/{cik_clean}/{accession_clean}/{accession}-index.htm"

        logger.debug(f"获取index页面: {index_url}")
        try:
            response = self._make_request(index_url)
            html_content = response.text

            soup = BeautifulSoup(html_content, 'lxml')

            htm_files = []
            for link in soup.find_all('a'):
                href = link.get('href', '')
                if (href.endswith('.htm') or href.endswith('.html')) and \
                    'index' not in href.lower() and \
                    not href.startswith('http'):
                    htm_files.append(href)

            if htm_files:
                # 选择最长的文件名（通常是主文档）
                primary = max(htm_files, key=len)
                logger.info(
                    f"从index找到主文档: {primary}",
                    extra={
                        "accession": accession,
                        "filename": primary,
                        "total_htm_files": len(htm_files)
                    }
                )
                return primary
            else:
                logger.warning(
                    f"index中未找到htm文件: {index_url}",
                    extra={
                        "accession": accession,
                        "index_url": index_url
                    }
                )
                return None

        except Exception as e:
            logger.error(
                f"解析index失败: {index_url}",
                extra={
                    "accession": accession,
                    "error": str(e)
                },
                exc_info=True
            )
            return None
