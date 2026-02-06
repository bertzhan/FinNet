# -*- coding: utf-8 -*-
"""
自适应限流器
线程安全的动态请求限流器，用于控制请求频率
"""

import threading
import time


class AdaptiveRateLimiter:
    """
    线程安全的自适应限流器，用于动态控制请求节奏。
    
    特点：
    - 请求成功时逐步放宽限流
    - 请求失败时适度降低速率
    - 被限流时显著降低速率
    """

    def __init__(
        self,
        base_interval: float = 0.2,
        max_interval: float = 10.0,
        increase_factor: float = 1.5,
        heavy_increase_factor: float = 2.5,
        decrease_factor: float = 0.85,
    ):
        """
        Args:
            base_interval: 基础请求间隔（秒）
            max_interval: 最大请求间隔（秒）
            increase_factor: 一般错误时的间隔增长因子
            heavy_increase_factor: 被限流时的间隔增长因子
            decrease_factor: 成功时的间隔缩减因子
        """
        self.base_interval = max(0.01, base_interval)
        self.interval = self.base_interval
        self.max_interval = max_interval
        self.increase_factor = increase_factor
        self.heavy_increase_factor = heavy_increase_factor
        self.decrease_factor = decrease_factor
        self.lock = threading.Lock()
        self.last_request = 0.0

    def acquire(self) -> None:
        """在发起请求前调用，确保请求之间的间隔满足当前速率。"""
        with self.lock:
            now = time.time()
            wait_time = max(0.0, self.last_request + self.interval - now)
        if wait_time > 0:
            time.sleep(wait_time)
        with self.lock:
            self.last_request = time.time()

    def on_success(self) -> None:
        """请求成功后轻微放宽速率。"""
        with self.lock:
            self.interval = max(self.base_interval, self.interval * self.decrease_factor)

    def on_error(self) -> None:
        """请求一般性失败后适度降低速率。"""
        with self.lock:
            self.interval = min(self.max_interval, self.interval * self.increase_factor)

    def on_throttle(self) -> None:
        """被限流或服务器拒绝时显著降低速率。"""
        with self.lock:
            self.interval = min(self.max_interval, self.interval * self.heavy_increase_factor)

    def update_base_interval(self, new_base: float) -> None:
        """根据并发度调整基础间隔。"""
        with self.lock:
            self.base_interval = max(0.01, new_base)
            self.interval = max(self.interval, self.base_interval)
    
    @property
    def current_interval(self) -> float:
        """获取当前请求间隔。"""
        with self.lock:
            return self.interval
