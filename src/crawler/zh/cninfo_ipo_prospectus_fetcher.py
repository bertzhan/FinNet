# -*- coding: utf-8 -*-
"""
CNINFO IPO招股说明书抓取工具（基于原版定期报告抓取脚本改造）
- 目标：抓取IPO招股说明书（首次公开发行股票招股说明书）
- orgId 获取：
  1) 优先：搜索API直接获取
  2) 兜底：HTML页面解析
- 交易所映射：保存目录 "SZ/SH/BJ"，接口 column "szse/sse/bse"
- 断点续抓 / orgId 缓存 / 滚动错误日志 / Windows 友好 CSV
- 多进程并发：支持多个 worker 进程并行下载
"""

import os
import re
import csv
import sys
import json
import time
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

# ----------------------- 常量与配置 -----------------------
CNINFO_API = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STATIC = "https://static.cninfo.com.cn/"
CNINFO_SEARCH = "https://www.cninfo.com.cn/new/search"

# IPO招股说明书类别（首次公开发行公告）
CATEGORY_IPO = "category_scgkfxgg_szsh;"

HEADERS_API = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Referer": "https://www.cninfo.com.cn/",
    "X-Requested-With": "XMLHttpRequest",
}
HEADERS_HTML = {
    "User-Agent": HEADERS_API["User-Agent"],
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.cninfo.com.cn/",
}

# 如需代理，按需填写；默认 None
PROXIES = None
# PROXIES = {"http": "http://ip:port", "https": "http://ip:port"}

# 招股说明书关键词（用于标题匹配）
IPO_KEYWORDS = ("招股说明书", "招股书")
EXCLUDE_IN_TITLE = ("摘要", "英文", "英文版", "更正", "补充", "修订", "注册稿",
                    "提示性公告", "意向书", "附录", "上市公告书")

# 状态文件路径（保存在脚本所在目录）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKPOINT_FILE = os.path.join(SCRIPT_DIR, "checkpoint_ipo.json")
ORGID_CACHE_FILE = os.path.join(SCRIPT_DIR, "orgid_cache_ipo.json")

RETRY_STATUS = (403, 502, 503, 504)
RETRY_TIMES = 3
RETRY_BACKOFF = 1.0
INTER_COMBO_SLEEP_RANGE = (2.0, 3.0)  # 组合间睡眠
INTER_SAME_STOCK_GAP = 1.0            # 同一股票间隔

CSV_ENCODING = "gbk" if platform.system().lower().startswith("win") else "utf-8-sig"

# ----------------------- 日志 -----------------------
ERROR_LOG_FILE = os.path.join(SCRIPT_DIR, "error_ipo.log")

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
    if s.startswith(("6", "68")):
        return "SH", "sse", "SH"  # 上海用 sse
    if s.startswith(("8", "43", "83")):
        return "BJ", "szse", "BJ"  # 北京也用 szse
    return "SZ", "szse", "SZ"

def normalize_text(s: str) -> str:
    if not s: return ""
    import unicodedata, re as _re
    s = unicodedata.normalize("NFKC", s)
    return _re.sub(r"\s+", "", s).lower()

def build_se_window_for_ipo(lookback_years: int = 20) -> str:
    """
    为IPO招股说明书构建时间窗口
    由于IPO时间不确定，使用较大的时间范围（默认最近20年）
    """
    end_year = datetime.now().year
    start_year = end_year - lookback_years
    return f"{start_year}-01-01~{end_year}-12-31"

def title_ok_for_ipo(title: str) -> bool:
    """
    检查标题是否为招股说明书
    - 必须包含"招股说明书"或"招股书"
    - 排除摘要、英文版、更正等
    """
    t = normalize_text(title)

    # 排除不需要的关键词
    if any(k in t for k in map(normalize_text, EXCLUDE_IN_TITLE)):
        return False

    # 必须包含招股说明书关键词
    return any(k in t for k in map(normalize_text, IPO_KEYWORDS))

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

