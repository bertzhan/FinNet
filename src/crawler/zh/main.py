# -*- coding: utf-8 -*-
"""
CNINFO 定期报告抓取（含全新 orgId 获取策略 + 多进程支持）
- orgId 获取：
  1) 优先：hisAnnouncement/query + stock=<code>.<EX>（如 000001.SZ），从返回公告中的 orgId 提取
  2) 兜底：检索 HTML 页，解析首条详情链接 querystring 里的 orgId
- 交易所映射：保存目录 "SZ/SH/BJ"，接口 column "szse/shse/bse"，stock 后缀 ".SZ/.SH/.BJ"
- Q4 跨年时间窗 + 分页；只用 adjunctUrl→static 直链下载（避免详情页 404）
- 断点续抓 / orgId 缓存 / 名称变更记录 / 滚动错误日志 / Windows 友好 CSV
- 多进程并发：支持多个 worker 进程并行下载，显著提升性能
"""

import os
import re
import csv
import sys
import json
import time
import glob
import random
import atexit
import logging
import argparse
import platform
import threading
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, Tuple, Optional, List
from urllib.parse import urlencode, urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from urllib3.util.retry import Retry

# SQLite-based 状态管理（替代 JSON）
try:
    from state_db import SharedStateSQLite
    USE_SQLITE = True
except ImportError:
    logging.warning("⚠️  未找到 state_db.py，将使用 JSON 模式（性能较低）")
    USE_SQLITE = False

# ----------------------- 常量与配置 -----------------------
CNINFO_API = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STATIC = "https://static.cninfo.com.cn/"
CNINFO_SEARCH = "https://www.cninfo.com.cn/new/search"

CATEGORY_ALL = "category_yjdbg_szsh;category_sjdbg_szsh;category_bndbg_szsh;category_ndbg_szsh;"

# Category mapping for each quarter (more reliable than title pattern matching)
CATEGORY_MAP = {
    "Q1": "category_yjdbg_szsh;",      # 一季度报告 (First quarter report)
    "Q2": "category_bndbg_szsh;",      # 半年度报告 (Semi-annual report)
    "Q3": "category_sjdbg_szsh;",      # 三季度报告 (Third quarter report)
    "Q4": "category_ndbg_szsh;",       # 年度报告 (Annual report)
}

HEADERS_API = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",  # Removed 'br' (Brotli) - requires brotli package
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.cninfo.com.cn",
    "Referer": "https://www.cninfo.com.cn/",
    "X-Requested-With": "XMLHttpRequest",
    "Connection": "keep-alive",
    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}
HEADERS_HTML = {
    "User-Agent": HEADERS_API["User-Agent"],
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",  # Removed 'br' (Brotli) - requires brotli package
    "Referer": "https://www.cninfo.com.cn/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
}

# 如需代理，按需填写；默认 None
PROXIES = None
# PROXIES = {"http": "http://ip:port", "https": "http://ip:port"}

# 排除关键词
EXCLUDE_IN_TITLE = ("摘要", "英文", "英文版")

# 状态文件路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# checkpoint.json 存储在输出目录（与输出绑定）
# orgid_cache 和 code_change_cache 存储在脚本目录（全局共享）
ORGID_CACHE_FILE = os.path.join(SCRIPT_DIR, "orgid_cache.json")
CODE_CHANGE_CACHE_FILE = os.path.join(SCRIPT_DIR, "code_change_cache.json")
NAME_CHANGE_CSV = os.path.join(SCRIPT_DIR, "name_changes.csv")

RETRY_STATUS = (403, 502, 503, 504)
RETRY_TIMES = 3
RETRY_BACKOFF = 1.0
INTER_COMBO_SLEEP_RANGE = (2.0, 3.0)  # 组合间睡眠
INTER_SAME_STOCK_GAP = 1.0            # 同一股票间隔

CSV_ENCODING = "gbk" if platform.system().lower().startswith("win") else "utf-8-sig"

# ----------------------- 日志 -----------------------
ERROR_LOG_FILE = os.path.join(SCRIPT_DIR, "error.log")

logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
file_handler = logging.FileHandler(ERROR_LOG_FILE, encoding="utf-8")
file_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.addHandler(file_handler)

_tail_thread = None
_tail_stop = threading.Event()

def _tail_worker(path: str):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as _:
            pass
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(0, os.SEEK_END)
        print(f"\n🔍 正在实时监控 {os.path.basename(path)} 日志输出...\n")
        while not _tail_stop.is_set():
            line = f.readline()
            if not line:
                time.sleep(0.5); continue
            print(line.rstrip())

def start_tail():
    global _tail_thread
    _tail_thread = threading.Thread(target=_tail_worker, args=(ERROR_LOG_FILE,), daemon=True)
    _tail_thread.start()

def stop_tail():
    _tail_stop.set()

atexit.register(stop_tail)

# ----------------------- 工具 -----------------------
def make_session(headers) -> requests.Session:
    s = requests.Session()
    s.headers.update(headers)
    retry = Retry(total=RETRY_TIMES, status_forcelist=list(RETRY_STATUS),
                  allowed_methods=frozenset(["GET", "POST"]),
                  backoff_factor=RETRY_BACKOFF, raise_on_status=False)
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter); s.mount("https://", adapter)

    # 关键：访问主页建立会话，获取 JSESSIONID Cookie
    try:
        s.get("https://www.cninfo.com.cn/", timeout=10, proxies=PROXIES)
        logging.debug("会话已建立（获取 JSESSIONID）")
    except Exception as e:
        logging.warning(f"建立会话失败: {e}")

    return s

def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

def normalize_code(code) -> str:
    s = str(code).strip()
    try:
        s = str(int(float(s)))
    except Exception:
        pass
    return s.zfill(6)

