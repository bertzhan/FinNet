# -*- coding: utf-8 -*-
"""
OrgID 解析器
提供多种方法获取股票代码对应的 orgId
"""

import logging
import re
from typing import Optional, Tuple
from datetime import datetime
from urllib.parse import urlencode, urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

from ..config import CNINFO_API, CNINFO_SEARCH, PROXIES, HEADERS_HTML
from ..utils.code_utils import normalize_code, detect_exchange
from ..utils.file_utils import make_session

logger = logging.getLogger(__name__)


def build_orgid(code: str) -> str:
    """
    根据股票代码构造 orgId（仅适用于部分公司）
    - 深圳: gssz + 0 + code (如 gssz0000001, 7位)
    - 上海: gssh + 0 + code (如 gssh0600519, 7位)
    - 北京: gsbj + 0 + code (如 gsbj0430001, 7位)
    注意：此方法仅对部分公司有效，其他公司需使用其他方法查询
    """
    exch_dir, _, _ = detect_exchange(code)
    code6 = normalize_code(code)
    code7 = f"0{code6}"  # 7位：前面补一个 0

    if exch_dir == "SH":
        return f"gssh{code7}"
    elif exch_dir == "BJ":
        return f"gsbj{code7}"
    else:  # SZ
        return f"gssz{code7}"


def get_orgid_via_search_api(api_session: requests.Session, code: str) -> Optional[Tuple[str, str]]:
    """
    通过搜索API获取orgId（推荐方法 - 简单可靠）
    使用 /new/information/topSearch/query 接口
    优势：不需要公司名，直接用股票代码查询

    Args:
        api_session: requests会话
        code: 股票代码

    Returns:
        (orgId, company_name) 或 None
    """
    code6 = normalize_code(code)

    # 正确的URL（不是detailOfQuery，而是query）
    url = "https://www.cninfo.com.cn/new/information/topSearch/query"

    # 直接用股票代码查询（不需要前缀）
    try:
        r = api_session.post(url, data={"keyWord": code6}, timeout=10, proxies=PROXIES)
        if r.status_code == 200:
            # 返回的是数组，不是keyBoardList
            js = r.json()
            if isinstance(js, list) and len(js) > 0:
                for item in js:
                    # 精确匹配股票代码
                    if item.get("code", "") == code6:
                        orgid = item.get("orgId")
                        company_name = item.get("zwjc", "")
                        if orgid:
                            logger.info(f"[orgId] 通过搜索API获取成功：{orgid} ({company_name})")
                            return orgid, company_name
    except Exception as e:
        logger.debug(f"搜索API查询失败 (code={code6}): {e}")

    return None


def get_orgid_by_searchkey(api_session: requests.Session, code: str, name: str, column_api: str) -> Optional[Tuple[str, str]]:
    """
    通过 searchkey 搜索公司名，从返回结果中提取真实的 orgId 和公司名称
    这是兜底方法，当搜索API失败时使用

    Returns:
        (orgId, company_name) 或 None
    """
    code6 = normalize_code(code)

    payload = {
        "stock": "",
        "column": column_api,
        "category": "",
        "seDate": f"{datetime.now().year-1}-01-01~{datetime.now().year}-12-31",
        "pageNum": "1",
        "pageSize": "30",
        "tabName": "fulltext",
        "searchkey": name,
        "plate": "",
    }

    try:
        logger.debug(f"使用 searchkey='{name}' 查询 orgId...")
        r = api_session.post(CNINFO_API, data=payload, timeout=20, proxies=PROXIES)
        if r.status_code == 200:
            data = r.json()
            anns = data.get("announcements") or []

            logger.debug(f"searchkey 返回 {len(anns)} 条公告")

            for ann in anns:
                ann_code = str(ann.get("secCode", "")).zfill(6)
                if ann_code == code6:
                    oid = ann.get("orgId")
                    sec_name = ann.get("secName", "")
                    if oid:
                        logger.info(f"[orgId] 通过 searchkey 获取成功：{oid} ({sec_name})")
                        return oid, sec_name

            logger.warning(f"searchkey 返回公告中未找到匹配的股票代码 {code6}")
            if anns and len(anns) > 0:
                logger.debug(f"前5条公告的股票代码: {[ann.get('secCode') for ann in anns[:5]]}")
        else:
            logger.warning(f"searchkey 请求失败: HTTP {r.status_code}")
    except Exception as e:
        logger.warning(f"searchkey 查询异常：{e}")

    return None