def ms_to_year(ms: int) -> str:
    """从毫秒时间戳中提取年份"""
    try:
        return datetime.fromtimestamp(ms/1000).strftime("%Y")
    except Exception:
        return str(datetime.now().year)

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
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def read_tasks_from_csv(path: str):
    """
    读取 CSV 任务文件（IPO版本：只需要 code 和 name）
    CSV格式：code,name
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
                for row in csv.DictReader(f):
                    try:
                        raw = (row.get("code") or "").strip()
                        code = normalize_code(raw) if raw else ""
                        name = (row.get("name") or "").strip()
                        if not code or not name:
                            continue
                        tasks.append((code, name))
                    except Exception as e:
                        logging.debug(f"跳过无效行: {e}")
                        continue
            logging.info(f"✅ 成功使用编码 {enc} 读取 {len(tasks)} 条任务")
            return tasks
        except (UnicodeDecodeError, UnicodeError) as e:
            last_error = e
            logging.debug(f"编码 {enc} 失败: {e}")
            tasks = []
            continue
        except Exception as e:
            logging.error(f"读取 CSV 失败 ({enc}): {e}")
            raise

    # 所有编码都失败
    logging.error(f"❌ 无法读取 CSV 文件，尝试了编码: {encodings}")
    logging.error(f"最后错误: {last_error}")
    logging.error(f"请确保 CSV 文件保存为 UTF-8 或 GBK 编码")
    raise ValueError(f"无法解码 CSV 文件: {path}")

# ----------------------- orgId 获取 -----------------------
def build_orgid(code: str) -> str:
    """
    根据股票代码构造 orgId
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
    通过搜索API获取orgId（推荐方法）
    """
    code6 = normalize_code(code)
    url = "https://www.cninfo.com.cn/new/information/topSearch/query"

    try:
        r = api_session.post(url, data={"keyWord": code6}, timeout=10, proxies=PROXIES)
        if r.status_code == 200:
            js = r.json()
            if isinstance(js, list) and len(js) > 0:
                for item in js:
                    if item.get("code", "") == code6:
                        orgid = item.get("orgId")
                        company_name = item.get("zwjc", "")
                        if orgid:
                            logging.info(f"[orgId] 通过搜索API获取成功：{orgid} ({company_name})")
                            return orgid, company_name
    except Exception as e:
        logging.debug(f"搜索API查询失败 (code={code6}): {e}")

    return None

def get_orgid_via_html(code: str, name: Optional[str], html_session: Optional[requests.Session] = None) -> Optional[Tuple[str, str]]:
    """
    通过HTML页面解析获取orgId（兜底方法）
    """
    code6 = normalize_code(code)
    exch_dir, column_api, stock_suffix = detect_exchange(code6)

    if html_session is None:
        html_session = make_session(HEADERS_HTML)

    search_keywords = ["招股说明书", "首次公开发行", ""]

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

            main = soup.find("div", class_="list-main")
            if main:
                items = main.find_all("div", class_="list-item")
                logging.debug(f"找到 {len(items)} 条公告")

                for item in items[:5]:
                    company_span = item.find("span", class_="company-name")
                    company_name = company_span.get_text(strip=True) if company_span else ""

                    a = item.select_one("span.ahover.ell a")
                    if not a or not a.get("href"):
                        continue

                    detail_url = urljoin("https://www.cninfo.com.cn", a["href"])
                    qs = parse_qs(urlparse(detail_url).query)
                    oid = (qs.get("orgId") or [""])[0]

                    stock_code = (qs.get("stockCode") or [""])[0]
                    if stock_code and normalize_code(stock_code) == code6:
                        if oid:
                            logging.info(f"[HTML兜底] 成功解析 orgId：{oid} ({company_name})")
                            return oid, company_name

            scripts = soup.find_all("script")
            for script in scripts:
                script_text = script.string or ""
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

# ----------------------- 公告抓取与下载 -----------------------
def fetch_ipo_announcements(api_session: requests.Session, code: str, orgId: Optional[str],
                           column_api: str, page_size=100) -> List[dict]:
    """
    抓取IPO招股说明书公告
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
                logging.warning(f"hisAnnouncement HTTP {data.status_code} ({code} 页 {page})")
                break
            data = data.json() if data.text.strip().startswith("{") else {}
        except RequestException as e:
            logging.warning(f"hisAnnouncement 请求异常（{code} 页 {page}）：{e}")
            break

        anns = (data or {}).get("announcements") or []
        if not anns: break
        all_list.extend(anns)
        if len(anns) < page_size: break
        page += 1

    return all_list

