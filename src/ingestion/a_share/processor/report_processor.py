# -*- coding: utf-8 -*-
"""
任务处理器
处理单个任务和多进程批量任务
"""

import os
import csv
import time
import random
import logging
import multiprocessing
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

from tqdm import tqdm

from ..config import (
    HEADERS_API, HEADERS_HTML, ORGID_CACHE_FILE, CODE_CHANGE_CACHE_FILE,
    CSV_ENCODING, INTER_COMBO_SLEEP_RANGE, INTER_SAME_STOCK_GAP
)
from ..utils.file_utils import (
    make_session, ensure_dir, read_tasks_from_csv,
    build_existing_pdf_cache, check_pdf_exists_in_cache
)
from ..utils.code_utils import detect_exchange, detect_code_change, get_all_related_codes, normalize_code
from ..utils.time_utils import parse_time_to_ms, ms_to_ddmmyyyy
from ..api.orgid_resolver import (
    build_orgid, get_orgid_via_search_api, get_orgid_by_searchkey, get_orgid_via_html
)
from ..api.client import fetch_anns_by_category, fetch_anns, pick_latest
from ..utils.file_utils import pdf_url_from_adj
from ..downloader.pdf_downloader import download_pdf_resilient
from ..state.shared_state import SharedState
from src.storage.object_store.path_manager import PathManager
from src.common.constants import Market, DocType

# SQLite-based 状态管理（替代 JSON）
try:
    from ..state.shared_state import SharedStateSQLite
    USE_SQLITE = True
except ImportError:
    logging.warning("⚠️  未找到 SharedStateSQLite，将使用 JSON 模式（性能较低）")
    USE_SQLITE = False

