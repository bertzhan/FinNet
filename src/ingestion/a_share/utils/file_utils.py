# -*- coding: utf-8 -*-
"""
文件操作工具函数
"""

import os
import json
import csv
import time
import glob
import platform
import logging
from typing import Optional, List, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..config import (
    CNINFO_STATIC, PROXIES, RETRY_TIMES, RETRY_STATUS, RETRY_BACKOFF,
    CSV_ENCODING, HEADERS_API
)
from .code_utils import normalize_code

logger = logging.getLogger(__name__)


def make_session(headers) -> requests.Session:
    """
    创建带重试机制的 HTTP Session
    
    Args:
        headers: HTTP 请求头
        
    Returns:
        配置好的 requests.Session
    """
    s = requests.Session()
    s.headers.update(headers)
    retry = Retry(
        total=RETRY_TIMES,
        status_forcelist=list(RETRY_STATUS),
        allowed_methods=frozenset(["GET", "POST"]),
        backoff_factor=RETRY_BACKOFF,
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)

    # 关键：访问主页建立会话，获取 JSESSIONID Cookie
    try:
        s.get("https://www.cninfo.com.cn/", timeout=10, proxies=PROXIES)
        logger.debug("会话已建立（获取 JSESSIONID）")
    except Exception as e:
        logger.warning(f"建立会话失败: {e}")

    return s


def ensure_dir(p: str):
    """
    确保目录存在（不存在则创建）
    
    Args:
        p: 目录路径
    """
    os.makedirs(p, exist_ok=True)


def pdf_url_from_adj(adj: str) -> str:
    """
    从附件URL构建完整的PDF URL
    
    Args:
        adj: 附件URL（相对路径）
        
    Returns:
        完整的PDF URL
    """
    return CNINFO_STATIC + (adj or "").lstrip("/")


def load_json(path, default):
    """
    加载JSON文件
    
    Args:
        path: 文件路径
        default: 默认值（文件不存在或解析失败时返回）
        
    Returns:
        解析后的JSON对象或默认值
    """
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    """
    保存JSON文件，带重试机制（解决Windows文件锁定问题）
    
    Args:
        path: 文件路径
        obj: 要保存的对象
    """
    tmp = path + ".tmp"
    max_retries = 5
    retry_delay = 0.1

    for attempt in range(max_retries):
        try:
            # 写入临时文件
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
            # 确保文件已关闭
            time.sleep(0.01)

            # 原子替换（Windows上可能失败，需要重试）
            if os.path.exists(path):
                # Windows: 先删除目标文件，再重命名
                if platform.system().lower().startswith("win"):
                    try:
                        os.remove(path)
                        time.sleep(0.02)  # 等待文件句柄释放
                    except (PermissionError, OSError):
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay * (2 ** attempt))
                            continue
                        raise
            os.rename(tmp, path)
            return
        except (PermissionError, OSError) as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (2 ** attempt))
                continue
            # 最后一次尝试失败，记录错误
            logger.warning(f"保存JSON文件失败（{path}）: {e}")
            # 清理临时文件
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except:
                    pass
            raise


def read_tasks_from_csv(path: str, default_year: Optional[int] = None, default_quarter: Optional[str] = None):
    """
    读取 CSV 任务文件，自动检测编码
    尝试顺序: UTF-8-sig -> UTF-8 -> GBK (Windows) -> GB2312
    
    Args:
        path: CSV文件路径
        default_year: 默认年份（如果CSV中没有year列）
        default_quarter: 默认季度（如果CSV中没有quarter列）
        
    Returns:
        任务列表，每个任务为 (code, name, year, quarter) 元组
    """
    encodings = ["utf-8-sig", "utf-8"]
    if platform.system().lower().startswith("win"):
        encodings.extend(["gbk", "gb2312"])

    for enc in encodings:
        try:
            with open(path, "r", encoding=enc, newline="", errors="replace") as f:
                reader = csv.DictReader(f)
                tasks = []
                for row in reader:
                    raw_code = row.get("code", "").strip()
                    name = row.get("name", "").strip()
                    year_str = row.get("year", "").strip()
                    quarter = row.get("quarter", "").strip()

                    if not raw_code or not name:
                        continue

                    # 规范化股票代码（如 "1" -> "000001"）
                    code = normalize_code(raw_code)
                    if not code:
                        logger.warning(f"无法规范化股票代码: {raw_code}，跳过")
                        continue

                    year = int(year_str) if year_str else default_year
                    if not year:
                        continue

                    if not quarter:
                        quarter = default_quarter or "Q4"

                    tasks.append((code, name, year, quarter))

                return tasks
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.error(f"读取CSV文件失败 ({enc}): {e}")
            break

    return []


def build_existing_pdf_cache(old_pdf_dir: Optional[str]) -> set:
    """
    扫描旧PDF目录，构建已存在文件的缓存（一次性扫描）

    Args:
        old_pdf_dir: 旧PDF目录路径

    Returns:
        set of (code, year, quarter) tuples
    """
    if not old_pdf_dir or not os.path.exists(old_pdf_dir):
        return set()

    cache = set()
    print(f"🔍 扫描旧PDF目录：{old_pdf_dir}")

    # 扫描所有交易所目录
    for exchange in ["SZ", "SH", "BJ"]:
        exchange_dir = os.path.join(old_pdf_dir, exchange)
        if not os.path.exists(exchange_dir):
            continue

        # 使用glob递归查找所有PDF文件
        pattern = os.path.join(exchange_dir, "**", "*.pdf")
        pdf_files = glob.glob(pattern, recursive=True)

        for pdf_path in pdf_files:
            # 解析文件名：code_year_quarter_date.pdf
            filename = os.path.basename(pdf_path)
            parts = filename.replace(".pdf", "").split("_")

            if len(parts) >= 3:
                code_raw = parts[0]
                year_str = parts[1]
                quarter = parts[2]

                try:
                    year = int(year_str)
                    code = normalize_code(code_raw)  # 标准化代码，确保匹配
                    cache.add((code, year, quarter))
                except ValueError:
                    continue

    print(f"✅ 找到 {len(cache)} 个已存在的报告")
    return cache


def check_pdf_exists_in_cache(cache: set, code: str, year: int, quarter: str) -> bool:
    """
    检查PDF是否在缓存中（O(1)查找，无I/O）

    Args:
        cache: 已存在文件的缓存集合
        code: 股票代码
        year: 年份
        quarter: 季度

    Returns:
        True 如果文件存在于缓存中
    """
    return (code, year, quarter) in cache
