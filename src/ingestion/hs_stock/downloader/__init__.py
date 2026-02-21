# -*- coding: utf-8 -*-
"""
下载器模块
包含纯粹的下载功能（PDF和HTML）
任务处理器已移至 processor/ 目录
"""

from .pdf_downloader import PDFDownloader, download_pdf_resilient
from .html_downloader import HTMLDownloader, download_html_resilient

__all__ = [
    'PDFDownloader', 'download_pdf_resilient',
    'HTMLDownloader', 'download_html_resilient',
]
