# -*- coding: utf-8 -*-
"""
披露易 API 客户端
封装香港交易所披露易的 API 调用
"""

import re
import json
import time
import tempfile
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import pandas as pd

from src.common.logger import get_logger
from ..utils.rate_limiter import AdaptiveRateLimiter
from ..utils.parser import HKEXTitleParser

logger = get_logger(__name__)


# API URLs
HKEX_BASE_URL = "https://www1.hkexnews.hk/search/titlesearch.xhtml"
HKEX_PDF_BASE = "https://www1.hkexnews.hk"
HKEX_ACTIVE_STOCK_URL = "https://www1.hkexnews.hk/ncms/script/eds/activestock_sehk_c.json"
HKEX_INACTIVE_STOCK_URL = "https://www1.hkexnews.hk/ncms/script/eds/inactivestock_sehk_c.json"
HKEX_PARTIAL_API_URL = "https://www1.hkexnews.hk/search/partial.do"
HKEX_STOCK_LIST_EXCEL_URLS = [
    "https://www.hkex.com.hk/chi/services/trading/securities/securitieslists/ListOfSecurities_c.xlsx",
    "https://www.hkexnews.hk/reports/securitieslists/sehk/ListOfSecurities_c.xlsx",
]
HKEX_REQUEST_TIMEOUT = 30

# HTTP Headers
HKEX_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/119.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
    "Origin": "https://www1.hkexnews.hk",
    "Referer": "https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=zh",
}


@dataclass
class HKEXDocType:
    """披露易文档类型"""
    key: str           # 类型标识
    name: str          # 类型名称
    t2code: str        # API 查询参数


@dataclass
class HKEXDocument:
    """披露易文档信息"""
    title: str         # 文档标题
    href: str          # 下载链接（相对路径）
    release_dt: datetime  # 发布时间


# 报告类型配置
HKEX_REPORT_TYPES: Dict[str, HKEXDocType] = {
    '年报': HKEXDocType(key='年报', name='年报', t2code='40100'),
    '中期报告': HKEXDocType(key='中期报告', name='中期报告', t2code='40200'),
    '季度报告': HKEXDocType(key='季度报告', name='季度报告', t2code='40300'),
}


def _create_http_session(
    pool_connections: int = 20,
    pool_maxsize: int = 40,
    total_retries: int = 3,
    backoff_factor: float = 0.3,
    status_forcelist: Optional[List[int]] = None,
) -> requests.Session:
    """创建带连接池和自动重试的 Session"""
    session = requests.Session()
    if status_forcelist is None:
        status_forcelist = [429, 500, 502, 503, 504]

    retry_strategy = Retry(
        total=total_retries,
        read=total_retries,
        connect=total_retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
        raise_on_status=False,
    )

    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _normalize_release_text(release_text: str) -> str:
    """标准化发布时间文本"""
    text = release_text.strip()
    try:
        text = text.encode("latin-1").decode("big5")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass

    label_patterns = [
        r"發佈時間[:：]\s*",
        r"發表時間[:：]\s*",
        r"公布時間[:：]\s*",
        r"發佈日期[:：]\s*",
        r"發布時間[:：]\s*",
        r"发布时间[:：]\s*",
        r"發布日期[:：]\s*",
        r"發布[:：]\s*",
        r"時間[:：]\s*",
    ]
    for pattern in label_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    return text.strip()


def _parse_release_datetime(release_text: str) -> datetime:
    """解析发布时间"""
    normalized_text = _normalize_release_text(release_text)
    match = re.search(r"(\d{2}/\d{2}/\d{4})\s*(\d{2}:\d{2})?", normalized_text)
    if not match:
        match = re.search(r"(\d{2}/\d{2}/\d{4})\s*(\d{2}:\d{2})?", release_text)
    if not match:
        raise ValueError(f"Unrecognized release time format: {release_text}")

    date_part = match.group(1)
    time_part = match.group(2) or "00:00"
    dt_str = f"{date_part} {time_part}"
    return datetime.strptime(dt_str, "%d/%m/%Y %H:%M")


