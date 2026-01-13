# -*- coding: utf-8 -*-
"""
CNINFO 爬虫配置和常量
"""

import os
import platform

# ----------------------- API URLs -----------------------
CNINFO_BASE_URL = "https://www.cninfo.com.cn"
CNINFO_API = f"{CNINFO_BASE_URL}/new/hisAnnouncement/query"
CNINFO_STATIC = "https://static.cninfo.com.cn/"
CNINFO_SEARCH = f"{CNINFO_BASE_URL}/new/search"

# ----------------------- Category Mappings -----------------------
CATEGORY_ALL = "category_yjdbg_szsh;category_sjdbg_szsh;category_bndbg_szsh;category_ndbg_szsh;"

# Category mapping for each quarter (more reliable than title pattern matching)
CATEGORY_MAP = {
    "Q1": "category_yjdbg_szsh;",      # 一季度报告 (First quarter report)
    "Q2": "category_bndbg_szsh;",      # 半年度报告 (Semi-annual report)
    "Q3": "category_sjdbg_szsh;",      # 三季度报告 (Third quarter report)
    "Q4": "category_ndbg_szsh;",       # 年度报告 (Annual report)
}

# IPO招股说明书类别（首次公开发行公告）
CATEGORY_IPO = "category_scgkfxgg_szsh;"

# ----------------------- HTTP Headers -----------------------
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

# ----------------------- Proxy Configuration -----------------------
# 如需代理，按需填写；默认 None
PROXIES = None
# PROXIES = {"http": "http://ip:port", "https": "http://ip:port"}

# ----------------------- Filtering Configuration -----------------------
# 排除关键词（定期报告）
EXCLUDE_IN_TITLE = ("摘要", "英文", "英文版")

# IPO招股说明书关键词和排除词
IPO_KEYWORDS = ("招股说明书", "招股书")
EXCLUDE_IN_TITLE_IPO = ("摘要", "英文", "英文版", "更正", "补充", "修订", "注册稿",
                        "提示性公告", "意向书", "附录", "上市公告书")

# ----------------------- Retry Configuration -----------------------
RETRY_STATUS = (403, 502, 503, 504)
RETRY_TIMES = 3
RETRY_BACKOFF = 1.0

# ----------------------- Rate Limiting -----------------------
INTER_COMBO_SLEEP_RANGE = (2.0, 3.0)  # 组合间睡眠
INTER_SAME_STOCK_GAP = 1.0            # 同一股票间隔

# ----------------------- File Encoding -----------------------
CSV_ENCODING = "gbk" if platform.system().lower().startswith("win") else "utf-8-sig"

# ----------------------- Cache File Paths -----------------------
# 状态文件路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# checkpoint.json 存储在输出目录（与输出绑定）
# orgid_cache 和 code_change_cache 存储在脚本目录（全局共享）
ORGID_CACHE_FILE = os.path.join(SCRIPT_DIR, "orgid_cache.json")
CODE_CHANGE_CACHE_FILE = os.path.join(SCRIPT_DIR, "code_change_cache.json")
NAME_CHANGE_CSV = os.path.join(SCRIPT_DIR, "name_changes.csv")

# ----------------------- Logging Configuration -----------------------
ERROR_LOG_FILE = os.path.join(SCRIPT_DIR, "error.log")