def detect_exchange(code: str) -> Tuple[str, str, str]:
    """
    返回: (exchange_dir, column_api, stock_suffix)
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
        logging.debug(f"未识别的股票代码: {s}，默认使用深圳交易所")
        return "SZ", "szse", "SZ"

def normalize_text(s: str) -> str:
    if not s: return ""
    import unicodedata, re as _re
    s = unicodedata.normalize("NFKC", s)
    return _re.sub(r"\s+", "", s).lower()

def build_se_windows(year: int, quarter: str) -> List[str]:
    if quarter in ("Q1", "Q2", "Q3"):
        return [f"{year}-01-01~{year}-12-31"]
    # Q4 跨年
    return [f"{year}-10-01~{year}-12-31", f"{year+1}-01-01~{year+1}-06-30"]

def q_pattern(year: int, q: str) -> re.Pattern:
    y = str(year)
    pat = {
        "Q1": rf"{y}年(?:(?:第?一)|一|1)(?:季度报告|季报)",
        "Q2": rf"{y}年(?:半年度|半年)报告",
        "Q3": rf"{y}年(?:(?:第?三)|三|3)(?:季度报告|季报)",
        "Q4": rf"{y}年?(?:年度报告|年报)",  # Fixed: 年? makes it match both "2023年度报告" and "2023年年度报告"
    }[q]
    return re.compile(pat)

def title_ok(title: str, year: int, quarter: str) -> bool:
    t = normalize_text(title)
    if any(k in t for k in map(normalize_text, EXCLUDE_IN_TITLE)):
        return False
    return q_pattern(year, quarter).search(t) is not None

def parse_time_to_ms(t) -> int:
    if isinstance(t, (int, float)):
        return int(t)
    if isinstance(t, str):
        try:
            return int(datetime.strptime(t, "%Y-%m-%d %H:%M").timestamp() * 1000)
        except Exception:
            return 0
    return 0

def ms_to_ddmmyyyy(ms: int) -> str:
    try:
        return datetime.fromtimestamp(ms/1000).strftime("%d-%m-%Y")
    except Exception:
        return "NA"

def pdf_url_from_adj(adj: str) -> str:
    return CNINFO_STATIC + (adj or "").lstrip("/")

def load_json(path, default):
    if not os.path.exists(path): return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, obj):
    """保存JSON文件，带重试机制（解决Windows文件锁定问题）"""
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
            logging.warning(f"保存JSON文件失败（{path}）: {e}")
            # 清理临时文件
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except:
                    pass
            raise

def append_name_change(csv_path: str, code: str, name_input: str, name_api: str):
    exists = os.path.exists(csv_path)
    with open(csv_path, "a" if exists else "w", encoding=CSV_ENCODING, newline="", errors="replace") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["code", "name_input", "name_from_api"])
        w.writerow([code, name_input, name_api])

def load_code_change_cache() -> Dict[str, List[str]]:
    """
    加载股票代码变更缓存
    格式: {orgId: [old_code, new_code, ...]}
    """
    return load_json(CODE_CHANGE_CACHE_FILE, {})

def save_code_change_cache(cache: Dict[str, List[str]]):
    """保存股票代码变更缓存"""
    save_json(CODE_CHANGE_CACHE_FILE, cache)

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
            logging.warning(
                f"[代码变更检测] orgId={orgId}: 请求代码 {requested_code_normalized} -> 实际代码 {most_common_code} "
                f"(公司名称: {', '.join(list(most_common_names)[:2])})"
            )
            return most_common_code
        else:
            # 公司名称完全不同，可能是合并重组，不判定为代码变更
            logging.info(
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

def read_tasks_from_csv(path: str, default_year: Optional[int] = None, default_quarter: Optional[str] = None):
    """
    读取 CSV 任务文件，自动检测编码
    尝试顺序: UTF-8-sig -> UTF-8 -> GBK (Windows) -> GB2312
    
    Args:
        path: CSV 文件路径
        default_year: 默认年份（如果CSV中没有year列）
        default_quarter: 默认季度（如果CSV中没有quarter列，格式：Q1/Q2/Q3/Q4）
    """
    tasks = []
    encodings = ["utf-8-sig", "utf-8"]
    if platform.system().lower().startswith("win"):
        encodings.extend(["gbk", "gb2312", "gb18030"])

    last_error = None
    for enc in encodings:
        try:
            logging.debug(f"尝试使用编码 {enc} 读取 CSV...")
            with open(path, "r", encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                # 检查CSV文件包含哪些列
                fieldnames = reader.fieldnames or []
                has_year = "year" in fieldnames
                has_quarter = "quarter" in fieldnames
                
                if not has_year and default_year is None:
                    logging.error("❌ CSV 文件中没有 'year' 列，且未提供 --year 参数")
                    raise ValueError("CSV 文件中缺少 'year' 列，请添加该列或使用 --year 参数")
                if not has_quarter and default_quarter is None:
                    logging.error("❌ CSV 文件中没有 'quarter' 列，且未提供 --quarter 参数")
                    raise ValueError("CSV 文件中缺少 'quarter' 列，请添加该列或使用 --quarter 参数")
                
                for row in reader:
                    try:
                        raw = (row.get("code") or "").strip()
                        code = normalize_code(raw) if raw else ""
                        name = (row.get("name") or "").strip()
                        
                        # 从CSV读取或使用默认值
                        if has_year:
                            year = int(str(row.get("year")).strip())
                        else:
                            year = default_year
                            
                        if has_quarter:
                            quarter = (row.get("quarter") or "").strip().upper()
                        else:
                            quarter = default_quarter.upper() if default_quarter else None
                        
                        if not code or not name:
                            continue
                        if quarter not in ("Q1","Q2","Q3","Q4"):
                            logging.warning(f"跳过无效季度 '{quarter}'（行：code={code}, name={name}）")
                            continue
                        tasks.append((code, name, year, quarter))
                    except Exception as e:
                        logging.debug(f"跳过无效行: {e}")
                        continue
            logging.info(f"✅ 成功使用编码 {enc} 读取 {len(tasks)} 条任务")
            return tasks
        except (UnicodeDecodeError, UnicodeError) as e:
            last_error = e
            logging.debug(f"编码 {enc} 失败: {e}")
            tasks = []  # 重置任务列表
            continue
        except Exception as e:
            logging.error(f"读取 CSV 失败 ({enc}): {e}")
            raise

    # 所有编码都失败
    logging.error(f"❌ 无法读取 CSV 文件，尝试了编码: {encodings}")
    logging.error(f"最后错误: {last_error}")
    logging.error(f"请确保 CSV 文件保存为 UTF-8 或 GBK 编码")
    raise ValueError(f"无法解码 CSV 文件: {path}")

# ----------------------- orgId 构造（按规则生成） -----------------------
def build_orgid(code: str) -> str:
    """
    根据股票代码构造 orgId（仅适用于部分公司）
    - 深圳: gssz + 0 + code (如 gssz0000001, 7位)
    - 上海: gssh + 0 + code (如 gssh0600519, 7位)
    - 北京: gsbj + 0 + code (如 gsbj0430001, 7位)
    注意：此方法仅对部分公司有效，其他公司需使用 searchkey 查询
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
                            logging.info(f"[orgId] 通过搜索API获取成功：{orgid} ({company_name})")
                            return orgid, company_name
    except Exception as e:
        logging.debug(f"搜索API查询失败 (code={code6}): {e}")

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
        logging.debug(f"使用 searchkey='{name}' 查询 orgId...")
        r = api_session.post(CNINFO_API, data=payload, timeout=20, proxies=PROXIES)
        if r.status_code == 200:
            data = r.json()
            anns = data.get("announcements") or []

            logging.debug(f"searchkey 返回 {len(anns)} 条公告")

            for ann in anns:
                ann_code = str(ann.get("secCode", "")).zfill(6)
                if ann_code == code6:
                    oid = ann.get("orgId")
                    sec_name = ann.get("secName", "")
                    if oid:
                        logging.info(f"[orgId] 通过 searchkey 获取成功：{oid} ({sec_name})")
                        return oid, sec_name

            logging.warning(f"searchkey 返回公告中未找到匹配的股票代码 {code6}")
            if anns and len(anns) > 0:
                logging.debug(f"前5条公告的股票代码: {[ann.get('secCode') for ann in anns[:5]]}")
        else:
            logging.warning(f"searchkey 请求失败: HTTP {r.status_code}")
    except Exception as e:
        logging.warning(f"searchkey 查询异常：{e}")

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

        logging.info(f"[HTML兜底] 尝试搜索关键词'{keyword}'：{code6}")

        try:
            r = html_session.get(url, timeout=20, proxies=PROXIES)
            if r.status_code != 200:
                logging.debug(f"HTML 检索失败：HTTP {r.status_code}")
                continue

            soup = BeautifulSoup(r.text, "html.parser")

            # 方法1：解析列表页的详情链接
            main = soup.find("div", class_="list-main")
            if main:
                items = main.find_all("div", class_="list-item")
                logging.debug(f"找到 {len(items)} 条公告")

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
                            logging.info(f"[HTML兜底] 成功解析 orgId：{oid} ({company_name})")
                            return oid, company_name

            # 方法2：从页面脚本中提取 orgId（备用）
            scripts = soup.find_all("script")
            for script in scripts:
                script_text = script.string or ""
                # 查找类似 "orgId":"9900012345" 的模式
                import re
                matches = re.findall(r'"orgId"\s*:\s*"([^"]+)"', script_text)
                if matches:
                    oid = matches[0]
                    logging.info(f"[HTML兜底] 从脚本中解析 orgId：{oid}")
                    return oid, name or ""

        except Exception as e:
            logging.debug(f"HTML 解析异常 (keyword={keyword}): {e}")
            continue

    logging.warning(f"[HTML兜底] 所有搜索关键词均失败：{code6}")
    return None