def get_orgid_via_html(code: str, name: Optional[str], html_session: Optional[requests.Session] = None) -> Optional[Tuple[str, str]]:
    """
    改进版：访问检索页并解析首条详情链接中的 orgId
    支持多种搜索关键词，返回 (orgId, 公司名称)

    Args:
        code: 股票代码
        name: 公司名称（可选，用于日志）
        html_session: 可复用的会话（可选）

    Returns:
        (orgId, company_name) 或 None
    """
    code6 = normalize_code(code)
    exch_dir, column_api, stock_suffix = detect_exchange(code6)

    # 创建或复用会话
    if html_session is None:
        html_session = make_session(HEADERS_HTML)

    # 尝试多种搜索关键词
    search_keywords = ["年度报告", "季度报告", ""]  # 空字符串表示不限定报告类型

    for keyword in search_keywords:
        params = {
            "stock": code6,
            "searchkey": keyword,
            "category": column_api,
            "pageNum": 1,
        }
        url = f"{CNINFO_SEARCH}?{urlencode(params, safe='')}"

        logger.info(f"[HTML兜底] 尝试搜索关键词'{keyword}'：{code6}")

        try:
            r = html_session.get(url, timeout=20, proxies=PROXIES)
            if r.status_code != 200:
                logger.debug(f"HTML 检索失败：HTTP {r.status_code}")
                continue

            soup = BeautifulSoup(r.text, "html.parser")

            # 方法1：解析列表页的详情链接
            main = soup.find("div", class_="list-main")
            if main:
                items = main.find_all("div", class_="list-item")
                logger.debug(f"找到 {len(items)} 条公告")

                for item in items[:5]:  # 检查前5条
                    # 提取公司名称
                    company_span = item.find("span", class_="company-name")
                    company_name = company_span.get_text(strip=True) if company_span else ""

                    # 提取详情链接
                    a = item.select_one("span.ahover.ell a")
                    if not a or not a.get("href"):
                        continue

                    detail_url = urljoin("https://www.cninfo.com.cn", a["href"])
                    qs = parse_qs(urlparse(detail_url).query)
                    oid = (qs.get("orgId") or [""])[0]

                    # 验证股票代码是否匹配
                    stock_code = (qs.get("stockCode") or [""])[0]
                    if stock_code and normalize_code(stock_code) == code6:
                        if oid:
                            logger.info(f"[HTML兜底] 成功解析 orgId：{oid} ({company_name})")
                            return oid, company_name

            # 方法2：从页面脚本中提取 orgId（备用）
            scripts = soup.find_all("script")
            for script in scripts:
                script_text = script.string or ""
                # 查找类似 "orgId":"9900012345" 的模式
                matches = re.findall(r'"orgId"\s*:\s*"([^"]+)"', script_text)
                if matches:
                    oid = matches[0]
                    logger.info(f"[HTML兜底] 从脚本中解析 orgId：{oid}")
                    return oid, name or ""

        except Exception as e:
            logger.debug(f"HTML 解析异常 (keyword={keyword}): {e}")
            continue

    logger.warning(f"[HTML兜底] 所有搜索关键词均失败：{code6}")
    return None


def get_orgid(code: str, name: Optional[str]) -> Optional[str]:
    """
    对外统一入口：HTML scraping fallback
    注意：此函数已不再使用，保留仅供向后兼容
    """
    code6 = normalize_code(code)
    result = get_orgid_via_html(code6, name)
    return result[0] if result else None


class OrgIDResolver:
    """
    OrgID 解析器类
    提供统一的接口获取股票代码对应的 orgId
    """
    
    def __init__(self, api_session: requests.Session, html_session: Optional[requests.Session] = None):
        """
        Args:
            api_session: API 请求会话
            html_session: HTML 请求会话（可选）
        """
        self.api_session = api_session
        self.html_session = html_session
    
    def resolve(self, code: str, name: Optional[str] = None) -> Optional[str]:
        """
        解析 orgId（按优先级尝试多种方法）
        
        Args:
            code: 股票代码
            name: 公司名称（可选）
            
        Returns:
            orgId 或 None
        """
        # 方法1：构造 orgId（快速但可能不准确）
        orgid = build_orgid(code)
        
        # 方法2：通过搜索API获取（推荐）
        result = get_orgid_via_search_api(self.api_session, code)
        if result:
            return result[0]
        
        # 方法3：通过 searchkey 获取
        if name:
            _, column_api, _ = detect_exchange(code)
            result = get_orgid_by_searchkey(self.api_session, code, name, column_api)
            if result:
                return result[0]
        
        # 方法4：HTML 解析（兜底）
        html_session = self.html_session or make_session(HEADERS_HTML)
        result = get_orgid_via_html(code, name, html_session)
        if result:
            return result[0]
        
        # 如果所有方法都失败，返回构造的 orgId（可能不准确）
        return orgid
