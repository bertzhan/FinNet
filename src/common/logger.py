# -*- coding: utf-8 -*-
"""
日志工具
提供统一的日志记录接口，支持结构化日志
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

from .config import common_config


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""

    # ANSI 颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
    }
    RESET = '\033[0m'

    def format(self, record):
        # 添加颜色
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"

        return super().format(record)


def setup_logger(
    name: str,
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_console: bool = True,
) -> logging.Logger:
    """
    创建日志记录器

    Args:
        name: 日志记录器名称
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径（可选）
        enable_console: 是否启用控制台输出

    Returns:
        日志记录器实例
    """
    logger = logging.getLogger(name)

    # 设置日志级别
    log_level = level or common_config.LOG_LEVEL
    logger.setLevel(getattr(logging, log_level.upper()))

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 日志格式
    log_format = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # 控制台 handler（彩色）
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_formatter = ColoredFormatter(log_format, datefmt=date_format)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    # 文件 handler（无色）
    if log_file:
        # 确保日志目录存在
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(log_format, datefmt=date_format)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # 防止日志传播到父 logger
    logger.propagate = False

    return logger


def get_logger(name: str, **kwargs) -> logging.Logger:
    """
    获取日志记录器（便捷方法）

    Args:
        name: 日志记录器名称（通常使用 __name__）
        **kwargs: 其他参数传递给 setup_logger

    Returns:
        日志记录器实例

    Example:
        from src.common.logger import get_logger
        logger = get_logger(__name__)
        logger.info("This is a log message")
    """
    return setup_logger(name, **kwargs)


# 创建默认日志目录
DEFAULT_LOG_DIR = Path(common_config.PROJECT_ROOT) / "logs"
DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)


class LoggerMixin:
    """日志 Mixin 类，为其他类提供日志功能"""

    @property
    def logger(self) -> logging.Logger:
        """返回当前类的日志记录器"""
        if not hasattr(self, '_logger'):
            self._logger = get_logger(self.__class__.__name__)
        return self._logger


# 模块级别日志记录器
module_logger = get_logger(__name__)
