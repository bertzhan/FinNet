# -*- coding: utf-8 -*-
"""
IPO 招股说明书 API 客户端
"""

import logging
from typing import List, Optional

import requests
from requests.exceptions import RequestException

from ..config import CNINFO_API, PROXIES, CATEGORY_IPO
from ..utils.code_utils import detect_exchange, normalize_code
from ..utils.time_utils import parse_time_to_ms
from ..utils.text_utils import normalize_text

logger = logging.getLogger(__name__)


def build_se_window_for_ipo(lookback_years: int = 20) -> str:
    """
    为IPO招股说明书构建时间窗口
    由于IPO时间不确定，使用较大的时间范围（默认最近20年）
    
    Args:
        lookback_years: 回溯年数
        
    Returns:
        时间窗口字符串，格式: "YYYY-MM-DD~YYYY-MM-DD"
    """
    from datetime import datetime
    end_year = datetime.now().year
    start_year = end_year - lookback_years
    return f"{start_year}-01-01~{end_year}-12-31"


def fetch_ipo_announcements(
    api_session: requests.Session,
    code: str,
    orgId: Optional[str],
    column_api: str,
    page_size: int = 100
) -> List[dict]:
    """
    抓取IPO招股说明书公告
    
    Args:
        api_session: API 请求会话
        code: 股票代码
        orgId: 组织ID（可选）
        column_api: 交易所API列名
        page_size: 每页大小
        
    Returns:
        公告列表
    """
    _, _, stock_suffix = detect_exchange(code)
    stock_field = f"{code},{orgId}" if orgId else f"{code}.{stock_suffix}"

    seDate = build_se_window_for_ipo(lookback_years=40)  # 覆盖1988年至今的所有IPO

    all_list: List[dict] = []
    page = 1

    while True:
        payload = {
            "tabName": "fulltext",
            "column": column_api,
            "stock": stock_field,
            "category": "",  # 不限制category，通过searchkey搜索
            "seDate": seDate,
            "pageNum": str(page),
            "pageSize": str(page_size),
            "searchkey": "招股说明书",  # 关键：使用搜索关键词
            "plate": "",
            "isHLtitle": "true",
        }

        try:
            data = api_session.post(CNINFO_API, data=payload, timeout=20, proxies=PROXIES)
            if data.status_code >= 400:
                logger.warning(f"hisAnnouncement HTTP {data.status_code} ({code} 页 {page})")
                break
            data = data.json() if data.text.strip().startswith("{") else {}
        except RequestException as e:
            logger.warning(f"hisAnnouncement 请求异常（{code} 页 {page}）：{e}")
            break

        anns = (data or {}).get("announcements") or []
        if not anns:
            break
        all_list.extend(anns)
        if len(anns) < page_size:
            break
        page += 1

    return all_list


def title_ok_for_ipo(title: str) -> bool:
    """
    检查标题是否为招股说明书
    - 必须包含"招股说明书"或"招股书"
    - 排除摘要、英文版、更正等
    
    Args:
        title: 公告标题
        
    Returns:
        True 如果标题匹配招股说明书
    """
    from ..config import IPO_KEYWORDS, EXCLUDE_IN_TITLE_IPO
    
    t = normalize_text(title)

    # 排除不需要的关键词
    if any(k in t for k in map(normalize_text, EXCLUDE_IN_TITLE_IPO)):
        return False

    # 必须包含招股说明书关键词
    return any(k in t for k in map(normalize_text, IPO_KEYWORDS))


def pick_latest_ipo(anns: List[dict], code: str) -> Optional[dict]:
    """
    从公告列表中选择最新的招股说明书
    支持PDF和HTML格式（早期文档多为HTML）
    
    Args:
        anns: 公告列表
        code: 股票代码
        
    Returns:
        最新的匹配公告，如果没有则返回 None
    """
    code_normalized = normalize_code(code)
    cands = []

    for a in anns:
        ann_code = normalize_code(str(a.get("secCode", "")))
        if ann_code != code_normalized:
            continue

        title = a.get("announcementTitle", "")
        if not title_ok_for_ipo(title):
            continue

        adj = a.get("adjunctUrl", "")
        if not adj:
            continue

        # 接受PDF和HTML格式
        adj_lower = adj.lower()
        if not (adj_lower.endswith(".pdf") or adj_lower.endswith(".html") or adj_lower.endswith(".htm")):
            continue

        ts = parse_time_to_ms(a.get("announcementTime"))
        cands.append((ts, a))

    if not cands:
        return None

    cands.sort(key=lambda x: x[0], reverse=True)
    return cands[0][1]


class IPOAPIClient:
    """
    IPO API 客户端类
    封装IPO招股说明书查询相关功能
    """
    
    def __init__(self, api_session: requests.Session):
        """
        Args:
            api_session: API 请求会话
        """
        self.api_session = api_session
    
    def fetch_announcements(
        self,
        code: str,
        orgId: Optional[str],
        column_api: str
    ) -> List[dict]:
        """
        获取IPO招股说明书公告列表
        
        Args:
            code: 股票代码
            orgId: 组织ID（可选）
            column_api: 交易所API列名
            
        Returns:
            公告列表
        """
        return fetch_ipo_announcements(
            self.api_session, code, orgId, column_api
        )
    
    def pick_latest_announcement(
        self,
        anns: List[dict],
        code: str
    ) -> Optional[dict]:
        """
        选择最新的招股说明书公告
        
        Args:
            anns: 公告列表
            code: 股票代码
            
        Returns:
            最新的匹配公告
        """
        return pick_latest_ipo(anns, code)
