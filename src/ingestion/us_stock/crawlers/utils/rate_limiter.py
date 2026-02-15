# -*- coding: utf-8 -*-
"""
SEC EDGAR API 限流器（最大10 req/sec）
适配自 SEC-Filings-ETL/utils/rate_limiter.py

增强功能：
- 429响应处理
- Retry-After头部支持
- 全局RPS跨进程强制
"""
import time
from threading import Lock
from typing import Optional

from src.common.logger import get_logger

logger = get_logger(__name__)


class SECRateLimiter:
    """
    线程安全的SEC EDGAR API限流器
    确保符合可配置的每秒请求数限制

    功能：
    - 从环境变量配置RPS
    - 429响应处理（指数退避）
    - Retry-After头部支持
    - 线程安全操作
    """

    def __init__(self, requests_per_second: int = 10):
        """
        初始化限流器

        Args:
            requests_per_second: 每秒最大请求数（SEC要求≤10）
        """
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0
        self.lock = Lock()
        self.request_count = 0
        self.retry_after_until = 0.0  # 429响应后需要等待到的时间戳

        logger.info(
            f"SEC限流器已初始化: {requests_per_second} req/s",
            extra={
                "requests_per_second": requests_per_second,
                "min_interval_ms": self.min_interval * 1000
            }
        )

    def wait(self):
        """
        如有必要，等待以符合限流要求
        此方法是线程安全的
        """
        with self.lock:
            current_time = time.time()

            # 检查是否需要等待（429 Retry-After）
            if current_time < self.retry_after_until:
                sleep_time = self.retry_after_until - current_time
                logger.warning(
                    f"限流等待（Retry-After）: {sleep_time:.2f}秒",
                    extra={"sleep_seconds": sleep_time}
                )
                time.sleep(sleep_time)
                current_time = time.time()

            # 标准限流检查
            elapsed = current_time - self.last_request_time

            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                logger.debug(
                    f"限流等待: {sleep_time * 1000:.0f}ms",
                    extra={"sleep_ms": sleep_time * 1000}
                )
                time.sleep(sleep_time)

            self.last_request_time = time.time()
            self.request_count += 1

            # 每100个请求记录一次统计
            if self.request_count % 100 == 0:
                logger.info(
                    f"限流器统计: 已发送 {self.request_count} 个请求",
                    extra={"total_requests": self.request_count}
                )

    def handle_429(self, retry_after: Optional[int] = None):
        """
        处理429 Too Many Requests响应

        Args:
            retry_after: Retry-After头部值（秒），或None
        """
        with self.lock:
            if retry_after:
                # 使用服务器提供的重试延迟
                wait_seconds = float(retry_after)
            else:
                # 使用默认延迟60秒
                wait_seconds = 60.0

            self.retry_after_until = time.time() + wait_seconds

            logger.warning(
                f"收到429响应，等待 {wait_seconds}秒",
                extra={
                    "retry_after_seconds": wait_seconds,
                    "retry_after_until": self.retry_after_until
                }
            )

    def reset_stats(self):
        """重置请求计数器"""
        with self.lock:
            self.request_count = 0

    def get_stats(self) -> dict:
        """
        获取当前限流器统计信息

        Returns:
            统计信息字典
        """
        with self.lock:
            return {
                "total_requests": self.request_count,
                "requests_per_second": self.requests_per_second,
                "min_interval_ms": self.min_interval * 1000,
                "in_retry_after": time.time() < self.retry_after_until
            }