def get_orgid(code: str, name: Optional[str]) -> Optional[str]:
    """
    对外统一入口：HTML scraping fallback
    注意：此函数已不再使用，保留仅供向后兼容
    """
    code6 = normalize_code(code)
    return get_orgid_via_html(code6, name)

# ----------------------- 公告抓取与下载 -----------------------
def fetch_anns_by_category(api_session: requests.Session, code: str, orgId: Optional[str],
                           column_api: str, year: int, quarter: str, page_size=100) -> List[dict]:
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

    all_list: List[dict] = []
    for seDate in build_se_windows(year, quarter):
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
            logging.debug(f"[API请求] stock={stock_field}, category={category}, seDate={seDate}, page={page}")
            data = None
            try:
                data = api_session.post(CNINFO_API, data=payload, timeout=20, proxies=PROXIES)
                if data.status_code >= 400:
                    logging.warning(f"hisAnnouncement HTTP {data.status_code} ({code} 页 {page})")
                    break
                response_text = data.text.strip()
                if not response_text.startswith("{"):
                    logging.warning(f"[API] 返回非JSON内容: {response_text[:200]}")
                    break
                data = data.json()
            except RequestException as e:
                logging.warning(f"hisAnnouncement 请求异常（{code} 页 {page}）：{e}")
                break
            except Exception as e:
                logging.warning(f"[API] JSON解析失败: {e}, 响应: {data.text[:200] if data else 'None'}")
                break

            anns = (data or {}).get("announcements") or []
            logging.debug(f"[API响应] 返回 {len(anns)} 条公告 (seDate={seDate})")
            if not anns: break
            all_list.extend(anns)
            if len(anns) < page_size: break
            page += 1
    return all_list

def fetch_anns(api_session: requests.Session, code: str, orgId: Optional[str],
               column_api: str, year: int, quarter: str, page_size=100) -> List[dict]:
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
            logging.debug(f"[API请求 CATEGORY_ALL] stock={stock_field}, seDate={seDate}, page={page}")
            data = None
            try:
                # 关键修改：使用 data= 而不是 json=（form-data 格式）
                data = api_session.post(CNINFO_API, data=payload, timeout=20, proxies=PROXIES)
                if data.status_code >= 400:
                    logging.warning(f"hisAnnouncement HTTP {data.status_code} ({code} 页 {page})")
                    break
                response_text = data.text.strip()
                if not response_text.startswith("{"):
                    logging.warning(f"[API] 返回非JSON内容: {response_text[:200]}")
                    break
                data = data.json()
            except RequestException as e:
                logging.warning(f"hisAnnouncement 请求异常（{code} 页 {page}）：{e}")
                break
            except Exception as e:
                logging.warning(f"[API] JSON解析失败: {e}, 响应: {data.text[:200] if data else 'None'}")
                break

            anns = (data or {}).get("announcements") or []
            logging.debug(f"[API响应] 返回 {len(anns)} 条公告 (seDate={seDate})")
            if not anns: break
            all_list.extend(anns)
            if len(anns) < page_size: break
            page += 1
    return all_list

def pick_latest(anns: List[dict], code: str, year: int, quarter: str, 
                related_codes: Optional[List[str]] = None) -> Optional[dict]:
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
            
        title = a.get("announcementTitle","")
        if not title_ok(title, year, quarter):
            continue
        adj = a.get("adjunctUrl","")
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
        logging.info(f"[代码变更] 使用历史代码 {actual_code} 找到报告（请求代码: {normalize_code(code)}）")
    
    return best_ann