def pick_latest_ipo(anns: List[dict], code: str) -> Optional[dict]:
    """
    从公告列表中选择最新的招股说明书
    支持PDF和HTML格式（早期文档多为HTML）
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

def html_to_text(html_content: str) -> str:
    """
    将HTML内容转换为纯文本
    提取主要内容，去除HTML标签和样式
    优化中文显示和格式
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # 移除不需要的标签
        for element in soup(["script", "style", "meta", "link", "noscript"]):
            element.decompose()

        # 获取文本内容，使用separator保持段落分隔
        text = soup.get_text(separator='\n')

        # 清理文本
        lines = []
        for line in text.splitlines():
            line = line.strip()
            # 跳过空行和只包含特殊字符的行
            if line and not line.replace('┈', '').replace('─', '').replace('　', '').strip() == '':
                lines.append(line)

        # 合并连续的相同行
        cleaned_lines = []
        prev_line = None
        for line in lines:
            if line != prev_line:
                cleaned_lines.append(line)
                prev_line = line

        text = '\n'.join(cleaned_lines)

        # 添加文档头部信息
        header = "=" * 60 + "\n"
        header += "IPO招股说明书 - 纯文本版\n"
        header += "本文档由HTML自动转换生成\n"
        header += "=" * 60 + "\n\n"

        return header + text
    except Exception as e:
        logging.warning(f"HTML转文本失败: {e}")
        return html_content

def download_html_resilient(session: requests.Session, url: str, path: str,
                            referer: Optional[str] = None, max_retries=3, convert_to_text=True):
    """
    下载HTML格式的公告并保存
    convert_to_text: 是否同时保存纯文本版本
    支持中文编码自动检测（GB2312/GBK/UTF-8）
    """
    last_err = None
    for attempt in range(1, max_retries+1):
        try:
            headers = {"Referer": referer} if referer else {}
            r = session.get(url, timeout=20, proxies=PROXIES, headers=headers)

            if r.status_code in RETRY_STATUS:
                time.sleep(RETRY_BACKOFF)
                continue
            if r.status_code >= 400:
                last_err = f"HTTP {r.status_code}"
                time.sleep(RETRY_BACKOFF)
                continue

            # 保存HTML内容
            ensure_dir(os.path.dirname(path))

            # 智能检测中文编码
            # 优先使用HTML meta标签指定的编码
            detected_encoding = r.encoding
            if r.apparent_encoding:
                detected_encoding = r.apparent_encoding

            # 对于中文内容，优先尝试常见编码
            if detected_encoding and detected_encoding.lower() in ['gb2312', 'gbk', 'gb18030']:
                try:
                    html_text = r.content.decode(detected_encoding)
                except:
                    html_text = r.content.decode('utf-8', errors='ignore')
            else:
                html_text = r.text

            # 修复HTML编码声明，确保与实际编码一致
            import re

            # 将所有GB2312/GBK编码声明替换为UTF-8
            # 匹配 <meta http-equiv="Content-Type" content="text/html; charset=gb2312">
            html_text = re.sub(
                r'<meta\s+http-equiv=["\']?Content-Type["\']?\s+content=["\']?text/html;\s*charset=gb2312["\']?\s*/?>',
                '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">',
                html_text,
                flags=re.IGNORECASE
            )

            # 匹配 <meta charset="gb2312">
            html_text = re.sub(
                r'<meta\s+charset=["\']?(gb2312|gbk|gb18030)["\']?\s*/?>',
                '<meta charset="UTF-8">',
                html_text,
                flags=re.IGNORECASE
            )

            # 如果还没有编码声明，添加一个
            if not re.search(r'<meta\s+(charset=|http-equiv=["\']?Content-Type)', html_text, re.IGNORECASE):
                if '<head>' in html_text:
                    html_text = html_text.replace('<head>', '<head>\n<meta charset="UTF-8">')
                elif '<HEAD>' in html_text:
                    html_text = html_text.replace('<HEAD>', '<HEAD>\n<meta charset="UTF-8">')

            # 保存HTML文件（统一使用UTF-8编码）
            with open(path, "w", encoding="utf-8") as f:
                f.write(html_text)

            # 同时保存纯文本版本
            if convert_to_text:
                text_content = html_to_text(html_text)
                text_path = path.replace('.html', '.txt').replace('.htm', '.txt')
                with open(text_path, "w", encoding="utf-8") as f:
                    f.write(text_content)
                logging.info(f"已转换为文本格式: {os.path.basename(text_path)}")

            return True, "ok"
        except RequestException as e:
            last_err = str(e)
            time.sleep(RETRY_BACKOFF)
        except Exception as e:
            last_err = str(e)
            time.sleep(RETRY_BACKOFF)

    return False, last_err or "HTTP 4xx/5xx"

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
    def __init__(self, checkpoint_file: str, orgid_cache_file: str):
        self.checkpoint_file = checkpoint_file
        self.orgid_cache_file = orgid_cache_file
        self.lock = multiprocessing.Lock()

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

