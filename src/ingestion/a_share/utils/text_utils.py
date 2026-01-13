# -*- coding: utf-8 -*-
"""
文本处理工具函数
"""

import re
import unicodedata
from typing import Pattern

from ..config import EXCLUDE_IN_TITLE


def normalize_text(s: str) -> str:
    """
    标准化文本（Unicode规范化 + 去除空格 + 转小写）
    
    Args:
        s: 原始文本
        
    Returns:
        标准化后的文本
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"\s+", "", s).lower()


def q_pattern(year: int, q: str) -> Pattern:
    """
    生成季度报告标题的正则表达式模式
    
    Args:
        year: 年份
        q: 季度 ("Q1", "Q2", "Q3", "Q4")
        
    Returns:
        编译后的正则表达式
    """
    y = str(year)
    pat = {
        "Q1": rf"{y}年(?:(?:第?一)|一|1)(?:季度报告|季报)",
        "Q2": rf"{y}年(?:半年度|半年)报告",
        "Q3": rf"{y}年(?:(?:第?三)|三|3)(?:季度报告|季报)",
        "Q4": rf"{y}年?(?:年度报告|年报)",  # Fixed: 年? makes it match both "2023年度报告" and "2023年年度报告"
    }[q]
    return re.compile(pat)


def title_ok(title: str, year: int, quarter: str) -> bool:
    """
    检查标题是否符合指定年份和季度的报告格式
    
    Args:
        title: 公告标题
        year: 年份
        quarter: 季度
        
    Returns:
        True 如果标题匹配
    """
    t = normalize_text(title)
    if any(k in t for k in map(normalize_text, EXCLUDE_IN_TITLE)):
        return False
    return q_pattern(year, quarter).search(t) is not None
