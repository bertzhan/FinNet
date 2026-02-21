# -*- coding: utf-8 -*-
"""
任务处理器模块
包含定期报告和IPO招股说明书的完整任务处理逻辑
"""

# 使用延迟导入避免 RuntimeWarning（当使用 python -m 运行时）
# 这些函数在需要时才会被导入，避免模块被提前加载到 sys.modules

__all__ = [
    'process_single_task',
    'run_multiprocessing',
    'run',
    'process_single_ipo_task',
    'run_ipo_multiprocessing',
    'run_ipo',
]


def __getattr__(name):
    """延迟导入函数（Python 3.7+）"""
    if name == 'process_single_task':
        from .report_processor import process_single_task
        return process_single_task
    elif name == 'run_multiprocessing':
        from .report_processor import run_multiprocessing
        return run_multiprocessing
    elif name == 'run':
        from .report_processor import run
        return run
    elif name == 'process_single_ipo_task':
        from .ipo_processor import process_single_ipo_task
        return process_single_ipo_task
    elif name == 'run_ipo_multiprocessing':
        from .ipo_processor import run_ipo_multiprocessing
        return run_ipo_multiprocessing
    elif name == 'run_ipo':
        from .ipo_processor import run_ipo
        return run_ipo
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
