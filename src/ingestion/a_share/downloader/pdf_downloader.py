# -*- coding: utf-8 -*-
"""
PDF 下载器
"""

import os
import time
import logging
from typing import Optional, Callable, Tuple

import requests
from requests.exceptions import RequestException

from ..config import PROXIES, RETRY_STATUS, RETRY_BACKOFF
from ..utils.file_utils import ensure_dir

logger = logging.getLogger(__name__)


def download_pdf_resilient(
    session: requests.Session,
    url: str,
    path: str,
    referer: Optional[str] = None,
    refresh_fn: Optional[Callable[[], Tuple[Optional[str], Optional[str]]]] = None,
    max_retries: int = 3
) -> Tuple[bool, str]:
    """
    带重试机制的PDF下载
    
    Args:
        session: requests会话
        url: PDF URL
        path: 保存路径
        referer: Referer头（可选）
        refresh_fn: 刷新URL的函数（404时调用，返回 (new_url, new_referer)）
        max_retries: 最大重试次数
        
    Returns:
        (是否成功, 错误信息)
    """
    cur_url, cur_ref = url, referer
    last_err = None
    
    for attempt in range(1, max_retries + 1):
        try:
            headers = {"Referer": cur_ref} if cur_ref else {}
            r = session.get(cur_url, timeout=20, stream=True, proxies=PROXIES, headers=headers)
            
            if r.status_code == 404 and refresh_fn:
                new_url, new_ref = refresh_fn()
                if new_url and new_url != cur_url:
                    logger.warning(f"404 刷新链接：\nold={cur_url}\nnew={new_url}")
                    cur_url, cur_ref = new_url, (new_ref or cur_ref)
                    continue
            
            if r.status_code in RETRY_STATUS:
                time.sleep(RETRY_BACKOFF)
                continue
            
            if r.status_code >= 400:
                last_err = f"HTTP {r.status_code}"
                time.sleep(RETRY_BACKOFF)
                continue

            # 验证PDF内容
            head = r.raw.read(5)
            r.raw.decode_content = True
            if not head.startswith(b"%PDF-"):
                return False, "非PDF内容"
            
            # 保存文件
            ensure_dir(os.path.dirname(path))
            with open(path, "wb") as f:
                f.write(head or b"")
                for chunk in r.iter_content(8192):
                    if chunk:
                        f.write(chunk)
            
            return True, "ok"
            
        except RequestException as e:
            last_err = str(e)
            time.sleep(RETRY_BACKOFF)
    
    return False, last_err or "HTTP 4xx/5xx"


class PDFDownloader:
    """
    PDF 下载器类
    """
    
    def __init__(self, session: requests.Session):
        """
        Args:
            session: requests会话
        """
        self.session = session
    
    def download(
        self,
        url: str,
        path: str,
        referer: Optional[str] = None,
        refresh_fn: Optional[Callable[[], Tuple[Optional[str], Optional[str]]]] = None,
        max_retries: int = 3
    ) -> Tuple[bool, str]:
        """
        下载PDF文件
        
        Args:
            url: PDF URL
            path: 保存路径
            referer: Referer头（可选）
            refresh_fn: 刷新URL的函数（404时调用）
            max_retries: 最大重试次数
            
        Returns:
            (是否成功, 错误信息)
        """
        return download_pdf_resilient(
            self.session, url, path, referer, refresh_fn, max_retries
        )
