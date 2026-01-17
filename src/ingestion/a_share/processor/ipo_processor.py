# -*- coding: utf-8 -*-
"""
IPO 招股说明书任务处理器
协调API调用、状态管理、文件下载等步骤
"""

import os
import csv
import time
import random
import logging
import multiprocessing
from typing import List, Optional, Tuple
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

from tqdm import tqdm

from ..config import (
    HEADERS_API, HEADERS_HTML, ORGID_CACHE_FILE,
    CSV_ENCODING, INTER_COMBO_SLEEP_RANGE, INTER_SAME_STOCK_GAP
)
from ..utils.file_utils import (
    make_session, ensure_dir, read_tasks_from_csv as _read_tasks_from_csv,
    load_json, save_json, pdf_url_from_adj
)
from ..utils.code_utils import detect_exchange, normalize_code
from ..utils.time_utils import parse_time_to_ms, ms_to_ddmmyyyy
from ..api.orgid_resolver import (
    build_orgid, get_orgid_via_search_api, get_orgid_via_html
)
from ..api.ipo_client import fetch_ipo_announcements, pick_latest_ipo
from ..downloader.pdf_downloader import download_pdf_resilient
from ..downloader.html_downloader import download_html_resilient, download_html_from_detail_page
from ..state.shared_state import SharedState
from src.storage.object_store.path_manager import PathManager
from src.common.constants import Market, DocType

logger = logging.getLogger(__name__)
# 确保日志级别足够低以显示调试信息
if logger.level == logging.NOTSET:
    logger.setLevel(logging.INFO)


def read_tasks_from_csv(path: str):
    """
    读取 CSV 任务文件（IPO版本：只需要 code 和 name）
    CSV格式：code,name
    """
    import platform
    from ..utils.code_utils import normalize_code
    
    tasks = []
    encodings = ["utf-8-sig", "utf-8"]
    if platform.system().lower().startswith("win"):
        encodings.extend(["gbk", "gb2312", "gb18030"])

    last_error = None
    for enc in encodings:
        try:
            logger.debug(f"尝试使用编码 {enc} 读取 CSV...")
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
                        logger.debug(f"跳过无效行: {e}")
                        continue
            logger.info(f"✅ 成功使用编码 {enc} 读取 {len(tasks)} 条任务")
            return tasks
        except (UnicodeDecodeError, UnicodeError) as e:
            last_error = e
            logger.debug(f"编码 {enc} 失败: {e}")
            tasks = []
            continue
        except Exception as e:
            logger.error(f"读取 CSV 失败 ({enc}): {e}")
            raise

    # 所有编码都失败
    logger.error(f"❌ 无法读取 CSV 文件，尝试了编码: {encodings}")
    logger.error(f"最后错误: {last_error}")
    raise ValueError(f"无法解码 CSV 文件: {path}")


def ms_to_year(ms: int) -> str:
    """从毫秒时间戳中提取年份"""
    try:
        return datetime.fromtimestamp(ms/1000).strftime("%Y")
    except Exception:
        return str(datetime.now().year)