def process_single_task(task_data: Tuple) -> Tuple[bool, Optional[Tuple]]:
    """
    处理单个下载任务（在独立进程中运行）
    """
    code, name, out_root, checkpoint_file, orgid_cache_file = task_data

    # 每个进程创建自己的 session
    api_session = make_session(HEADERS_API)
    html_session = make_session(HEADERS_HTML)

    # 创建共享状态管理器
    shared = SharedState(checkpoint_file, orgid_cache_file)

    # 检查是否已完成
    key = f"{code}-IPO"
    checkpoint = shared.load_checkpoint()
    if checkpoint.get(key):
        return True, None

    exch_dir, column_api, _ = detect_exchange(code)
    real_company_name = name

    try:
        # orgId 获取策略
        orgId = shared.get_orgid(code)
        if not orgId:
            orgId = build_orgid(code)
            shared.save_orgid(code, orgId)
            logging.info(f"[{code}] orgId 构造方法：{orgId}")

        # 抓取IPO公告
        anns = fetch_ipo_announcements(api_session, code, orgId, column_api)

        if not anns:
            # 尝试通过搜索API获取真实 orgId
            logging.warning(f"[{code}] 构造的 orgId 可能无效，尝试搜索API方法...")
            result = get_orgid_via_search_api(api_session, code)
            if result:
                real_orgid, company_name = result
                real_company_name = company_name
                if real_orgid != orgId:
                    logging.info(f"[{code}] orgId 更新为真实值：{real_orgid}")
                    orgId = real_orgid
                    shared.save_orgid(code, orgId)
                    anns = fetch_ipo_announcements(api_session, code, orgId, column_api)

            # HTML兜底
            if not anns:
                logging.warning(f"[{code}] 搜索API失败，使用 HTML 兜底方法...")
                html_result = get_orgid_via_html(code, name, html_session)
                if html_result:
                    real_orgid, company_name = html_result
                    if real_orgid != orgId:
                        logging.info(f"[{code}] [HTML兜底] orgId 更新为真实值：{real_orgid} ({company_name})")
                        orgId = real_orgid
                        shared.save_orgid(code, orgId)
                        anns = fetch_ipo_announcements(api_session, code, orgId, column_api)

        if not anns:
            logging.error(f"[{code}] 未获得公告列表：{real_company_name}（{code}）IPO")
            return False, (code, real_company_name, "no announcements")

        # 取最新的招股说明书
        best = pick_latest_ipo(anns, code)
        if not best:
            logging.error(f"[{code}] 公告过滤后为空：{real_company_name}（{code}）IPO")
            return False, (code, real_company_name, "not found after filter")

        # 下载
        adj = best.get("adjunctUrl", "")
        doc_url = pdf_url_from_adj(adj)
        ts = parse_time_to_ms(best.get("announcementTime"))
        pub_date = ms_to_ddmmyyyy(ts)
        pub_year = ms_to_year(ts)

        # 判断文件类型
        adj_lower = adj.lower()
        is_html = adj_lower.endswith(".html") or adj_lower.endswith(".htm")
        file_ext = ".html" if is_html else ".pdf"

        out_dir = os.path.join(out_root, exch_dir, code)
        ensure_dir(out_dir)
        fname = f"{code}_{pub_year}_{pub_date}{file_ext}"
        out_path = os.path.join(out_dir, fname)

        # 根据文件类型选择下载函数
        if is_html:
            logging.info(f"[{code}] 下载HTML格式文档：{doc_url}")
            ok, msg = download_html_resilient(html_session, doc_url, out_path, referer=None, max_retries=3)
        else:
            # 定义刷新函数
            def refresh_fn():
                anns2 = fetch_ipo_announcements(api_session, code, orgId, column_api)
                b2 = pick_latest_ipo(anns2, code)
                if not b2: return None, None
                return pdf_url_from_adj(b2.get("adjunctUrl", "")), None

            logging.info(f"[{code}] 下载PDF格式文档：{doc_url}")
            ok, msg = download_pdf_resilient(html_session, doc_url, out_path, referer=None,
                                            refresh_fn=refresh_fn, max_retries=3)

        if ok:
            logging.info(f"[{code}] 保存成功：{out_path}")
            shared.save_checkpoint(key)
            return True, None
        else:
            logging.error(f"[{code}] 下载失败：{real_company_name}（{code}）IPO - {msg}")
            return False, (code, real_company_name, f"download failed: {msg}")

    except Exception as e:
        logging.error(f"[{code}] 处理异常：{real_company_name}（{code}）IPO - {e}")
        return False, (code, real_company_name, f"exception: {str(e)}")
    finally:
        time.sleep(random.uniform(0.5, 1.5))