logger = logging.getLogger(__name__)


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
        logger.info(f"[{code}] PDF已存在于旧目录，跳过下载")
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
            logger.info(f"[{code}] orgId 构造方法：{orgId}")

        # 加载代码变更缓存
        code_change_cache = shared.load_code_change_cache()
        related_codes = get_all_related_codes(code, orgId, code_change_cache)

        # 抓公告 - 使用类别过滤（始终先尝试带orgId查询）
        anns = fetch_anns_by_category(api_session, code, orgId, column_api, year, quarter)

        # 兜底1：如果类别过滤无结果，尝试使用 CATEGORY_ALL（可能是类别分类问题）
        if not anns:
            logger.warning(f"[{code}] 类别过滤查询无结果，尝试使用 CATEGORY_ALL")
            anns = fetch_anns(api_session, code, orgId, column_api, year, quarter)  # fetch_anns uses CATEGORY_ALL
            if anns:
                logger.info(f"[{code}] CATEGORY_ALL查询成功，返回 {len(anns)} 条公告")

        # 兜底2：如果带orgId查询无结果，尝试不带orgId查询（处理合并/重组场景，orgId变更）
        if not anns and orgId:
            logger.warning(f"[{code}] 带orgId查询无结果，尝试不带orgId查询（可能是公司名变更）")
            anns = fetch_anns(api_session, code, None, column_api, year, quarter)  # Use CATEGORY_ALL without orgId
            if anns:
                logger.info(f"[{code}] 不带orgId查询成功，返回 {len(anns)} 条公告")
        
        # 检测代码变更
        if anns:
            actual_code = detect_code_change(anns, code, orgId)
            if actual_code and actual_code not in related_codes:
                logger.info(f"[{code}] 检测到代码变更：{code} -> {actual_code}")
                related_codes.append(actual_code)
                # 更新缓存
                shared.save_code_change(orgId, related_codes)
        
        if not anns:
            # 尝试通过搜索API获取真实 orgId（新方法，不需要公司名）
            logger.warning(f"[{code}] 构造的 orgId 可能无效，尝试搜索API方法...")
            result = get_orgid_via_search_api(api_session, code)
            if result:
                real_orgid, company_name = result
                real_company_name = company_name  # 保存真实公司名
                if real_orgid != orgId:
                    logger.info(f"[{code}] orgId 更新为真实值：{real_orgid}")
                    orgId = real_orgid
                    shared.save_orgid(code, orgId)
                    anns = fetch_anns_by_category(api_session, code, orgId, column_api, year, quarter)

            # 如果搜索API也失败，使用searchkey方法（需要公司名）
            if not anns:
                logger.warning(f"[{code}] 搜索API失败，尝试 searchkey 方法...")
                searchkey_result = get_orgid_by_searchkey(api_session, code, name, column_api)
                if searchkey_result:
                    real_orgid, _ = searchkey_result
                    if real_orgid and real_orgid != orgId:
                        logger.info(f"[{code}] orgId 更新为真实值：{real_orgid}")
                        orgId = real_orgid
                        shared.save_orgid(code, orgId)
                        anns = fetch_anns_by_category(api_session, code, orgId, column_api, year, quarter)

            # 方法4：最后的兜底 - HTML 页面解析（不依赖公司名，最可靠）
            if not anns:
                logger.warning(f"[{code}] searchkey 方法也失败，使用 HTML 兜底方法...")
                html_result = get_orgid_via_html(code, name, html_session)
                if html_result:
                    real_orgid, company_name = html_result
                    if real_orgid != orgId:
                        logger.info(f"[{code}] [HTML兜底] orgId 更新为真实值：{real_orgid} ({company_name})")
                        orgId = real_orgid
                        shared.save_orgid(code, orgId)
                        # 用新 orgId 重新抓取
                        anns = fetch_anns_by_category(api_session, code, orgId, column_api, year, quarter)

        if not anns:
            logger.error(f"[{code}] 未获得公告列表：{real_company_name}（{code}）{year}-{quarter}")
            return False, (code, real_company_name, year, quarter, "no announcements")

        # 取最新版（使用相关代码列表）
        best = pick_latest(anns, code, year, quarter, related_codes=related_codes)
        if not best:
            logger.error(f"[{code}] 公告过滤后为空：{real_company_name}（{code}）{year}-{quarter}")
            return False, (code, real_company_name, year, quarter, "not found after filter")

        # 下载
        adj = best.get("adjunctUrl", "")
        pdf_url = pdf_url_from_adj(adj)
        ts = parse_time_to_ms(best.get("announcementTime"))
        pub_date = ms_to_ddmmyyyy(ts)  # 发布日期（用于元数据）
        pub_date_iso = datetime.fromtimestamp(ts/1000).isoformat() if ts > 0 else None  # ISO格式日期

        # 使用 PathManager 生成与 MinIO 一致的路径结构
        # 季度字符串转数字（如 "Q2" -> 2）
        quarter_num = int(quarter[1:]) if quarter.startswith("Q") else 4
        
        # 根据季度确定文档类型
        # Q1, Q3: 季度报告 (quarterly_reports)
        # Q2: 半年报 (interim_reports)
        # Q4: 年报 (annual_reports)
        if quarter_num == 4:
            doc_type = DocType.ANNUAL_REPORT
        elif quarter_num == 2:
            doc_type = DocType.INTERIM_REPORT
        else:
            doc_type = DocType.QUARTERLY_REPORT
        
        # 生成文件名
        fname = f"{code}_{year}_{quarter}.pdf"
        
        # 使用 PathManager 生成路径（与 MinIO 一致）
        path_manager = PathManager()
        # Q2（半年报）和 Q4（年报）不需要季度文件夹
        quarter_for_path = quarter_num if quarter_num not in [2, 4] else None
        minio_path = path_manager.get_bronze_path(
            market=Market.A_SHARE,
            doc_type=doc_type,
            stock_code=code,
            year=year,
            quarter=quarter_for_path,
            filename=fname
        )
        
        # 转换为本地文件系统路径
        out_path = os.path.join(out_root, minio_path)
        out_dir = os.path.dirname(out_path)
        ensure_dir(out_dir)

        # 定义刷新函数（先尝试带orgId，失败则不带orgId）
        def refresh_fn():
            anns2 = fetch_anns_by_category(api_session, code, orgId, column_api, year, quarter)
            if not anns2 and orgId:
                anns2 = fetch_anns_by_category(api_session, code, None, column_api, year, quarter)
            b2 = pick_latest(anns2, code, year, quarter, related_codes=related_codes)
            if not b2:
                return None, None
            return pdf_url_from_adj(b2.get("adjunctUrl", "")), None

        ok, msg = download_pdf_resilient(html_session, pdf_url, out_path, referer=None,
                                        refresh_fn=refresh_fn, max_retries=3)
        if ok:
            logger.info(f"[{code}] 保存成功：{out_path}")
            shared.save_checkpoint(key)
            
            # 注意：MinIO 上传已移除，由 report_crawler.py 统一处理
            
            return True, None
        else:
            logger.error(f"[{code}] 下载失败：{real_company_name}（{code}）{year}-{quarter} - {msg}")
            return False, (code, real_company_name, year, quarter, f"download failed: {msg}")

    except Exception as e:
        logger.error(f"[{code}] 处理异常：{real_company_name}（{code}）{year}-{quarter} - {e}")
        return False, (code, real_company_name, year, quarter, f"exception: {str(e)}")
    finally:
        # 添加随机延迟，避免过度请求
        time.sleep(random.uniform(0.5, 1.5))


