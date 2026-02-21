# -*- coding: utf-8 -*-
"""
HTML 下载器
支持HTML格式文档的下载和转换
"""

import os
import re
import time
import logging
from typing import Optional, Tuple

import requests
from requests.exceptions import RequestException
from bs4 import BeautifulSoup

from ..config import PROXIES, RETRY_STATUS, RETRY_BACKOFF
from ..utils.file_utils import ensure_dir

logger = logging.getLogger(__name__)


def html_to_text(html_content: str) -> str:
    """
    将HTML内容转换为纯文本
    提取主要内容，去除HTML标签和样式
    优化中文显示和格式
    
    Args:
        html_content: HTML内容
        
    Returns:
        纯文本内容
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
        logger.warning(f"HTML转文本失败: {e}")
        return html_content


def download_html_resilient(
    session: requests.Session,
    url: str,
    path: str,
    referer: Optional[str] = None,
    max_retries: int = 3,
    convert_to_text: bool = True
) -> Tuple[bool, str]:
    """
    下载HTML格式的公告并保存
    convert_to_text: 是否同时保存纯文本版本
    支持中文编码自动检测（GB2312/GBK/UTF-8）
    
    Args:
        session: requests会话
        url: HTML URL
        path: 保存路径
        referer: Referer头（可选）
        max_retries: 最大重试次数
        convert_to_text: 是否转换为文本格式
        
    Returns:
        (是否成功, 错误信息)
    """
    last_err = None
    
    for attempt in range(1, max_retries + 1):
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

            # 智能检测中文编码（改进版）
            html_text = None
            detected_encoding = None
            
            # 方法1: 尝试从HTML meta标签中提取编码
            try:
                # 先尝试用UTF-8解码，查看meta标签
                temp_text = r.content.decode('utf-8', errors='ignore')
                meta_match = re.search(
                    r'<meta\s+[^>]*(?:charset|content\s*=\s*["\']?[^"\']*charset\s*=\s*)([^"\'>\s]+)',
                    temp_text,
                    re.IGNORECASE
                )
                if meta_match:
                    detected_encoding = meta_match.group(1).lower()
                    # 尝试用检测到的编码重新解码
                    if detected_encoding in ['gb2312', 'gbk', 'gb18030', 'utf-8']:
                        html_text = r.content.decode(detected_encoding)
            except:
                pass
            
            # 方法2: 如果方法1失败，使用requests的编码检测
            if html_text is None:
                detected_encoding = r.encoding
                if r.apparent_encoding:
                    detected_encoding = r.apparent_encoding
                
                if detected_encoding:
                    try:
                        html_text = r.content.decode(detected_encoding)
                    except:
                        html_text = None
            
            # 方法3: 尝试常见的中文编码（GB2312, GBK, GB18030, UTF-8）
            if html_text is None:
                encodings_to_try = ['gb2312', 'gbk', 'gb18030', 'utf-8']
                for enc in encodings_to_try:
                    try:
                        html_text = r.content.decode(enc)
                        detected_encoding = enc
                        logger.debug(f"成功使用编码 {enc} 解码HTML")
                        break
                    except (UnicodeDecodeError, LookupError):
                        continue
            
            # 方法4: 最后尝试使用chardet（如果可用）
            if html_text is None:
                try:
                    import chardet
                    detected = chardet.detect(r.content)
                    if detected and detected.get('encoding'):
                        enc = detected['encoding'].lower()
                        if enc in ['gb2312', 'gbk', 'gb18030', 'utf-8', 'utf-8-sig']:
                            html_text = r.content.decode(enc, errors='ignore')
                            detected_encoding = enc
                            logger.debug(f"使用chardet检测到的编码 {enc}")
                except ImportError:
                    pass
                except Exception as e:
                    logger.debug(f"chardet检测失败: {e}")
            
            # 方法5: 如果所有方法都失败，使用UTF-8并忽略错误
            if html_text is None:
                html_text = r.content.decode('utf-8', errors='ignore')
                detected_encoding = 'utf-8'
                logger.warning(f"无法确定编码，使用UTF-8（可能包含乱码）")
            
            # 记录检测到的编码
            if detected_encoding:
                logger.debug(f"检测到HTML编码: {detected_encoding}")

            # 修复HTML编码声明，确保与实际编码一致
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
                logger.info(f"已转换为文本格式: {os.path.basename(text_path)}")

            return True, "ok"
            
        except RequestException as e:
            last_err = str(e)
            time.sleep(RETRY_BACKOFF)
        except Exception as e:
            last_err = str(e)
            time.sleep(RETRY_BACKOFF)

    return False, last_err or "HTTP 4xx/5xx"


def download_html_from_detail_page(
    session: requests.Session,
    detail_url: str,
    path: str,
    code: str,
    max_retries: int = 3
) -> Tuple[bool, str]:
    """
    从公告详情页提取HTML内容
    
    CNINFO的公告详情页可能包含实际的HTML文档内容，或者包含指向HTML文档的链接
    
    Args:
        session: requests会话
        detail_url: 公告详情页URL
        path: 保存路径
        code: 股票代码（用于日志）
        
    Returns:
        (是否成功, 错误信息)
    """
    from ..config import PROXIES, RETRY_STATUS, RETRY_BACKOFF
    
    last_err = None
    
    for attempt in range(1, max_retries + 1):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.cninfo.com.cn/"
            }
            r = session.get(detail_url, timeout=20, proxies=PROXIES, headers=headers)
            
            if r.status_code in RETRY_STATUS:
                time.sleep(RETRY_BACKOFF)
                continue
            
            if r.status_code >= 400:
                last_err = f"HTTP {r.status_code}"
                time.sleep(RETRY_BACKOFF)
                continue
            
            # 解析HTML页面，查找实际的文档链接或内容
            # 先检测编码
            html_content = None
            try:
                # 尝试多种编码
                for enc in ['utf-8', 'gb2312', 'gbk', 'gb18030']:
                    try:
                        html_content = r.content.decode(enc)
                        break
                    except:
                        continue
                if html_content is None:
                    html_content = r.content.decode('utf-8', errors='ignore')
            except:
                html_content = r.text
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 方法1: 查找iframe中的文档
            iframe = soup.find('iframe', {'id': 'detail'}) or soup.find('iframe', {'name': 'content'})
            if iframe and iframe.get('src'):
                iframe_url = iframe.get('src')
                # 如果是相对路径，转换为绝对路径
                if not iframe_url.startswith('http'):
                    from urllib.parse import urljoin
                    iframe_url = urljoin(detail_url, iframe_url)
                
                logger.info(f"[{code}] 找到iframe文档链接: {iframe_url}")
                # 尝试下载iframe中的内容
                return download_html_resilient(session, iframe_url, path, referer=detail_url, max_retries=2)
            
            # 方法2: 查找直接嵌入的HTML内容
            content_div = soup.find('div', {'id': 'content'}) or soup.find('div', {'class': 'detail-content'})
            if content_div:
                # 获取完整的HTML文档结构
                html_content = str(content_div)
                
                # 构建完整的HTML文档
                full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>IPO招股说明书</title>
</head>
<body>
{html_content}
</body>
</html>"""
                
                # 保存提取的内容
                ensure_dir(os.path.dirname(path))
                with open(path, "w", encoding="utf-8") as f:
                    f.write(full_html)
                
                # 转换为文本
                text_content = html_to_text(full_html)
                text_path = path.replace('.html', '.txt').replace('.htm', '.txt')
                with open(text_path, "w", encoding="utf-8") as f:
                    f.write(text_content)
                
                logger.info(f"[{code}] 从详情页提取HTML内容成功")
                return True, "ok"
            
            # 方法3: 查找文档下载链接
            download_links = soup.find_all('a', href=True)
            for link in download_links:
                href = link.get('href', '')
                if href and ('.html' in href.lower() or '.htm' in href.lower()):
                    if not href.startswith('http'):
                        from urllib.parse import urljoin
                        href = urljoin(detail_url, href)
                    
                    logger.info(f"[{code}] 找到文档下载链接: {href}")
                    return download_html_resilient(session, href, path, referer=detail_url, max_retries=2)
            
            last_err = "未找到HTML文档内容或链接"
            break
            
        except RequestException as e:
            last_err = str(e)
            time.sleep(RETRY_BACKOFF)
        except Exception as e:
            last_err = str(e)
            logger.warning(f"[{code}] 解析详情页异常: {e}")
            time.sleep(RETRY_BACKOFF)
    
    return False, last_err or "无法从详情页获取HTML"


class HTMLDownloader:
    """
    HTML 下载器类
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
        max_retries: int = 3,
        convert_to_text: bool = True
    ) -> Tuple[bool, str]:
        """
        下载HTML文件
        
        Args:
            url: HTML URL
            path: 保存路径
            referer: Referer头（可选）
            max_retries: 最大重试次数
            convert_to_text: 是否转换为文本格式
            
        Returns:
            (是否成功, 错误信息)
        """
        return download_html_resilient(
            self.session, url, path, referer, max_retries, convert_to_text
        )