def run_multiprocessing(input_csv: str, out_root: str, fail_csv: str,
                       workers: int = 4, debug=False):
    """
    多进程并行下载模式
    """
    if debug:
        logger.setLevel(logging.DEBUG)
        logging.info("调试模式已启用")

    tasks = read_tasks_from_csv(input_csv)
    total = len(tasks)
    print(f"共读取任务：{total} 条")
    print(f"使用 {workers} 个并行进程处理")

    # 准备任务数据
    task_data_list = [
        (code, name, out_root, CHECKPOINT_FILE, ORGID_CACHE_FILE)
        for code, name in tasks
    ]

    failures = []
    completed = 0

    # 使用进程池并行处理
    with ProcessPoolExecutor(max_workers=workers) as executor:
        future_to_task = {
            executor.submit(process_single_task, task_data): task_data
            for task_data in task_data_list
        }

        with tqdm(total=total, desc="抓取进度", unit="任务") as pbar:
            for future in as_completed(future_to_task):
                task_data = future_to_task[future]
                code, name = task_data[:2]

                try:
                    success, failure_record = future.result()
                    if success:
                        completed += 1
                    elif failure_record:
                        failures.append(failure_record)
                except Exception as e:
                    logging.error(f"任务处理异常：{name}（{code}）IPO - {e}")
                    failures.append((code, name, f"exception: {str(e)}"))

                pbar.update(1)

    # 写入失败记录
    if failures:
        with open(fail_csv, "w", encoding=CSV_ENCODING, newline="", errors="replace") as f:
            w = csv.writer(f)
            w.writerow(["code", "name", "reason"])
            w.writerows(failures)
        print(f"❌ 写入失败记录：{fail_csv}（编码：{CSV_ENCODING}）")
        print(f"✅ 成功：{completed}/{total} ({completed*100//total}%)")
    else:
        print("✅ 全部成功，无失败记录。")