def download_pdf_resilient(session: requests.Session, url: str, path: str,
                           referer: Optional[str] = None,
                           refresh_fn=None, max_retries=3):
    cur_url, cur_ref = url, referer
    last_err = None
    for attempt in range(1, max_retries+1):
        try:
            headers = {"Referer": cur_ref} if cur_ref else {}
            r = session.get(cur_url, timeout=20, stream=True, proxies=PROXIES, headers=headers)
            if r.status_code == 404 and refresh_fn:
                new_url, new_ref = refresh_fn()
                if new_url and new_url != cur_url:
                    logging.warning(f"404 刷新链接：\nold={cur_url}\nnew={new_url}")
                    cur_url, cur_ref = new_url, (new_ref or cur_ref)
                    continue
            if r.status_code in RETRY_STATUS:
                time.sleep(RETRY_BACKOFF); continue
            if r.status_code >= 400:
                last_err = f"HTTP {r.status_code}"
                time.sleep(RETRY_BACKOFF); continue

            head = r.raw.read(5); r.raw.decode_content = True
            if not head.startswith(b"%PDF-"):
                return False, "非PDF内容"
            ensure_dir(os.path.dirname(path))
            with open(path, "wb") as f:
                f.write(head or b"")
                for chunk in r.iter_content(8192):
                    if chunk: f.write(chunk)
            return True, "ok"
        except RequestException as e:
            last_err = str(e)
            time.sleep(RETRY_BACKOFF)
    return False, last_err or "HTTP 4xx/5xx"

# ----------------------- 多进程支持 -----------------------
class SharedState:
    """线程安全的共享状态管理器"""
    def __init__(self, checkpoint_file: str, orgid_cache_file: str, code_change_cache_file: str, shared_lock=None):
        self.checkpoint_file = checkpoint_file
        self.orgid_cache_file = orgid_cache_file
        self.code_change_cache_file = code_change_cache_file
        # 使用传入的共享锁（多进程）或创建新锁（单进程）
        self.lock = shared_lock if shared_lock is not None else multiprocessing.Lock()

    def load_checkpoint(self) -> Dict[str, bool]:
        with self.lock:
            return load_json(self.checkpoint_file, {})

    def save_checkpoint(self, key: str):
        with self.lock:
            data = load_json(self.checkpoint_file, {})
            data[key] = True
            save_json(self.checkpoint_file, data)

    def load_orgid_cache(self) -> Dict[str, str]:
        with self.lock:
            return load_json(self.orgid_cache_file, {})

    def save_orgid(self, code: str, orgid: str):
        with self.lock:
            data = load_json(self.orgid_cache_file, {})
            data[code] = orgid
            save_json(self.orgid_cache_file, data)

    def get_orgid(self, code: str) -> Optional[str]:
        with self.lock:
            data = load_json(self.orgid_cache_file, {})
            return data.get(code)
    
    def load_code_change_cache(self) -> Dict[str, List[str]]:
        with self.lock:
            return load_json(self.code_change_cache_file, {})
    
    def save_code_change(self, orgid: str, codes: List[str]):
        """保存代码变更记录"""
        with self.lock:
            data = load_json(self.code_change_cache_file, {})
            # 合并新旧代码列表
            existing = data.get(orgid, [])
            for code in codes:
                code_norm = normalize_code(code)
                if code_norm not in existing:
                    existing.append(code_norm)
            data[orgid] = existing
            save_json(self.code_change_cache_file, data)

# ----------------------- MinIO上传辅助函数 -----------------------
def upload_to_minio_in_process(local_path: str, code: str, year: int, quarter: str, out_root: str,
                               publish_date: Optional[str] = None):
    """
    在工作进程中上传文件到MinIO
    
    Args:
        local_path: 本地文件路径
        code: 股票代码
        year: 年份
        quarter: 季度（如 "Q1"）
        out_root: 输出根目录
        publish_date: 发布日期（ISO格式，可选）
    """
    try:
        # 检查环境变量
        use_minio = os.getenv("USE_MINIO", "false").lower() == "true"
        if not use_minio:
            return  # MinIO未启用，跳过
        
        minio_upload_on_download = os.getenv("MINIO_UPLOAD_ON_DOWNLOAD", "true").lower() == "true"
        if not minio_upload_on_download:
            return  # 配置为不在下载时上传
        
        # 读取MinIO配置
        minio_endpoint = os.getenv("MINIO_ENDPOINT")
        minio_access_key = os.getenv("MINIO_ACCESS_KEY")
        minio_secret_key = os.getenv("MINIO_SECRET_KEY")
        minio_bucket = os.getenv("MINIO_BUCKET", "company-datalake")
        
        if not all([minio_endpoint, minio_access_key, minio_secret_key]):
            logging.warning(f"[{code}] MinIO配置不完整，跳过上传")
            return
        
        # 创建MinIO客户端（每个进程独立创建）
        try:
            from minio import Minio
            from minio.error import S3Error
        except ImportError:
            logging.warning(f"[{code}] minio库未安装，跳过上传")
            return
        
        endpoint = minio_endpoint.replace("http://", "").replace("https://", "")
        secure = minio_endpoint.startswith("https://")
        
        client = Minio(
            endpoint,
            access_key=minio_access_key,
            secret_key=minio_secret_key,
            secure=secure
        )
        
        # 确保桶存在
        try:
            if not client.bucket_exists(minio_bucket):
                client.make_bucket(minio_bucket)
        except S3Error as e:
            logging.warning(f"[{code}] 检查/创建桶失败: {e}")
            return
        
        # 生成对象名称（符合plan.md规范）
        # 格式: bronze/zh_stock/quarterly_reports/{year}/{quarter}/{stock_code}/{filename}
        filename = os.path.basename(local_path)
        
        # 确定文档类型
        quarter_num = int(quarter[1]) if quarter.startswith("Q") else 4
        if quarter_num == 4:
            doc_type = "annual_reports"
        elif quarter_num == 2:
            doc_type = "interim_reports"
        else:
            doc_type = "quarterly_reports"
        
        # 构建对象名称（去掉key=value格式，直接使用值）
        object_name = f"bronze/zh_stock/{doc_type}/{year}/{quarter}/{code}/{filename}"
        
        # 检查文件是否已存在
        try:
            client.stat_object(minio_bucket, object_name)
            logging.info(f"[{code}] 文件已在MinIO中存在，跳过上传: {object_name}")
            return
        except S3Error:
            pass  # 文件不存在，继续上传
        
        # 上传文件（带元数据）
        try:
            # 准备元数据
            metadata = {
                "stock_code": code,
                "year": str(year),
                "quarter": quarter,
            }
            if publish_date:
                metadata["publish_date"] = publish_date
            
            client.fput_object(
                minio_bucket,
                object_name,
                local_path,
                content_type='application/pdf',
                metadata=metadata
            )
            logging.info(f"[{code}] ✅ 已上传到MinIO: {object_name} (发布日期: {publish_date or 'N/A'})")
        except S3Error as e:
            # 上传失败，记录到失败文件
            error_msg = str(e)
            logging.error(f"[{code}] ❌ MinIO上传失败: {error_msg}")
            _record_minio_upload_failure(code, year, quarter, local_path, error_msg, out_root)
        except Exception as e:
            error_msg = str(e)
            logging.error(f"[{code}] ❌ MinIO上传异常: {error_msg}")
            _record_minio_upload_failure(code, year, quarter, local_path, error_msg, out_root)
    
    except Exception as e:
        # 任何异常都不应该阻塞下载流程
        logging.warning(f"[{code}] MinIO上传处理异常（不影响下载）: {e}")