def _parse_documents_from_html(html: str) -> List[HKEXDocument]:
    """从 HTML 响应中解析文档列表"""
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table.table tbody tr")
    documents: List[HKEXDocument] = []

    if not rows:
        return documents

    for row in rows:
        link = row.select_one("div.doc-link a")
        time_cell = row.select_one("td.release-time")
        if not link or not time_cell:
            continue

        title = " ".join(link.get_text(strip=True).split())
        release_text = time_cell.get_text(strip=True)
        try:
            release_dt = _parse_release_datetime(release_text)
        except ValueError:
            continue
        href = link.get("href", "").strip()
        if not href:
            continue

        documents.append(
            HKEXDocument(
                title=title,
                href=href,
                release_dt=release_dt,
            )
        )

    return documents


class HKEXClient:
    """
    披露易 API 客户端
    
    提供：
    - 股票列表获取
    - 报告查询
    - PDF 下载
    """
    
    def __init__(
        self,
        base_interval: float = 0.3,
        max_interval: float = 6.0,
    ):
        """
        Args:
            base_interval: 基础请求间隔
            max_interval: 最大请求间隔
        """
        self.session = _create_http_session()
        self.rate_limiter = AdaptiveRateLimiter(
            base_interval=base_interval,
            max_interval=max_interval
        )
        self.title_parser = HKEXTitleParser()
        self.report_types = HKEX_REPORT_TYPES
        self.pdf_base_url = HKEX_PDF_BASE
        
        # 股票代码到 orgId 的映射缓存
        self._org_id_cache: Dict[str, int] = {}
    
    def _download_stock_list_excel(self, save_path: Optional[str] = None) -> Optional[str]:
        """
        从香港交易所下载证券列表 Excel 文件（中文繁体版）
        
        Args:
            save_path: 保存路径（如果为 None，则保存到临时文件）
            
        Returns:
            文件路径，如果下载失败则返回 None
        """
        if save_path is None:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
            save_path = temp_file.name
            temp_file.close()
        
        # 确保目录存在
        os.makedirs(os.path.dirname(save_path) if os.path.dirname(save_path) else '.', exist_ok=True)
        
        for url in HKEX_STOCK_LIST_EXCEL_URLS:
            try:
                self.rate_limiter.acquire()
                response = self.session.get(url, timeout=HKEX_REQUEST_TIMEOUT, headers=HKEX_HEADERS, stream=True)
                
                if response.status_code == 200:
                    self.rate_limiter.on_success()
                    with open(save_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    logger.info(f"成功下载证券列表 Excel: {save_path}")
                    return save_path
                else:
                    self.rate_limiter.on_error()
            except Exception as e:
                logger.warning(f"下载失败 ({url}): {e}")
                self.rate_limiter.on_error()
        
        logger.error("所有下载 URL 都失败了")
        return None
    
    def _parse_stock_list_excel(self, excel_path: str) -> pd.DataFrame:
        """
        解析证券列表 Excel 文件，筛选出股本證券公司
        
        筛选条件：
        - 分類 = "股本"
        - 次分類 = "股本證券(主板)" 或 "股本證券(創業板)"
        
        Args:
            excel_path: Excel 文件路径
            
        Returns:
            筛选后的 DataFrame，包含 code, name, category, sub_category 列
        """
        try:
            excel_file = pd.ExcelFile(excel_path)
            all_stocks = []
            
            for sheet_name in excel_file.sheet_names:
                logger.debug(f"处理工作表: {sheet_name}")
                
                # 尝试不同的跳过行数
                for skip_rows in [0, 1, 2, 3]:
                    try:
                        df = pd.read_excel(excel_path, sheet_name=sheet_name, skiprows=skip_rows)
                        
                        # 查找列名
                        code_col = None
                        name_col = None
                        category_col = None
                        subcategory_col = None
                        
                        for col in df.columns:
                            col_str = str(col).strip()
                            if '股份代' in col_str or '代號' in col_str or 'code' in col_str.lower():
                                code_col = col
                            elif '股份名' in col_str or '名稱' in col_str or 'name' in col_str.lower():
                                name_col = col
                            elif col_str == '分類' or 'category' in col_str.lower():
                                category_col = col
                            elif '次分類' in col_str or 'sub-category' in col_str.lower() or 'subcategory' in col_str.lower():
                                subcategory_col = col
                        
                        if code_col and name_col and category_col and subcategory_col:
                            # 选择需要的列
                            stocks_df = df[[code_col, name_col, category_col, subcategory_col]].copy()
                            
                            # 清理数据
                            stocks_df = stocks_df.dropna(subset=[code_col])
                            stocks_df[code_col] = stocks_df[code_col].astype(str).str.strip()
                            stocks_df[name_col] = stocks_df[name_col].astype(str).str.strip()
                            stocks_df[category_col] = stocks_df[category_col].astype(str).str.strip()
                            stocks_df[subcategory_col] = stocks_df[subcategory_col].astype(str).str.strip()
                            
                            # 过滤：只保留数字代码
                            stocks_df = stocks_df[stocks_df[code_col].str.match(r'^\d+$', na=False)]
                            
                            # 筛选：分類 = "股本"
                            category_mask = stocks_df[category_col] == '股本'
                            stocks_df = stocks_df[category_mask]
                            
                            # 筛选：次分類 = "股本證券(主板)" 或 "股本證券(創業板)"
                            subcategory_mask = stocks_df[subcategory_col].isin([
                                '股本證券(主板)',
                                '股本證券(創業板)'
                            ])
                            stocks_df = stocks_df[subcategory_mask]
                            
                            # 补零到5位
                            stocks_df[code_col] = stocks_df[code_col].str.zfill(5)
                            
                            # 重命名列
                            stocks_df = stocks_df.rename(columns={
                                code_col: 'code',
                                name_col: 'name',
                                category_col: 'category',
                                subcategory_col: 'sub_category'
                            })
                            
                            all_stocks.append(stocks_df)
                            logger.debug(f"工作表 {sheet_name}: 找到 {len(stocks_df)} 条股本证券记录")
                            break
                            
                    except (ValueError, KeyError, pd.errors.EmptyDataError, pd.errors.ParserError) as e:
                        logger.debug(f"跳过 {skip_rows} 行失败: {e}")
                        continue
            
            if not all_stocks:
                logger.warning("未能从 Excel 中解析出任何股本证券记录")
                return pd.DataFrame(columns=['code', 'name', 'category', 'sub_category'])
            
            # 合并所有工作表的数据
            result_df = pd.concat(all_stocks, ignore_index=True)
            logger.info(f"从 Excel 解析出 {len(result_df)} 条股本证券记录")
            return result_df
            
        except Exception as e:
            logger.error(f"解析 Excel 文件失败: {e}", exc_info=True)
            return pd.DataFrame(columns=['code', 'name', 'category', 'sub_category'])
    
    def get_stock_list(self, include_inactive: bool = False, equity_only: bool = True, excel_path: Optional[str] = None) -> List[Dict]:
        """
        获取港股股票列表
        
        如果 equity_only=True，会从 HKEX 下载 Excel 文件并根据分類和次分類过滤股本证券。
        然后从 JSON API 获取 stockId 并合并。
        
        Args:
            include_inactive: 是否包含已除牌的股票
            equity_only: 是否只返回股本证券（通过 Excel 分類过滤）
            excel_path: Excel 文件路径（如果为 None，则自动下载）
            
        Returns:
            股票信息列表，每个元素包含 code, name, stock_id, category, sub_category 等
        """
        stocks = []
        equity_df = None
        
        if equity_only:
            # 从 Excel 文件解析股本证券列表
            if excel_path and os.path.exists(excel_path):
                logger.info(f"使用现有 Excel 文件: {excel_path}")
            else:
                logger.info("下载证券列表 Excel 文件...")
                excel_path = self._download_stock_list_excel(excel_path)
                if not excel_path:
                    logger.error("无法下载 Excel 文件，回退到 JSON API 方式")
                    equity_only = False
            
            if excel_path:
                # 解析 Excel，获取股本证券列表
                equity_df = self._parse_stock_list_excel(excel_path)
                
                if equity_df is None or len(equity_df) == 0:
                    logger.warning("Excel 解析结果为空，回退到 JSON API 方式")
                    equity_only = False
                else:
                    # 构建股本证券代码集合
                    equity_codes = set(equity_df['code'].tolist())
                    logger.info(f"从 Excel 获取 {len(equity_codes)} 个股本证券代码")
        
        # 从 JSON API 获取所有股票的 orgId 和名称
        stock_info_map = {}  # {code: {'org_id': int, 'name': str, 'name_en': str, 'is_active': bool}}
        
        # 获取活跃股票
        try:
            active_data = self._fetch_stock_json(HKEX_ACTIVE_STOCK_URL)
            for item in active_data:
                code = str(item.get("c", "")).strip().zfill(5)
                name = item.get("n", "")
                name_en = item.get("e", "")
                stock_id = item.get("i")
                if code and stock_id is not None:
                    stock_info_map[code] = {
                        'org_id': int(stock_id),
                        'name': name,
                        'name_en': name_en,
                        'is_active': True
                    }
                    self._org_id_cache[code] = int(stock_id)
        except Exception as e:
            logger.warning(f"获取活跃股票列表失败: {e}")
        
        # 获取非活跃股票
        if include_inactive:
            try:
                inactive_data = self._fetch_stock_json(HKEX_INACTIVE_STOCK_URL)
                for item in inactive_data:
                    code = str(item.get("c", "")).strip().zfill(5)
                    name = item.get("n", "")
                    name_en = item.get("e", "")
                    stock_id = item.get("i")
                    if code and stock_id is not None:
                        # 如果已存在，跳过（活跃股票优先）
                        if code not in stock_info_map:
                            stock_info_map[code] = {
                                'org_id': int(stock_id),
                                'name': name,
                                'name_en': name_en,
                                'is_active': False
                            }
                            self._org_id_cache[code] = int(stock_id)
            except Exception as e:
                logger.warning(f"获取非活跃股票列表失败: {e}")
        
        logger.info(f"从 JSON API 获取了 {len(stock_info_map)} 个股票的信息")
        
        # 合并数据
        if equity_only and equity_df is not None and len(equity_df) > 0:
            # 使用 Excel 解析的结果，合并 stockId 和名称
            for _, row in equity_df.iterrows():
                code = row['code']
                excel_name = row['name']
                category = row.get('category', '')
                sub_category = row.get('sub_category', '')
                stock_info = stock_info_map.get(code)
                
                if stock_info:
                    stock_data = {
                        'code': code,
                        'name': excel_name,  # 使用 Excel 中的名称（更准确）
                        'org_id': stock_info['org_id'],
                        'category': category,
                        'sub_category': sub_category,
                    }
                    # 添加英文名称（如果有）
                    if stock_info.get('name_en'):
                        stock_data['org_name_en'] = stock_info.get('name_en')
                    stocks.append(stock_data)
                else:
                    logger.debug(f"未找到 orgId: {code} ({excel_name})")
            
            logger.info(f"合并后得到 {len(stocks)} 条股本证券记录（有 orgId）")
        else:
            # 回退到原来的方式：使用 JSON API 的所有数据
            for code, stock_info in stock_info_map.items():
                stock_data = {
                    'code': code,
                    'name': stock_info['name'],
                    'org_id': stock_info['org_id'],
                    'category': None,
                    'sub_category': None,
                }
                # 添加英文名称（如果有）
                if stock_info.get('name_en'):
                    stock_data['org_name_en'] = stock_info.get('name_en')
                stocks.append(stock_data)
        
        return stocks
    
    def _fetch_stock_json(self, url: str) -> List[Dict]:
        """获取股票 JSON 数据"""
        self.rate_limiter.acquire()
        try:
            response = self.session.get(url, timeout=HKEX_REQUEST_TIMEOUT, headers=HKEX_HEADERS)
            if response.status_code == 200:
                self.rate_limiter.on_success()
            elif response.status_code in (403, 429):
                self.rate_limiter.on_throttle()
            else:
                self.rate_limiter.on_error()
            response.raise_for_status()
            
            # 解析 JSONP 响应
            text = response.text.strip()
            if text.startswith("callback("):
                text = text[len("callback("):]
                if text.endswith(");"):
                    text = text[:-2]
                elif text.endswith(")"):
                    text = text[:-1]
            
            return json.loads(text)
        except Exception as e:
            self.rate_limiter.on_error()
            raise
    
    def get_org_id(self, stock_code: str) -> Optional[int]:
        """
        获取股票的 orgId（用于披露易查询）
        
        Args:
            stock_code: 股票代码（5位数字）
            
        Returns:
            orgId，如果找不到则返回 None
        """
        code = stock_code.strip().zfill(5)
        
        # 先从缓存查找
        if code in self._org_id_cache:
            return self._org_id_cache[code]
        
        # 如果缓存为空，尝试加载股票列表
        if not self._org_id_cache:
            self.get_stock_list(include_inactive=True)
        
        return self._org_id_cache.get(code)
    
    def get_stock_id(self, stock_code: str) -> Optional[int]:
        """
        获取股票的 stockId（已废弃，请使用 get_org_id）
        
        为了向后兼容保留此方法
        """
        return self.get_org_id(stock_code)
    
    def query_reports(
        self,
        stock_code: str,
        org_id: Optional[int],
        report_type: str,
        start_date: str = "2022-01-01",
        end_date: str = "2025-12-31"
    ) -> Tuple[List[Dict], Optional[str]]:
        """
        查询指定公司的报告列表
        
        Args:
            stock_code: 股票代码
            org_id: 披露易 orgId（兼容 stock_id 参数）
            report_type: 报告类型（'年报', '中期报告', '季度报告'）
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            
        Returns:
            (报告列表, 错误信息)
        """
        # 兼容 stock_id 参数
        if org_id is None:
            return [], "缺少 orgId"
        
        stock_id = org_id  # 用于 API 调用
        
        doc_type = self.report_types.get(report_type)
        if not doc_type:
            return [], f"未配置的报告类型: {report_type}"
        
        # 格式化日期
        start_str = start_date.replace("-", "")
        end_str = end_date.replace("-", "")
        
        payload = {
            "lang": "zh",
            "category": "0",
            "market": "SEHK",
            "searchType": "1",
            "t1code": "40000",
            "t2Gcode": "-2",
            "t2code": doc_type.t2code,
            "stockId": str(stock_id),
            "from": start_str,
            "to": end_str,
            "MB-Daterange": "0",
            "title": "",
            "sortDirection": "1",
            "sortBy": "1",
            "rowRange": "100",
            "currentPage": "1",
            "documentType": "",
        }
        
        response = None
        try:
            self.rate_limiter.acquire()
            response = self.session.post(
                HKEX_BASE_URL,
                data=payload,
                timeout=HKEX_REQUEST_TIMEOUT,
                headers=HKEX_HEADERS
            )
            status_code = response.status_code
            if status_code == 200:
                self.rate_limiter.on_success()
            elif status_code in (403, 429):
                self.rate_limiter.on_throttle()
            else:
                self.rate_limiter.on_error()
            response.raise_for_status()
        except requests.RequestException as exc:
            if response is None:
                self.rate_limiter.on_error()
            else:
                status_code = getattr(response, "status_code", None)
                if status_code in (403, 429):
                    self.rate_limiter.on_throttle()
                else:
                    self.rate_limiter.on_error()
            logger.warning(f"查询披露易失败: {exc}")
            return [], f"请求失败: {exc}"
        
        # 解析 HTML 响应
        documents = _parse_documents_from_html(response.text)
        announcements: List[Dict] = []
        
        for doc in documents:
            announcement_time_ms = int(doc.release_dt.timestamp() * 1000)
            quarter = self.title_parser.identify_quarter(doc.title)
            
            # 如果无法识别季度，根据报告类型设置默认值
            if not quarter:
                if report_type == '年报':
                    quarter = 'Q4'
                elif report_type == '中期报告':
                    quarter = 'Q2'
                elif report_type == '季度报告':
                    # 根据发布日期推断
                    release_month = doc.release_dt.month
                    if release_month in [1, 2, 3]:
                        quarter = 'Q1'
                    elif release_month in [4, 5, 6]:
                        quarter = 'Q2'
                    elif release_month in [7, 8, 9]:
                        quarter = 'Q3'
                    elif release_month in [10, 11, 12]:
                        quarter = 'Q4'
            
            fiscal_year = self.title_parser.extract_year_from_title(doc.title, announcement_time_ms)
            if not fiscal_year:
                fiscal_year = str(doc.release_dt.year)
            
            announcements.append({
                "announcementTitle": doc.title,
                "announcementTime": announcement_time_ms,
                "adjunctUrl": doc.href,
                "hkexQuarter": quarter,
                "hkexFiscalYear": fiscal_year,
                "hkexDocType": doc_type.key,
                "hkexSourceType": report_type,
            })
        
        if not announcements:
            reason = (
                "披露易返回0条记录，可能是报告未发布、超出查询区间，"
                "或该公司此类型报告未在披露易披露"
            )
            return [], reason
        
        return announcements, None
    
    def filter_real_report(self, announcements: List[Dict]) -> List[Dict]:
        """
        过滤真实的财务报表（排除补充公告、通知信函等）
        
        Args:
            announcements: 公告列表
            
        Returns:
            过滤后的公告列表
        """
        filtered = []
        for ann in announcements:
            title = ann.get("announcementTitle", "")
            if not self.title_parser.should_exclude_announcement(title):
                filtered.append(ann)
        return filtered
    
    def download_pdf(
        self,
        pdf_url: str,
        save_path: str,
        timeout: int = 60
    ) -> Tuple[bool, Optional[str]]:
        """
        下载 PDF 文件
        
        Args:
            pdf_url: PDF URL（相对路径或完整 URL）
            save_path: 保存路径
            timeout: 超时时间
            
        Returns:
            (是否成功, 错误信息)
        """
        # 构造完整 URL
        if not pdf_url.startswith("http"):
            full_url = f"{self.pdf_base_url}{pdf_url}"
        else:
            full_url = pdf_url
        
        try:
            self.rate_limiter.acquire()
            response = self.session.get(
                full_url,
                timeout=timeout,
                headers=HKEX_HEADERS,
                stream=True
            )
            
            if response.status_code == 200:
                self.rate_limiter.on_success()
            elif response.status_code in (403, 429):
                self.rate_limiter.on_throttle()
                return False, f"被限流: {response.status_code}"
            else:
                self.rate_limiter.on_error()
                return False, f"HTTP 错误: {response.status_code}"
            
            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 写入文件
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            return True, None
            
        except requests.RequestException as e:
            self.rate_limiter.on_error()
            return False, f"下载失败: {e}"
        except Exception as e:
            return False, f"保存失败: {e}"
    
    def select_best_report(
        self,
        announcements: List[Dict],
        year: int,
        quarter: str
    ) -> Optional[Dict]:
        """
        从公告列表中选择最佳的报告（按年份和季度匹配）
        
        Args:
            announcements: 公告列表
            year: 目标年份
            quarter: 目标季度 ('Q1', 'Q2', 'Q3', 'Q4')
            
        Returns:
            最佳匹配的公告，如果没有则返回 None
        """
        # 先过滤真实报表
        filtered = self.filter_real_report(announcements)
        
        if not filtered:
            return None
        
        # 按年份和季度匹配
        matched = []
        for ann in filtered:
            ann_year = ann.get("hkexFiscalYear", "")
            ann_quarter = ann.get("hkexQuarter", "")
            
            if str(ann_year) == str(year) and ann_quarter == quarter:
                matched.append(ann)
        
        if not matched:
            # 如果没有精确匹配，尝试只匹配年份
            for ann in filtered:
                ann_year = ann.get("hkexFiscalYear", "")
                if str(ann_year) == str(year):
                    matched.append(ann)
        
        if matched:
            # 返回发布时间最晚的（通常是最新版本）
            matched.sort(key=lambda x: x.get("announcementTime", 0), reverse=True)
            return matched[0]
        
        return None