# ----------------------- 主流程 -----------------------
def run(input_csv: str, out_root: str, fail_csv: str, watch_log=False, debug=False):
    if debug:
        logger.setLevel(logging.DEBUG)
        logging.info("调试模式已启用")

    if watch_log:
        start_tail()

    api_session = make_session(HEADERS_API)
    html_session = make_session(HEADERS_HTML)

    checkpoint: Dict[str, bool] = load_json(CHECKPOINT_FILE, {})
    orgid_cache: Dict[str, str] = load_json(ORGID_CACHE_FILE, {})

    tasks = read_tasks_from_csv(input_csv)
    total = len(tasks)
    print(f"共读取任务：{total} 条")

    failures = []
    last_code = None

    for code, name in tqdm(tasks, desc="抓取进度", unit="任务"):
        key = f"{code}-IPO"
        if checkpoint.get(key):
            continue

        if last_code == code:
            time.sleep(INTER_SAME_STOCK_GAP)
        last_code = code

        exch_dir, column_api, stock_suffix = detect_exchange(code)
        logging.info(f"正在抓取：{name}（{code}） IPO招股说明书 [{column_api}]")

        real_company_name = name

        # orgId 获取策略
        orgId = orgid_cache.get(code)
        if not orgId:
            orgId = build_orgid(code)
            orgid_cache[code] = orgId
            save_json(ORGID_CACHE_FILE, orgid_cache)
            logging.info(f"[orgId] 构造方法：{orgId}")

        # 抓取IPO公告
        anns = fetch_ipo_announcements(api_session, code, orgId, column_api)

        if not anns:
            # 搜索API方法
            logging.warning(f"构造的 orgId 可能无效，尝试搜索API方法...")
            result = get_orgid_via_search_api(api_session, code)
            if result:
                real_orgid, api_company_name = result
                real_company_name = api_company_name
                if real_orgid != orgId:
                    logging.info(f"[orgId] 更新为真实值：{real_orgid}")
                    orgId = real_orgid
                    orgid_cache[code] = orgId
                    save_json(ORGID_CACHE_FILE, orgid_cache)
                    anns = fetch_ipo_announcements(api_session, code, orgId, column_api)

            # HTML兜底
            if not anns:
                logging.warning(f"搜索API失败，使用 HTML 兜底方法...")
                html_result = get_orgid_via_html(code, name, html_session)
                if html_result:
                    real_orgid, company_name = html_result
                    if real_orgid != orgId:
                        logging.info(f"[HTML兜底] orgId 更新为真实值：{real_orgid} ({company_name})")
                        orgId = real_orgid
                        orgid_cache[code] = orgId
                        save_json(ORGID_CACHE_FILE, orgid_cache)
                        anns = fetch_ipo_announcements(api_session, code, orgId, column_api)

        if not anns:
            logging.error(f"未获得公告列表：{real_company_name}（{code}）IPO")
            failures.append((code, real_company_name, "no announcements"))
            time.sleep(random.uniform(*INTER_COMBO_SLEEP_RANGE))
            continue

        # 取最新的招股说明书
        best = pick_latest_ipo(anns, code)
        if not best:
            logging.error(f"公告过滤后为空：{real_company_name}（{code}）IPO")
            failures.append((code, real_company_name, "not found after filter"))
            time.sleep(random.uniform(*INTER_COMBO_SLEEP_RANGE))
            continue

        # 下载
        adj = best.get("adjunctUrl", "")
        doc_url = pdf_url_from_adj(adj)
        ts = parse_time_to_ms(best.get("announcementTime"))
        pub_date = ms_to_ddmmyyyy(ts)
        pub_year = ms_to_year(ts)

        # 判断文件类型
        adj_lower = adj.lower()
        is_html = adj_lower.endswith(".html") or adj_lower.endswith(".htm")
        file_ext = ".html" if is_html else ".pdf"

        out_dir = os.path.join(out_root, exch_dir, code)
        ensure_dir(out_dir)
        fname = f"{code}_{pub_year}_{pub_date}{file_ext}"
        out_path = os.path.join(out_dir, fname)

        # 根据文件类型选择下载函数
        if is_html:
            logging.info(f"下载HTML格式文档：{doc_url}")
            ok, msg = download_html_resilient(html_session, doc_url, out_path, referer=None, max_retries=3)
        else:
            # 定义刷新函数
            def refresh_fn():
                anns2 = fetch_ipo_announcements(api_session, code, orgId, column_api)
                b2 = pick_latest_ipo(anns2, code)
                if not b2: return None, None
                return pdf_url_from_adj(b2.get("adjunctUrl", "")), None

            logging.debug(f"Downloading: url={doc_url} -> {out_path}")
            ok, msg = download_pdf_resilient(html_session, doc_url, out_path, referer=None, refresh_fn=refresh_fn, max_retries=3)

        if ok:
            logging.info(f"保存成功：{out_path}")
            checkpoint[key] = True
            save_json(CHECKPOINT_FILE, checkpoint)
        else:
            logging.error(f"下载失败：{real_company_name}（{code}）IPO - {msg}")
            failures.append((code, real_company_name, f"download failed: {msg}"))

        time.sleep(random.uniform(*INTER_COMBO_SLEEP_RANGE))

    # 失败记录
    if failures:
        with open(fail_csv, "w", encoding=CSV_ENCODING, newline="", errors="replace") as f:
            w = csv.writer(f)
            w.writerow(["code", "name", "reason"])
            w.writerows(failures)
        print(f"❌ 写入失败记录：{fail_csv}（编码：{CSV_ENCODING}）")
    else:
        print("✅ 全部成功，无失败记录。")

# ----------------------- CLI -----------------------
if __name__ == "__main__":
    p = argparse.ArgumentParser(description="CNINFO IPO招股说明书抓取工具")
    p.add_argument("--input", required=True, help="输入 CSV（code,name）")
    p.add_argument("--out", required=True, help="输出根目录")
    p.add_argument("--fail", required=True, help="失败记录 CSV")
    p.add_argument("--workers", type=int, default=0, help="并行进程数（0=顺序模式，推荐 4-8）")
    p.add_argument("--watch-log", action="store_true", help="实时滚动显示 error.log（仅顺序模式）")
    p.add_argument("--debug", action="store_true", help="调试模式（输出更多日志）")
    args = p.parse_args()

    # 多进程模式 or 顺序模式
    if args.workers > 0:
        if args.watch_log:
            print("⚠️  多进程模式下不支持 --watch-log，已忽略")
        run_multiprocessing(args.input, args.out, args.fail, workers=args.workers, debug=args.debug)
    else:
        run(args.input, args.out, args.fail, watch_log=args.watch_log, debug=args.debug)