def _record_minio_upload_failure(code: str, year: int, quarter: str, file_path: str, 
                                 error_msg: str, out_root: str):
    """
    记录MinIO上传失败
    
    Args:
        code: 股票代码
        year: 年份
        quarter: 季度
        file_path: 文件路径
        error_msg: 错误信息
        out_root: 输出根目录
    """
    try:
        fail_csv = os.path.join(out_root, "minio_upload_failed.csv")
        file_exists = os.path.exists(fail_csv)
        
        with open(fail_csv, 'a', encoding=CSV_ENCODING, newline='', errors='replace') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['code', 'year', 'quarter', 'file_path', 'error_message', 'timestamp'])
            writer.writerow([code, year, quarter, file_path, error_msg, datetime.now().isoformat()])
    except Exception as e:
        logging.warning(f"记录MinIO上传失败信息时出错: {e}")


def process_single_task(task_data: Tuple) -> Tuple[bool, Optional[Tuple]]:
    """
    处理单个下载任务（在独立进程中运行）

    Args:
        task_data: (code, name, year, quarter, out_root, orgid_cache_file, code_change_cache_file, shared_lock, existing_pdf_cache)

    Returns:
        (success, failure_record or None)
    """
    code, name, year, quarter, out_root, orgid_cache_file, code_change_cache_file, shared_lock, existing_pdf_cache = task_data

    # 每个进程创建自己的 session
    api_session = make_session(HEADERS_API)
    html_session = make_session(HEADERS_HTML)

    # checkpoint 存储在输出目录
    checkpoint_file = os.path.join(out_root, "checkpoint.json")

    # 创建共享状态管理器（SQLite 或 JSON+锁）
    if USE_SQLITE:
        shared = SharedStateSQLite(checkpoint_file, orgid_cache_file, code_change_cache_file)
    else:
        shared = SharedState(checkpoint_file, orgid_cache_file, code_change_cache_file, shared_lock)

    # 检查是否已完成
    key = f"{code}-{year}-{quarter}"
    checkpoint = shared.load_checkpoint()
    if checkpoint.get(key):
        return True, None

    # 检查PDF是否已存在于旧目录（使用缓存，O(1)查找）
    if existing_pdf_cache and check_pdf_exists_in_cache(existing_pdf_cache, code, year, quarter):
        logging.info(f"[{code}] PDF已存在于旧目录，跳过下载")
        shared.save_checkpoint(key)  # 标记为已完成，避免重复检查
        return True, None

    exch_dir, column_api, _ = detect_exchange(code)

    # 用于保存从API获取的真实公司名（用于失败记录）
    real_company_name = name

    try:
        # orgId 获取策略
        orgId = shared.get_orgid(code)
        if not orgId:
            orgId = build_orgid(code)
            shared.save_orgid(code, orgId)
            logging.info(f"[{code}] orgId 构造方法：{orgId}")

        # 加载代码变更缓存
        code_change_cache = shared.load_code_change_cache()
        related_codes = get_all_related_codes(code, orgId, code_change_cache)

        # 抓公告 - 使用类别过滤（始终先尝试带orgId查询）
        anns = fetch_anns_by_category(api_session, code, orgId, column_api, year, quarter)

        # 兜底1：如果类别过滤无结果，尝试使用 CATEGORY_ALL（可能是类别分类问题）
        if not anns:
            logging.warning(f"[{code}] 类别过滤查询无结果，尝试使用 CATEGORY_ALL")
            anns = fetch_anns(api_session, code, orgId, column_api, year, quarter)  # fetch_anns uses CATEGORY_ALL
            if anns:
                logging.info(f"[{code}] CATEGORY_ALL查询成功，返回 {len(anns)} 条公告")

        # 兜底2：如果带orgId查询无结果，尝试不带orgId查询（处理合并/重组场景，orgId变更）
        if not anns and orgId:
            logging.warning(f"[{code}] 带orgId查询无结果，尝试不带orgId查询（可能是公司名变更）")
            anns = fetch_anns(api_session, code, None, column_api, year, quarter)  # Use CATEGORY_ALL without orgId
            if anns:
                logging.info(f"[{code}] 不带orgId查询成功，返回 {len(anns)} 条公告")
        
        # 检测代码变更
        if anns:
            actual_code = detect_code_change(anns, code, orgId)
            if actual_code and actual_code not in related_codes:
                logging.info(f"[{code}] 检测到代码变更：{code} -> {actual_code}")
                related_codes.append(actual_code)
                # 更新缓存
                shared.save_code_change(orgId, related_codes)
        
        if not anns:
            # 尝试通过搜索API获取真实 orgId（新方法，不需要公司名）
            logging.warning(f"[{code}] 构造的 orgId 可能无效，尝试搜索API方法...")
            result = get_orgid_via_search_api(api_session, code)
            if result:
                real_orgid, company_name = result
                real_company_name = company_name  # 保存真实公司名
                if real_orgid != orgId:
                    logging.info(f"[{code}] orgId 更新为真实值：{real_orgid}")
                    orgId = real_orgid
                    shared.save_orgid(code, orgId)
                    anns = fetch_anns_by_category(api_session, code, orgId, column_api, year, quarter)

            # 如果搜索API也失败，使用searchkey方法（需要公司名）
            if not anns:
                logging.warning(f"[{code}] 搜索API失败，尝试 searchkey 方法...")
                searchkey_result = get_orgid_by_searchkey(api_session, code, name, column_api)
                if searchkey_result:
                    real_orgid, _ = searchkey_result
                    if real_orgid and real_orgid != orgId:
                        logging.info(f"[{code}] orgId 更新为真实值：{real_orgid}")
                        orgId = real_orgid
                        shared.save_orgid(code, orgId)
                        anns = fetch_anns_by_category(api_session, code, orgId, column_api, year, quarter)

            # 方法4：最后的兜底 - HTML 页面解析（不依赖公司名，最可靠）
            if not anns:
                logging.warning(f"[{code}] searchkey 方法也失败，使用 HTML 兜底方法...")
                html_result = get_orgid_via_html(code, name, html_session)
                if html_result:
                    real_orgid, company_name = html_result
                    if real_orgid != orgId:
                        logging.info(f"[{code}] [HTML兜底] orgId 更新为真实值：{real_orgid} ({company_name})")
                        orgId = real_orgid
                        shared.save_orgid(code, orgId)
                        # 用新 orgId 重新抓取
                        anns = fetch_anns_by_category(api_session, code, orgId, column_api, year, quarter)

        if not anns:
            logging.error(f"[{code}] 未获得公告列表：{real_company_name}（{code}）{year}-{quarter}")
            return False, (code, real_company_name, year, quarter, "no announcements")

        # 取最新版（使用相关代码列表）
        best = pick_latest(anns, code, year, quarter, related_codes=related_codes)
        if not best:
            logging.error(f"[{code}] 公告过滤后为空：{real_company_name}（{code}）{year}-{quarter}")
            return False, (code, real_company_name, year, quarter, "not found after filter")

        # 下载
        adj = best.get("adjunctUrl", "")
        pdf_url = pdf_url_from_adj(adj)
        ts = parse_time_to_ms(best.get("announcementTime"))
        pub_date = ms_to_ddmmyyyy(ts)  # 发布日期（用于元数据）
        pub_date_iso = datetime.fromtimestamp(ts/1000).isoformat() if ts > 0 else None  # ISO格式日期

        out_dir = os.path.join(out_root, exch_dir, code, str(year))
        ensure_dir(out_dir)
        # 文件名不包含发布日期，只包含：股票代码_年份_季度.pdf
        fname = f"{code}_{year}_{quarter}.pdf"
        out_path = os.path.join(out_dir, fname)

        # 定义刷新函数（先尝试带orgId，失败则不带orgId）
        def refresh_fn():
            anns2 = fetch_anns_by_category(api_session, code, orgId, column_api, year, quarter)
            if not anns2 and orgId:
                anns2 = fetch_anns_by_category(api_session, code, None, column_api, year, quarter)
            b2 = pick_latest(anns2, code, year, quarter, related_codes=related_codes)
            if not b2: return None, None
            return pdf_url_from_adj(b2.get("adjunctUrl", "")), None

        ok, msg = download_pdf_resilient(html_session, pdf_url, out_path, referer=None,
                                        refresh_fn=refresh_fn, max_retries=3)
        if ok:
            logging.info(f"[{code}] 保存成功：{out_path}")
            shared.save_checkpoint(key)
            
            # 立即上传到MinIO（如果启用）
            # quarter 应该是字符串格式（"Q1", "Q2"等），如果不是则转换
            quarter_str = quarter if isinstance(quarter, str) else f"Q{quarter}"
            upload_to_minio_in_process(out_path, code, year, quarter_str, out_root, pub_date_iso)
            
            return True, None
        else:
            logging.error(f"[{code}] 下载失败：{real_company_name}（{code}）{year}-{quarter} - {msg}")
            return False, (code, real_company_name, year, quarter, f"download failed: {msg}")

    except Exception as e:
        logging.error(f"[{code}] 处理异常：{real_company_name}（{code}）{year}-{quarter} - {e}")
        return False, (code, real_company_name, year, quarter, f"exception: {str(e)}")
    finally:
        # 添加随机延迟，避免过度请求
        time.sleep(random.uniform(0.5, 1.5))

