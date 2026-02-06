#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
港交所披露易 - 港股上市公司报告爬虫（增强版）
功能：批量下载港股公司的年报、中报、季报PDF文件
新增：
  1. 筛选真实财务报表，排除通告、函件等非报表文件
  2. 集成股票列表下载功能，自动从香港交易所获取最新上市公司列表
  3. 详细的下载日志系统（CSV/Excel格式）
  4. 自动依赖安装功能
  5. stockId补全和异动监测功能
  
"""

import argparse
import glob
import json
import logging
import os
import random
import re
import sys
import time
import hashlib
import threading
from dataclasses import dataclass
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 依赖检测
REQUIRED_PACKAGES = ['requests', 'pandas', 'openpyxl', 'akshare']
def ensure_required_packages():
    missing = []
    for package in REQUIRED_PACKAGES:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    if missing:
        print("\n" + "="*70)
        print("缺少必要依赖包，请先安装后再运行脚本：")
        for package in missing:
            print(f"  pip install {package}")
        print("="*70 + "\n")
        sys.exit(1)

ensure_required_packages()

import requests
import pandas as pd
import akshare as ak
from bs4 import BeautifulSoup


DEFAULT_START_YEAR = 2022
DEFAULT_END_YEAR = 2025
DEFAULT_MAX_WORKERS = 10
DEFAULT_LOG_FORMAT = "excel"
DEFAULT_RUNTIME_LOG_NAME = "crawler_runtime.log"

HKEX_BASE_URL = "https://www1.hkexnews.hk/search/titlesearch.xhtml"
HKEX_PDF_BASE = "https://www1.hkexnews.hk"
HKEX_ACTIVE_STOCK_URL = "https://www1.hkexnews.hk/ncms/script/eds/activestock_sehk_c.json"
HKEX_INACTIVE_STOCK_URL = "https://www1.hkexnews.hk/ncms/script/eds/inactivestock_sehk_c.json"
HKEX_PARTIAL_API_URL = "https://www1.hkexnews.hk/search/partial.do"
HKEX_OUTPUT_ENCODING = "utf-8-sig"
HKEX_PARTIAL_DELAY = 0.2
HKEX_REQUEST_TIMEOUT = 30
STOCK_JSON_DIR = Path(__file__).resolve().parent / "stockid_json"
STOCK_JSON_SNAPSHOT_DIR = STOCK_JSON_DIR / "snapshots"
STOCK_JSON_ALERT_DIR = STOCK_JSON_DIR / "alerts"
STOCK_JSON_ALERT_ABS_THRESHOLD = 50
STOCK_JSON_ALERT_PERCENT_THRESHOLD = 0.05

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

MODULE_LOGGER = logging.getLogger("hkex_crawler")


class ConsoleMessenger:
    """统一处理控制台输出与日志写入。"""

    def __init__(self, logger: Optional[logging.Logger] = None, enable_stdout: bool = True):
        self.logger = logger or logging.getLogger(__name__)
        self.enable_stdout = enable_stdout

    def log(self, level: str, message: str) -> None:
        if self.enable_stdout:
            print(message)
        log_func = getattr(self.logger, level, self.logger.info)
        log_func(message)

    def info(self, message: str) -> None:
        self.log("info", message)

    def warning(self, message: str) -> None:
        self.log("warning", message)

    def error(self, message: str) -> None:
        self.log("error", message)


class AdaptiveRateLimiter:
    """线程安全的自适应限流器，用于动态控制请求节奏。"""

    def __init__(
        self,
        base_interval: float = 0.2,
        max_interval: float = 10.0,
        increase_factor: float = 1.5,
        heavy_increase_factor: float = 2.5,
        decrease_factor: float = 0.85,
    ):
        self.base_interval = max(0.01, base_interval)
        self.interval = self.base_interval
        self.max_interval = max_interval
        self.increase_factor = increase_factor
        self.heavy_increase_factor = heavy_increase_factor
        self.decrease_factor = decrease_factor
        self.lock = threading.Lock()
        self.last_request = 0.0

    def acquire(self) -> None:
        """在发起请求前调用，确保请求之间的间隔满足当前速率。"""
        with self.lock:
            now = time.time()
            wait_time = max(0.0, self.last_request + self.interval - now)
        if wait_time > 0:
            time.sleep(wait_time)
        with self.lock:
            self.last_request = time.time()

    def on_success(self) -> None:
        """请求成功后轻微放宽速率。"""
        with self.lock:
            self.interval = max(self.base_interval, self.interval * self.decrease_factor)

    def on_error(self) -> None:
        """请求一般性失败后适度降低速率。"""
        with self.lock:
            self.interval = min(self.max_interval, self.interval * self.increase_factor)

    def on_throttle(self) -> None:
        """被限流或服务器拒绝时显著降低速率。"""
        with self.lock:
            self.interval = min(self.max_interval, self.interval * self.heavy_increase_factor)

    def update_base_interval(self, new_base: float) -> None:
        """根据并发度调整基础间隔。"""
        with self.lock:
            self.base_interval = max(0.01, new_base)
            self.interval = max(self.interval, self.base_interval)


def _create_http_session(
    *,
    pool_connections: int = 20,
    pool_maxsize: int = 40,
    total_retries: int = 3,
    backoff_factor: float = 0.3,
    status_forcelist: Optional[Sequence[int]] = None,
) -> requests.Session:
    """创建带连接池和自动重试的 Session。"""
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


@dataclass
class HKEXDocType:
    key: str
    name: str
    t2code: str


@dataclass
class HKEXDocument:
    title: str
    href: str
    release_dt: datetime


FULLWIDTH_DIGITS = str.maketrans({chr(ord("０") + i): str(i) for i in range(10)})


def _hkex_normalize_release_text(release_text: str) -> str:
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


def _hkex_parse_release_datetime(release_text: str) -> datetime:
    normalized_text = _hkex_normalize_release_text(release_text)
    match = re.search(r"(\d{2}/\d{2}/\d{4})\s*(\d{2}:\d{2})?", normalized_text)
    if not match:
        match = re.search(r"(\d{2}/\d{2}/\d{4})\s*(\d{2}:\d{2})?", release_text)
    if not match:
        raise ValueError(f"Unrecognized release time format: {release_text}")

    date_part = match.group(1)
    time_part = match.group(2) or "00:00"
    dt_str = f"{date_part} {time_part}"
    return datetime.strptime(dt_str, "%d/%m/%Y %H:%M")


def _hkex_parse_documents(html: str) -> List[HKEXDocument]:
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
            release_dt = _hkex_parse_release_datetime(release_text)
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


def _hkex_parse_jsonp(text: str) -> dict:
    text = text.strip()
    prefix = "callback("
    if text.startswith(prefix):
        text = text[len(prefix) :]
        if text.endswith(");"):
            text = text[:-2]
        elif text.endswith(")"):
            text = text[:-1]
    return json.loads(text)


GLOBAL_HTTP_SESSION = _create_http_session()
GLOBAL_RATE_LIMITER = AdaptiveRateLimiter(base_interval=0.3, max_interval=6.0)


def _hkex_ensure_json_file(
    url: str,
    path: Path,
    *,
    session: Optional[requests.Session] = None,
    rate_limiter: Optional[AdaptiveRateLimiter] = None,
) -> None:
    if path.exists():
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    session = session or GLOBAL_HTTP_SESSION
    rate_limiter = rate_limiter or GLOBAL_RATE_LIMITER

    try:
        if rate_limiter:
            rate_limiter.acquire()
        response = session.get(url, timeout=30, headers=HKEX_HEADERS)
        if rate_limiter:
            if response.status_code == 200:
                rate_limiter.on_success()
            elif response.status_code in (403, 429):
                rate_limiter.on_throttle()
            else:
                rate_limiter.on_error()
        response.raise_for_status()
    except requests.RequestException as exc:
        if rate_limiter:
            status_code = getattr(exc.response, "status_code", None)
            if status_code in (403, 429):
                rate_limiter.on_throttle()
            else:
                rate_limiter.on_error()
        raise
    path.write_bytes(response.content)
    response.close()


def _hkex_build_code_map(data: Iterable[dict]) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    for item in data:
        code = str(item.get("c", "")).strip()
        stock_id = item.get("i")
        if not code or stock_id is None:
            continue
        mapping[code.zfill(5)] = int(stock_id)
    return mapping


def _hkex_load_stock_mapping(paths: Iterable[Path]) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    for path in paths:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        mapping.update(_hkex_build_code_map(data))
    return mapping


def _hkex_diff_stock_json(old_path: Path, new_path: Path) -> Tuple[Set[str], Set[str], Set[str], Dict[str, int], Dict[str, int]]:
    old_map = _hkex_build_code_map(json.loads(old_path.read_text(encoding="utf-8")))
    new_map = _hkex_build_code_map(json.loads(new_path.read_text(encoding="utf-8")))
    added = set(new_map) - set(old_map)
    removed = set(old_map) - set(new_map)
    changed = {code for code in new_map.keys() & old_map.keys() if new_map[code] != old_map[code]}
    return added, removed, changed, old_map, new_map


def _hkex_evaluate_stockid_changes(previous_snapshot: Path, current_snapshot: Path, category: str) -> None:
    try:
        added, removed, changed, old_map, new_map = _hkex_diff_stock_json(previous_snapshot, current_snapshot)
    except json.JSONDecodeError as exc:
        MODULE_LOGGER.warning("无法解析 stockId 快照差异 (%s): %s", category, exc, exc_info=True)
        return

    total_new = max(len(new_map), 1)
    percent_change = max(
        len(changed) / total_new,
        len(added) / total_new,
        len(removed) / total_new,
    )

    if (
        len(changed) >= STOCK_JSON_ALERT_ABS_THRESHOLD
        or len(added) >= STOCK_JSON_ALERT_ABS_THRESHOLD
        or len(removed) >= STOCK_JSON_ALERT_ABS_THRESHOLD
        or percent_change >= STOCK_JSON_ALERT_PERCENT_THRESHOLD
    ):
        alert_dir = (STOCK_JSON_ALERT_DIR / category)
        alert_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        alert_path = alert_dir / f"alert_{timestamp}.txt"

        summary_lines = [
            f"时间: {timestamp}",
            f"类别: {category}",
            f"总数量(旧): {len(old_map)}",
            f"总数量(新): {len(new_map)}",
            f"新增: {len(added)}",
            f"移除: {len(removed)}",
            f"变更: {len(changed)}",
            f"百分比变化: {percent_change:.2%}",
        ]

        if added:
            summary_lines.append("新增示例: " + ", ".join(sorted(added)[:10]))
        if removed:
            summary_lines.append("移除示例: " + ", ".join(sorted(removed)[:10]))
        if changed:
            changed_samples = [
                f"{code}:{old_map.get(code)}->{new_map.get(code)}"
                for code in sorted(changed)[:10]
            ]
            summary_lines.append("变更示例: " + ", ".join(changed_samples))

        alert_path.write_text("\n".join(summary_lines), encoding="utf-8")
        MODULE_LOGGER.warning(
            "stockId 变动告警(%s): 新增 %s, 移除 %s, 变更 %s，详情见 %s",
            category,
            len(added),
            len(removed),
            len(changed),
            alert_path,
        )


def _hkex_snapshot_stock_json(source_path: Path, category: str) -> None:
    if not source_path.exists():
        return

    snapshot_dir = STOCK_JSON_SNAPSHOT_DIR / category
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    source_bytes = source_path.read_bytes()
    existing_snapshots = sorted(snapshot_dir.glob(f"*_{source_path.name}"))

    if existing_snapshots:
        last_bytes = existing_snapshots[-1].read_bytes()
        if last_bytes == source_bytes:
            return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_path = snapshot_dir / f"{timestamp}_{source_path.name}"
    snapshot_path.write_bytes(source_bytes)

    if existing_snapshots:
        _hkex_evaluate_stockid_changes(existing_snapshots[-1], snapshot_path, category)


def _hkex_fetch_stock_id_from_partial(
    code: str,
    query: str,
    lang: str = "EN",
    *,
    session: Optional[requests.Session] = None,
    rate_limiter: Optional[AdaptiveRateLimiter] = None,
) -> Optional[int]:
    params = {
        "callback": "callback",
        "lang": lang,
        "type": "A",
        "name": query,
    }
    session = session or GLOBAL_HTTP_SESSION
    rate_limiter = rate_limiter or GLOBAL_RATE_LIMITER

    try:
        if rate_limiter:
            rate_limiter.acquire()
        response = session.get(HKEX_PARTIAL_API_URL, params=params, timeout=15, headers=HKEX_HEADERS)
        if rate_limiter:
            if response.status_code == 200:
                rate_limiter.on_success()
            elif response.status_code in (403, 429):
                rate_limiter.on_throttle()
            else:
                rate_limiter.on_error()
        response.raise_for_status()
    except requests.RequestException as exc:
        if rate_limiter:
            status_code = getattr(exc.response, "status_code", None)
            if status_code in (403, 429):
                rate_limiter.on_throttle()
            else:
                rate_limiter.on_error()
        raise
    data = _hkex_parse_jsonp(response.text)
    for item in data.get("stockInfo", []):
        candidate = str(item.get("code", "")).strip().zfill(5)
        if candidate == code:
            stock_id = item.get("stockId")
            if stock_id is not None:
                return int(stock_id)
    return None


def _hkex_supplement_mapping_with_partial(
    codes: Iterable[str],
    mapping: Dict[str, int],
    *,
    session: Optional[requests.Session] = None,
    rate_limiter: Optional[AdaptiveRateLimiter] = None,
) -> None:
    missing_codes = [code for code in codes if code not in mapping]
    session = session or GLOBAL_HTTP_SESSION
    rate_limiter = rate_limiter or GLOBAL_RATE_LIMITER

    for idx, code in enumerate(missing_codes, 1):
        queries = [code]
        stripped = code.lstrip("0")
        if stripped and stripped != code:
            queries.append(stripped)

        stock_id: Optional[int] = None
        for query in queries:
            for lang in ("EN", "ZH"):
                try:
                    stock_id = _hkex_fetch_stock_id_from_partial(
                        code,
                        query=query,
                        lang=lang,
                        session=session,
                        rate_limiter=rate_limiter,
                    )
                except requests.RequestException:
                    continue
                if stock_id is not None:
                    break
            if stock_id is not None:
                break

        if stock_id is not None:
            mapping[code] = stock_id
        if idx < len(missing_codes):
            time.sleep(HKEX_PARTIAL_DELAY)


def _hkex_append_stock_id_column(
    df: pd.DataFrame,
    stock_json_dir: Path,
    *,
    session: Optional[requests.Session] = None,
    rate_limiter: Optional[AdaptiveRateLimiter] = None,
) -> pd.DataFrame:
    active_json = stock_json_dir / "activestock_sehk_c.json"
    inactive_json = stock_json_dir / "inactivestock_sehk_c.json"
    session = session or GLOBAL_HTTP_SESSION
    rate_limiter = rate_limiter or GLOBAL_RATE_LIMITER

    _hkex_ensure_json_file(
        HKEX_ACTIVE_STOCK_URL,
        active_json,
        session=session,
        rate_limiter=rate_limiter,
    )
    _hkex_snapshot_stock_json(active_json, "active")
    _hkex_ensure_json_file(
        HKEX_INACTIVE_STOCK_URL,
        inactive_json,
        session=session,
        rate_limiter=rate_limiter,
    )
    _hkex_snapshot_stock_json(inactive_json, "inactive")

    mapping = _hkex_load_stock_mapping([active_json])
    codes = df["股份代號"].astype(str).str.strip().str.zfill(5)

    _hkex_supplement_mapping_with_partial(
        codes.unique(),
        mapping,
        session=session,
        rate_limiter=rate_limiter,
    )

    df = df.copy()
    df["股份代號"] = codes
    df["stockId"] = df["股份代號"].map(mapping)
    df["stockId"] = df["stockId"].apply(lambda x: int(x) if pd.notna(x) else pd.NA).astype("Int64")
    return df


def resolve_path(base_dir: str, path_value: Optional[str]) -> Optional[str]:
    """Resolve relative paths against the script directory."""
    if not path_value:
        return None
    if os.path.isabs(path_value):
        return os.path.normpath(path_value)
    return os.path.normpath(os.path.join(base_dir, path_value))


def setup_runtime_logger(log_dir: str) -> Tuple[logging.Logger, str]:
    """Initialize runtime logger with rotating file handler."""
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, DEFAULT_RUNTIME_LOG_NAME)

    logger = logging.getLogger("cninfo_runtime")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.propagate = False

    return logger, log_file


def parse_arguments(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments for scheduled or interactive runs."""
    parser = argparse.ArgumentParser(
        description="CNInfo HK report crawler (enhanced)"
    )
    parser.add_argument("--config", help="Path to JSON configuration for scheduled runs")
    parser.add_argument("--auto", action="store_true", help="Run in non-interactive mode using config/defaults")
    parser.add_argument("--non-interactive", action="store_true", help="Alias of --auto for backward compatibility")
    parser.add_argument("--company-range", help="Company range in 'start-end' (1-based inclusive) format")
    parser.add_argument("--start-idx", type=int, help="Company start index (1-based)")
    parser.add_argument("--end-idx", type=int, help="Company end index (1-based inclusive)")
    parser.add_argument("--year-range", help="Fiscal year range in 'start-end' format")
    parser.add_argument("--start-year", type=int, help="Fiscal year range start")
    parser.add_argument("--end-year", type=int, help="Fiscal year range end")
    parser.add_argument("--threads", type=int, help="Number of download threads")
    parser.add_argument("--max-workers", type=int, help="Alias for --threads")
    parser.add_argument("--skip-listing-update", action="store_true", help="Skip listing date update step")
    parser.add_argument("--force-download-list", action="store_true", help="Force refresh of HKEX stock list")
    parser.add_argument("--log-format", choices=["excel", "csv"], help="Log format for download logger")
    parser.add_argument("--stock-list", help="Path to stock list CSV file")
    parser.add_argument("--output-dir", help="Directory to store downloaded reports")
    parser.add_argument("--log-dir", help="Directory to store runtime/download logs")
    parser.add_argument("--listing-mode", choices=["1", "2", "3"], help="Listing date update mode")
    return parser.parse_args(argv)


