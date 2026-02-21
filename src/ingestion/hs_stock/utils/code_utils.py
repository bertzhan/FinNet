# -*- coding: utf-8 -*-
"""
代码处理工具函数
"""

import logging
from typing import Tuple, Optional, List, Dict

from .text_utils import normalize_text

logger = logging.getLogger(__name__)


def normalize_code(code) -> str:
    """
    标准化股票代码（6位数字，不足补0）
    
    Args:
        code: 股票代码（字符串或数字）
        
    Returns:
        标准化后的6位代码字符串
    """
    s = str(code).strip()
    try:
        s = str(int(float(s)))
    except Exception:
        pass
    return s.zfill(6)


def detect_exchange(code: str) -> Tuple[str, str, str]:
    """
    检测股票代码所属交易所
    
    Returns:
        (exchange_dir, column_api, stock_suffix)
        - exchange_dir: 保存目录名 "SZ"/"SH"/"BJ"
        - column_api:   接口 column "szse"/"sse"  (注意：上海用 sse 不是 shse，北京也用 szse)
        - stock_suffix: stock=code.<suffix> 用 ".SZ/.SH/.BJ"
    """
    s = str(code)
    # 按照从具体到一般的顺序匹配，避免前缀重叠
    if s.startswith("688"):  # 科创板
        return "SH", "sse", "SH"
    elif s.startswith("6"):  # 上海主板
        return "SH", "sse", "SH"
    elif s.startswith(("300", "301")):  # 创业板
        return "SZ", "szse", "SZ"
    elif s.startswith(("000", "001", "002", "003")):  # 深圳主板/中小板
        return "SZ", "szse", "SZ"
    elif s.startswith(("8", "43", "83")):  # 北京交易所
        return "BJ", "szse", "BJ"
    else:
        # 未识别的代码，默认深圳
        logger.debug(f"未识别的股票代码: {s}，默认使用深圳交易所")
        return "SZ", "szse", "SZ"


def detect_code_change(anns: List[dict], requested_code: str, orgId: str) -> Optional[str]:
    """
    检测股票代码变更（改进版：避免合并重组误判）
    如果公告中的股票代码与请求的代码不一致，返回实际代码

    Args:
        anns: 公告列表
        requested_code: 请求的股票代码
        orgId: 组织ID

    Returns:
        实际股票代码，如果没有变更则返回 None
    """
    if not anns:
        return None

    requested_code_normalized = normalize_code(requested_code)

    # 统计公告中出现的所有股票代码和对应的公司名称
    code_info = {}  # {code: {"count": int, "names": set}}
    for ann in anns:
        code = normalize_code(str(ann.get("secCode", "")))
        name = normalize_text(str(ann.get("secName", "")))

        if code and code != "000000":
            if code not in code_info:
                code_info[code] = {"count": 0, "names": set()}
            code_info[code]["count"] += 1
            if name:
                code_info[code]["names"].add(name)

    if not code_info:
        return None

    # 找出出现最多的股票代码
    most_common_code = max(code_info.keys(), key=lambda k: code_info[k]["count"])

    # 如果最常见的代码与请求的代码不同
    if most_common_code != requested_code_normalized:
        # 检查公司名称是否一致（避免合并重组误判）
        requested_names = code_info.get(requested_code_normalized, {}).get("names", set())
        most_common_names = code_info[most_common_code]["names"]

        # 计算名称相似度
        name_overlap = requested_names & most_common_names  # 交集

        # 如果有相同的公司名称，或者请求的代码没有公告（纯代码变更场景）
        if name_overlap or not requested_names:
            logger.warning(
                f"[代码变更检测] orgId={orgId}: 请求代码 {requested_code_normalized} -> 实际代码 {most_common_code} "
                f"(公司名称: {', '.join(list(most_common_names)[:2])})"
            )
            return most_common_code
        else:
            # 公司名称完全不同，可能是合并重组，不判定为代码变更
            logger.info(
                f"[代码变更检测] orgId={orgId}: 检测到不同股票代码，但公司名称不一致，疑似合并重组，不作变更处理 "
                f"(请求: {requested_code_normalized}={requested_names}, 最多: {most_common_code}={most_common_names})"
            )

    return None


def get_all_related_codes(code: str, orgId: Optional[str], code_change_cache: Dict[str, List[str]]) -> List[str]:
    """
    获取与给定代码相关的所有历史代码

    Args:
        code: 当前股票代码
        orgId: 组织ID
        code_change_cache: 代码变更缓存

    Returns:
        相关代码列表（包括当前代码）
    """
    code_normalized = normalize_code(code)
    related_codes = [code_normalized]

    if orgId and orgId in code_change_cache:
        cached_codes = code_change_cache[orgId]
        for c in cached_codes:
            c_norm = normalize_code(c)
            if c_norm not in related_codes:
                related_codes.append(c_norm)

    return related_codes