def run_multiprocessing(input_csv: str, out_root: str, fail_csv: str,
                       workers: int = 4, debug=False, old_pdf_dir: Optional[str] = None,
                       default_year: Optional[int] = None, default_quarter: Optional[str] = None):
    """
    多进程并行下载模式

    Args:
        input_csv: 输入CSV文件路径
        out_root: 输出根目录
        fail_csv: 失败记录CSV路径
        workers: worker进程数 (建议 4-8)
        debug: 调试模式
        old_pdf_dir: 旧PDF目录路径（如果存在，会先检查该目录避免重复下载）
        default_year: 默认年份（如果CSV中没有year列）
        default_quarter: 默认季度（如果CSV中没有quarter列）
    """
    if debug:
        logger.setLevel(logging.DEBUG)
        logging.info("调试模式已启用")

    tasks = read_tasks_from_csv(input_csv, default_year, default_quarter)
    total = len(tasks)
    print(f"共读取任务：{total} 条")
    print(f"使用 {workers} 个并行进程处理")

    if USE_SQLITE:
        print("✅ 使用 SQLite 状态管理（高性能、无文件锁冲突）")
    else:
        print("⚠️  使用 JSON 状态管理（建议升级到 SQLite）")

    # 构建已存在PDF的缓存（一次性扫描，所有进程共享）
    existing_pdf_cache = build_existing_pdf_cache(old_pdf_dir)

    # 创建跨进程共享的锁
    manager = multiprocessing.Manager()
    shared_lock = manager.Lock()

    # 准备任务数据（包含共享锁和PDF缓存）
    task_data_list = [
        (code, name, year, quarter, out_root, ORGID_CACHE_FILE, CODE_CHANGE_CACHE_FILE, shared_lock, existing_pdf_cache)
        for code, name, year, quarter in tasks
    ]

    failures = []
    completed = 0

    # 使用进程池并行处理
    with ProcessPoolExecutor(max_workers=workers) as executor:
        # 提交所有任务
        future_to_task = {
            executor.submit(process_single_task, task_data): task_data
            for task_data in task_data_list
        }

        # 使用tqdm显示进度
        with tqdm(total=total, desc="抓取进度", unit="任务") as pbar:
            for future in as_completed(future_to_task):
                task_data = future_to_task[future]
                code, name, year, quarter = task_data[:4]

                try:
                    success, failure_record = future.result()
                    if success:
                        completed += 1
                    elif failure_record:
                        failures.append(failure_record)
                except Exception as e:
                    logging.error(f"任务处理异常：{name}（{code}）{year}-{quarter} - {e}")
                    failures.append((code, name, year, quarter, f"exception: {str(e)}"))

                pbar.update(1)

    # 写入失败记录
    if failures:
        with open(fail_csv, "w", encoding=CSV_ENCODING, newline="", errors="replace") as f:
            w = csv.writer(f)
            w.writerow(["code", "name", "year", "quarter", "reason"])
            w.writerows(failures)
        print(f"❌ 写入失败记录：{fail_csv}（编码：{CSV_ENCODING}）")
        print(f"✅ 成功：{completed}/{total} ({completed*100//total}%)")
    else:
        print("✅ 全部成功，无失败记录。")