def run_multiprocessing(
    input_csv: str,
    out_root: str,
    fail_csv: str,
    workers: int = 4,
    debug: bool = False,
    old_pdf_dir: Optional[str] = None,
    default_year: Optional[int] = None,
    default_quarter: Optional[str] = None
):
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
        logger.info("调试模式已启用")

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
                    logger.error(f"任务处理异常：{name}（{code}）{year}-{quarter} - {e}")
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


def run(
    input_csv: str,
    out_root: str,
    fail_csv: str,
    watch_log: bool = False,
    debug: bool = False,
    old_pdf_dir: Optional[str] = None,
    default_year: Optional[int] = None,
    default_quarter: Optional[str] = None
):
    """
    顺序执行模式（CLI入口，保留向后兼容）
    
    Args:
        input_csv: 输入CSV文件路径
        out_root: 输出根目录
        fail_csv: 失败记录CSV路径
        watch_log: 是否实时滚动显示日志
        debug: 调试模式
        old_pdf_dir: 旧PDF目录路径
        default_year: 默认年份
        default_quarter: 默认季度
    """
    # 注意：watch_log 功能已移除，保留参数以兼容旧代码
    if watch_log:
        logger.warning("watch_log 功能已移除")
    
    if debug:
        logger.setLevel(logging.DEBUG)
        logger.info("调试模式已启用")

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
        from ..utils.file_utils import load_json
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
            logger.info(f"[{code}] PDF已存在于旧目录，跳过下载")
            if USE_SQLITE and state:
                state.save_checkpoint(key)
            else:
                from ..utils.file_utils import save_json
                checkpoint[key] = True
                save_json(checkpoint_file, checkpoint)
            continue

        if last_code == code:
            time.sleep(INTER_SAME_STOCK_GAP)
        last_code = code

        exch_dir, column_api, stock_suffix = detect_exchange(code)
        logger.info(f"正在抓取：{name}（{code}） {year}-{quarter} [{column_api}]")

        # 用于保存从API获取的真实公司名（用于失败记录）
        real_company_name = name

        # orgId 获取策略：先从缓存，再尝试构造，最后用多种方法查询
        orgId = orgid_cache.get(code)
        if not orgId:
            # 方法1：尝试简单构造（快速，但仅适用部分公司）
            orgId = build_orgid(code)
            if USE_SQLITE and state:
                state.save_orgid(code, orgId)
            else:
                from ..utils.file_utils import save_json
                orgid_cache[code] = orgId
                save_json(ORGID_CACHE_FILE, orgid_cache)
            logger.info(f"[orgId] 构造方法：{orgId}")

        # 获取相关代码列表（处理代码变更）
        related_codes = get_all_related_codes(code, orgId, code_change_cache)

        # 抓公告（多窗 + 分页）- 使用类别过滤（始终先尝试带orgId查询）
        anns = fetch_anns_by_category(api_session, code, orgId, column_api, year, quarter)

        # 兜底1：如果类别过滤无结果，尝试使用 CATEGORY_ALL（可能是类别分类问题）
        if not anns:
            logger.warning(f"[{code}] 类别过滤查询无结果，尝试使用 CATEGORY_ALL")
            anns = fetch_anns(api_session, code, orgId, column_api, year, quarter)
            if anns:
                logger.info(f"[{code}] CATEGORY_ALL查询成功，返回 {len(anns)} 条公告")

        # 兜底2：如果带orgId查询无结果，尝试不带orgId查询（处理合并/重组场景，orgId变更）
        if not anns and orgId:
            logger.warning(f"[{code}] 带orgId查询无结果，尝试不带orgId查询（可能是公司名变更）")
            anns = fetch_anns(api_session, code, None, column_api, year, quarter)
            if anns:
                logger.info(f"[{code}] 不带orgId查询成功，返回 {len(anns)} 条公告")

        # 检测代码变更
        if anns:
            actual_code = detect_code_change(anns, code, orgId)
            if actual_code and actual_code not in related_codes:
                logger.info(f"[代码变更检测] {code} -> {actual_code}")
                related_codes.append(actual_code)
                # 更新缓存
                if orgId:
                    if USE_SQLITE and state:
                        state.save_code_change(orgId, related_codes)
                    else:
                        from ..utils.file_utils import save_json
                        if orgId not in code_change_cache:
                            code_change_cache[orgId] = []
                        for c in related_codes:
                            if c not in code_change_cache[orgId]:
                                code_change_cache[orgId].append(c)
                        save_json(CODE_CHANGE_CACHE_FILE, code_change_cache)
        
        if not anns:
            # 方法2：如果构造的 orgId 无效，尝试通过搜索API获取真实 orgId（不需要公司名）
            logger.warning(f"构造的 orgId 可能无效，尝试搜索API方法...")
            result = get_orgid_via_search_api(api_session, code)
            if result:
                real_orgid, api_company_name = result
                real_company_name = api_company_name  # 保存真实公司名
                if real_orgid != orgId:
                    logger.info(f"[orgId] 更新为真实值：{real_orgid}")
                    orgId = real_orgid
                    if USE_SQLITE and state:
                        state.save_orgid(code, orgId)
                    else:
                        from ..utils.file_utils import save_json
                        orgid_cache[code] = orgId
                        save_json(ORGID_CACHE_FILE, orgid_cache)
                    # 用新 orgId 重新抓取
                    anns = fetch_anns_by_category(api_session, code, orgId, column_api, year, quarter)

            # 如果搜索API也失败，使用searchkey方法（需要公司名）
            if not anns:
                logger.warning(f"搜索API失败，尝试 searchkey 方法...")
                searchkey_result = get_orgid_by_searchkey(api_session, code, name, column_api)
                if searchkey_result:
                    real_orgid, _ = searchkey_result
                    if real_orgid and real_orgid != orgId:
                        logger.info(f"[orgId] 更新为真实值：{real_orgid}")
                        orgId = real_orgid
                        if USE_SQLITE and state:
                            state.save_orgid(code, orgId)
                        else:
                            from ..utils.file_utils import save_json
                            orgid_cache[code] = orgId
                            save_json(ORGID_CACHE_FILE, orgid_cache)
                        # 用新 orgId 重新抓取
                        anns = fetch_anns_by_category(api_session, code, orgId, column_api, year, quarter)

            # 方法4：最后的兜底 - HTML 页面解析（不依赖公司名，最可靠）
            if not anns:
                logger.warning(f"searchkey 方法也失败，使用 HTML 兜底方法...")
                html_result = get_orgid_via_html(code, name, html_session)
                if html_result:
                    real_orgid, company_name = html_result
                    if real_orgid != orgId:
                        logger.info(f"[HTML兜底] orgId 更新为真实值：{real_orgid} ({company_name})")
                        orgId = real_orgid
                        if USE_SQLITE and state:
                            state.save_orgid(code, orgId)
                        else:
                            from ..utils.file_utils import save_json
                            orgid_cache[code] = orgId
                            save_json(ORGID_CACHE_FILE, orgid_cache)
                        # 用新 orgId 重新抓取
                        anns = fetch_anns_by_category(api_session, code, orgId, column_api, year, quarter)

        if not anns:
            logger.error(f"未获得公告列表：{real_company_name}（{code}）{year}-{quarter}")
            failures.append((code, real_company_name, year, quarter, "no announcements"))
            time.sleep(random.uniform(*INTER_COMBO_SLEEP_RANGE))
            continue

        # 取最新版（使用相关代码列表处理代码变更）
        best = pick_latest(anns, code, year, quarter, related_codes=related_codes)
        if not best:
            logger.error(f"公告过滤后为空：{real_company_name}（{code}）{year}-{quarter}")
            failures.append((code, real_company_name, year, quarter, "not found after filter"))
            time.sleep(random.uniform(*INTER_COMBO_SLEEP_RANGE))
            continue

        # 下载
        adj = best.get("adjunctUrl", "")
        pdf_url = pdf_url_from_adj(adj)
        ts = parse_time_to_ms(best.get("announcementTime"))
        pub_date = ms_to_ddmmyyyy(ts)  # 发布日期（用于日志）
        pub_date_iso = datetime.fromtimestamp(ts/1000).isoformat() if ts > 0 else None  # ISO格式日期（用于元数据）

        # 使用 PathManager 生成与 MinIO 一致的路径结构
        # 季度字符串转数字（如 "Q2" -> 2）
        quarter_num = int(quarter[1:]) if quarter.startswith("Q") else 4
        
        # 根据季度确定文档类型
        # Q1, Q3: 季度报告 (quarterly_reports)
        # Q2: 半年报 (interim_reports)
        # Q4: 年报 (annual_reports)
        if quarter_num == 4:
            doc_type = DocType.ANNUAL_REPORT
        elif quarter_num == 2:
            doc_type = DocType.INTERIM_REPORT
        else:
            doc_type = DocType.QUARTERLY_REPORT
        
        # 生成文件名
        fname = f"{code}_{year}_{quarter}.pdf"
        
        # 使用 PathManager 生成路径（与 MinIO 一致）
        path_manager = PathManager()
        # Q2（半年报）和 Q4（年报）不需要季度文件夹
        quarter_for_path = quarter_num if quarter_num not in [2, 4] else None
        minio_path = path_manager.get_bronze_path(
            market=Market.A_SHARE,
            doc_type=doc_type,
            stock_code=code,
            year=year,
            quarter=quarter_for_path,
            filename=fname
        )
        
        # 转换为本地文件系统路径
        out_path = os.path.join(out_root, minio_path)
        out_dir = os.path.dirname(out_path)
        ensure_dir(out_dir)

        # 定义刷新函数（404 时重新拉列表，先尝试带orgId，失败则不带orgId）
        def refresh_fn():
            anns2 = fetch_anns_by_category(api_session, code, orgId, column_api, year, quarter)
            if not anns2 and orgId:
                anns2 = fetch_anns_by_category(api_session, code, None, column_api, year, quarter)
            b2 = pick_latest(anns2, code, year, quarter, related_codes=related_codes)
            if not b2:
                return None, None
            return pdf_url_from_adj(b2.get("adjunctUrl", "")), None

        logger.debug(f"Downloading: url={pdf_url} -> {out_path}")
        ok, msg = download_pdf_resilient(html_session, pdf_url, out_path, referer=None, refresh_fn=refresh_fn, max_retries=3)
        if ok:
            logger.info(f"保存成功：{out_path}")
            if USE_SQLITE and state:
                state.save_checkpoint(key)
            else:
                from ..utils.file_utils import save_json
                checkpoint[key] = True
                save_json(checkpoint_file, checkpoint)
        else:
            logger.error(f"下载失败：{real_company_name}（{code}）{year}-{quarter} - {msg}")
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


if __name__ == "__main__":
    import argparse
    
    p = argparse.ArgumentParser(description="CNINFO 定期报告抓取（含新 orgId 获取策略 + 多进程支持）")
    p.add_argument("--input", required=True, help="输入 CSV（code,name 或 code,name,year,quarter）")
    p.add_argument("--out", required=True, help="输出根目录")
    p.add_argument("--fail", required=True, help="失败记录 CSV")
    p.add_argument("--year", type=int, default=None, help="默认年份（如果CSV中没有year列）")
    p.add_argument("--quarter", type=str, default=None, choices=["Q1", "Q2", "Q3", "Q4"], help="默认季度（如果CSV中没有quarter列）")
    p.add_argument("--workers", type=int, default=0, help="并行进程数（0=顺序模式，推荐 4-8）")
    p.add_argument("--old-pdf-dir", type=str, default=None, help="旧PDF目录路径（如存在，会先检查避免重复下载）")
    p.add_argument("--watch-log", action="store_true", help="实时滚动显示 error.log（仅顺序模式，已废弃）")
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
