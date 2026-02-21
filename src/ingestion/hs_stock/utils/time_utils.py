# -*- coding: utf-8 -*-
"""
时间处理工具函数
"""

from typing import List
from datetime import datetime


def build_se_windows(year: int, quarter: str) -> List[str]:
    """
    构建查询时间窗口（用于API查询）
    
    Args:
        year: 年份
        quarter: 季度 ("Q1", "Q2", "Q3", "Q4")
        
    Returns:
        时间窗口列表，格式: ["YYYY-MM-DD~YYYY-MM-DD"]
    """
    if quarter in ("Q1", "Q2", "Q3"):
        return [f"{year}-01-01~{year}-12-31"]
    # Q4 跨年
    return [f"{year}-10-01~{year}-12-31", f"{year+1}-01-01~{year+1}-06-30"]


def parse_time_to_ms(t) -> int:
    """
    解析时间戳（毫秒）
    
    Args:
        t: 时间戳（整数、浮点数或字符串）
        
    Returns:
        毫秒时间戳
    """
    if isinstance(t, (int, float)):
        return int(t)
    if isinstance(t, str):
        try:
            return int(datetime.strptime(t, "%Y-%m-%d %H:%M").timestamp() * 1000)
        except Exception:
            return 0
    return 0


def ms_to_ddmmyyyy(ms: int) -> str:
    """
    将毫秒时间戳转换为 DD-MM-YYYY 格式
    
    Args:
        ms: 毫秒时间戳
        
    Returns:
        格式化的日期字符串，失败返回 "NA"
    """
    try:
        return datetime.fromtimestamp(ms/1000).strftime("%d-%m-%Y")
    except Exception:
        return "NA"