# ----------------------- 主流程 -----------------------
def run(input_csv: str, out_root: str, fail_csv: str, watch_log=False, debug=False, old_pdf_dir: Optional[str] = None,
        default_year: Optional[int] = None, default_quarter: Optional[str] = None):
    if debug:
        logger.setLevel(logging.DEBUG)
        logging.info("调试模式已启用")

    if watch_log:
        start_tail()

    api_session = make_session(HEADERS_API)
    html_session = make_session(HEADERS_HTML)

    # checkpoint 存储在输出目录
    checkpoint_file = os.path.join(out_root, "checkpoint.json")

    # 使用 SQLite 或 JSON
    if USE_SQLITE:
        state = SharedStateSQLite(checkpoint_file, ORGID_CACHE_FILE, CODE_CHANGE_CACHE_FILE)
        checkpoint = state.load_checkpoint()
        orgid_cache = state.load_orgid_cache()
        code_change_cache = state.load_code_change_cache()
        print("✅ 使用 SQLite 状态管理")
    else:
        state = None
        checkpoint = load_json(checkpoint_file, {})
        orgid_cache = load_json(ORGID_CACHE_FILE, {})
        code_change_cache = load_json(CODE_CHANGE_CACHE_FILE, {})
        print("⚠️  使用 JSON 状态管理")

    tasks = read_tasks_from_csv(input_csv, default_year, default_quarter)
    total = len(tasks)
    print(f"共读取任务：{total} 条")

    # 构建已存在PDF的缓存（一次性扫描）
    existing_pdf_cache = build_existing_pdf_cache(old_pdf_dir)

    failures = []
    last_code = None

    for code, name, year, quarter in tqdm(tasks, desc="抓取进度", unit="任务"):
        key = f"{code}-{year}-{quarter}"
        if checkpoint.get(key):
            continue

        # 检查PDF是否已存在于旧目录（使用缓存，O(1)查找）
        if existing_pdf_cache and check_pdf_exists_in_cache(existing_pdf_cache, code, year, quarter):
            logging.info(f"[{code}] PDF已存在于旧目录，跳过下载")
            if USE_SQLITE and state:
                state.save_checkpoint(key)
            else:
                checkpoint[key] = True
                save_json(checkpoint_file, checkpoint)
            continue

        if last_code == code:
            time.sleep(INTER_SAME_STOCK_GAP)
        last_code = code

        exch_dir, column_api, stock_suffix = detect_exchange(code)
        logging.info(f"正在抓取：{name}（{code}） {year}-{quarter} [{column_api}]")

        # 用于保存从API获取的真实公司名（用于失败记录）
        real_company_name = name

        # orgId 获取策略：先从缓存，再尝试构造，最后用 searchkey 查询
        orgId = orgid_cache.get(code)
        if not orgId:
            # 方法1：尝试简单构造（快速，但仅适用部分公司）
            orgId = build_orgid(code)
            if USE_SQLITE and state:
                state.save_orgid(code, orgId)
            else:
                orgid_cache[code] = orgId
                save_json(ORGID_CACHE_FILE, orgid_cache)
            logging.info(f"[orgId] 构造方法：{orgId}")

        # 获取相关代码列表（处理代码变更）
        related_codes = get_all_related_codes(code, orgId, code_change_cache)

        # 抓公告（多窗 + 分页）- 使用类别过滤（始终先尝试带orgId查询）
        anns = fetch_anns_by_category(api_session, code, orgId, column_api, year, quarter)

        # DEBUG: 打印所有返回的公告标题
        if anns:
            logging.info(f"[DEBUG] 返回 {len(anns)} 条公告:")
            for ann in anns[:10]:  # 只显示前10条
                logging.info(f"  - {ann.get('secName')} {ann.get('announcementTitle')}")

        # 兜底1：如果类别过滤无结果，尝试使用 CATEGORY_ALL（可能是类别分类问题）
        if not anns:
            logging.warning(f"[{code}] 类别过滤查询无结果，尝试使用 CATEGORY_ALL")
            anns = fetch_anns(api_session, code, orgId, column_api, year, quarter)  # fetch_anns uses CATEGORY_ALL
            if anns:
                logging.info(f"[{code}] CATEGORY_ALL查询成功，返回 {len(anns)} 条公告")

        # 兜底2：如果带orgId查询无结果，尝试不带orgId查询（处理合并/重组场景，orgId变更）
        if not anns and orgId:
            logging.warning(f"[{code}] 带orgId查询无结果，尝试不带orgId查询（可能是公司名变更）")
            anns = fetch_anns(api_session, code, None, column_api, year, quarter)  # Use CATEGORY_ALL without orgId
            if anns:
                logging.info(f"[{code}] 不带orgId查询成功，返回 {len(anns)} 条公告")

        # 检测代码变更
        if anns:
            actual_code = detect_code_change(anns, code, orgId)
            if actual_code and actual_code not in related_codes:
                logging.info(f"[代码变更检测] {code} -> {actual_code}")
                related_codes.append(actual_code)
                # 更新缓存
                if orgId:
                    if USE_SQLITE and state:
                        state.save_code_change(orgId, related_codes)
                    else:
                        if orgId not in code_change_cache:
                            code_change_cache[orgId] = []
                        for c in related_codes:
                            if c not in code_change_cache[orgId]:
                                code_change_cache[orgId].append(c)
                        save_json(CODE_CHANGE_CACHE_FILE, code_change_cache)
        
        if not anns:
            # 方法2：如果构造的 orgId 无效，尝试通过搜索API获取真实 orgId（不需要公司名）
            logging.warning(f"构造的 orgId 可能无效，尝试搜索API方法...")
            result = get_orgid_via_search_api(api_session, code)
            if result:
                real_orgid, api_company_name = result
                real_company_name = api_company_name  # 保存真实公司名
                if real_orgid != orgId:
                    logging.info(f"[orgId] 更新为真实值：{real_orgid}")
                    orgId = real_orgid
                    if USE_SQLITE and state:
                        state.save_orgid(code, orgId)
                    else:
                        orgid_cache[code] = orgId
                        save_json(ORGID_CACHE_FILE, orgid_cache)
                    # 用新 orgId 重新抓取
                    anns = fetch_anns_by_category(api_session, code, orgId, column_api, year, quarter)

            # 如果搜索API也失败，使用searchkey方法（需要公司名）
            if not anns:
                logging.warning(f"搜索API失败，尝试 searchkey 方法...")
                searchkey_result = get_orgid_by_searchkey(api_session, code, name, column_api)
                if searchkey_result:
                    real_orgid, _ = searchkey_result
                    if real_orgid and real_orgid != orgId:
                        logging.info(f"[orgId] 更新为真实值：{real_orgid}")
                        orgId = real_orgid
                        if USE_SQLITE and state:
                            state.save_orgid(code, orgId)
                        else:
                            orgid_cache[code] = orgId
                            save_json(ORGID_CACHE_FILE, orgid_cache)
                        # 用新 orgId 重新抓取
                        anns = fetch_anns_by_category(api_session, code, orgId, column_api, year, quarter)

            # 方法4：最后的兜底 - HTML 页面解析（不依赖公司名，最可靠）
            if not anns:
                logging.warning(f"searchkey 方法也失败，使用 HTML 兜底方法...")
                html_result = get_orgid_via_html(code, name, html_session)
                if html_result:
                    real_orgid, company_name = html_result
                    if real_orgid != orgId:
                        logging.info(f"[HTML兜底] orgId 更新为真实值：{real_orgid} ({company_name})")
                        orgId = real_orgid
                        if USE_SQLITE and state:
                            state.save_orgid(code, orgId)
                        else:
                            orgid_cache[code] = orgId
                            save_json(ORGID_CACHE_FILE, orgid_cache)
                        # 用新 orgId 重新抓取
                        anns = fetch_anns_by_category(api_session, code, orgId, column_api, year, quarter)

        if not anns:
            logging.error(f"未获得公告列表：{real_company_name}（{code}）{year}-{quarter}")
            failures.append((code, real_company_name, year, quarter, "no announcements"))
            time.sleep(random.uniform(*INTER_COMBO_SLEEP_RANGE))
            continue

        # 取最新版（使用相关代码列表处理代码变更）
        best = pick_latest(anns, code, year, quarter, related_codes=related_codes)
        if not best:
            logging.error(f"公告过滤后为空：{real_company_name}（{code}）{year}-{quarter}")
            failures.append((code, real_company_name, year, quarter, "not found after filter"))
            time.sleep(random.uniform(*INTER_COMBO_SLEEP_RANGE))
            continue

        # 下载
        adj = best.get("adjunctUrl","")
        pdf_url = pdf_url_from_adj(adj)
        ts = parse_time_to_ms(best.get("announcementTime"))
        pub_date = ms_to_ddmmyyyy(ts)  # 发布日期（用于日志）
        pub_date_iso = datetime.fromtimestamp(ts/1000).isoformat() if ts > 0 else None  # ISO格式日期（用于元数据）

        out_dir = os.path.join(out_root, exch_dir, code, str(year))
        ensure_dir(out_dir)
        # 文件名不包含发布日期，只包含：股票代码_年份_季度.pdf
        fname = f"{code}_{year}_{quarter}.pdf"
        out_path = os.path.join(out_dir, fname)

        # 定义刷新函数（404 时重新拉列表，先尝试带orgId，失败则不带orgId）
        def refresh_fn():
            anns2 = fetch_anns_by_category(api_session, code, orgId, column_api, year, quarter)
            if not anns2 and orgId:
                anns2 = fetch_anns_by_category(api_session, code, None, column_api, year, quarter)
            b2 = pick_latest(anns2, code, year, quarter, related_codes=related_codes)
            if not b2: return None, None
            return pdf_url_from_adj(b2.get("adjunctUrl","")), None

        logging.debug(f"Downloading: url={pdf_url} -> {out_path}")
        ok, msg = download_pdf_resilient(html_session, pdf_url, out_path, referer=None, refresh_fn=refresh_fn, max_retries=3)
        if ok:
            logging.info(f"保存成功：{out_path}")
            if USE_SQLITE and state:
                state.save_checkpoint(key)
            else:
                checkpoint[key] = True
                save_json(checkpoint_file, checkpoint)
        else:
            logging.error(f"下载失败：{real_company_name}（{code}）{year}-{quarter} - {msg}")
            failures.append((code, real_company_name, year, quarter, f"download failed: {msg}"))

        time.sleep(random.uniform(*INTER_COMBO_SLEEP_RANGE))

    # 失败记录
    if failures:
        with open(fail_csv, "w", encoding=CSV_ENCODING, newline="", errors="replace") as f:
            w = csv.writer(f)
            w.writerow(["code", "name", "year", "quarter", "reason"])
            w.writerows(failures)
        print(f"❌ 写入失败记录：{fail_csv}（编码：{CSV_ENCODING}）")
    else:
        print("✅ 全部成功，无失败记录。")

