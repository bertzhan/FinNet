# -*- coding: utf-8 -*-
"""
CNINFO API 客户端
"""

import logging
from typing import List, Optional, Dict

import requests
from requests.exceptions import RequestException

from ..config import CNINFO_API, PROXIES, CATEGORY_MAP, CATEGORY_ALL
from ..utils.code_utils import detect_exchange, normalize_code
from ..utils.time_utils import build_se_windows
from ..utils.text_utils import title_ok

logger = logging.getLogger(__name__)


def fetch_anns_by_category(
    api_session: requests.Session,
    code: str,
    orgId: Optional[str],
    column_api: str,
    year: int,
    quarter: str,
    page_size: int = 100
) -> List[dict]:
    """
    使用类别过滤的公告抓取（推荐方法）
    - 直接使用对应季度的类别，服务器端过滤，更可靠
    - 避免复杂的标题正则匹配和标题格式变化问题
    - 优先使用 stock="<code>,<orgId>"；若无 orgId，则退化为 stock="<code>.<EX>"
    """
    _, _, stock_suffix = detect_exchange(code)
    stock_field = f"{code},{orgId}" if orgId else f"{code}.{stock_suffix}"

    # 使用季度对应的具体类别，而不是 CATEGORY_ALL
    category = CATEGORY_MAP.get(quarter, CATEGORY_ALL)
    
    # 调试：记录类别映射结果
    if category == CATEGORY_ALL:
        logger.warning(f"[{code}] 季度 '{quarter}' 未在 CATEGORY_MAP 中找到，使用 CATEGORY_ALL")
    else:
        logger.debug(f"[{code}] 季度 '{quarter}' 映射到类别: {category}")
    
    # 构建时间窗口
    se_windows = build_se_windows(year, quarter)
    logger.debug(f"[{code}] 时间窗口: {se_windows}")

    all_list: List[dict] = []
    for seDate in se_windows:
        page = 1
        while True:
            payload = {
                "tabName": "fulltext",
                "column": column_api,
                "stock": stock_field,
                "category": category,  # 使用具体类别
                "seDate": seDate,
                "pageNum": str(page),
                "pageSize": str(page_size),
                "searchkey": "",
                "plate": "",
                "isHLtitle": "true",
            }
            logger.debug(f"[API请求] stock={stock_field}, category={category}, seDate={seDate}, page={page}")
            data = None
            try:
                data = api_session.post(CNINFO_API, data=payload, timeout=20, proxies=PROXIES)
                if data.status_code >= 400:
                    logger.warning(f"hisAnnouncement HTTP {data.status_code} ({code} 页 {page})")
                    break
                response_text = data.text.strip()
                if not response_text.startswith("{"):
                    logger.warning(f"[API] 返回非JSON内容: {response_text[:200]}")
                    break
                data = data.json()
            except RequestException as e:
                logger.warning(f"hisAnnouncement 请求异常（{code} 页 {page}）：{e}")
                break
            except Exception as e:
                logger.warning(f"[API] JSON解析失败: {e}, 响应: {data.text[:200] if data else 'None'}")
                break

            anns = (data or {}).get("announcements") or []
            logger.debug(f"[API响应] 返回 {len(anns)} 条公告 (seDate={seDate})")
            if not anns:
                break
            all_list.extend(anns)
            if len(anns) < page_size:
                break
            page += 1
    return all_list


