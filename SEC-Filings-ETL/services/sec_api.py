"""
SEC EDGAR API client for fetching company and filing data.

Performance optimizations:
- Shared HTTP client with connection pooling and HTTP/2
- Disk-based TTL cache for company submissions
- Enhanced rate limiting with 429 handling
"""
import json
from datetime import datetime, date
from typing import Dict, List, Optional, Union
from urllib.parse import urljoin

import httpx
import structlog

from config.settings import settings
from utils.rate_limiter import SECRateLimiter
from utils.http_client import get_http_client
from utils.disk_cache import get_cache
from utils import retry_with_backoff

logger = structlog.get_logger()


def _to_date_or_none(value: Optional[Union[str, date]]) -> Optional[date]:
    """
    Convert a date string or date object to a date object.

    Supports ISO formats:
    - YYYY-MM-DD (e.g., "2025-03-31")
    - YYYYMMDD (e.g., "20250331")

    Args:
        value: Date string, date object, or None

    Returns:
        date object or None if conversion fails or input is None/empty
    """
    if value is None or value == "":
        return None

    # Already a date object
    if isinstance(value, date):
        return value

    # String conversion
    if not isinstance(value, str):
        return None

    # Try ISO format with dashes (YYYY-MM-DD)
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        pass

    # Try compact format (YYYYMMDD)
    try:
        return datetime.strptime(value, '%Y%m%d').date()
    except (ValueError, TypeError):
        pass

    # Conversion failed
    logger.warning("failed_to_parse_date", value=value)
    return None