def load_config_file(base_dir: str, config_path: Optional[str]) -> Dict:
    """Load JSON configuration file if provided."""
    if not config_path:
        return {}

    resolved_path = resolve_path(base_dir, config_path)
    if not resolved_path or not os.path.exists(resolved_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(resolved_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("配置文件内容必须为JSON对象")

    return data


def parse_company_range(value) -> Tuple[int, Optional[int]]:
    """Convert range input to zero-based start index and exclusive end index."""
    if value is None or value == "":
        return 0, None

    if isinstance(value, (list, tuple)) and len(value) == 2:
        start_raw, end_raw = value
    elif isinstance(value, str):
        if "-" not in value:
            raise ValueError("公司范围格式应为 '起始-结束'")
        start_raw, end_raw = value.split("-", 1)
    else:
        raise ValueError("无法解析公司范围配置")

    start = int(str(start_raw).strip())
    end = int(str(end_raw).strip())

    if start <= 0 or end <= 0:
        raise ValueError("公司序号必须为正整数")
    if end < start:
        raise ValueError("结束序号必须大于或等于起始序号")

    return start - 1, end


def parse_year_range(value, default_start: int, default_end: int) -> Tuple[int, int]:
    """Parse fiscal year range values."""
    if value is None or value == "":
        return default_start, default_end

    if isinstance(value, (list, tuple)) and len(value) == 2:
        start_raw, end_raw = value
    elif isinstance(value, str):
        if "-" not in value:
            raise ValueError("年份范围格式应为 '起始-结束'")
        start_raw, end_raw = value.split("-", 1)
    else:
        raise ValueError("无法解析年份范围配置")

    start_year = int(str(start_raw).strip())
    end_year = int(str(end_raw).strip())

    if end_year < start_year:
        raise ValueError("结束年份必须大于或等于起始年份")

    return start_year, end_year


def merge_settings(script_dir: str, args: argparse.Namespace, config: Dict) -> Dict:
    """Combine defaults, config values, and CLI overrides."""
    settings = {
        "stock_list_file": os.path.join(script_dir, "HKEX", "company_stockid.csv"),
        "output_dir": os.path.join(script_dir, "HKEX"),
        "log_dir": os.path.join(script_dir, "日志文件"),
        "log_format": DEFAULT_LOG_FORMAT,
        "start_idx": 0,
        "end_idx": None,
        "start_year": DEFAULT_START_YEAR,
        "end_year": DEFAULT_END_YEAR,
        "max_workers": DEFAULT_MAX_WORKERS,
        "update_listing": True,
        "force_download_list": False,
        "non_interactive": False,
        "listing_mode": "3",
    }

    # Apply configuration file values
    if config:
        stock_list_path = resolve_path(script_dir, config.get("stock_list_file"))
        if stock_list_path:
            settings["stock_list_file"] = stock_list_path

        output_dir = resolve_path(script_dir, config.get("output_dir"))
        if output_dir:
            settings["output_dir"] = output_dir

        log_dir = resolve_path(script_dir, config.get("log_dir"))
        if log_dir:
            settings["log_dir"] = log_dir

        if config.get("log_format"):
            settings["log_format"] = str(config["log_format"]).lower()

        company_range = config.get("company_range")
        if company_range is not None:
            settings["start_idx"], settings["end_idx"] = parse_company_range(company_range)
        else:
            start_idx_cfg = config.get("start_idx")
            end_idx_cfg = config.get("end_idx")
            if start_idx_cfg is not None:
                settings["start_idx"] = max(int(start_idx_cfg) - 1, 0)
            if end_idx_cfg is not None:
                settings["end_idx"] = int(end_idx_cfg)

        year_range = config.get("year_range")
        if year_range is not None:
            settings["start_year"], settings["end_year"] = parse_year_range(
                year_range,
                settings["start_year"],
                settings["end_year"],
            )
        else:
            if config.get("start_year") is not None:
                settings["start_year"] = int(config["start_year"])
            if config.get("end_year") is not None:
                settings["end_year"] = int(config["end_year"])

        threads_cfg = config.get("threads") or config.get("max_workers")
        if threads_cfg is not None:
            settings["max_workers"] = max(1, int(threads_cfg))

        if config.get("update_listing") is not None:
            settings["update_listing"] = bool(config["update_listing"])

        if config.get("force_download_list") is not None:
            settings["force_download_list"] = bool(config["force_download_list"])

        if config.get("non_interactive") is not None:
            settings["non_interactive"] = bool(config["non_interactive"])

        if config.get("listing_mode") in {"1", "2", "3"}:
            settings["listing_mode"] = config["listing_mode"]

    # Apply CLI overrides
    if args.stock_list:
        stock_list_path = resolve_path(script_dir, args.stock_list)
        if stock_list_path:
            settings["stock_list_file"] = stock_list_path

    if args.output_dir:
        output_dir = resolve_path(script_dir, args.output_dir)
        if output_dir:
            settings["output_dir"] = output_dir

    if args.log_dir:
        log_dir = resolve_path(script_dir, args.log_dir)
        if log_dir:
            settings["log_dir"] = log_dir

    if args.log_format:
        settings["log_format"] = args.log_format.lower()

    company_range_arg = args.company_range
    if company_range_arg is not None:
        settings["start_idx"], settings["end_idx"] = parse_company_range(company_range_arg)

    if args.start_idx is not None:
        settings["start_idx"] = max(args.start_idx - 1, 0)

    if args.end_idx is not None:
        settings["end_idx"] = int(args.end_idx)

    year_range_arg = args.year_range
    if year_range_arg is not None:
        settings["start_year"], settings["end_year"] = parse_year_range(
            year_range_arg,
            settings["start_year"],
            settings["end_year"],
        )

    if args.start_year is not None:
        settings["start_year"] = int(args.start_year)

    if args.end_year is not None:
        settings["end_year"] = int(args.end_year)

    threads_arg = args.threads or args.max_workers
    if threads_arg is not None:
        settings["max_workers"] = max(1, int(threads_arg))

    if args.skip_listing_update:
        settings["update_listing"] = False

    if args.force_download_list:
        settings["force_download_list"] = True

    if args.listing_mode in {"1", "2", "3"}:
        settings["listing_mode"] = args.listing_mode

    if args.auto or args.non_interactive:
        settings["non_interactive"] = True

    # Ensure logical consistency
    if settings["end_year"] < settings["start_year"]:
        raise ValueError("结束年份不能早于起始年份")

    if settings["end_idx"] is not None and settings["end_idx"] <= settings["start_idx"]:
        raise ValueError("结束公司序号必须大于起始序号")

    if settings["log_format"] not in {"excel", "csv"}:
        raise ValueError("日志格式仅支持 excel 或 csv")

    settings["max_workers"] = max(1, min(32, settings["max_workers"]))

    return settings


def run_scheduled(settings: Dict, runtime_logger: logging.Logger) -> int:
    """Execute crawler in non-interactive/scheduled mode."""
    stock_list_file = settings["stock_list_file"]
    output_dir = settings["output_dir"]
    log_dir = settings["log_dir"]
    log_format = settings["log_format"]

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)
    stock_parent = os.path.dirname(stock_list_file)
    if stock_parent:
        os.makedirs(stock_parent, exist_ok=True)

    crawler = CninfoHKReportCrawlerEnhanced(
        stock_list_file,
        output_dir,
        log_dir,
        log_format,
        enable_console_output=False,
    )

    try:
        refresh_required = settings["force_download_list"] or settings.get("non_interactive", False)
        if refresh_required or not os.path.exists(stock_list_file):
            runtime_logger.info(
                "开始获取或刷新HKEX股票列表 (force=%s, non_interactive=%s)",
                settings["force_download_list"],
                settings.get("non_interactive", False),
            )
            if not crawler.ensure_stock_list(force_download=True):
                runtime_logger.error("获取股票列表失败，任务终止")
                return 1
        else:
            runtime_logger.info("使用现有股票列表: %s", stock_list_file)

        runtime_logger.info(
            "开始批量下载：公司范围 %s-%s，年份 %s-%s，线程 %s",
            settings["start_idx"] + 1,
            settings["end_idx"] if settings["end_idx"] else "ALL",
            settings["start_year"],
            settings["end_year"],
            settings["max_workers"],
        )

        crawler.run(
            start_idx=settings["start_idx"],
            end_idx=settings["end_idx"],
            start_year=settings["start_year"],
            end_year=settings["end_year"],
            max_workers=settings["max_workers"],
        )

        runtime_logger.info("财务报表下载完成")

        if settings["update_listing"]:
            listing_output_file = os.path.join(output_dir, "company_with_listing_date.csv")
            runtime_logger.info("开始更新上市日期，模式=%s", settings["listing_mode"])
            success = run_listing_date_update(
                company_csv_path=stock_list_file,
                output_csv_path=listing_output_file,
                mode_choice=settings["listing_mode"],
                non_interactive=True,
            )
            if success:
                runtime_logger.info("上市日期更新完成: %s", listing_output_file)
            else:
                runtime_logger.warning("上市日期更新未成功，请检查日志")
        else:
            runtime_logger.info("已根据参数跳过上市日期更新")

        runtime_logger.info("任务执行完毕")
        return 0

    except Exception as err:  # pylint: disable=broad-except
        runtime_logger.exception("定时任务执行异常: %s", err)
        return 1


class DownloadLogger:
    """下载日志管理器"""
    
    def __init__(self, log_dir: str = "日志文件", log_format: str = "excel"):
        """
        初始化日志管理器
        
        Args:
            log_dir: 日志文件保存目录
            log_format: 日志格式 ('csv' 或 'excel')
        """
        self.log_dir = log_dir
        self.log_format = log_format.lower()
        
        # 创建日志目录
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 生成日志文件名（带时间戳）
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if self.log_format == 'excel':
            self.log_file = os.path.join(log_dir, f'下载日志_{timestamp}.xlsx')
            self.log_columns = [
                'stock_code', 'stock_name', 'report_type', 'report_year', 
                'report_period', 'file_name', 'original_filename', 'file_url', 'download_status',
                '备注', 'download_timestamp', 'file_size_kb', 
                'file_md5', 'data_source'
            ]
        else:
            self.log_file = os.path.join(log_dir, f'下载日志_{timestamp}.csv')
            self.log_columns = [
                'stock_code', 'stock_name', 'report_type', 'report_year', 
                'report_period', 'file_name', 'original_filename', 'file_url', 'download_status',
                '备注', 'download_timestamp', 'file_size_kb', 
                'file_md5', 'data_source'
            ]
        
        # 初始化日志数据列表
        self.log_data = []
        
        # 线程安全锁（用于日志操作）
        self.log_lock = threading.Lock()
        
        # 定时保存配置（防止断电断网导致数据丢失）
        self.auto_save_interval = 50  # 每50条记录自动保存一次
        self.auto_save_time_interval = 300  # 每5分钟（300秒）自动保存一次
        self.auto_save_last_time = time.time()
        self.last_save_count = 0
        
        # 格式化时间间隔显示（更友好）
        time_interval_minutes = self.auto_save_time_interval // 60
        time_interval_seconds = self.auto_save_time_interval % 60
        if time_interval_seconds == 0:
            time_str = f"{time_interval_minutes}分钟"
        else:
            time_str = f"{time_interval_minutes}分{time_interval_seconds}秒"
        
        print(f"\n[日志系统] 日志文件: {os.path.abspath(self.log_file)}")
        print(f"[日志系统] 格式: {self.log_format.upper()}")
        print(f"[日志系统] 自动保存: 每{self.auto_save_interval}条记录或每{time_str}（防止断电断网丢失数据）")
    
    def calculate_md5(self, file_path: str) -> Optional[str]:
        """
        计算文件的MD5哈希值
        
        Args:
            file_path: 文件路径
            
        Returns:
            MD5哈希值（十六进制字符串），失败返回None
        """
        try:
            if not os.path.exists(file_path):
                return None

            md5_hash = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    md5_hash.update(chunk)
            return md5_hash.hexdigest()
        except (OSError, ValueError) as err:
            MODULE_LOGGER.warning("calculate_md5 failed for %s: %s", file_path, err, exc_info=True)
            return None
    
    def log_download(self, 
                    stock_code: str,
                    stock_name: str,
                    report_type: str,
                    report_year: str,
                    report_period: Optional[str],
                    file_name: str,
                    file_url: str,
                    download_status: str,
                    reason: Optional[str] = None,
                    file_path: Optional[str] = None,
                    original_filename: Optional[str] = None,
                    data_source: str = "巨潮资讯网"):
        """
        记录下载日志
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            report_type: 报告类型
            report_year: 报告年份
            report_period: 报告期末日
            file_name: 文件名（标准命名格式）
            file_url: 下载URL
            download_status: 下载状态 (Success/Failed/Skipped)
            reason: 备注信息（成功/失败/跳过的原因说明）
            file_path: 文件保存路径（用于计算MD5和大小）
            original_filename: 原始文件名（从URL中提取）
            data_source: 数据来源
        """
        # 如果未提供原始文件名，从URL中提取
        if not original_filename and file_url:
            try:
                # 从URL中提取文件名（最后一个/后的部分）
                original_filename = file_url.split('/')[-1].split('?')[0]  # 去除查询参数
            except (AttributeError, IndexError) as err:
                MODULE_LOGGER.warning("Failed to derive original filename from %s: %s", file_url, err, exc_info=True)
                original_filename = ''
        # 计算文件大小和MD5
        file_size_kb = None
        file_md5 = None
        
        if file_path and os.path.exists(file_path):
            try:
                file_size_kb = round(os.path.getsize(file_path) / 1024, 2)
                if download_status == "Success":
                    file_md5 = self.calculate_md5(file_path)
            except OSError as err:
                MODULE_LOGGER.warning("Failed to collect metadata for %s: %s", file_path, err, exc_info=True)
        
        # 记录时间戳
        download_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 添加日志记录
        log_entry = {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'report_type': report_type,
            'report_year': str(report_year),
            'report_period': report_period or '',
            'file_name': file_name,
            'original_filename': original_filename or '',
            'file_url': file_url,
            'download_status': download_status,
            '备注': reason or '',
            'download_timestamp': download_timestamp,
            'file_size_kb': file_size_kb if file_size_kb else '',
            'file_md5': file_md5 or '',
            'data_source': data_source
        }
        
        # 线程安全：使用锁保护日志数据
        with self.log_lock:
            self.log_data.append(log_entry)
            
            # 检查是否需要自动保存
            self._auto_save_if_needed()
    
    def _auto_save_if_needed(self):
        """根据需要自动保存日志（防止断电断网导致数据丢失，线程安全）"""
        # 注意：此方法应该在log_lock保护下调用
        current_time = time.time()
        should_save = False
        
        # 检查记录数量
        current_count = len(self.log_data)
        if current_count - self.last_save_count >= self.auto_save_interval:
            should_save = True
        
        # 检查时间间隔
        if current_time - self.auto_save_last_time >= self.auto_save_time_interval:
            should_save = True
        
        if should_save and self.log_data:
            try:
                # 在锁外保存，避免长时间持有锁
                log_data_copy = self.log_data.copy()
                # 释放锁后再保存（通过返回标志，由调用者处理）
                # 但这里已经在锁内，所以需要特殊处理
                # 先更新计数，再在锁外保存
                self.auto_save_last_time = current_time
                self.last_save_count = current_count

                # 使用线程异步保存，避免阻塞（静默模式，不打印详细消息）
                threading.Thread(
                    target=self._save_log_internal,
                    args=(True,),
                    kwargs={'log_data': log_data_copy},
                    daemon=True
                ).start()
            except RuntimeError as err:
                MODULE_LOGGER.error("Failed to spawn auto-save thread: %s", err, exc_info=True)
                print(f"[日志系统] 自动保存失败: {err}")
    
    def _save_log_internal(self, silent: bool = False, log_data: Optional[List] = None):
        """内部保存日志方法（线程安全）"""
        # 如果提供了log_data副本，使用副本；否则使用当前数据（需要锁保护）
        if log_data is None:
            with self.log_lock:
                if not self.log_data:
                    if not silent:
                        print("[日志系统] 没有日志数据需要保存")
                    return
                log_data = self.log_data.copy()
        
        if not log_data:
            if not silent:
                print("[日志系统] 没有日志数据需要保存")
            return
        
        try:
            df = pd.DataFrame(log_data, columns=self.log_columns)
            
            # 按公司代码和下载时间排序，使同一公司的日志聚集在一起
            # 排序规则：先按 stock_code（公司代码），再按 download_timestamp（下载时间）
            if 'stock_code' in df.columns and 'download_timestamp' in df.columns:
                df = df.sort_values(by=['stock_code', 'download_timestamp'], 
                                   ascending=[True, True], 
                                   na_position='last')
            
            if self.log_format == 'excel':
                df.to_excel(self.log_file, index=False, engine='openpyxl')
            else:
                df.to_csv(self.log_file, index=False, encoding='utf-8-sig')
            
            if not silent:
                print(f"\n[日志系统] 已保存 {len(log_data)} 条日志记录")
                print(f"[日志系统] 日志文件: {os.path.abspath(self.log_file)}")
            else:
                # 静默模式：只显示简要信息，避免打断主程序输出
                print(f"[日志系统] 自动保存: {len(log_data)} 条记录已保存", end='\r')
        except (OSError, PermissionError, ValueError) as err:
            print(f"[日志系统] 保存日志失败: {err}")
            MODULE_LOGGER.error("Failed to save download log %s: %s", self.log_file, err, exc_info=True)
            raise
    
    def save_log(self):
        """保存日志到文件（线程安全）"""
        with self.log_lock:
            if not self.log_data:
                print("[日志系统] 没有日志数据需要保存")
                return
            log_data_copy = self.log_data.copy()
        
        self._save_log_internal(silent=False, log_data=log_data_copy)
    
    def get_log_dataframe(self) -> pd.DataFrame:
        """获取日志数据的DataFrame"""
        if not self.log_data:
            return pd.DataFrame(columns=self.log_columns)
        return pd.DataFrame(self.log_data, columns=self.log_columns)


class CninfoHKReportCrawlerEnhanced:
    """巨潮资讯网港股报告爬虫（增强版）"""
    
    # 中文数字到阿拉伯数字的映射（类常量）
    CHINESE_NUMERIC_MAP = {
        '零': '0', '〇': '0', '一': '1', '二': '2', '三': '3',
        '四': '4', '五': '5', '六': '6', '七': '7', '八': '8', '九': '9'
    }
    
    # 中文月份到数字的映射（类常量）
    CHINESE_MONTH_MAP = {
        '一月': 1, '二月': 2, '三月': 3, '四月': 4, '五月': 5, '六月': 6,
        '七月': 7, '八月': 8, '九月': 9, '十月': 10, '十一月': 11, '十二月': 12
    }

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/120.0.0.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    
    def __init__(self, excel_path: str, output_dir: str = "HKEX", 
                 log_dir: str = "日志文件", log_format: str = "excel",
                 enable_console_output: bool = True):
        """
        初始化爬虫
        
        Args:
            excel_path: 股票列表文件路径（支持CSV或Excel格式）
            output_dir: 输出目录（默认：HKEX）
            log_dir: 日志文件保存目录（默认：日志文件）
            log_format: 日志格式 ('csv' 或 'excel'，默认 'excel')
        """
        self.excel_path = excel_path
        self.output_dir = output_dir
        self.pdf_base_url = HKEX_PDF_BASE

        # 请求头基础配置（User-Agent将随机生成）
        self.base_headers = HKEX_HEADERS.copy()

        # 全局会话与限流器
        self.rate_limiter = AdaptiveRateLimiter(base_interval=0.3, max_interval=8.0)
        pool_connections = 24
        pool_maxsize = 48
        self.api_session = _create_http_session(
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            total_retries=4,
            backoff_factor=0.4,
        )
        self.api_session.headers.update(self.base_headers)
        self.download_session = _create_http_session(
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            total_retries=4,
            backoff_factor=0.5,
        )
        self.download_session.headers.update(self.base_headers)
        # 兼容旧属性命名
        self.hkex_session = self.api_session
        
        # 初始化日志管理器
        self.logger = DownloadLogger(log_dir, log_format)
        
        # 线程锁：用于保护共享资源（stats和logger）
        self.stats_lock = threading.Lock()
        self.logger_lock = threading.Lock()
        self.print_lock = threading.Lock()
        self.console = ConsoleMessenger(MODULE_LOGGER, enable_stdout=enable_console_output)
        
        # 初始化文件URL缓存（从日志文件加载，用于快速查询避免重复下载）
        self.file_url_cache: Dict[str, str] = {}  # {file_name: file_url}
        self.cache_lock = threading.Lock()  # 缓存更新锁
        self._load_file_url_cache()
        
        # 报告类型配置
        self.report_types: Dict[str, HKEXDocType] = {
            '年报': HKEXDocType(key='annual', name='Annual Report', t2code='40100'),
            '中期报告': HKEXDocType(key='interim', name='Interim/Half-Year Report', t2code='40200'),
            '季度报告': HKEXDocType(key='quarterly', name='Quarterly Report', t2code='40300'),
        }
        
        # 统计信息
        self.stats = {
            'total_companies': 0,
            'total_announcements': 0,
            'filtered_reports': 0,
            'downloaded': 0,
            'skipped': 0,
            'failed': 0,
            'company_errors': 0
        }
        self.runtime_stockid_cache: Dict[str, str] = {}
    
    def _log(self, message: str, level: str = "info") -> None:
        """统一控制台输出与日志写入（线程安全）。"""
        with self.print_lock:
            self.console.log(level, message)
    
    def _load_file_url_cache(self):
        """
        从所有日志文件中加载文件URL缓存（启动时调用一次）
        缓存格式：{file_name: file_url}
        """
        log_dir = self.logger.log_dir
        if not os.path.exists(log_dir):
            return
        
        try:
            # 查找所有日志文件
            log_files = []
            for ext in ['*.xlsx', '*.csv']:
                log_files.extend(glob.glob(os.path.join(log_dir, ext)))
            
            # 按修改时间排序，最新的在前
            log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            
            # 加载所有日志文件
            for log_file in log_files:
                try:
                    if log_file.endswith('.xlsx'):
                        df = pd.read_excel(log_file)
                    else:
                        df = pd.read_csv(log_file, encoding='utf-8-sig')
                    
                    # 检查必要的列
                    if 'file_name' not in df.columns or 'file_url' not in df.columns:
                        continue
                    
                    # 只加载成功下载的记录
                    success_records = df[
                        (df['download_status'] == 'Success') &
                        (df['file_name'].notna()) &
                        (df['file_url'].notna())
                    ]
                    
                    # 更新缓存（后面的记录会覆盖前面的，确保最新）
                    for _, row in success_records.iterrows():
                        file_name = str(row['file_name']).strip()
                        file_url = str(row['file_url']).strip()
                        if file_name and file_url:
                            self.file_url_cache[file_name] = file_url
                            
                except Exception as e:
                    MODULE_LOGGER.debug("Failed to load cache from %s: %s", log_file, e)
                    continue
            
            cache_size = len(self.file_url_cache)
            if cache_size > 0:
                self._log(f"[缓存] 已加载 {cache_size} 个文件的URL映射", level="info")
        except Exception as e:
            MODULE_LOGGER.warning("Failed to load file URL cache: %s", e, exc_info=True)
    
    def _get_existing_file_url_from_log(self, file_name: str) -> Optional[str]:
        """
        从缓存中获取已存在文件对应的URL（O(1)查询，非常快）
        
        Args:
            file_name: 文件名（标准命名格式）
            
        Returns:
            文件对应的URL，如果不存在则返回None
        """
        if not file_name:
            return None
        
        # 从内存缓存查询（O(1)时间复杂度）
        return self.file_url_cache.get(file_name)
    
    def _update_file_url_cache(self, file_name: str, file_url: str):
        """
        更新文件URL缓存（下载新文件后调用）
        
        Args:
            file_name: 文件名
            file_url: 文件URL
        """
        if file_name and file_url:
            with self.cache_lock:
                self.file_url_cache[file_name] = file_url
    
    def _clear_file_url_cache(self):
        """
        清理文件URL缓存（程序结束时调用，释放内存）
        注意：二次运行时会重新从日志文件加载，所以会查询到前一次运行的内容
        """
        with self.cache_lock:
            self.file_url_cache.clear()
    
    def _resolve_stock_id(self, stock_code: str, stock_name: str = "") -> Optional[str]:
        """运行时尝试通过披露易接口补全缺失的 stockId。"""
        code = stock_code.zfill(5)
        if code in self.runtime_stockid_cache:
            return self.runtime_stockid_cache[code]

        temp_mapping: Dict[str, int] = {}
        _hkex_supplement_mapping_with_partial(
            [code],
            temp_mapping,
            session=self.api_session,
            rate_limiter=self.rate_limiter,
        )
        stock_id = temp_mapping.get(code)
        if stock_id is not None:
            resolved = str(stock_id)
            self.runtime_stockid_cache[code] = resolved
            self._log(f"    [{code}] 已自动补充缺失的 stockId={resolved}")
            with self.logger_lock:
                self.logger.log_download(
                    stock_code=code,
                    stock_name=stock_name or code,
                    report_type="stockId补全",
                    report_year='',
                    report_period=None,
                    file_name='',
                    file_url='',
                    download_status="Success",
                    reason="stockId补全成功",
                    file_path=None,
                    original_filename='',
                    data_source="披露易partial.do",
                )
            return resolved

        self._log(
            f"    [{code}] 无法通过接口补充 stockId，建议刷新股票列表",
            level="warning",
        )
        with self.logger_lock:
            self.logger.log_download(
                stock_code=code,
                stock_name=stock_name or code,
                report_type="stockId补全",
                report_year='',
                report_period=None,
                file_name='',
                file_url='',
                download_status="Failed",
                reason="partial.do 补全失败",
                file_path=None,
                original_filename='',
                data_source="披露易partial.do",
            )
        return None
    
    def _get_request_headers(self, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """生成带随机User-Agent的请求头"""
        headers = self.base_headers.copy()
        headers['User-Agent'] = random.choice(self.USER_AGENTS)
        if extra_headers:
            headers.update(extra_headers)
        return headers
    
    def download_hkex_stock_list(self, save_path: str = 'ListOfSecurities_c.xlsx') -> bool:
        """
        从香港交易所下载证券列表文件（中文繁体版）
        
        Args:
            save_path: 保存路径
            
        Returns:
            是否下载成功
        """
        download_urls = [
            "https://www.hkex.com.hk/chi/services/trading/securities/securitieslists/ListOfSecurities_c.xlsx",
            "https://www.hkexnews.hk/reports/securitieslists/sehk/ListOfSecurities_c.xlsx",
        ]
        
        print("\n" + "="*70)
        print("从香港交易所下载证券列表")
        print("="*70)
        
        for url in download_urls:
            print(f"\n尝试: {url}")
            
            try:
                self.rate_limiter.acquire()
                with self.download_session.get(
                    url,
                    headers=self._get_request_headers(),
                    timeout=30,
                    stream=True,
                ) as response:
                    status_code = response.status_code
                    if status_code == 200:
                        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
                        with open(save_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        self.rate_limiter.on_success()
                        
                        file_size = os.path.getsize(save_path) / 1024
                        print(f"[成功] 下载成功！")
                        print(f"  文件大小: {file_size:.2f} KB")
                        print(f"  保存路径: {save_path}")
                        return True
                    elif status_code in (403, 429):
                        self.rate_limiter.on_throttle()
                        print(f"[失败] HTTP {status_code} - 请求过于频繁")
                    else:
                        self.rate_limiter.on_error()
                        print(f"[失败] HTTP {status_code}")
            except requests.RequestException as req_err:
                print(f"[错误] {str(req_err)[:50]}")
                MODULE_LOGGER.warning("Failed to download %s: %s", url, req_err, exc_info=True)
                self.rate_limiter.on_error()
        
        print("\n所有URL都失败了")
        return False
    
    def parse_hkex_stock_list(self, excel_path: str = 'ListOfSecurities_c.xlsx', 
                              raw_company_path: str = 'HKEX/company.csv') -> Optional[pd.DataFrame]:
        """
        解析证券列表（繁体中文版），筛选出股本證券公司
        
        筛选条件：
        - 第3列"分類"：股本
        - 第4列"次分類"：股本證券(主板) 或 股本證券(創業板)
        
        Args:
            excel_path: 输入的Excel文件路径
            raw_company_path: 输出的仅包含基础字段的 CSV 文件路径（不含 stockId）
            
        Returns:
            DataFrame: 筛选后的公司列表（不含 stockId）
        """
        print("\n" + "="*70)
        print("解析证券列表文件（繁体中文）")
        print("="*70)
        
        try:
            # 读取Excel，可能有多个sheet
            excel_file = pd.ExcelFile(excel_path)
            print(f"\n文件包含 {len(excel_file.sheet_names)} 个工作表")
            
            # 尝试读取每个sheet
            all_stocks = []
            
            for sheet_name in excel_file.sheet_names:
                print(f"\n处理工作表: {sheet_name}")
                
                try:
                    # 读取数据，尝试不同的跳过行数
                    for skip_rows in [0, 1, 2, 3]:
                        try:
                            df = pd.read_excel(excel_path, sheet_name=sheet_name, skiprows=skip_rows)

                            # 查找繁体中文列名
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
                                print(f"  [成功] 找到所需列 (跳过 {skip_rows} 行)")

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
                                print(f"  清理后剩余 {len(stocks_df)} 条记录")

                                # 筛选：分類 = "股本"
                                category_mask = stocks_df[category_col] == '股本'
                                stocks_df = stocks_df[category_mask]
                                print(f"  筛选【分類=股本】后剩余 {len(stocks_df)} 条记录")

                                # 筛选：次分類 = "股本證券(主板)" 或 "股本證券(創業板)"
                                subcategory_mask = stocks_df[subcategory_col].isin([
                                    '股本證券(主板)',
                                    '股本證券(創業板)'
                                ])
                                stocks_df = stocks_df[subcategory_mask]
                                print(f"  筛选【次分類=股本證券】后剩余 {len(stocks_df)} 条记录")

                                # 重命名列（保持繁体原文）
                                stocks_df = stocks_df.rename(columns={
                                    code_col: '股份代號',
                                    name_col: '股份名稱',
                                    category_col: '分類',
                                    subcategory_col: '次分類'
                                })

                                # 补零到5位
                                stocks_df['股份代號'] = stocks_df['股份代號'].str.zfill(5)

                                all_stocks.append(stocks_df)
                                print(f"  [OK] 成功解析 {len(stocks_df)} 条记录")
                                break

                        except (ValueError, KeyError, pd.errors.EmptyDataError, pd.errors.ParserError) as parse_err:
                            MODULE_LOGGER.warning(
                                "Failed to parse sheet %s (skip_rows=%s): %s",
                                sheet_name,
                                skip_rows,
                                parse_err,
                                exc_info=True,
                            )
                            continue

                except (OSError, ValueError, pd.errors.EmptyDataError, pd.errors.ParserError) as err:
                    print(f"  处理失败: {err}")
                    MODULE_LOGGER.error("Failed to process sheet %s in %s: %s", sheet_name, excel_path, err, exc_info=True)
            
            if all_stocks:
                # 合并所有数据
                final_df = pd.concat(all_stocks, ignore_index=True)
                
                # 去重（基本去重）
                final_df = final_df.drop_duplicates(subset=['股份代號'])
                
                # 去重处理：去除8开头（非08开头）且存在对应0开头代码的重复项
                print(f"\n进行去重处理（去除8开头重复代码）...")
                before_count = len(final_df)
                
                # 获取所有股票代码集合，用于快速查找
                all_codes = set(final_df['股份代號'].tolist())
                
                # 找出所有以8开头但不是08开头的代码（8XXXX，但排除创业板08XXX）
                # 规则：去除8XXXX（首位是8且不以08开头），如果存在对应的0XXXX
                # 注意：08XXX不在去重范围，需要保留
                codes_to_remove = []
                for code in final_df['股份代號']:
                    # 检查：5位数代码，首位是8，且不以08开头（排除创业板08XXX）
                    if len(code) == 5 and code.startswith('8') and not code.startswith('08'):
                        # 生成对应的0开头代码（0XXXX）
                        corresponding_code = '0' + code[1:]
                        # 如果存在对应的0开头代码，则标记8开头的为删除
                        if corresponding_code in all_codes:
                            codes_to_remove.append(code)
                
                # 删除标记的代码
                if codes_to_remove:
                    removed_count = len(codes_to_remove)
                    final_df = final_df[~final_df['股份代號'].isin(codes_to_remove)]
                    print(f"  已去除 {removed_count} 个8开头的重复代码:")
                    for code in sorted(codes_to_remove)[:10]:  # 只显示前10个
                        corresponding_code = '0' + code[1:]
                        print(f"    {code} -> 保留 {corresponding_code}")
                    if removed_count > 10:
                        print(f"    ... 还有 {removed_count - 10} 个")
                else:
                    print(f"  未发现需要去重的8开头代码")
                
                after_count = len(final_df)
                if before_count != after_count:
                    print(f"  去重前: {before_count} 家，去重后: {after_count} 家，减少: {before_count - after_count} 家")
                
                final_df = final_df.sort_values('股份代號')
                final_df = final_df.reset_index(drop=True)
                
                print(f"\n" + "="*70)
                print(f"解析完成！")
                print("="*70)
                print(f"总计: {len(final_df)} 家港股上市公司")
                
                # 统计次分類分布
                print(f"\n次分類统计:")
                for subcategory, count in final_df['次分類'].value_counts().items():
                    print(f"  {subcategory}: {count} 家")
                
                # 保存原始名单（无 stockId）
                raw_dir = os.path.dirname(raw_company_path)
                if raw_dir and not os.path.exists(raw_dir):
                    os.makedirs(raw_dir)
                    print(f"\n创建目录: {raw_dir}")
                final_df.to_csv(raw_company_path, index=False, encoding='utf-8-sig')
                print(f"\n已保存公司名单 (无 stockId) 到: {raw_company_path}")
                
                # 显示前10条
                print(f"\n前10家公司:")
                for i, row in final_df.head(10).iterrows():
                    print(f"  {row['股份代號']} - {row['股份名稱']} - {row['次分類']}")
                
                return final_df
            else:
                print("未能解析出数据")
                return None
                
        except (FileNotFoundError, OSError, ValueError, pd.errors.EmptyDataError, pd.errors.ParserError) as err:
            print(f"解析错误: {err}")
            MODULE_LOGGER.error("parse_hkex_stock_list failed for %s: %s", excel_path, err, exc_info=True)
            return None
    
    def ensure_stock_list(self, force_download: bool = False) -> bool:
        """
        确保股票列表文件存在，如果不存在则自动下载并解析
        
        Args:
            force_download: 是否强制重新下载
            
        Returns:
            是否成功获取股票列表
        """
        # 获取脚本所在目录（确保路径始终基于程序文件位置）
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 使用绝对路径，确保文件始终保存在程序所在目录
        excel_file = os.path.join(script_dir, 'ListOfSecurities_c.xlsx')
        csv_file = os.path.join(script_dir, 'HKEX', 'company_stockid.csv')
        raw_output = self.excel_path  # 使用传入路径保存无 stockId 名单（默认 HKEX/company.csv）

        # 检查CSV文件是否存在
        if os.path.exists(csv_file) and not force_download:
            print(f"\n发现已存在的股票列表: {csv_file}")
            # 若原始名单缺失，尝试从现有文件生成
            if not os.path.exists(raw_output):
                try:
                    df_existing = pd.read_csv(csv_file, encoding='utf-8-sig')
                    df_raw = df_existing.drop(columns=['stockId'], errors='ignore')
                    os.makedirs(os.path.dirname(raw_output), exist_ok=True)
                    df_raw.to_csv(raw_output, index=False, encoding='utf-8-sig')
                    print(f"[补齐] 已根据 {csv_file} 生成无 stockId 名单: {raw_output}")
                except (OSError, ValueError, pd.errors.EmptyDataError, pd.errors.ParserError) as recreate_error:
                    print(f"[警告] 无法自动生成 {raw_output}：{recreate_error}")
                    MODULE_LOGGER.warning(
                        "Failed to backfill raw company list from %s: %s",
                        csv_file,
                        recreate_error,
                        exc_info=True,
                    )
                    print("        可使用 --force-download-list 重新下载生成完整名单。")
            return True
        
        # 检查Excel源文件
        if os.path.exists(excel_file) and not force_download:
            print(f"\n发现已存在的Excel文件: {excel_file}")
        else:
            print("\n未找到股票列表文件，开始从香港交易所下载...")
            if not self.download_hkex_stock_list(excel_file):
                print("\n[错误] 下载失败！")
                print("\n请手动下载并保存为 ListOfSecurities_c.xlsx:")
                print("  https://www.hkex.com.hk/chi/services/trading/securities/securitieslists/ListOfSecurities_c.xlsx")
                return False
        
        # 解析Excel文件
        print("\n开始解析Excel文件...")
        df_raw = self.parse_hkex_stock_list(excel_file, raw_company_path=raw_output)
        if df_raw is None:
            return False

        try:
            df_with_stockid = _hkex_append_stock_id_column(
                df_raw,
                STOCK_JSON_DIR,
                session=self.api_session,
                rate_limiter=self.rate_limiter,
            )
            df_with_stockid.to_csv(csv_file, index=False, encoding='utf-8-sig')
            print(f"\n已保存公司名单 (含 stockId) 到: {csv_file}")
            return True
        except (KeyError, ValueError, json.JSONDecodeError, OSError) as exc:
            print(f"\n[错误] 生成 stockId 列失败: {exc}")
            MODULE_LOGGER.error("Failed to append stockId column: %s", exc, exc_info=True)
            print("您可以稍后重新运行并选择重新下载列表。")
            return False
    
    @staticmethod
    def _chinese_numeric_to_arabic(chinese_text: str) -> str:
        """
        将中文数字文本转换为阿拉伯数字
        
        Args:
            chinese_text: 中文数字文本（如 "二三" -> "23"）
            
        Returns:
            阿拉伯数字字符串
        """
        return ''.join(CninfoHKReportCrawlerEnhanced.CHINESE_NUMERIC_MAP.get(ch, ch) for ch in chinese_text)
    
    @staticmethod
    def _determine_fiscal_year(year_end: int, month_end: int, is_annual_report: bool) -> int:
        """
        根据截止日期和报告类型确定财年
        
        Args:
            year_end: 截止年份（如 2023）
            month_end: 截止月份（如 3 表示3月）
            is_annual_report: 是否为年报
            
        Returns:
            财年年份
            
        Example:
            _determine_fiscal_year(2023, 3, True) -> 2022  # 年报：3月31日截止 → 前一年财年
            _determine_fiscal_year(2023, 3, False) -> 2023  # 季报：3月31日截止 → 当年财年（Q1）
            _determine_fiscal_year(2023, 6, False) -> 2023  # 其他月份 → 当年财年
        """
        if month_end == 3:
            if is_annual_report:
                return year_end - 1  # 年报：3月31日截止 → 前一年财年
            else:
                return year_end     # 季报：3月31日截止 → 当年财年（Q1）
        else:
            return year_end  # 其他月份 → 当年财年
    
    def load_stock_codes(self) -> List[Dict[str, str]]:
        """
        从CSV或Excel文件读取股票代码列表
        
        Returns:
            股票信息列表 [{'code': '00001', 'name': 'XXX'}, ...]
        """
        print(f"\n[1/4] 读取股票代码列表...")
        print(f"文件路径: {self.excel_path}")
        
        try:
            # 根据文件扩展名选择读取方式
            if self.excel_path.endswith('.csv'):
                df = pd.read_csv(self.excel_path, encoding='utf-8-sig')
            else:
                df = pd.read_excel(self.excel_path)
            
            # 查找可能的股票代码列（增加繁体中文支持）
            possible_code_columns = ['股份代號', '股票代码', '代码', 'Code', 'code', 'Stock Code', 'stock_code']
            possible_name_columns = ['股份名稱', '公司名称', '名称', 'Name', 'name', 'Company Name', 'company_name']
            
            code_column = None
            name_column = None
            
            for col in possible_code_columns:
                if col in df.columns:
                    code_column = col
                    break
            
            for col in possible_name_columns:
                if col in df.columns:
                    name_column = col
                    break
            
            if not code_column:
                code_column = df.columns[0]
                print(f"警告: 未找到标准代码列，使用第一列: {code_column}")
            
            if 'stockId' not in df.columns:
                print("警告: 股票列表缺少 stockId 列，尝试自动补充...")
                try:
                    df = _hkex_append_stock_id_column(
                        df,
                        STOCK_JSON_DIR,
                        session=self.api_session,
                        rate_limiter=self.rate_limiter,
                    )
                    if self.excel_path.endswith('.csv'):
                        df.to_csv(self.excel_path, index=False, encoding=HKEX_OUTPUT_ENCODING)
                    else:
                        df.to_excel(self.excel_path, index=False)
                    print("已自动补充 stockId 列并保存。")
                except (ValueError, KeyError, json.JSONDecodeError, OSError) as exc:
                    print(f"错误: 无法自动生成 stockId 列 - {exc}")
                    MODULE_LOGGER.error("Failed to auto append stockId column for %s: %s", self.excel_path, exc, exc_info=True)
                    print("请确保 HKEX/company_stockid.csv 包含 stockId 列后重试。")
                    return []

            # 提取股票代码
            stock_list = []
            # 过滤衍生权证：排除首位为8且非08xxx的5位代码（保留创业板08xxx）
            if code_column:
                df[code_column] = df[code_column].astype(str).str.strip()
                initial_count = len(df)
                warrant_mask = (
                    df[code_column].str.len() == 5
                ) & df[code_column].str.startswith('8') & ~df[code_column].str.startswith('08')
                filtered_count = warrant_mask.sum()
                if filtered_count:
                    df = df[~warrant_mask]
                    print(f"过滤衍生权证代码: 已剔除 {filtered_count} 条首位为8的衍生权证（保留08xxx创业板），剩余 {len(df)} 条")
                    # 同步更新源文件，保持HKEX/company.csv与运行时一致
                    try:
                        if self.excel_path.endswith('.csv'):
                            df.to_csv(self.excel_path, index=False, encoding='utf-8-sig')
                        else:
                            df.to_excel(self.excel_path, index=False)
                        print(f"已同步更新 {self.excel_path}，移除衍生权证代码")
                    except (OSError, PermissionError) as write_error:
                        print(f"警告: 无法更新 {self.excel_path}，请手动处理 ({write_error})")
                        MODULE_LOGGER.warning("Failed to persist filtered stock list to %s: %s", self.excel_path, write_error, exc_info=True)
                elif initial_count:
                    print("未检测到首位为8且非08开头的衍生权证代码")
            for _, row in df.iterrows():
                code = str(row[code_column]).strip().zfill(5)
                name = str(row[name_column]).strip() if name_column else code
                stock_id_val = row.get('stockId')
                stock_id: Optional[str]
                if pd.isna(stock_id_val):
                    stock_id = None
                else:
                    try:
                        stock_id = str(int(stock_id_val))
                    except (ValueError, TypeError):
                        stock_id = str(stock_id_val).strip()

                stock_list.append({'code': code, 'name': name, 'stockId': stock_id})
            
            print(f"成功读取 {len(stock_list)} 个股票代码")
            preview = [f"{s['code']}-{s['name'][:10]}" for s in stock_list[:5]]
            print(f"前5个: {preview}")
            
            self.stats['total_companies'] = len(stock_list)
            return stock_list
            
        except (FileNotFoundError, OSError, ValueError, pd.errors.EmptyDataError, pd.errors.ParserError) as err:
            print(f"错误: 读取文件失败 - {err}")
            MODULE_LOGGER.error("load_stock_codes failed for %s: %s", self.excel_path, err, exc_info=True)
            return []
    
    def query_reports(self, stock_code: str, stock_id: Optional[str], report_type_key: str) -> Tuple[List[Dict], Optional[str]]:
        """
        查询指定公司的报告列表（基于港交所披露易 titlesearch 接口）
        """
        if not stock_id:
            with self.print_lock:
                print(f"    [警告] {stock_code} 缺少 stockId，无法查询披露易记录")
            return [], "缺少 stockId"

        doc_type = self.report_types.get(report_type_key)
        if not doc_type:
            return [], f"未配置的报告类型：{report_type_key}"

        start_date = getattr(self, "start_date", "2022-01-01").replace("-", "")
        end_date = getattr(self, "end_date", "2025-12-31").replace("-", "")

        payload = {
            "lang": "zh",
            "category": "0",
            "market": "SEHK",
            "searchType": "1",
            "t1code": "40000",
            "t2Gcode": "-2",
            "t2code": doc_type.t2code,
            "stockId": stock_id,
            "from": start_date,
            "to": end_date,
            "MB-Daterange": "0",
            "title": "",
            "sortDirection": "1",
            "sortBy": "1",
            "rowRange": "100",
            "currentPage": "1",
            "documentType": "",
        }

        response: Optional[requests.Response] = None
        try:
            self.rate_limiter.acquire()
            response = self.hkex_session.post(
                HKEX_BASE_URL,
                data=payload,
                timeout=HKEX_REQUEST_TIMEOUT,
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
            self._log(f"    [错误] 查询披露易失败: {exc}", level="warning")
            return [], f"请求失败: {exc}"

        documents = _hkex_parse_documents(response.text)
        announcements: List[Dict] = []

        for doc in documents:
            announcement_time_ms = int(doc.release_dt.timestamp() * 1000)
            quarter = self.identify_quarter(doc.title)
            if not quarter:
                if report_type_key == '年报':
                    quarter = 'Q4'
                elif report_type_key == '中期报告':
                    quarter = 'Q2'
                elif report_type_key == '季度报告':
                    # 为季度报告添加默认季度推断：根据发布日期推断季度
                    release_month = doc.release_dt.month
                    if release_month in [1, 2, 3]:
                        quarter = 'Q1'
                    elif release_month in [4, 5, 6]:
                        quarter = 'Q2'
                    elif release_month in [7, 8, 9]:
                        quarter = 'Q3'
                    elif release_month in [10, 11, 12]:
                        quarter = 'Q4'
            fiscal_year = self.extract_year_from_title(doc.title, announcement_time_ms)
            if not fiscal_year:
                fiscal_year = str(doc.release_dt.year)
            announcements.append(
                {
                    "announcementTitle": doc.title,
                    "announcementTime": announcement_time_ms,
                    "adjunctUrl": doc.href,
                    "hkexQuarter": quarter,
                    "hkexFiscalYear": fiscal_year,
                    "hkexDocType": doc_type.key,
                    "hkexSourceType": report_type_key,
                }
            )

        if not announcements:
            reason = (
                "披露易返回0条记录，可能是报告未发布、超出查询区间，"
                "或该公司此类型报告未在披露易披露"
            )
            return [], reason

        return announcements, None
    
    def identify_quarter(self, title: str) -> Optional[str]:
        """
        识别季度型公告的季度号。
        - 年报、中期报告的季度在调用方根据 t2code 默认设置，无需关键词判断。
        - 对季度类公告区分第一季度(Q1)、第二季度(Q2)、第三季度(Q3)和第四季度(Q4)。
        - 支持基于日期的季度推断（如"截至6月30日"→Q2）。
        """
        title = re.sub(r'<[^>]+>', '', title)
        title_lower = title.lower()

        # Q1 关键词识别
        q1_keywords = [
            '第一季度', '第一季', '首季度', '首季', '一季度', '一季',
            '1季', 'q1', '1q', 'Q1', '1Q',  # 添加大写格式
            'first quarter', '1st quarter', 'First Quarter', '1st Quarter'  # 英文大写
        ]
        if any(keyword in title_lower for keyword in q1_keywords):
            return 'Q1'

        # Q2 关键词识别
        q2_keywords = [
            '第二季度', '第二季', '二季度', '二季',
            '2季', 'q2', '2q', 'Q2', '2Q',  # 添加大写格式
            'second quarter', '2nd quarter', 'Second Quarter', '2nd Quarter',  # 英文大写
            '中期', '中報', '半年', '半年度', 'interim', 'half-year', 'half year',
            '六個月', '六个月'  # 添加六个月关键词
        ]
        if any(keyword in title_lower for keyword in q2_keywords):
            return 'Q2'

        # Q3 关键词识别
        q3_keywords = [
            '第三季度', '第三季', '三季度', '三季',
            '3季', 'q3', '3q', 'Q3', '3Q',  # 添加大写格式
            'third quarter', '3rd quarter', 'Third Quarter', '3rd Quarter',  # 英文大写
            '九个月', '九個月', 'nine-month', 'nine month', 'Nine-Month', 'Nine Month'
        ]
        if any(keyword in title_lower for keyword in q3_keywords):
            return 'Q3'

        # Q4 关键词识别
        q4_keywords = [
            '第四季度', '第四季', '四季度', '四季',
            '4季', 'q4', '4q', 'Q4', '4Q',  # 添加大写格式
            'fourth quarter', '4th quarter', 'Fourth Quarter', '4th Quarter',  # 英文大写
            '年终', '年終', 'year-end', 'year end', 'Year-End', 'Year End'
        ]
        if any(keyword in title_lower for keyword in q4_keywords):
            return 'Q4'
        
        # 特殊格式：三個月、三个月（需要结合日期推断季度）
        if '三個月' in title or '三个月' in title:
            # 结合日期推断季度（在后面的日期推断逻辑中处理）
            pass

        # 基于日期的季度推断
        # 匹配"截至XX年XX月XX日止"或"截至XX年XX月止"格式
        截至格式 = re.search(r'截至.*?(\d{4})年(\d{1,2})月(?:(\d{1,2})日)?', title)
        if 截至格式:
            month = int(截至格式.group(2))
            # 根据月份推断季度
            if month in [1, 2, 3]:
                return 'Q1'
            elif month in [4, 5, 6]:
                return 'Q2'
            elif month in [7, 8, 9]:
                return 'Q3'
            elif month in [10, 11, 12]:
                return 'Q4'

        # 匹配中文日期格式"截至二零XX年XX月XX日止"
        中文截至格式 = re.search(r'截至.*?二[零〇](\d{2})年', title)
        if 中文截至格式:
            # 查找中文月份
            for 月份, 数字 in self.CHINESE_MONTH_MAP.items():
                if 月份 in title:
                    month = 数字
                    # 根据月份推断季度
                    if month in [1, 2, 3]:
                        return 'Q1'
                    elif month in [4, 5, 6]:
                        return 'Q2'
                    elif month in [7, 8, 9]:
                        return 'Q3'
                    elif month in [10, 11, 12]:
                        return 'Q4'
                    break

        return None
    
    def extract_year_from_title(self, title: str, timestamp: int) -> str:
        """
        从标题中提取年份（考虑财年截止日期）
        
        注意：对于"截至XX年X月X日止"格式，需要特殊处理
        例如："截至2022年3月31日止"的年报实际是2021财年
        """
        # 清除HTML标签
        title = re.sub(r'<[^>]+>', '', title)

        try:
            dt = datetime.fromtimestamp(timestamp / 1000)
        except (OSError, ValueError, OverflowError):
            dt = datetime.utcnow()
        release_year_str = str(dt.year)

        # 先检查是否为"截至XX年XX月止"格式
        # 这种格式下，需要根据截止月份判断财年
        
        # 方案1：阿拉伯数字年份和月份
        截至格式 = re.search(r'截至.*?(\d{4})年(\d{1,2})月', title)
        if 截至格式:
            year_end = int(截至格式.group(1))
            month_end = int(截至格式.group(2))
            
            # 财年判断规则：根据报告类型区分
            is_annual_report = any(kw in title for kw in ['年报', '年報', '年度', 'annual'])
            fiscal_year = self._determine_fiscal_year(year_end, month_end, is_annual_report)
            return str(fiscal_year)

        # 方案2：中文年份（二零二三年）+ 中文或阿拉伯数字月份
        # 匹配：截至二零二三年三月 或 截至二〇二三年三月
        中文年份格式 = re.search(r'截至.*?二[零〇]([零〇一二三四五六七八九]{2})年', title)
        if 中文年份格式:
            # 将中文数字转换为阿拉伯数字
            中文年份 = 中文年份格式.group(1)
            阿拉伯年份 = self._chinese_numeric_to_arabic(中文年份)
            year_end = 2000 + int(阿拉伯年份)

            # 提取月份（优先使用中文月份，其次阿拉伯数字月份）
            month_end = None
            for 月份, 数字 in self.CHINESE_MONTH_MAP.items():
                if 月份 in title:
                    month_end = 数字
                    break
            
            # 如果找不到中文月份，尝试阿拉伯数字月份
            if month_end is None:
                月份匹配 = re.search(r'二[零〇]\d{2}年(\d{1,2})月', title)
                if 月份匹配:
                    month_end = int(月份匹配.group(1))

            # 判断财年（使用辅助函数）
            if month_end is not None:
                is_annual_report = any(kw in title for kw in ['年报', '年報', '年度', 'annual'])
                fiscal_year = self._determine_fiscal_year(year_end, month_end, is_annual_report)
                return str(fiscal_year)
            
            # 如果无法确定月份，返回年份
            return str(year_end)

        # 优先检查跨年格式（避免被单年份格式误匹配）
        # 年报跨年格式：2022-2023 年报 或 2022/2023年报 → 2022年（取第一个年份）
        # 注意：需要先检查跨年格式，避免"年度格式"误匹配跨年格式中的第二个年份
        # 按顺序检查不同格式（从最常见到最不常见）
        # 格式1: 2022/2023年报 或 2022-2023年报（无空格，年份在年报前） - 最常见
        年报跨年格式1 = re.search(r'(\d{4})[-/](\d{4})(?:年报|年報)', title)
        if 年报跨年格式1:
            return 年报跨年格式1.group(1)  # 取第一个年份（前一个年份）
        
        # 格式1a: 2022/2023年度年报 或 2022-2023年度年报（包含"年度"关键词）
        年报跨年格式1a = re.search(r'(\d{4})[-/](\d{4})年度(?:年报|年報|业绩|業績)', title)
        if 年报跨年格式1a:
            return 年报跨年格式1a.group(1)  # 取第一个年份（前一个年份）
        
        # 格式2: 2022/2023 年报 或 2022-2023 年报（有空格，年份在年报前）
        年报跨年格式2 = re.search(r'(\d{4})[-/](\d{4})\s+(?:年报|年報|annual)', title)
        if 年报跨年格式2:
            return 年报跨年格式2.group(1)  # 取第一个年份（前一个年份）
        
        # 格式2a: 2022/2023 年度年报 或 2022-2023 年度年报（有空格，包含"年度"）
        年报跨年格式2a = re.search(r'(\d{4})[-/](\d{4})\s+年度(?:年报|年報|业绩|業績)', title)
        if 年报跨年格式2a:
            return 年报跨年格式2a.group(1)  # 取第一个年份（前一个年份）
        
        # 格式3: 年报 2022/2023 或 年报 2022-2023（年份在年报后）
        年报跨年格式3 = re.search(r'(?:年报|年報|annual)\s+(\d{4})[-/](\d{4})', title)
        if 年报跨年格式3:
            return 年报跨年格式3.group(1)  # 取第一个年份（前一个年份）
        
        # 格式3a: 年度年报 2022/2023 或 年度业绩 2022-2023（年份在报告类型后，包含"年度"，有空格）
        年报跨年格式3a = re.search(r'年度(?:年报|年報|业绩|業績)\s+(\d{4})[-/](\d{4})', title)
        if 年报跨年格式3a:
            return 年报跨年格式3a.group(1)  # 取第一个年份（前一个年份）
        
        # 格式3b: 年度報告2022/2023 或 年度报告2022/2023（年份在"年度報告"后，无空格）
        年度報告跨年格式 = re.search(r'年度(?:報告|报告)\s*(\d{4})[-/](\d{4})', title)
        if 年度報告跨年格式:
            return 年度報告跨年格式.group(1)  # 取第一个年份（前一个年份）
        
        # 查找省略年份的跨年格式：年报 2024/25 → 2024年（取第一个年份）
        # 年报省略年份格式：年报 2024/25 → 2024年
        年报省略年份格式 = re.search(r'(?:年报|年報|annual).*?(\d{4})[/-](\d{2})|(\d{4})[/-](\d{2})\s*(?:年报|年報|annual)', title)
        if 年报省略年份格式:
            # 取第一个匹配的年份组
            first_year = 年报省略年份格式.group(1) or 年报省略年份格式.group(3)
            if first_year:
                return first_year
        
        # 省略年份格式（包含"年度"）：2024/25年度年报 → 2024年（取第一个年份）
        年报省略年份格式年度 = re.search(r'(\d{4})[/-](\d{2})年度(?:年报|年報|业绩|業績)', title)
        if 年报省略年份格式年度:
            return 年报省略年份格式年度.group(1)  # 取第一个年份（前一个年份）
        
        # 中文数字年报跨年格式：二零二四∕二零二五年年报 → 2024年（取第一个年份）
        # 注意：必须在"年度格式"之前，避免误匹配
        # 注意：.*? 允许匹配"年度"等中间词
        中文年报跨年格式 = re.search(r'二[零〇]([零〇一二三四五六七八九]{2})[∕/]二[零〇]([零〇一二三四五六七八九]{2})年.*?(?:年报|年報|年度|业绩|業績|annual)', title)
        if 中文年报跨年格式:
            # 将第一个中文年份转换为阿拉伯数字
            中文年份1 = 中文年报跨年格式.group(1)
            阿拉伯年份1 = self._chinese_numeric_to_arabic(中文年份1)
            return str(2000 + int(阿拉伯年份1))  # 取第一个年份（前一个年份）
        
        # 中报省略年份格式：中期报告 2023/24 → 2023年（取第一个年份）
        中报省略年份格式 = re.search(r'(?:中期|中報|interim).*?(\d{4})[/-](\d{2})|(\d{4})[/-](\d{2})\s*(?:中期|中報|interim)', title)
        if 中报省略年份格式:
            # 取第一个匹配的年份组
            first_year = 中报省略年份格式.group(1) or 中报省略年份格式.group(3)
            if first_year:
                return first_year
        
        # 中报跨年格式（完整年份）：支持多种格式
        # 格式1: 2022-2023 中期报告 或 2022/2023 中期报告（有空格，年份在前）
        中报跨年格式1 = re.search(r'(\d{4})[-/](\d{4})\s+(?:中期|中報|interim)', title)
        if 中报跨年格式1:
            return 中报跨年格式1.group(1)  # 取第一个年份（前一个年份）
        
        # 格式2: 2022-2023中期报告 或 2022/2023中期报告（无空格，年份在前）
        中报跨年格式2 = re.search(r'(\d{4})[-/](\d{4})(?:中期|中報|interim)', title)
        if 中报跨年格式2:
            return 中报跨年格式2.group(1)  # 取第一个年份（前一个年份）
        
        # 格式3: 中期报告 2022-2023 或 中期报告 2022/2023（年份在后）
        中报跨年格式3 = re.search(r'(?:中期|中報|interim).*?(\d{4})[-/](\d{4})', title)
        if 中报跨年格式3:
            return 中报跨年格式3.group(1)  # 取第一个年份（前一个年份）
        
        # 中文数字跨年格式：二零二三∕二零二四年中期报告 → 2023年（取第一个年份）
        中文中报跨年格式 = re.search(r'二[零〇]([零〇一二三四五六七八九]{2})[∕/]二[零〇]([零〇一二三四五六七八九]{2})年.*?(?:中期|中報|interim)', title)
        if 中文中报跨年格式:
            # 将第一个中文年份转换为阿拉伯数字
            中文年份1 = 中文中报跨年格式.group(1)
            阿拉伯年份1 = self._chinese_numeric_to_arabic(中文年份1)
            return str(2000 + int(阿拉伯年份1))  # 取第一个年份（前一个年份）
        
        # 季报跨年格式：2023-2024 第一季度报告 → 2023年（取第一个年份）
        季报跨年格式 = re.search(r'(\d{4})[-/](\d{4})\s*(?:第一季|第三季|一季度|三季度|1季|3季|Q1|Q3)', title)
        if 季报跨年格式:
            return 季报跨年格式.group(1)  # 取第一个年份（前一个年份）
        
        # 中文数字季报跨年格式：二零二三∕二零二四年第一季度报告 → 2023年（取第一个年份）
        中文季报跨年格式 = re.search(r'二[零〇]([零〇一二三四五六七八九]{2})[∕/]二[零〇]([零〇一二三四五六七八九]{2})年.*?(?:第一季|第三季|一季度|三季度)', title)
        if 中文季报跨年格式:
            # 将第一个中文年份转换为阿拉伯数字
            中文年份1 = 中文季报跨年格式.group(1)
            阿拉伯年份1 = self._chinese_numeric_to_arabic(中文年份1)
            return str(2000 + int(阿拉伯年份1))  # 取第一个年份（前一个年份）
        
        # 通用跨年格式匹配（兜底规则，确保所有跨年格式都取第一个年份）
        # 格式：2023/24、2023-24、2023/2024、2023-2024 等（无论是否有报告类型标识）
        # 注意：这个规则必须在所有特定报告类型的跨年格式之后，避免误匹配
        通用跨年格式1 = re.search(r'(\d{4})[-/](\d{4})', title)  # 完整年份：2023-2024
        if 通用跨年格式1:
            return 通用跨年格式1.group(1)  # 取第一个年份（前一个年份）
        
        通用跨年格式2 = re.search(r'(\d{4})[-/](\d{2})(?!\d)', title)  # 省略年份：2023/24（确保后面不是数字）
        if 通用跨年格式2:
            return 通用跨年格式2.group(1)  # 取第一个年份（前一个年份）
        
        # 标准格式：直接从标题提取年份（单年份格式）
        # 优先查找"XX年报"、"20XX年度"等明确的年份标识
        # 注意：这个必须在所有跨年格式检查之后，避免误匹配跨年格式中的年份
        # 使用负向前瞻确保不是跨年格式的一部分
        
        # 格式A: 2023年年報 或 2023年報（年份在"年報"前，有"年"字）
        年度格式A = re.search(r'(\d{4})年(?!.*?[-/]\d{2,4}).*?(?:报|年度|业绩)', title)
        if 年度格式A:
            return 年度格式A.group(1)
        
        # 格式B: 2023年報 或 2023 年報（年份在"年報"前，无"年"字，可能有空格）
        年度格式B = re.search(r'(\d{4})\s*年報', title)
        if 年度格式B:
            return 年度格式B.group(1)
        
        # 格式C: 年報2022 或 年报2022（年份在"年報"后，无"年"字）
        年度格式C = re.search(r'(?:年报|年報)\s*(\d{4})(?![-/]\d)', title)
        if 年度格式C:
            return 年度格式C.group(1)
        
        # 格式D: 年報（2023）或 年报(2023)（年份在括号中）
        年度括号格式 = re.search(r'(?:年报|年報|annual).*?[（(](\d{4})[）)]', title)
        if 年度括号格式:
            return 年度括号格式.group(1)
        
        # 格式E: 财年格式 FY2023、2023财年、Fiscal Year 2023
        财年格式1 = re.search(r'(?:FY|Fiscal Year)\s*(\d{4})', title, re.I)
        if 财年格式1:
            return 财年格式1.group(1)
        
        财年格式2 = re.search(r'(\d{4})\s*(?:财年|財年|FY)', title, re.I)
        if 财年格式2:
            return 财年格式2.group(1)
        
        # 格式F: 英文格式 Annual Report 2023 或 2023 Annual Report
        英文年报格式1 = re.search(r'Annual Report\s+(\d{4})', title, re.I)
        if 英文年报格式1:
            return 英文年报格式1.group(1)
        
        英文年报格式2 = re.search(r'(\d{4})\s+Annual Report', title, re.I)
        if 英文年报格式2:
            return 英文年报格式2.group(1)
        
        # 格式G: 年份在方括号中 年報【2023】或 年报[2023]
        年度方括号格式 = re.search(r'(?:年报|年報).*?[【[（(](\d{4})[】\]）)]', title)
        if 年度方括号格式:
            return 年度方括号格式.group(1)
        
        # 查找二零一X年格式（2010-2019年，如"二零一七年年報"）
        二零一X年格式 = re.search(r'二零一([零一二三四五六七八九])年', title)
        if 二零一X年格式:
            # 将中文数字转换为阿拉伯数字
            中文数字 = 二零一X年格式.group(1)
            阿拉伯数字 = self.CHINESE_NUMERIC_MAP.get(中文数字, '0')
            return '201' + 阿拉伯数字
        
        # 查找二零XX年格式（XX是两位阿拉伯数字，如"二零17年"）
        二零格式 = re.search(r'二零(\d{2})年', title)
        if 二零格式:
            return '20' + 二零格式.group(1)
        
        # 查找二零二X格式（2020-2029年，如"二零二三年年報"）
        二零二X格式 = re.search(r'二零二([零一二三四五六七八九])', title)
        if 二零二X格式:
            # 将中文数字转换为阿拉伯数字
            中文数字 = 二零二X格式.group(1)
            阿拉伯数字 = self.CHINESE_NUMERIC_MAP.get(中文数字, '0')
            return '202' + 阿拉伯数字

        # 查找任意四位数字年份
        任意年份 = re.search(r'20(\d{2})', title)
        if 任意年份:
            return '20' + 任意年份.group(1)

        # 如果都找不到，用发布时间的前一年（因为报告通常在次年发布）
        # 如果发布月份是1-4月，很可能是前一年的年报
        if dt.month <= 4:
            return str(dt.year - 1)
        return release_year_str
    
    def extract_report_period(self, title: str, timestamp: int) -> Optional[str]:
        """
        从标题中提取报告期末日期
        
        Args:
            title: 公告标题
            timestamp: 发布时间戳
            
        Returns:
            报告期末日期 (格式: YYYY-MM-DD 或 YYYY-MM)，如果无法提取则返回None
        """
        # 清除HTML标签
        title = re.sub(r'<[^>]+>', '', title)
        
        # 方案1：截至XX年XX月XX日止 或 截至XX年XX月止
        截至格式 = re.search(r'截至.*?(\d{4})年(\d{1,2})月(?:(\d{1,2})日)?', title)
        if 截至格式:
            year = 截至格式.group(1)
            month = 截至格式.group(2).zfill(2)
            day = 截至格式.group(3)
            if day:
                day = day.zfill(2)
                return f"{year}-{month}-{day}"
            else:
                # 根据月份确定月末日期
                month_int = int(month)
                if month_int in [1, 3, 5, 7, 8, 10, 12]:
                    return f"{year}-{month}-31"
                elif month_int in [4, 6, 9, 11]:
                    return f"{year}-{month}-30"
                elif month_int == 2:
                    # 简化处理，统一为28日
                    return f"{year}-{month}-28"
                return f"{year}-{month}"
        
        # 方案2：中文月份
        中文截至格式 = re.search(r'截至.*?二[零〇](\d{2})年', title)
        if 中文截至格式:
            year = '20' + 中文截至格式.group(1)
            # 查找中文月份
            for 月份, 数字 in self.CHINESE_MONTH_MAP.items():
                if 月份 in title:
                    month = str(数字).zfill(2)
                    # 尝试查找日期
                    日期匹配 = re.search(rf'{月份}(\d{{1,2}})日', title)
                    if 日期匹配:
                        day = 日期匹配.group(1).zfill(2)
                        return f"{year}-{month}-{day}"
                    return f"{year}-{month}"
        
        # 如果无法提取，返回None
        return None
    
    def _title_contains_year_range(self, title: str) -> bool:
        """
        判断标题是否包含跨年范围（例如 2022-2023、2022/23 等）
        """
        clean_title = re.sub(r'<[^>]+>', '', title)
        patterns = [
            r'20\d{2}\s*[-/]\s*20\d{2}',      # 2022-2023 / 2022/2023
            r'20\d{2}\s*[-/]\s*\d{2}(?!\d)',  # 2022/23
            r'20\d{2}\s*至\s*20\d{2}',        # 2022至2023
            r'二[零〇][零〇一二三四五六七八九]{2}[∕/－-]二[零〇][零〇一二三四五六七八九]{2}',  # 中文数字
        ]
        return any(re.search(pattern, clean_title) for pattern in patterns)
    
    def get_actual_report_type(self, quarter: Optional[str]) -> str:
        """
        根据季度判断实际的报告类型
        
        Args:
            quarter: 季度标识 ('Q1', 'Q2', 'Q3', 'Q4' 或 None)
            
        Returns:
            报告类型: '年报', '中期报告', '第一季度报告', '第三季度报告'
        """
        if not quarter:
            return '未知'
        
        if quarter == 'Q4':
            return '年报'
        elif quarter == 'Q2':
            return '中期报告'
        elif quarter == 'Q1':
            return '第一季度报告'
        elif quarter == 'Q3':
            return '第三季度报告'
        else:
            return '未知'
    
    def _should_exclude_announcement(self, title: str) -> bool:
        """
        检查公告是否应该被剔除（通知、信函、申請、表格等非报表文件）
        
        Args:
            title: 公告标题
            
        Returns:
            True: 应该剔除，False: 应该保留
        """
        # 清除HTML标签
        clean_title = re.sub(r'<[^>]+>', '', title).strip()
        title_lower = clean_title.lower()
        
        # 补充公告关键词（即使包含报告类型关键词，如果是补充公告也应该剔除）
        supplement_keywords = [
            '補充公告', '补充公告', '補充公布', '补充公布',
            'supplement', 'supplementary announcement',
            '補充', '补充'  # 如果标题以"補充"开头或包含"補充公告"，应该剔除
        ]
        
        # 检查是否是补充公告（优先检查，即使包含报告类型关键词也要剔除）
        # 补充公告通常格式：補充公告、補充公布、有關...之補充公告
        # 注意：避免误判，如"補充資料"、"補充說明"等可能不是补充公告
        is_supplement = False
        for keyword in supplement_keywords:
            if keyword in title_lower:
                # 如果标题以补充关键词开头，或者是"補充公告"格式，应该剔除
                if title_lower.startswith(keyword) or '補充公告' in title_lower or '补充公告' in title_lower:
                    is_supplement = True
                    break
                # 如果包含"補充公布"、"補充公布"格式，应该剔除
                if '補充公布' in title_lower or '补充公布' in title_lower:
                    is_supplement = True
                    break
                # 如果包含"補充"且标题较长（可能是补充公告），进一步检查
                if keyword in ['補充', '补充'] and len(clean_title) > 20:
                    # 检查：如果包含"有關...之補充"格式，应该剔除
                    if re.search(r'有關.*?之補充|有关.*?之补充', title_lower):
                        is_supplement = True
                        break
                    # 检查：如果包含"補充公告"或"补充公告"，应该剔除
                    if '補充公告' in title_lower or '补充公告' in title_lower:
                        is_supplement = True
                        break
                    # 避免误判：如果只是"補充資料"、"補充說明"等，不一定是补充公告
                    # 只有当明确包含"補充公告"、"補充公布"时才剔除
                    if not re.search(r'補充(?:資料|说明|說明|材料|文件)', title_lower):
                        # 如果包含"補充"且不是补充资料/说明，可能是补充公告
                        if re.search(r'補充.*?(?:公告|公布)', title_lower):
                            is_supplement = True
                            break
        
        if is_supplement:
            return True
        
        # 澄清公告关键词（即使包含报告类型关键词，如果是澄清公告也应该剔除）
        clarification_keywords = [
            '澄清公告', '澄清公布', '澄清公佈',
            'clarification', 'clarification announcement',
            '澄清'  # 如果标题包含"澄清"，应该剔除
        ]
        
        # 检查是否是澄清公告（优先检查，即使包含报告类型关键词也要剔除）
        # 澄清公告通常格式：澄清公告、澄清公布、(經修訂) 澄清公佈 - ...年報【澄清】
        is_clarification = False
        for keyword in clarification_keywords:
            if keyword in title_lower:
                # 如果标题包含"澄清公告"、"澄清公布"、"澄清公佈"格式，应该剔除
                if '澄清公告' in title_lower or '澄清公布' in title_lower or '澄清公佈' in title_lower:
                    is_clarification = True
                    break
                # 如果包含"澄清"且标题较长（可能是澄清公告），进一步检查
                if keyword == '澄清' and len(clean_title) > 10:
                    # 检查：如果包含"澄清公告"、"澄清公布"、"澄清公佈"，应该剔除
                    if re.search(r'澄清(?:公告|公布|公佈)', title_lower):
                        is_clarification = True
                        break
                    # 如果标题包含"澄清"且包含报告类型关键词（如"年報【澄清】"），应该剔除
                    # 这是澄清公告，不是实际报告
                    if re.search(r'澄清.*?(?:年報|年报|中期|季度|報告|报告)', title_lower) or \
                       re.search(r'(?:年報|年报|中期|季度|報告|报告).*?澄清', title_lower):
                        is_clarification = True
                        break
        
        if is_clarification:
            return True
        
        # 通知信函关键词（即使包含报告类型关键词，如果是通知信函也应该剔除）
        # 例如：登記股東通知信函-於本公司網站刊發2024年中期報告之發佈通知
        notice_letter_keywords = [
            '通知信函', '通知信', '通知函',
            '登記持有人通知信函', '登记持有人通知信函',
            '登記股東通知信函', '登记股东通知信函',
            '非登記持有人通知信函', '非登记持有人通知信函',
            '股東通知信函', '股东通知信函',
            '持有人通知信函',
        ]
        
        # 检查是否是通知信函（优先检查，即使包含报告类型关键词也要剔除）
        # 通知信函通常格式：登記股東通知信函-於本公司網站刊發...報告之發佈通知
        is_notice_letter = False
        # 先检查是否包含通知信函关键词
        for keyword in notice_letter_keywords:
            if keyword in title_lower:
                # 如果标题包含"通知信函"相关关键词，应该剔除
                # 这些只是通知，不是实际报告
                is_notice_letter = True
                break
        # 如果还没匹配到，使用正则表达式检查通知信函模式
        if not is_notice_letter:
            if re.search(r'(?:登記|登记|非登記|非登记)?(?:持有人|股東|股东)?通知(?:信)?函', title_lower):
                is_notice_letter = True
        
        if is_notice_letter:
            return True
        
        # 更正公告关键词（即使包含报告类型关键词，如果是更正公告也应该剔除）
        # 例如：關於2024年中期報告的更正公告
        correction_keywords = [
            '更正公告', '更正公布', '更正公佈',
            'correction', 'correction announcement',
            '更正'  # 如果标题包含"更正"，应该剔除
        ]
        
        # 检查是否是更正公告（优先检查，即使包含报告类型关键词也要剔除）
        # 更正公告通常格式：關於...報告的更正公告、更正公告-...年報
        is_correction = False
        for keyword in correction_keywords:
            if keyword in title_lower:
                # 如果标题包含"更正公告"、"更正公布"、"更正公佈"格式，应该剔除
                if '更正公告' in title_lower or '更正公布' in title_lower or '更正公佈' in title_lower:
                    is_correction = True
                    break
                # 如果包含"更正"且标题较长（可能是更正公告），进一步检查
                if keyword == '更正' and len(clean_title) > 10:
                    # 检查：如果包含"更正公告"、"更正公布"、"更正公佈"，应该剔除
                    if re.search(r'更正(?:公告|公布|公佈)', title_lower):
                        is_correction = True
                        break
                    # 如果标题包含"更正"且包含报告类型关键词（如"關於...年報的更正公告"），应该剔除
                    # 这是更正公告，不是实际报告
                    if re.search(r'更正.*?(?:年報|年报|中期|季度|報告|报告)', title_lower) or \
                       re.search(r'(?:年報|年报|中期|季度|報告|报告).*?更正', title_lower) or \
                       re.search(r'關於.*?(?:年報|年报|中期|季度|報告|报告).*?更正', title_lower):
                        is_correction = True
                        break
        
        if is_correction:
            return True
        
        # 剔除关键词（通知、信函、申請、表格等）
        # 注意：不包含ESG相关关键词，因为年报和ESG有时会合并起名字
        # 注意："補充"、"补充"也包含在此，作为兜底（补充公告检查在前面优先执行）
        exclude_keywords = [
            '通知', '通告', '公告', '通知信', '通知函', '通知書',
            '信函', '函件', '函', '信件', '信',
            '申請', '申请', '申請書', '申请书',
            '表格', '表', '表格文件',
            '補充', '补充', '更正', '修正', '修訂', '修订',
            '說明', '说明', '說明書', '说明书',
            '回覆', '回复', '答覆', '答复',
            '通知股東', '通知股东', '股東通知', '股东通知',
            '登記', '登记', '註冊', '注册',
            '發佈通知', '发布通知', '刊發', '刊发',
            '澄清',  # 澄清公告不需要下载
        ]
        
        # 报告类型关键词（如果包含这些，即使有剔除关键词也保留）
        report_keywords = [
            # 年报关键词
            '年报', '年報', '年度报告', '年度報告', 'annual',
            'annual report', 'annual results',  # 英文大写和Results格式
            '年度業績', '年度业绩',  # 业绩格式
            # 中期报告关键词
            '中期', '中報', '中期报告', '中期報告', 'interim', 'half-year',
            'interim report', 'interim results',  # 英文大写和Results格式
            '中期業績', '中期业绩', '半年度', '半年度报告', '半年度報告',  # 半年度格式
            # 季度报告关键词
            '季度', '季報', '季度报告', '季度報告', 'quarter', 'q1', 'q2', 'q3', 'q4',
            'quarterly report', 'quarterly results',  # 英文大写和Results格式
            '季度業績', '季度业绩',  # 业绩格式
            '第一季', '第二季', '第三季', '第四季',
            # 通用关键词
            '业绩', '業績', 'results', 'financial',
            '財務', '财务', '财务报表', '財務報表', 'financial statement', 'financial report',
            '業績公告', '业绩公告', '財務摘要', '财务摘要',  # 其他表述
        ]
        
        # 检查是否包含报告类型关键词
        has_report_keyword = any(keyword in title_lower for keyword in report_keywords)
        
        # 如果包含报告类型关键词，保留
        if has_report_keyword:
            return False
        
        # 检查是否包含剔除关键词
        has_exclude_keyword = any(keyword in title_lower for keyword in exclude_keywords)
        
        # 如果包含剔除关键词且不包含报告类型关键词，剔除
        if has_exclude_keyword:
            return True
        
        return False
    
    def generate_filename(self, stock_code: str, announcement: Dict) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        生成文件名和保存路径
        
        Returns:
            (save_path, filename, report_period) 三元组
        """
        title = announcement.get('announcementTitle', '')
        timestamp = announcement.get('announcementTime', 0)
        
        # 识别季度
        quarter = announcement.get('hkexQuarter') or self.identify_quarter(title)
        
        # 如果季度仍为None，尝试根据发布日期推断（兜底逻辑，避免遗漏文件）
        if not quarter:
            try:
                dt = datetime.fromtimestamp(timestamp / 1000)
                release_month = dt.month
                if release_month in [1, 2, 3]:
                    quarter = 'Q1'
                elif release_month in [4, 5, 6]:
                    quarter = 'Q2'
                elif release_month in [7, 8, 9]:
                    quarter = 'Q3'
                elif release_month in [10, 11, 12]:
                    quarter = 'Q4'
            except (OSError, ValueError, OverflowError):
                pass
        
        if not quarter:
            return None, None, None
        
        # 提取年份
        year = announcement.get('hkexFiscalYear') or self.extract_year_from_title(title, timestamp)
        
        # 如果年份仍为None，使用发布年份（兜底逻辑，避免遗漏文件）
        if not year:
            try:
                dt = datetime.fromtimestamp(timestamp / 1000)
                year = str(dt.year)
            except (OSError, ValueError, OverflowError):
                return None, None, None
        
        # 提取报告期末日期
        report_period = self.extract_report_period(title, timestamp)
        
        # 如果无法从标题提取报告期末日期，根据季度和财年推断
        if not report_period:
            year_int = int(year)
            if quarter == 'Q1':
                report_period = f"{year_int}-03-31"
            elif quarter == 'Q2':
                report_period = f"{year_int}-06-30"
            elif quarter == 'Q3':
                report_period = f"{year_int}-09-30"
            elif quarter == 'Q4':
                report_period = f"{year_int}-12-31"
        
        # 格式化发布日期
        dt = datetime.fromtimestamp(timestamp / 1000)
        publish_date = dt.strftime('%d-%m-%Y')
        publish_year = dt.strftime('%Y')
        
        # 使用原文件标题中的年份作为命名年份
        # extract_year_from_title 已经处理了跨年格式（取前一个年份）和单年份格式
        naming_year = str(year)
        
        # 如果无法从标题提取年份，进行推测
        if not naming_year or naming_year == 'None':
            # 推测逻辑：根据发布日期和季度推断
            if quarter == 'Q4':
                # 年报通常在次年1-4月发布，使用发布年份的前一年
                if dt.month <= 4:
                    naming_year = str(dt.year - 1)
                else:
                    naming_year = str(dt.year)
            elif quarter == 'Q2':
                # 中期报告通常在7-9月发布，使用发布年份
                naming_year = str(dt.year)
            else:
                # Q1和Q3通常在发布年份
                naming_year = str(dt.year)
        
        # 生成文件名（只使用年份，不包含完整的报告期末日期）
        # naming_year 是文件名中的第一个年份（对于跨年格式，取前一个年份）
        filename = f"{stock_code}_{naming_year}_{quarter}_{publish_date}.pdf"
        
        # 生成完整路径：按照文件名中的第一个年份（naming_year）来存放
        # 例如：00XXX_2023_Q4_05-11-2024.pdf 存放在 {output_dir}/{stock_code}/2023/ 文件夹下
        save_path = os.path.join(self.output_dir, stock_code, naming_year, filename)
        
        return save_path, filename, report_period
    
    def _handle_download_error(self, error_type: str, attempt: int, max_retries: int, 
                                error_msg: str = "", wait_base: float = 2.0) -> Tuple[bool, Optional[str]]:
        """统一的错误处理逻辑"""
        self.rate_limiter.on_error()
        if attempt < max_retries - 1:
            time.sleep(wait_base + random.random())
            return None, None  # 继续重试
        return False, error_msg or f"{error_type}错误"

    def download_pdf(self, url: str, save_path: str, max_retries: int = 3) -> Tuple[bool, Optional[str]]:
        """
        下载PDF文件（支持自动重试）
        
        Returns:
            (success, error_message) 元组
            success: 是否下载成功
            error_message: 如果失败，返回错误信息；成功则返回None
        """
        for attempt in range(max_retries):
            response: Optional[requests.Response] = None
            try:
                self.rate_limiter.acquire()
                response = self.download_session.get(
                    url,
                    headers=self._get_request_headers(),
                    timeout=30,
                    stream=True,
                )
                status_code = response.status_code

                if status_code == 200:
                    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
                    with open(save_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    self.rate_limiter.on_success()
                    return True, None
                if status_code == 404:
                    self.rate_limiter.on_error()
                    return False, "HTTP 404 - 文件不存在"
                if status_code in (403, 429):
                    self.rate_limiter.on_throttle()
                    if attempt < max_retries - 1:
                        wait_seconds = min(180, max(5.0, self.rate_limiter.interval * (attempt + 1) * 4))
                        time.sleep(wait_seconds)
                        continue
                    return False, f"HTTP {status_code} - 访问频率过高，已多次退避"
                if 500 <= status_code < 600:
                    self.rate_limiter.on_error()
                    if attempt < max_retries - 1:
                        wait_seconds = min(90, (2 ** attempt) * 2 + random.random())
                        time.sleep(wait_seconds)
                        continue
                    return False, f"HTTP {status_code} - 服务器错误"

                self.rate_limiter.on_error()
                return False, f"HTTP {status_code} - 未知响应"

            except requests.exceptions.Timeout:
                ret, msg = self._handle_download_error("网络超时", attempt, max_retries)
                if ret is not None:
                    return ret, msg
                continue
            except requests.exceptions.ConnectionError:
                ret, msg = self._handle_download_error("连接", attempt, max_retries, "连接错误")
                if ret is not None:
                    return ret, msg
                continue
            except requests.RequestException as req_err:
                self.rate_limiter.on_error()
                if attempt < max_retries - 1:
                    time.sleep(2 + random.random())
                    continue
                MODULE_LOGGER.error("Request error when downloading %s: %s", url, req_err, exc_info=True)
                return False, f"请求异常: {str(req_err)[:100]}"
            except OSError as os_err:
                self.rate_limiter.on_error()
                if attempt < max_retries - 1:
                    time.sleep(2 + random.random())
                    continue
                MODULE_LOGGER.error("File write error for %s: %s", save_path, os_err, exc_info=True)
                return False, f"文件写入异常: {str(os_err)[:100]}"
            finally:
                if response is not None:
                    response.close()
        
        return False, "下载失败（已达最大重试次数）"
    
    def _log_company_header(self, stock_code: str, company_name: str, stock_id: Optional[str], index: int, total: int) -> None:
        stock_id_display = f" (stockId={stock_id})" if stock_id else ""
        separator = "=" * 70
        self._log(f"\n{separator}")
        self._log(f"[{index}/{total}] {stock_code} - {company_name}{stock_id_display}")
        self._log(separator)
    
    def _update_announcement_stats(self, company_stats: Dict[str, int], 
                                   company_key: str, count: int, global_key: str) -> None:
        """更新公告统计（用于查询结果和筛选结果）"""
        company_stats[company_key] += count
        with self.stats_lock:
            self.stats[global_key] += count
    
    def _update_stats_and_log(self, company_stats: Dict[str, int], stat_key: str, 
                              stock_code: str, company_name: str, actual_report_type: str,
                              year_value: str, report_period: Optional[str], filename: str,
                              pdf_url: str, download_status: str, reason: Optional[str],
                              file_path: Optional[str], original_filename: str) -> None:
        """统一的统计更新和日志记录方法"""
        company_stats[stat_key] += 1
        with self.stats_lock:
            self.stats[stat_key] += 1
        with self.logger_lock:
            self.logger.log_download(
                stock_code=stock_code,
                stock_name=company_name,
                report_type=actual_report_type,
                report_year=year_value,
                report_period=report_period,
                file_name=filename,
                file_url=pdf_url,
                download_status=download_status,
                reason=reason,
                file_path=file_path,
                original_filename=original_filename,
                data_source="香港交易所披露易"
            )

    def _handle_no_announcements(
        self,
        stock_code: str,
        company_name: str,
        report_type_key: str,
        empty_reason: Optional[str],
        state: Dict[str, object],
    ) -> bool:
        brief_reason = empty_reason or "披露易返回空结果"
        self._log(f"    [{stock_code}] 无数据 - {brief_reason}")
        log_report_type = "全部报告" if empty_reason == "缺少 stockId" else report_type_key
        
        # 优化跳过原因描述
        if empty_reason == "缺少 stockId":
            skip_reason = "缺少 stockId，无法查询报告"
        elif empty_reason:
            skip_reason = f"查询无结果：{brief_reason}"
        else:
            skip_reason = "披露易返回空结果，跳过下载"
        
        skip_reason_detail = (
            skip_reason if log_report_type == report_type_key else f"{skip_reason}（{log_report_type}）"
        )

        if (
            not state["no_data_logged"]
            or brief_reason != state["last_reason"]
            or log_report_type != state["last_report_type"]
        ):
            with self.logger_lock:
                self.logger.log_download(
                    stock_code=stock_code,
                    stock_name=company_name,
                    report_type=log_report_type,
                    report_year='',
                    report_period=None,
                    file_name='',
                    file_url='',
                    download_status="Skipped",
                    reason=skip_reason_detail,
                    file_path=None,
                    original_filename='',
                    data_source="香港交易所披露易"
                )
            state["no_data_logged"] = True
            state["last_reason"] = brief_reason
            state["last_report_type"] = log_report_type

        return empty_reason == "缺少 stockId"

    def _handle_announcement(
        self,
        stock_info: Dict,
        company_name: str,
        announcement: Dict,
        sequence_number: int,
        company_stats: Dict[str, int],
    ) -> None:
        stock_code = stock_info['code']
        title = announcement.get('announcementTitle', '')
        adjunct_url = announcement.get('adjunctUrl', '')

        if not adjunct_url:
            return

        pdf_url = urljoin(self.pdf_base_url, adjunct_url)
        timestamp = announcement.get('announcementTime', 0)
        year = announcement.get('hkexFiscalYear') or self.extract_year_from_title(title, timestamp)
        quarter = announcement.get('hkexQuarter') or self.identify_quarter(title)
        year_value = year or ''
        actual_report_type = self.get_actual_report_type(quarter)
        original_filename = re.sub(r'<[^>]+>', '', title).strip()

        save_path, filename, report_period = self.generate_filename(stock_code, announcement)
        if not save_path or not filename:
            reason = "无法生成文件名（缺少季度或年份信息）"
            self._log(f"        [{stock_code}] [失败] {reason}", level="warning")
            self._update_stats_and_log(
                company_stats, 'failed', stock_code, company_name, actual_report_type,
                year_value, report_period, '', pdf_url, "Failed", reason,
                None, original_filename
            )
            return

        # 处理文件已存在的情况：检查URL是否相同，避免重复下载
        filename_conflict = False
        conflict_reason = None
        if os.path.exists(save_path):
            # 从缓存中检查已存在文件的URL（O(1)查询，微秒级）
            existing_url = self._get_existing_file_url_from_log(filename)
            
            # 直接比较URL（URL中没有查询时间戳，无需规范化）
            if existing_url and existing_url == pdf_url:
                # URL相同，说明是同一个文件，跳过下载
                skip_reason = "文件已存在且URL相同，跳过下载"
                self._log(f"        [{stock_code}] [跳过] {skip_reason}: {filename}")
                self._update_stats_and_log(
                    company_stats, 'skipped', stock_code, company_name, actual_report_type,
                    year_value, report_period, filename, pdf_url, "Skipped", skip_reason,
                    save_path, original_filename
                )
                return
            elif existing_url and existing_url != pdf_url:
                # URL不同，说明是不同的文件，生成新文件名
                filename_conflict = True
                conflict_reason = "文件已存在但URL不同，已生成新文件名"
                self._log(f"        [{stock_code}] [冲突] {conflict_reason}: {filename}", level="warning")
            else:
                # 无法获取已存在文件的URL，为安全起见生成新文件名
                filename_conflict = True
                conflict_reason = "文件已存在但无法验证URL，已生成新文件名"
                self._log(f"        [{stock_code}] [冲突] {conflict_reason}: {filename}", level="warning")
            
            # URL不同或无法获取URL，生成新的唯一文件名（添加序号）
            if filename_conflict:
                filename = self._generate_unique_filename(save_path, filename)
                save_path = os.path.join(os.path.dirname(save_path), filename)

        self._log(f"    [{stock_code}] [{sequence_number}] [下载] {filename}")
        self._log(f"        [{stock_code}] {title[:60]}...")
        success, download_error = self.download_pdf(pdf_url, save_path)

        if success:
            # 更新缓存（下载成功后）
            self._update_file_url_cache(filename, pdf_url)
            self._log(f"        [{stock_code}] [成功] {filename}")
            
            # 生成成功备注
            if filename_conflict:
                # 文件名冲突，说明是因为文件已存在但URL不同，生成了新文件名
                success_reason = conflict_reason
            else:
                # 没有文件名冲突，说明是首次下载
                success_reason = "首次下载成功"
            
            self._update_stats_and_log(
                company_stats, 'downloaded', stock_code, company_name, actual_report_type,
                year_value, report_period, filename, pdf_url, "Success", success_reason,
                save_path, original_filename
            )
        else:
            self._log(f"        [{stock_code}] [失败] {download_error}", level="warning")
            self._update_stats_and_log(
                company_stats, 'failed', stock_code, company_name, actual_report_type,
                year_value, report_period, filename, pdf_url, "Failed", download_error,
                None, original_filename
            )

        time.sleep(0.2 + random.random() * 0.4)
    
    def _generate_unique_filename(self, existing_path: str, base_filename: str) -> str:
        """
        生成唯一的文件名（当文件已存在时，添加序号后缀）
        
        Args:
            existing_path: 已存在的文件路径
            base_filename: 基础文件名
            
        Returns:
            新的唯一文件名（格式：{原文件名}_数字.pdf）
        """
        directory = os.path.dirname(existing_path)
        name_part, ext_part = os.path.splitext(base_filename)
        
        counter = 1
        while True:
            new_filename = f"{name_part}_{counter}{ext_part}"
            new_path = os.path.join(directory, new_filename)
            if not os.path.exists(new_path):
                return new_filename
            counter += 1
            if counter > 100:  # 防止无限循环
                # 使用时间戳作为最后手段
                timestamp = datetime.now().strftime('%H%M%S')
                return f"{name_part}_{timestamp}{ext_part}"
    
    def _process_report_type(
        self,
        stock_info: Dict,
        company_name: str,
        report_type_key: str,
        company_stats: Dict[str, int],
        state: Dict[str, object],
    ) -> bool:
        stock_code = stock_info['code']
        stock_id = stock_info.get('stockId')
        announcements, empty_reason = self.query_reports(stock_code, stock_id, report_type_key)

        if not announcements:
            return self._handle_no_announcements(stock_code, company_name, report_type_key, empty_reason, state)

        self._log(f"    [{stock_code}] 查询到 {len(announcements)} 条公告")
        self._update_announcement_stats(company_stats, 'total', len(announcements), 'total_announcements')

        # 筛选有效公告：必须有PDF附件，且不是通知、信函、申請、表格等非报表文件
        valid_announcements = []
        excluded_count = 0
        for announcement in announcements:
            if not announcement.get('adjunctUrl'):
                continue
            
            title = announcement.get('announcementTitle', '')
            if self._should_exclude_announcement(title):
                excluded_count += 1
                continue
            
            valid_announcements.append(announcement)
        
        if excluded_count > 0:
            self._log(f"    [{stock_code}] 剔除 {excluded_count} 条非报表文件（通知/信函/申請/表格等）")
        
        self._update_announcement_stats(company_stats, 'filtered', len(valid_announcements), 'filtered_reports')

        for sequence_number, announcement in enumerate(valid_announcements, 1):
            self._handle_announcement(stock_info, company_name, announcement, sequence_number, company_stats)

        self._log(f"    [{stock_code}] 有效公告: {len(valid_announcements)}/{len(announcements)}")
        return False

    def process_company(self, stock_info: Dict, index: int, total: int):
        """处理单个公司的所有报告（线程安全版本）"""
        stock_code = stock_info['code']
        company_name = stock_info['name']
        if not stock_info.get('stockId'):
            resolved = self._resolve_stock_id(stock_code, company_name)
            if resolved:
                stock_info['stockId'] = resolved
        company_stats = {
            'total': 0,
            'filtered': 0,
            'downloaded': 0,
            'skipped': 0,
            'failed': 0
        }
        state = {"no_data_logged": False, "last_reason": "", "last_report_type": ""}

        self._log_company_header(stock_code, company_name, stock_info.get('stockId'), index, total)

        for report_type_key in ['年报', '中期报告', '季度报告']:
            self._log(f"\n  [{stock_code}] [{report_type_key}]")
            should_break = self._process_report_type(
                stock_info,
                company_name,
                report_type_key,
                company_stats,
                state,
            )
            if should_break:
                break

        self._log(
            f"\n  [{stock_code}] 公司统计: 查询{company_stats['total']} | 有效{company_stats['filtered']} | "
            f"下载{company_stats['downloaded']} | 跳过{company_stats['skipped']}"
        )
    
    def run(self, start_idx: int = 0, end_idx: Optional[int] = None, 
            start_year: int = 2022, end_year: int = 2025, max_workers: int = 10):
        """
        运行爬虫（多线程版本）
        
        Args:
            start_idx: 起始公司索引（从0开始）
            end_idx: 结束公司索引（不包含），None表示到最后
            start_year: 起始年份
            end_year: 结束年份
            max_workers: 最大线程数（默认5，建议3-10）
        """
        print("\n" + "="*70)
        print("巨潮资讯网 - 港股上市公司报告爬虫（增强版 - 多线程）")
        print("="*70)
        print(f"输出目录: {os.path.abspath(self.output_dir)}")
        print(f"财务年度: {start_year} - {end_year} 年")
        print(f"查询日期: {start_year}-01-01 ~ {end_year + 1}-12-31 (含{end_year}年报)")
        print(f"新增功能: 智能筛选真实财务报表 + 多线程下载")
        print(f"线程数: {max_workers} (建议3-10，避免被服务器拒绝)")
        print("="*70)
        adaptive_base_interval = 0.2 + max(0, max_workers - 1) * 0.05
        self.rate_limiter.update_base_interval(min(1.5, adaptive_base_interval))
        
        # 读取股票代码
        stock_list = self.load_stock_codes()
        
        if not stock_list:
            print("\n[错误] 未能读取股票代码")
            return
        
        # 限制公司范围
        total_companies = len(stock_list)
        if end_idx is None:
            end_idx = total_companies
        
        # 确保索引有效
        start_idx = max(0, min(start_idx, total_companies - 1))
        end_idx = max(start_idx + 1, min(end_idx, total_companies))
        
        stock_list = stock_list[start_idx:end_idx]
        self.stats['total_companies'] = len(stock_list)
        print(f"\n[范围] 处理第 {start_idx + 1} 至第 {end_idx} 家公司（共 {len(stock_list)} 家）")
        
        # 保存年份范围供查询使用
        # 注意：年报通常在次年发布，所以结束日期要加1年
        # 例如：2024年报在2025年3-4月发布
        self.start_date = f"{start_year}-01-01"
        self.end_date = f"{end_year + 1}-12-31"  # 结束年份+1，确保能查到该年的年报
        
        print(f"\n[2/4] 开始多线程爬取报告...")
        print(f"[提示] 使用 {max_workers} 个线程并发下载，速度将显著提升")
        
        # 使用线程池并发处理公司
        completed = 0
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_stock = {
                executor.submit(self.process_company, stock_info, idx, len(stock_list)): stock_info
                for idx, stock_info in enumerate(stock_list, 1)
            }
            
            # 处理完成的任务
            try:
                for future in as_completed(future_to_stock):
                    stock_info = future_to_stock[future]
                    completed += 1
                    
                    try:
                        future.result()  # 获取结果，如果有异常会抛出
                    except Exception as exc:  # pylint: disable=broad-except
                        stock_code = stock_info.get('code', 'UNKNOWN')
                        company_name = stock_info.get('name', '')
                        error_message = f"公司处理异常: {exc}"
                        print(f"\n[错误] 处理 {stock_code} 时出错: {exc}")
                        MODULE_LOGGER.error("Exception while processing %s: %s", stock_code, exc, exc_info=True)
                        with self.stats_lock:
                            self.stats['company_errors'] += 1
                        with self.logger_lock:
                            self.logger.log_download(
                                stock_code=stock_code,
                                stock_name=company_name,
                                report_type="全部报告",
                                report_year='',
                                report_period=None,
                                file_name='',
                                file_url='',
                                download_status="Failed",
                                reason=error_message,
                                file_path=None,
                                original_filename='',
                                data_source="香港交易所披露易"
                            )
                    
                    # 显示进度
                    elapsed = time.time() - start_time
                    avg_time = elapsed / completed if completed > 0 else 0
                    remaining = len(stock_list) - completed
                    eta = avg_time * remaining if remaining > 0 else 0
                    
                    print(f"\n[进度] {completed}/{len(stock_list)} 完成 | "
                          f"已用时: {elapsed/60:.1f}分钟 | "
                          f"预计剩余: {eta/60:.1f}分钟")
                    
            except KeyboardInterrupt:
                print("\n\n[中断] 用户停止，正在清理线程...")
                # 取消未完成的任务
                for future in future_to_stock:
                    future.cancel()
                print("[提示] 已取消所有未完成的任务")
        
        # 保存日志
        self.logger.save_log()
        
        # 清理缓存（释放内存，虽然Python会自动垃圾回收，但显式清理更明确）
        self._clear_file_url_cache()
        
        self.print_final_stats()
    
    def print_final_stats(self):
        """打印最终统计信息"""
        print("\n" + "="*70)
        print("[3/4] 爬取完成 - 统计报告")
        print("="*70)
        print(f"处理公司数: {self.stats['total_companies']}")
        print(f"查询公告数: {self.stats['total_announcements']}")
        print(f"有效报表数: {self.stats['filtered_reports']} "
              f"(筛选率: {self.stats['filtered_reports']/self.stats['total_announcements']*100:.1f}%)" if self.stats['total_announcements'] > 0 else "")
        print(f"成功下载: {self.stats['downloaded']}")
        print(f"跳过文件: {self.stats['skipped']} (已存在)")
        print(f"失败文件: {self.stats['failed']}")
        print(f"公司处理异常: {self.stats['company_errors']}")
        
        if self.stats['filtered_reports'] > 0:
            success_rate = (self.stats['downloaded'] / self.stats['filtered_reports']) * 100
            print(f"下载成功率: {success_rate:.1f}%")
        
        print("="*70)
        print(f"\n[4/4] 文件保存位置: {os.path.abspath(self.output_dir)}")
        print("\n爬虫任务完成！")


def run_listing_date_update(company_csv_path: str,
                            output_csv_path: str,
                            mode_choice: Optional[str] = None,
                            non_interactive: bool = False) -> bool:
    """根据AKShare获取上市日期并保存到输出文件。"""
    print("\n" + "=" * 70)
    print("港股上市日期批量更新")
    print("=" * 70)

    if not os.path.exists(company_csv_path):
        print(f"\n[错误] 未找到公司列表文件: {company_csv_path}")
        print("请先确保已生成 HKEX/company.csv")
        return False

    try:
        df = pd.read_csv(company_csv_path, encoding='utf-8-sig')
    except (FileNotFoundError, OSError, ValueError, pd.errors.EmptyDataError, pd.errors.ParserError) as err:
        print(f"\n[错误] 读取文件失败: {err}")
        MODULE_LOGGER.error("Failed to read company CSV %s: %s", company_csv_path, err, exc_info=True)
        return False

    total_companies = len(df)
    print(f"读取公司数量: {total_companies}")

    if '上市日期' not in df.columns:
        df['上市日期'] = ''
    else:
        df['上市日期'] = df['上市日期'].fillna('').astype(str)

    # 交互选择处理范围
    if mode_choice is None:
        if non_interactive:
            mode_choice = '3'
        else:
            print("\n请选择上市日期更新范围:")
            print("  1. 测试模式（前10家公司）")
            print("  2. 小批量（前100家公司）")
            print("  3. 完整处理（全部公司，可能耗时约1.5小时）")
            mode_choice = input("\n请输入选择 (1/2/3，默认3): ").strip() or '3'

    if mode_choice == '1':
        end_idx = min(10, total_companies)
        print("\n[测试模式] 仅更新前10家公司")
    elif mode_choice == '2':
        end_idx = min(100, total_companies)
        print("\n[小批量模式] 更新前100家公司")
    else:
        end_idx = total_companies
        print(f"\n[完整模式] 更新全部 {total_companies} 家公司")
        if not non_interactive:
            confirm = input("此操作耗时较长，确认继续？(y/n，默认y): ").strip().lower() or 'y'
            if confirm != 'y':
                print("\n已取消上市日期更新")
                return False

    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)

    success_count = 0
    fail_count = 0
    start_time = datetime.now()

    print("\n开始获取上市日期...")
    print("-" * 70)

    for idx in range(end_idx):
        row = df.iloc[idx]
        stock_code = str(row['股份代號']).zfill(5)
        stock_name = row.get('股份名稱', '')

        print(f"[{idx + 1}/{end_idx}] {stock_code} - {stock_name}")

        try:
            profile = ak.stock_hk_security_profile_em(symbol=stock_code)

            if isinstance(profile, pd.DataFrame) and not profile.empty and '上市日期' in profile.columns:
                listing_date = profile['上市日期'].iloc[0]

                if pd.notna(listing_date):
                    if isinstance(listing_date, str) and ' ' in listing_date:
                        listing_date = listing_date.split(' ')[0]

                    df.at[idx, '上市日期'] = listing_date
                    print(f"  [成功] 上市日期: {listing_date}")
                    success_count += 1
                else:
                    print("  [无数据] 上市日期为空")
                    fail_count += 1
            else:
                print("  [失败] 未获取到上市日期数据")
                fail_count += 1

        except (requests.RequestException, ValueError, KeyError, TypeError) as err:
            print(f"  [错误] {str(err)[:80]}")
            MODULE_LOGGER.warning("Failed to fetch listing date for %s: %s", stock_code, err, exc_info=True)
            fail_count += 1

        if (idx + 1) % 10 == 0:
            try:
                df.to_csv(output_csv_path, index=False, encoding='utf-8-sig')
                elapsed = (datetime.now() - start_time).total_seconds()
                avg_time = elapsed / (idx + 1)
                remaining = max(end_idx - idx - 1, 0) * avg_time
                print(f"\n  [进度] 已处理 {idx + 1}/{end_idx} | 成功 {success_count} | 失败 {fail_count}")
                print(f"  [时间] 已用 {elapsed/60:.1f} 分钟 | 预计剩余 {remaining/60:.1f} 分钟")
                print(f"  [保存] 临时保存到 {output_csv_path}")
            except (OSError, PermissionError, ValueError) as save_error:
                print(f"\n  [警告] 保存文件失败: {save_error}")
                MODULE_LOGGER.warning("Temporary save of listing dates failed: %s", save_error, exc_info=True)

        time.sleep(0.5)

    try:
        df.to_csv(output_csv_path, index=False, encoding='utf-8-sig')
        print(f"\n[保存] 最终文件已保存到: {output_csv_path}")
    except (OSError, PermissionError, ValueError) as err:
        print(f"\n[错误] 保存上市日期文件失败: {err}")
        MODULE_LOGGER.error("Failed to persist listing dates to %s: %s", output_csv_path, err, exc_info=True)
        return False

    print("\n" + "=" * 70)
    print("上市日期更新完成")
    print("=" * 70)
    print(f"总处理数: {end_idx}")
    print(f"成功获取: {success_count}")
    print(f"失败/无数据: {fail_count}")
    if end_idx:
        print(f"成功率: {success_count / end_idx * 100:.1f}%")
    print(f"输出文件: {output_csv_path}")

    preview = df.head(min(10, end_idx))
    if not preview.empty:
        print("\n前几家公司上市日期预览:")
        print(preview[['股份代號', '股份名稱', '上市日期']].to_string(index=False))

    return True


def main(raw_args: Optional[List[str]] = None):
    """主函数"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    args = parse_arguments(raw_args)

    try:
        config_data = load_config_file(script_dir, getattr(args, "config", None))
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as config_error:
        print(f"\n[错误] 配置文件处理失败: {config_error}")
        sys.exit(1)

    try:
        settings = merge_settings(script_dir, args, config_data)
    except (ValueError, TypeError) as merge_error:
        print(f"\n[错误] 参数解析失败: {merge_error}")
        MODULE_LOGGER.error("merge_settings failed: %s", merge_error, exc_info=True)
        sys.exit(1)

    runtime_logger, runtime_log_file = setup_runtime_logger(settings["log_dir"])
    runtime_mode = "定时/非交互" if settings["non_interactive"] else "交互"
    runtime_logger.info("运行模式: %s", runtime_mode)
    runtime_logger.info("运行日志文件: %s", runtime_log_file)
    print(f"\n[运行日志] {runtime_log_file}")

    if settings["non_interactive"]:
        exit_code = run_scheduled(settings, runtime_logger)
        sys.exit(exit_code)

    non_interactive = False

    stock_list_file = settings["stock_list_file"]
    output_dir = settings["output_dir"]
    log_dir = settings["log_dir"]
    log_format = settings["log_format"]
    force_download_list = settings["force_download_list"]
    
    # 创建爬虫实例（用于访问下载功能）
    temp_crawler = CninfoHKReportCrawlerEnhanced(
        stock_list_file,
        output_dir,
        log_dir,
        log_format,
        enable_console_output=not settings["non_interactive"],
    )
    
    # 检查股票列表文件是否存在，不存在则自动下载
    if not os.path.exists(stock_list_file):
        print("\n" + "="*70)
        print("未找到股票列表文件，将自动从香港交易所下载")
        print("="*70)
        
        if not temp_crawler.ensure_stock_list():
            print("\n[错误] 无法获取股票列表，程序退出")
            return
    else:
        # 询问是否更新列表
        print("\n" + "="*70)
        print(f"发现已存在的股票列表: {stock_list_file}")
        print("="*70)
        
        # 检查是否为强制刷新或非交互模式
        if force_download_list:
            print("\n根据参数要求，重新下载最新股票列表...")
            temp_crawler.ensure_stock_list(force_download=True)
        elif non_interactive:  # 兼容旧逻辑
            print("使用现有列表（非交互模式）")
        else:
            update_choice = input("\n是否重新从香港交易所下载最新列表？(y/n，默认n): ").strip().lower()
            
            if update_choice == 'y':
                print("\n开始更新股票列表...")
                temp_crawler.ensure_stock_list(force_download=True)
    
    # 统计当前列表公司数量
    total_companies_in_list = 0
    try:
        company_df_snapshot = pd.read_csv(stock_list_file, encoding='utf-8-sig')
        total_companies_in_list = len(company_df_snapshot)
    except (OSError, ValueError, pd.errors.EmptyDataError, pd.errors.ParserError) as snapshot_error:
        MODULE_LOGGER.warning("Failed to load company snapshot from %s: %s", stock_list_file, snapshot_error, exc_info=True)
        total_companies_in_list = 0
    
    print("\n" + "="*70)
    print("港股财务报表批量下载工具 - 参数设置")
    print("="*70)
    print("提示：以下所有参数都可以自定义设置，直接回车使用默认值")
    if total_companies_in_list:
        print(f"提示：当前列表共 {total_companies_in_list} 家公司")
    print("="*70)
    
    # 是否更新上市日期
    if settings["non_interactive"]:
        update_listing_choice_raw = 'y'
    else:
        update_listing_choice_raw = input("\n是否需要在下载完成后更新上市日期？(y/n，默认y): ").strip().lower() or 'y'
    update_listing_choice = update_listing_choice_raw.lower()
    update_listing_enabled = update_listing_choice not in ('n', 'no')
    if update_listing_enabled:
        print("[确认] 下载完财报后将自动更新上市日期")
    else:
        print("[提示] 将跳过上市日期更新")
    
    # ==================== 1. 设置股票范围 ====================
    print("\n【步骤1/3】设置股票范围:")
    if total_companies_in_list:
        print(f"提示：当前列表包含 {total_companies_in_list} 家上市公司")
        print("示例：输入 1-50 表示下载第1到第50家公司")
        print(f"示例：输入 1-{total_companies_in_list} 或留空表示下载全部公司")
    else:
        print("提示：港股共有约2717家上市公司（实际数量取决于列表文件）")
        print("示例：输入 1-50 表示下载第1到第50家公司")
        print("示例：输入 1-200 表示下载第1到第200家公司，留空表示下载全部公司")
        print("提示：无法确定公司总数，将按默认设置处理")
    
    while True:
        stock_range = input("\n请输入股票范围 (格式: 起始序号-结束序号，如 1-50，默认全部): ").strip()
        
        if not stock_range:
            start_idx = 0
            end_idx = None
            if total_companies_in_list:
                print(f"[默认] 将下载全部 {total_companies_in_list} 家公司")
            else:
                print("[默认] 将下载全部公司")
            break
        
        try:
            if '-' in stock_range:
                start_str, end_str = stock_range.split('-')
                start_idx = int(start_str.strip()) - 1  # 转为0-based索引
                end_idx = int(end_str.strip())
                
                max_company_index = total_companies_in_list if total_companies_in_list else 2717
                if start_idx < 0 or start_idx >= max_company_index:
                    print(f"[错误] 起始序号必须在 1-{max_company_index} 之间")
                    continue
                if end_idx <= start_idx or end_idx > max_company_index:
                    print(f"[错误] 结束序号必须大于起始序号且不超过{max_company_index}")
                    continue
                
                print(f"[确认] 将处理第 {start_idx + 1} 至第 {end_idx} 家公司（共 {end_idx - start_idx} 家）")
                break
            else:
                print("[错误] 格式错误，请使用 '起始-结束' 格式，如 1-50")
                
        except ValueError:
            print("[错误] 请输入有效的数字")
    
    # ==================== 2. 设置年份范围 ====================
    print("\n【步骤2/3】设置年份范围:")
    print("提示：建议下载范围 2022-2025")
    print("示例：输入 2022-2025 表示只下载2022、2023、2024、2025四年的报告")
    
    while True:
        year_range = input("\n请输入年份范围 (格式: 起始年份-结束年份，如 2022-2025，默认 2022-2025): ").strip()
        
        if not year_range:
            start_year = 2022
            end_year = 2025
            print(f"[默认] 使用默认年份范围：2022-2025")
            break
        
        try:
            if '-' in year_range:
                start_year_str, end_year_str = year_range.split('-')
                start_year = int(start_year_str.strip())
                end_year = int(end_year_str.strip())
                
                if start_year < 2000 or start_year > 2030:
                    print("[错误] 起始年份必须在 2000-2030 之间")
                    continue
                if end_year <= start_year or end_year > 2030:
                    print(f"[错误] 结束年份必须大于起始年份且不超过2030")
                    continue
                
                print(f"[确认] 将下载 {start_year}-{end_year} 年的报告（{end_year - start_year + 1} 年）")
                break
            else:
                print("[错误] 格式错误，请使用 '起始年份-结束年份' 格式，如 2022-2024")
                
        except ValueError:
            print("[错误] 请输入有效的年份")
    
    # ==================== 3. 设置线程数 ====================
    print("\n【步骤3/3】设置多线程下载配置:")
    print("提示：线程数越多速度越快，但可能被服务器拒绝")
    print("建议：5-8个线程，默认8个")
    print("注意：如果遇到频繁被拒绝，请降低线程数")
    
    while True:
        threads_input = input("\n请输入线程数 (1-20，默认8): ").strip() if not non_interactive else ''
        
        if not threads_input:
            max_workers = 8
            if not non_interactive:
                print(f"[默认] 使用8个线程")
            break
        
        try:
            max_workers = int(threads_input)
            if 1 <= max_workers <= 20:
                print(f"[确认] 使用 {max_workers} 个线程")
                break
            else:
                print("[错误] 线程数应在 1-20 之间，建议3-10")
        except ValueError:
            print("[错误] 请输入有效的数字")

    # ==================== 显示最终配置 ====================
    print("\n" + "="*70)
    print("最终配置确认")
    print("="*70)
    if end_idx is not None:
        effective_end_idx = end_idx
        total_selected = max(effective_end_idx - start_idx, 0)
        print(f"股票范围: 第 {start_idx + 1} 至第 {effective_end_idx} 家")
        print(f"公司数量: {total_selected} 家")
    elif total_companies_in_list:
        effective_end_idx = total_companies_in_list
        total_selected = max(total_companies_in_list - start_idx, 0)
        print(f"股票范围: 第 {start_idx + 1} 至第 {effective_end_idx} 家")
        print(f"公司数量: {total_selected} 家")
    else:
        effective_end_idx = None
        total_selected = None
        print("股票范围: 未知（未能推断公司总数）")
        print("公司数量: 未知（请确认 HKEX/company.csv 内容）")
    print(f"年份范围: {start_year}-{end_year} ({end_year - start_year + 1} 年)")
    print(f"报告类型: 年报、中期报告、季度报告")
    print(f"线程数: {max_workers} (多线程并发下载)")
    print(f"保存目录: {os.path.abspath(output_dir)}")
    print(f"上市日期更新: {'是' if update_listing_enabled else '否'}")
    
    # 估算时间
    if total_selected is not None:
        company_count = total_selected
    else:
        estimated_total = 2717
        company_count = estimated_total - start_idx
    if company_count <= 10:
        estimated_time = f"约{company_count * 2}分钟"
    elif company_count <= 100:
        estimated_time = f"约{company_count * 1.5 / 60:.1f}小时"
    else:
        estimated_time = f"约{company_count * 1.2 / 60 / max_workers:.1f}小时（多线程）"
    print(f"预计时间: {estimated_time}")
    print("="*70)
    
    confirm = input("\n确认以上配置并开始下载？(yes/no，默认yes): ").strip().lower()
    if confirm == 'no' or confirm == 'n':
        print("\n已取消下载")
        runtime_logger.info("用户取消下载操作")
        return
    
    # 创建爬虫实例并运行
    crawler = CninfoHKReportCrawlerEnhanced(
        stock_list_file,
        output_dir,
        log_dir,
        log_format,
        enable_console_output=not settings["non_interactive"],
    )
    
    try:
        crawler.run(
            start_idx=start_idx,
            end_idx=end_idx,
            start_year=start_year,
            end_year=end_year,
            max_workers=max_workers
        )

        if update_listing_enabled:
            listing_output_file = os.path.join(output_dir, "company_with_listing_date.csv")
            try:
                success = run_listing_date_update(
                    company_csv_path=stock_list_file,
                    output_csv_path=listing_output_file,
                    mode_choice=None,
                    non_interactive=non_interactive
                )
                if not success:
                    print("\n[提示] 上市日期更新未完成，可稍后手动运行脚本重新更新")
                    runtime_logger.warning("上市日期更新未成功")
                else:
                    runtime_logger.info("上市日期更新完成: %s", listing_output_file)
            except (ValueError, OSError, RuntimeError, requests.RequestException) as listing_error:
                print(f"\n[错误] 上市日期更新过程中出现异常: {listing_error}")
                runtime_logger.exception("上市日期更新异常: %s", listing_error)
        else:
            runtime_logger.info("根据配置跳过上市日期更新")
    except KeyboardInterrupt:
        print("\n\n[中断] 程序被用户中断")
        print(f"[提示] 重新运行程序时，已下载的文件会自动跳过")
        runtime_logger.warning("用户中断下载任务")
    except Exception as err:  # pylint: disable=broad-except
        print(f"\n[严重错误] {err}")
        runtime_logger.exception("交互运行发生严重错误: %s", err)
        raise
    else:
        runtime_logger.info(
            "交互模式下载完成：公司范围 %s-%s，年份 %s-%s",
            start_idx + 1,
            effective_end_idx if 'effective_end_idx' in locals() and effective_end_idx else 'ALL',
            start_year,
            end_year,
        )


if __name__ == "__main__":
    main()

