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
            # 使用 (connect_timeout, read_timeout) 元组，读取超时设置更长以支持大文件
            r = session.get(cur_url, timeout=(10, 300), stream=True, proxies=PROXIES, headers=headers)
            
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
            
            # 保存文件（带超时保护）
            ensure_dir(os.path.dirname(path))
            try:
                bytes_written = 0
                with open(path, "wb") as f:
                    f.write(head or b"")
                    bytes_written += len(head or b"")
                    for chunk in r.iter_content(8192):
                        if chunk:
                            f.write(chunk)
                            bytes_written += len(chunk)
                logger.debug(f"文件写入完成: {path}, 共 {bytes_written} bytes")
            except Exception as write_err:
                # 写入过程中出错（网络中断等），删除不完整的文件
                logger.warning(f"文件写入过程中出错: {write_err}, 删除不完整文件: {path}")
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except:
                        pass
                last_err = f"文件写入失败: {write_err}"
                time.sleep(RETRY_BACKOFF)
                continue
            
            # 验证文件完整性
            try:
                file_size = os.path.getsize(path)
                
                # 1. 检查文件大小是否合理（至少 1KB）
                if file_size < 1024:
                    logger.warning(f"文件太小（{file_size} bytes），可能下载不完整: {path}")
                    os.remove(path)  # 删除不完整的文件
                    last_err = f"文件太小（{file_size} bytes），可能下载不完整"
                    time.sleep(RETRY_BACKOFF)
                    continue
                
                # 2. 检查 Content-Length（如果存在）
                if 'Content-Length' in r.headers:
                    expected_size = int(r.headers['Content-Length'])
                    if file_size != expected_size:
                        logger.warning(
                            f"文件大小不匹配：期望 {expected_size} bytes，实际 {file_size} bytes: {path}"
                        )
                        os.remove(path)  # 删除不完整的文件
                        last_err = f"文件大小不匹配：期望 {expected_size} bytes，实际 {file_size} bytes"
                        time.sleep(RETRY_BACKOFF)
                        continue
                
                # 3. 验证 PDF 文件完整性（检查是否以 %%EOF 结尾）
                try:
                    with open(path, 'rb') as f:
                        # 读取最后 1KB 来查找 %%EOF
                        f.seek(max(0, file_size - 1024), os.SEEK_SET)
                        tail = f.read()
                        if b'%%EOF' not in tail:
                            logger.warning(f"PDF 文件不完整（缺少 %%EOF 标记）: {path}")
                            os.remove(path)  # 删除不完整的文件
                            last_err = "PDF 文件不完整（缺少 %%EOF 标记）"
                            time.sleep(RETRY_BACKOFF)
                            continue
                except Exception as e:
                    logger.warning(f"PDF 完整性验证失败: {e}, 文件: {path}")
                    os.remove(path)  # 删除可能损坏的文件
                    last_err = f"PDF 完整性验证失败: {e}"
                    time.sleep(RETRY_BACKOFF)
                    continue
                
                # 所有验证通过
                logger.debug(f"文件下载完成并验证通过: {path} ({file_size} bytes)")
                return True, "ok"
                
            except Exception as e:
                logger.error(f"文件完整性验证异常: {e}, 文件: {path}")
                if os.path.exists(path):
                    try:
                        os.remove(path)  # 删除可能损坏的文件
                    except:
                        pass
                last_err = f"文件完整性验证异常: {e}"
                time.sleep(RETRY_BACKOFF)
                continue
            
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