class SECAPIClient:
    """
    Client for SEC EDGAR API interactions.

    Performance features:
    - Shared HTTP client (connection pooling, HTTP/2)
    - Disk cache for company submissions (12h TTL)
    - Enhanced rate limiting with 429 handling
    """

    BASE_URL = "https://www.sec.gov"
    DATA_URL = "https://data.sec.gov"

    def __init__(self, use_cache: bool = True):
        """
        Initialize SEC API client.

        Args:
            use_cache: Enable disk cache for submissions (default: True)
        """
        self.rate_limiter = SECRateLimiter(requests_per_second=settings.sec_rps)
        self.client = get_http_client()
        self.cache = get_cache() if use_cache else None
        self.headers = {
            "User-Agent": settings.sec_user_agent,
            "Accept": "application/json"
        }

        logger.info(
            "sec_api_client_initialized",
            user_agent=settings.sec_user_agent,
            rps=settings.sec_rps,
            cache_enabled=use_cache,
            http2=True
        )
    
    def _make_request(self, url: str, stream: bool = False) -> httpx.Response:
        """
        Make rate-limited HTTP request to SEC using shared client.

        Args:
            url: Full URL to request
            stream: Whether to stream the response

        Returns:
            Response object

        Raises:
            httpx.HTTPError: On request failure
        """
        self.rate_limiter.wait()

        try:
            response = self.client.get(url, headers=self.headers)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            # Handle 429 Too Many Requests
            if e.response.status_code == 429:
                retry_after = e.response.headers.get('Retry-After')
                retry_after_seconds = int(retry_after) if retry_after else None
                self.rate_limiter.handle_429(retry_after_seconds)
                logger.warning(
                    "sec_api_429_received",
                    url=url,
                    retry_after=retry_after_seconds
                )
            raise
    
    @retry_with_backoff(max_attempts=3, initial_delay=10.0, exceptions=(httpx.HTTPError,))
    def fetch_company_tickers(self) -> Dict[str, Dict]:
        """
        Fetch all company tickers from SEC.
        
        Returns:
            Dictionary mapping CIK to company info:
            {
                "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
                ...
            }
        """
        url = f"{self.BASE_URL}/files/company_tickers.json"
        logger.info("fetching_company_tickers", url=url)
        
        response = self._make_request(url)
        data = response.json()
        
        logger.info("company_tickers_fetched", count=len(data))
        return data
    
    @retry_with_backoff(max_attempts=3, initial_delay=10.0, exceptions=(httpx.HTTPError,))
    def fetch_company_submissions(self, cik: str) -> Dict:
        """
        Fetch all submissions for a company with disk caching.

        Cache key: submissions:{cik}
        TTL: Configured by SEC_CACHE_TTL_HOURS (default 12h)

        Args:
            cik: Company CIK (will be zero-padded to 10 digits)

        Returns:
            Submissions JSON data containing filings metadata
        """
        # SEC API requires CIK zero-padded to 10 digits
        cik_padded = cik.zfill(10)
        cache_key = f"submissions:{cik_padded}"

        # Try cache first
        if self.cache:
            cached_data = self.cache.get(cache_key)
            if cached_data is not None:
                logger.debug(
                    "submissions_cache_hit",
                    cik=cik,
                    cik_padded=cik_padded
                )
                return cached_data

        # Cache miss - fetch from SEC
        url = f"{self.DATA_URL}/submissions/CIK{cik_padded}.json"

        logger.debug(
            "fetching_submissions",
            cik=cik,
            cik_padded=cik_padded,
            url=url,
            cache_miss=True
        )

        response = self._make_request(url)
        data = response.json()

        # Store in cache
        if self.cache:
            self.cache.set(cache_key, data)

        return data
    
    def download_file(self, url: str, output_path: str, chunk_size: int = None) -> int:
        """
        Download a file from SEC to local path using shared client.

        Args:
            url: URL to download
            output_path: Local path to save file
            chunk_size: Size of download chunks (default from settings)

        Returns:
            File size in bytes
        """
        if chunk_size is None:
            chunk_size = settings.download_chunk_size

        self.rate_limiter.wait()

        logger.debug("downloading_file", url=url, output=output_path, chunk_size=chunk_size)

        try:
            with self.client.stream("GET", url, headers=self.headers) as response:
                response.raise_for_status()

                total_size = 0
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_bytes(chunk_size=chunk_size):
                        f.write(chunk)
                        total_size += len(chunk)

            logger.debug("file_downloaded", url=url, size_bytes=total_size)
            return total_size

        except httpx.HTTPStatusError as e:
            # Handle 429 Too Many Requests
            if e.response.status_code == 429:
                retry_after = e.response.headers.get('Retry-After')
                retry_after_seconds = int(retry_after) if retry_after else None
                self.rate_limiter.handle_429(retry_after_seconds)
                logger.warning(
                    "sec_api_429_received",
                    url=url,
                    retry_after=retry_after_seconds
                )
            raise
    
    def construct_document_url(self, cik: str, accession: str, filename: str) -> str:
        """
        Construct URL for a specific document.

        Args:
            cik: Company CIK
            accession: Accession number (format: 0001234567-23-000123)
            filename: Document filename

        Returns:
            Full URL to document

        Example:
            https://www.sec.gov/Archives/edgar/data/320193/000032019323000123/aapl-20230930.htm
        """
        # Remove dashes from accession number for URL path
        accession_clean = accession.replace('-', '')
        cik_clean = cik.lstrip('0')  # Remove leading zeros

        url = f"{self.BASE_URL}/Archives/edgar/data/{cik_clean}/{accession_clean}/{filename}"
        return url

    def construct_primary_html_url(self, cik: str, accession: str, primary_document: Optional[str] = None) -> str:
        """
        Construct URL for primary HTML document or index fallback.

        This method builds the correct SEC EDGAR URL using the company's CIK
        (not the accession prefix). If primary_document is missing, falls back
        to index.html.

        Args:
            cik: Company CIK (e.g., "0001766600" or "1766600")
            accession: Accession number (format: 0001234567-23-000123)
            primary_document: Primary document filename (e.g., "sndl-20241231.htm")
                            If None or empty, returns index.html URL

        Returns:
            Full URL to primary document or index.html

        Examples:
            >>> construct_primary_html_url("0001766600", "0000950170-25-040545", "sndl-20241231.htm")
            'https://www.sec.gov/Archives/edgar/data/1766600/000095017025040545/sndl-20241231.htm'

            >>> construct_primary_html_url("0001766600", "0000950170-25-040545", None)
            'https://www.sec.gov/Archives/edgar/data/1766600/000095017025040545/index.html'
        """
        # Normalize CIK: remove leading zeros
        cik_no_zeros = cik.lstrip('0')

        # Normalize accession: remove dashes
        acc_no_dashes = accession.replace('-', '')

        # Determine filename: use primary_document if available, else index.html
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
        Parse filings from submissions data.
        
        Args:
            submissions_data: Data from fetch_company_submissions
            form_types: List of form types to include (e.g., ['10-K', '10-Q'])
            start_date: Filter filings on or after this date
            end_date: Filter filings before or on this date
        
        Returns:
            List of filing dictionaries with relevant metadata
        """
        filings = []
        
        recent_filings = submissions_data.get('filings', {}).get('recent', {})
        if not recent_filings:
            return filings
        
        # Parse recent filings
        for i in range(len(recent_filings.get('accessionNumber', []))):
            form = recent_filings['form'][i]

            # Filter by form type
            if form not in form_types:
                continue

            # Convert filing_date to date object
            filing_date_str = recent_filings['filingDate'][i]
            filing_date = _to_date_or_none(filing_date_str)

            if filing_date is None:
                logger.warning("skipping_filing_invalid_date", accession=recent_filings['accessionNumber'][i])
                continue

            # Filter by date range
            if start_date and filing_date < start_date.date():
                continue
            if end_date and filing_date > end_date.date():
                continue

            # Convert report_date to date object (may be None)
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
        
        logger.debug("filings_parsed", count=len(filings))
        return filings

    def get_primary_document_from_index(self, cik: str, accession: str) -> str:
        """
        从filing index页面获取主文档文件名

        当SEC API的submissions数据中primaryDocument字段为空时，
        通过访问filing的index页面来获取实际的主文档文件名。

        Args:
            cik: 公司CIK（可以带前导零）
            accession: Accession number (格式: 0000950170-25-040545)

        Returns:
            主文档文件名，如 "sndl-20241231.htm" 或 "abevform20f_2023.htm"
            如果找不到，返回 None

        Example:
            >>> client.get_primary_document_from_index("1766600", "0000950170-25-040545")
            "sndl-20241231.htm"
        """
        accession_clean = accession.replace('-', '')
        cik_clean = cik.lstrip('0')
        index_url = f"{self.BASE_URL}/Archives/edgar/data/{cik_clean}/{accession_clean}/{accession}-index.htm"

        logger.debug("fetching_index_page", url=index_url, cik=cik, accession=accession)
        try:
            response = self._make_request(index_url)
            html_content = response.text

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'lxml')

            htm_files = []
            for link in soup.find_all('a'):
                href = link.get('href', '')
                if (href.endswith('.htm') or href.endswith('.html')) and \
                    'index' not in href.lower() and \
                    not href.startswith('http'):
                    htm_files.append(href)

            if htm_files:
                primary = max(htm_files, key=len)
                logger.info(
                    "primary_document_found_from_index",
                    accession=accession,
                    filename=primary,
                    total_htm_files=len(htm_files),
                    all_files=htm_files
                )
                return primary
            else:
                logger.warning(
                    "no_htm_files_found_in_index",
                    accession=accession,
                    index_url=index_url
                )
                return None

        except Exception as e:
            logger.error(
                "index_parsing_failed",
                accession=accession,
                index_url=index_url,
                error=str(e),
                exc_info=True
            )
            return None