def process_single_ipo_task(task_data: Tuple) -> Tuple[bool, Optional[Tuple]]:
    """
    处理单个IPO下载任务（在独立进程中运行）

    Args:
        task_data: (code, name, out_root, checkpoint_file, orgid_cache_file)

    Returns:
        (success, failure_record or None)
    """
    code, name, out_root, checkpoint_file, orgid_cache_file = task_data

    # 每个进程创建自己的 session
    api_session = make_session(HEADERS_API)
    html_session = make_session(HEADERS_HTML)

    # 创建共享状态管理器（IPO版本，不需要code_change_cache）
    # 创建一个临时的code_change_cache文件路径（不会被使用）
    code_change_cache_file = os.path.join(os.path.dirname(checkpoint_file), "code_change_cache_ipo.json")
    shared_lock = multiprocessing.Lock()
    shared = SharedState(checkpoint_file, orgid_cache_file, code_change_cache_file, shared_lock)

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
            logger.info(f"[{code}] orgId 构造方法：{orgId}")

        # 抓取IPO公告
        anns = fetch_ipo_announcements(api_session, code, orgId, column_api)

        if not anns:
            # 尝试通过搜索API获取真实 orgId
            logger.debug(f"[{code}] 构造的 orgId 可能无效，尝试搜索API方法...")
            result = get_orgid_via_search_api(api_session, code)
            if result:
                real_orgid, company_name = result
                real_company_name = company_name
                if real_orgid != orgId:
                    logger.info(f"[{code}] orgId 更新为真实值：{real_orgid}")
                    orgId = real_orgid
                    shared.save_orgid(code, orgId)
                    anns = fetch_ipo_announcements(api_session, code, orgId, column_api)

            # HTML兜底
            if not anns:
                logger.warning(f"[{code}] 搜索API失败，使用 HTML 兜底方法...")
                html_result = get_orgid_via_html(code, name, html_session)
                if html_result:
                    real_orgid, company_name = html_result
                    if real_orgid != orgId:
                        logger.info(f"[{code}] [HTML兜底] orgId 更新为真实值：{real_orgid} ({company_name})")
                        orgId = real_orgid
                        shared.save_orgid(code, orgId)
                        anns = fetch_ipo_announcements(api_session, code, orgId, column_api)

        if not anns:
            logger.error(f"[{code}] 未获得公告列表：{real_company_name}（{code}）IPO")
            return False, (code, real_company_name, "no announcements")

        # 取最新的招股说明书
        best = pick_latest_ipo(anns, code)
        if not best:
            logger.error(f"[{code}] 公告过滤后为空：{real_company_name}（{code}）IPO")
            logger.debug(f"[{code}] 所有公告标题: {[a.get('announcementTitle', '') for a in anns[:10]]}")
            return False, (code, real_company_name, "not found after filter")

        # 下载
        adj = best.get("adjunctUrl", "")
        logger.info(f"[{code}] 找到公告: {best.get('announcementTitle', '')}, adjunctUrl: {adj}")
        ts = parse_time_to_ms(best.get("announcementTime"))
        pub_date = ms_to_ddmmyyyy(ts)
        pub_year = ms_to_year(ts)

        # 判断文件类型
        adj_lower = adj.lower()
        is_html = adj_lower.endswith(".html") or adj_lower.endswith(".htm")
        file_ext = ".html" if is_html else ".pdf"

        # 构建URL：HTML文件可能需要完整的URL，PDF文件使用CNINFO_STATIC前缀
        if is_html:
            # HTML文件：adjunctUrl可能是完整URL或相对路径
            if adj.startswith("http://") or adj.startswith("https://"):
                doc_url = adj
            else:
                # 相对路径，需要构建完整URL
                from ..config import CNINFO_STATIC
                doc_url = CNINFO_STATIC + adj.lstrip("/")
        else:
            # PDF文件：使用CNINFO_STATIC前缀
            doc_url = pdf_url_from_adj(adj)

        # 使用 PathManager 生成与 MinIO 一致的路径结构
        # 文件名统一为 document.pdf 或 document.html
        fname = f"document{file_ext}"
        path_manager = PathManager()
        minio_path = path_manager.get_bronze_path(
            market=Market.A_SHARE,
            doc_type=DocType.IPO_PROSPECTUS,
            stock_code=code,
            year=None,  # IPO不需要年份
            quarter=None,  # IPO不需要季度
            filename=fname
        )
        
        # 转换为本地文件系统路径
        out_path = os.path.join(out_root, minio_path)
        out_dir = os.path.dirname(out_path)
        ensure_dir(out_dir)
        
        # 发布日期信息保存在变量中，后续可以写入metadata
        # pub_date: DDMMYYYY格式
        # pub_year: YYYY格式
        # pub_date_iso: ISO格式（用于metadata）
        pub_date_iso = datetime.fromtimestamp(ts/1000).isoformat() if ts > 0 else None

        # 根据文件类型选择下载函数
        if is_html:
            logger.info(f"[{code}] 下载HTML格式文档：{doc_url}")
            logger.info(f"[{code}] HTML文件完整信息 - title: {best.get('announcementTitle', '')}, adj: {adj}, url: {doc_url}")
            
            # 尝试直接下载
            ok, msg = download_html_resilient(html_session, doc_url, out_path, referer=None, max_retries=3)
            
            if not ok and "404" in msg:
                # 尝试从公告详情页获取HTML内容
                logger.warning(f"[{code}] 直接URL下载失败（404），尝试从公告详情页获取...")
                
                # 构建公告详情页URL
                announcement_id = best.get("announcementId", "")
                org_id = best.get("orgId", orgId) or orgId
                
                if announcement_id and org_id:
                    from ..config import CNINFO_BASE_URL
                    # CNINFO公告详情页格式：https://www.cninfo.com.cn/new/disclosure/detail?plate=&orgId=xxx&stockCode=xxx&announcementId=xxx
                    detail_url = f"{CNINFO_BASE_URL}/new/disclosure/detail?plate=&orgId={org_id}&stockCode={code}&announcementId={announcement_id}"
                    logger.info(f"[{code}] 尝试从详情页获取: {detail_url}")
                    
                    # 从详情页提取HTML内容
                    ok, msg = download_html_from_detail_page(html_session, detail_url, out_path, code)
                    
                    if ok:
                        logger.info(f"[{code}] 从详情页成功获取HTML内容")
                    else:
                        logger.warning(f"[{code}] 从详情页获取也失败: {msg}")
                else:
                    logger.warning(f"[{code}] 缺少公告ID或orgId，无法构建详情页URL")
        else:
            # 定义刷新函数
            def refresh_fn():
                anns2 = fetch_ipo_announcements(api_session, code, orgId, column_api)
                b2 = pick_latest_ipo(anns2, code)
                if not b2:
                    return None, None
                return pdf_url_from_adj(b2.get("adjunctUrl", "")), None

            logger.info(f"[{code}] 下载PDF格式文档：{doc_url}")
            ok, msg = download_pdf_resilient(html_session, doc_url, out_path, referer=None,
                                            refresh_fn=refresh_fn, max_retries=3)

        if ok:
            logger.info(f"[{code}] 保存成功：{out_path}")
            # 保存发布日期信息和URL到metadata文件（供crawler读取）
            metadata_file = out_path.replace(file_ext, ".meta.json")
            metadata_info = {
                'publication_date': pub_date,  # DDMMYYYY格式
                'publication_year': pub_year,  # YYYY格式
                'publication_date_iso': pub_date_iso,  # ISO格式
                'source_url': doc_url  # 文档来源URL
            }
            save_json(metadata_file, metadata_info)
            shared.save_checkpoint(key)
            return True, None
        else:
            logger.error(f"[{code}] 下载失败：{real_company_name}（{code}）IPO - {msg}")
            return False, (code, real_company_name, f"download failed: {msg}")

    except Exception as e:
        logger.error(f"[{code}] 处理异常：{real_company_name}（{code}）IPO - {e}")
        return False, (code, real_company_name, f"exception: {str(e)}")
    finally:
        time.sleep(random.uniform(0.5, 1.5))


