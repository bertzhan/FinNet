# -*- coding: utf-8 -*-
"""
A-share crawler module
Provides CNINFO crawler implementation
"""

from .crawlers import ReportCrawler, CninfoIPOProspectusCrawler

# 向后兼容：保留旧名称
CninfoAShareCrawler = ReportCrawler

# 导出主要类和函数（向后兼容）
# 使用延迟导入避免 RuntimeWarning
def _lazy_import_processor_functions():
    """延迟导入处理器函数"""
    from .processor.report_processor import process_single_task, run_multiprocessing, run
    from .processor.ipo_processor import process_single_ipo_task, run_ipo_multiprocessing, run_ipo
    return {
        'process_single_task': process_single_task,
        'run_multiprocessing': run_multiprocessing,
        'run': run,
        'process_single_ipo_task': process_single_ipo_task,
        'run_ipo_multiprocessing': run_ipo_multiprocessing,
        'run_ipo': run_ipo,
    }

# 为了向后兼容，仍然导出这些函数名
# 但使用延迟导入避免模块提前加载
def __getattr__(name):
    """延迟导入函数（Python 3.7+）"""
    processor_funcs = [
        'process_single_task', 'run_multiprocessing', 'run',
        'process_single_ipo_task', 'run_ipo_multiprocessing', 'run_ipo'
    ]
    if name in processor_funcs:
        funcs = _lazy_import_processor_functions()
        return funcs[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# 为了向后兼容，仍然在 __all__ 中声明
# 实际导入会在首次访问时进行
from .utils.file_utils import build_existing_pdf_cache
from .api.orgid_resolver import OrgIDResolver, build_orgid, get_orgid
from .api.client import CNInfoAPIClient, fetch_anns_by_category, fetch_anns, pick_latest
from .api.ipo_client import IPOAPIClient, fetch_ipo_announcements, pick_latest_ipo

__all__ = [
    'ReportCrawler',
    'CninfoAShareCrawler',  # 向后兼容
    'CninfoIPOProspectusCrawler',
    # 向后兼容导出
    'process_single_task',
    'run_multiprocessing',
    'run',
    'process_single_ipo_task',
    'run_ipo_multiprocessing',
    'run_ipo',
    'build_existing_pdf_cache',
    'OrgIDResolver',
    'build_orgid',
    'get_orgid',
    'CNInfoAPIClient',
    'fetch_anns_by_category',
    'fetch_anns',
    'pick_latest',
    'IPOAPIClient',
    'fetch_ipo_announcements',
    'pick_latest_ipo',
]