def fetch_anns(
    api_session: requests.Session,
    code: str,
    orgId: Optional[str],
    column_api: str,
    year: int,
    quarter: str,
    page_size: int = 100
) -> List[dict]:
    """
    多时间窗、分页抓取并合并
    优先使用 stock="<code>,<orgId>"；若无 orgId，则退化为 stock="<code>.<EX>"

    注意：此函数保留向后兼容，但推荐使用 fetch_anns_by_category() 获得更可靠的结果
    """
    _, _, stock_suffix = detect_exchange(code)
    stock_field = f"{code},{orgId}" if orgId else f"{code}.{stock_suffix}"

    all_list: List[dict] = []
    for seDate in build_se_windows(year, quarter):
        page = 1
        while True:
            payload = {
                "tabName": "fulltext",
                "column": column_api,
                "stock": stock_field,
                "category": CATEGORY_ALL,
                "seDate": seDate,
                "pageNum": str(page),  # 转为字符串
                "pageSize": str(page_size),  # 转为字符串
                "searchkey": "",
                "plate": "",
                "isHLtitle": "true",
            }
            logger.debug(f"[API请求 CATEGORY_ALL] stock={stock_field}, seDate={seDate}, page={page}")
            data = None
            try:
                # 关键修改：使用 data= 而不是 json=（form-data 格式）
                data = api_session.post(CNINFO_API, data=payload, timeout=20, proxies=PROXIES)
                if data.status_code >= 400:
                    logger.warning(f"hisAnnouncement HTTP {data.status_code} ({code} 页 {page})")
                    break
                response_text = data.text.strip()
                if not response_text.startswith("{"):
                    logger.warning(f"[API] 返回非JSON内容: {response_text[:200]}")
                    break
                data = data.json()
            except RequestException as e:
                logger.warning(f"hisAnnouncement 请求异常（{code} 页 {page}）：{e}")
                break
            except Exception as e:
                logger.warning(f"[API] JSON解析失败: {e}, 响应: {data.text[:200] if data else 'None'}")
                break

            anns = (data or {}).get("announcements") or []
            logger.debug(f"[API响应] 返回 {len(anns)} 条公告 (seDate={seDate})")
            if not anns:
                break
            all_list.extend(anns)
            if len(anns) < page_size:
                break
            page += 1
    return all_list


def pick_latest(
    anns: List[dict],
    code: str,
    year: int,
    quarter: str,
    related_codes: Optional[List[str]] = None
) -> Optional[dict]:
    """
    从公告列表中选择最新的匹配报告
    
    Args:
        anns: 公告列表
        code: 主要股票代码
        year: 年份
        quarter: 季度
        related_codes: 相关股票代码列表（用于处理代码变更）
        
    Returns:
        最新的匹配公告，如果没有则返回 None
    """
    from ..utils.time_utils import parse_time_to_ms
    
    # 如果没有提供相关代码，使用主代码
    if related_codes is None:
        related_codes = [normalize_code(code)]
    else:
        related_codes = [normalize_code(c) for c in related_codes]
    
    cands = []
    for a in anns:
        ann_code = normalize_code(str(a.get("secCode", "")))
        
        # 检查是否匹配任何相关代码
        if ann_code not in related_codes:
            continue
            
        title = a.get("announcementTitle", "")
        if not title_ok(title, year, quarter):
            continue
        adj = a.get("adjunctUrl", "")
        if not adj or not adj.lower().endswith(".pdf"):
            continue
        ts = parse_time_to_ms(a.get("announcementTime"))
        cands.append((ts, a, ann_code))  # 保存实际代码
    
    if not cands:
        return None
    cands.sort(key=lambda x: x[0], reverse=True)
    
    # 如果使用的是非主代码，记录日志
    best_ann = cands[0][1]
    actual_code = cands[0][2]
    if actual_code != normalize_code(code):
        logger.info(f"[代码变更] 使用历史代码 {actual_code} 找到报告（请求代码: {normalize_code(code)}）")
    
    return best_ann


class CNInfoAPIClient:
    """
    CNINFO API 客户端类
    封装公告查询相关功能
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
        year: int,
        quarter: str,
        use_category: bool = True
    ) -> List[dict]:
        """
        获取公告列表
        
        Args:
            code: 股票代码
            orgId: 组织ID（可选）
            year: 年份
            quarter: 季度
            use_category: 是否使用类别过滤（推荐）
            
        Returns:
            公告列表
        """
        _, column_api, _ = detect_exchange(code)
        
        if use_category:
            return fetch_anns_by_category(
                self.api_session, code, orgId, column_api, year, quarter
            )
        else:
            return fetch_anns(
                self.api_session, code, orgId, column_api, year, quarter
            )
    
    def pick_latest_announcement(
        self,
        anns: List[dict],
        code: str,
        year: int,
        quarter: str,
        related_codes: Optional[List[str]] = None
    ) -> Optional[dict]:
        """
        选择最新的匹配公告
        
        Args:
            anns: 公告列表
            code: 主要股票代码
            year: 年份
            quarter: 季度
            related_codes: 相关股票代码列表
            
        Returns:
            最新的匹配公告
        """
        return pick_latest(anns, code, year, quarter, related_codes)