# ----------------------- CLI -----------------------
if __name__ == "__main__":
    p = argparse.ArgumentParser(description="CNINFO 定期报告抓取（含新 orgId 获取策略 + 多进程支持）")
    p.add_argument("--input", required=True, help="输入 CSV（code,name 或 code,name,year,quarter）")
    p.add_argument("--out", required=True, help="输出根目录")
    p.add_argument("--fail", required=True, help="失败记录 CSV")
    p.add_argument("--year", type=int, default=None, help="默认年份（如果CSV中没有year列）")
    p.add_argument("--quarter", type=str, default=None, choices=["Q1", "Q2", "Q3", "Q4"], help="默认季度（如果CSV中没有quarter列）")
    p.add_argument("--workers", type=int, default=0, help="并行进程数（0=顺序模式，推荐 4-8）")
    p.add_argument("--old-pdf-dir", type=str, default=None, help="旧PDF目录路径（如存在，会先检查避免重复下载）")
    p.add_argument("--watch-log", action="store_true", help="实时滚动显示 error.log（仅顺序模式）")
    p.add_argument("--debug", action="store_true", help="调试模式（输出更多日志）")
    args = p.parse_args()

    # 多进程模式 or 顺序模式
    if args.workers > 0:
        if args.watch_log:
            print("⚠️  多进程模式下不支持 --watch-log，已忽略")
        run_multiprocessing(args.input, args.out, args.fail, workers=args.workers, debug=args.debug, 
                          old_pdf_dir=args.old_pdf_dir, default_year=args.year, default_quarter=args.quarter)
    else:
        run(args.input, args.out, args.fail, watch_log=args.watch_log, debug=args.debug, 
            old_pdf_dir=args.old_pdf_dir, default_year=args.year, default_quarter=args.quarter)