def run_ipo_multiprocessing(
    input_csv: str,
    out_root: str,
    fail_csv: str,
    workers: int = 4,
    debug: bool = False
):
    """
    多进程并行下载模式（IPO版本）
    
    Args:
        input_csv: 输入CSV文件路径
        out_root: 输出根目录
        fail_csv: 失败记录CSV路径
        workers: worker进程数 (建议 4-8)
        debug: 调试模式
    """
    if debug:
        logger.setLevel(logging.DEBUG)
        logger.info("调试模式已启用")

    tasks = read_tasks_from_csv(input_csv)
    total = len(tasks)
    print(f"共读取任务：{total} 条")
    print(f"使用 {workers} 个并行进程处理")

    # 准备任务数据
    checkpoint_file = os.path.join(out_root, "checkpoint_ipo.json")
    orgid_cache_file = os.path.join(os.path.dirname(__file__), "../orgid_cache_ipo.json")
    
    task_data_list = [
        (code, name, out_root, checkpoint_file, orgid_cache_file)
        for code, name in tasks
    ]

    failures = []
    completed = 0

    # 使用进程池并行处理
    with ProcessPoolExecutor(max_workers=workers) as executor:
        future_to_task = {
            executor.submit(process_single_ipo_task, task_data): task_data
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
                    logger.error(f"任务处理异常：{name}（{code}）IPO - {e}")
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


def run_ipo(
    input_csv: str,
    out_root: str,
    fail_csv: str,
    watch_log: bool = False,
    debug: bool = False
):
    """
    顺序执行模式（IPO版本，CLI入口，保留向后兼容）
    
    Args:
        input_csv: 输入CSV文件路径
        out_root: 输出根目录
        fail_csv: 失败记录CSV路径
        watch_log: 是否实时滚动显示日志（已废弃）
        debug: 调试模式
    """
    if watch_log:
        logger.warning("watch_log 功能已移除")
    
    if debug:
        logger.setLevel(logging.DEBUG)
        logger.info("调试模式已启用")

    api_session = make_session(HEADERS_API)
    html_session = make_session(HEADERS_HTML)

    checkpoint_file = os.path.join(out_root, "checkpoint_ipo.json")
    script_dir = os.path.dirname(os.path.dirname(__file__))  # 回到 a_share 目录
    orgid_cache_file = os.path.join(script_dir, "orgid_cache_ipo.json")

    checkpoint: dict = load_json(checkpoint_file, {})
    orgid_cache: dict = load_json(orgid_cache_file, {})

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
        logger.info(f"正在抓取：{name}（{code}） IPO招股说明书 [{column_api}]")

        real_company_name = name

        # orgId 获取策略
        orgId = orgid_cache.get(code)
        if not orgId:
            orgId = build_orgid(code)
            orgid_cache[code] = orgId
            save_json(orgid_cache_file, orgid_cache)
            logger.info(f"[orgId] 构造方法：{orgId}")

        # 抓取IPO公告
        anns = fetch_ipo_announcements(api_session, code, orgId, column_api)

        if not anns:
            # 搜索API方法
            logger.debug(f"构造的 orgId 可能无效，尝试搜索API方法...")
            result = get_orgid_via_search_api(api_session, code)
            if result:
                real_orgid, api_company_name = result
                real_company_name = api_company_name
                if real_orgid != orgId:
                    logger.info(f"[orgId] 更新为真实值：{real_orgid}")
                    orgId = real_orgid
                    orgid_cache[code] = orgId
                    save_json(orgid_cache_file, orgid_cache)
                    anns = fetch_ipo_announcements(api_session, code, orgId, column_api)

            # HTML兜底
            if not anns:
                logger.warning(f"搜索API失败，使用 HTML 兜底方法...")
                html_result = get_orgid_via_html(code, name, html_session)
                if html_result:
                    real_orgid, company_name = html_result
                    if real_orgid != orgId:
                        logger.info(f"[HTML兜底] orgId 更新为真实值：{real_orgid} ({company_name})")
                        orgId = real_orgid
                        orgid_cache[code] = orgId
                        save_json(orgid_cache_file, orgid_cache)
                        anns = fetch_ipo_announcements(api_session, code, orgId, column_api)

        if not anns:
            logger.error(f"未获得公告列表：{real_company_name}（{code}）IPO")
            failures.append((code, real_company_name, "no announcements"))
            time.sleep(random.uniform(*INTER_COMBO_SLEEP_RANGE))
            continue

        # 取最新的招股说明书
        best = pick_latest_ipo(anns, code)
        if not best:
            logger.error(f"公告过滤后为空：{real_company_name}（{code}）IPO")
            failures.append((code, real_company_name, "not found after filter"))
            time.sleep(random.uniform(*INTER_COMBO_SLEEP_RANGE))
            continue

        # 下载
        adj = best.get("adjunctUrl", "")
        ts = parse_time_to_ms(best.get("announcementTime"))
        pub_date = ms_to_ddmmyyyy(ts)
        pub_year = ms_to_year(ts)

        # 判断文件类型
        adj_lower = adj.lower()
        is_html = adj_lower.endswith(".html") or adj_lower.endswith(".htm")
        file_ext = ".html" if is_html else ".pdf"

        # 构建URL：HTML文件可能需要完整的URL，PDF文件使用CNINFO_STATIC前缀
        if is_html:
            # HTML文件：adjunctUrl可能是完整URL或相对路径
            if adj.startswith("http://") or adj.startswith("https://"):
                doc_url = adj
            else:
                # 相对路径，需要构建完整URL
                from ..config import CNINFO_STATIC
                doc_url = CNINFO_STATIC + adj.lstrip("/")
            logger.debug(f"HTML文件URL: {doc_url} (adjunctUrl: {adj})")
        else:
            # PDF文件：使用CNINFO_STATIC前缀
            doc_url = pdf_url_from_adj(adj)
            logger.debug(f"PDF文件URL: {doc_url} (adjunctUrl: {adj})")

        # 使用 PathManager 生成与 MinIO 一致的路径结构
        # 文件名统一为 document.pdf 或 document.html
        fname = f"document{file_ext}"
        path_manager = PathManager()
        minio_path = path_manager.get_bronze_path(
            market=Market.A_SHARE,
            doc_type=DocType.IPO_PROSPECTUS,
            stock_code=code,
            year=None,  # IPO不需要年份
            quarter=None,  # IPO不需要季度
            filename=fname
        )
        
        # 转换为本地文件系统路径
        out_path = os.path.join(out_root, minio_path)
        out_dir = os.path.dirname(out_path)
        ensure_dir(out_dir)
        
        # 发布日期信息保存在变量中，后续可以写入metadata
        # pub_date: DDMMYYYY格式
        # pub_year: YYYY格式
        # pub_date_iso: ISO格式（用于metadata）
        pub_date_iso = datetime.fromtimestamp(ts/1000).isoformat() if ts > 0 else None

        # 根据文件类型选择下载函数
        if is_html:
            logger.info(f"下载HTML格式文档：{doc_url}")
            ok, msg = download_html_resilient(html_session, doc_url, out_path, referer=None, max_retries=3)
        else:
            # 定义刷新函数
            def refresh_fn():
                anns2 = fetch_ipo_announcements(api_session, code, orgId, column_api)
                b2 = pick_latest_ipo(anns2, code)
                if not b2:
                    return None, None
                adj2 = b2.get("adjunctUrl", "")
                if adj2.lower().endswith((".html", ".htm")):
                    # HTML文件URL处理
                    if adj2.startswith("http://") or adj2.startswith("https://"):
                        return adj2, None
                    else:
                        from ..config import CNINFO_STATIC
                        return CNINFO_STATIC + adj2.lstrip("/"), None
                else:
                    # PDF文件URL处理
                    return pdf_url_from_adj(adj2), None

            logger.debug(f"Downloading: url={doc_url} -> {out_path}")
            ok, msg = download_pdf_resilient(html_session, doc_url, out_path, referer=None, refresh_fn=refresh_fn, max_retries=3)

        if ok:
            logger.info(f"保存成功：{out_path}")
            # 保存发布日期信息到metadata文件（供crawler读取）
            metadata_file = out_path.replace(file_ext, ".meta.json")
            metadata_info = {
                'publication_date': pub_date,  # DDMMYYYY格式
                'publication_year': pub_year,  # YYYY格式
                'publication_date_iso': pub_date_iso  # ISO格式
            }
            save_json(metadata_file, metadata_info)
            checkpoint[key] = True
            save_json(checkpoint_file, checkpoint)
        else:
            logger.error(f"下载失败：{real_company_name}（{code}）IPO - {msg}")
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
    import argparse
    
    p = argparse.ArgumentParser(description="CNINFO IPO招股说明书抓取工具")
    p.add_argument("--input", required=True, help="输入 CSV（code,name）")
    p.add_argument("--out", required=True, help="输出根目录")
    p.add_argument("--fail", required=True, help="失败记录 CSV")
    p.add_argument("--workers", type=int, default=0, help="并行进程数（0=顺序模式，推荐 4-8）")
    p.add_argument("--watch-log", action="store_true", help="实时滚动显示 error.log（已废弃）")
    p.add_argument("--debug", action="store_true", help="调试模式（输出更多日志）")
    args = p.parse_args()

    # 多进程模式 or 顺序模式
    if args.workers > 0:
        if args.watch_log:
            print("⚠️  多进程模式下不支持 --watch-log，已忽略")
        run_ipo_multiprocessing(args.input, args.out, args.fail, workers=args.workers, debug=args.debug)
    else:
        run_ipo(args.input, args.out, args.fail, watch_log=args.watch_log, debug=args.debug)
