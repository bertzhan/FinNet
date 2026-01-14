# -*- coding: utf-8 -*-
"""
Dagster 调度模块
统一导出所有 Jobs、Schedules 和 Sensors

使用 Definitions 对象来管理所有定义，这是 Dagster 推荐的方式
"""

from dagster import Definitions

from .jobs import (
    crawl_a_share_reports_job,
    crawl_a_share_ipo_job,
    daily_crawl_reports_schedule,
    daily_crawl_ipo_schedule,
    manual_trigger_reports_sensor,
    manual_trigger_ipo_sensor,
)

# 创建 Definitions 对象（Dagster 1.5+ 推荐方式）
# 这允许模块中有多个 Jobs、Schedules 和 Sensors
defs = Definitions(
    jobs=[
        crawl_a_share_reports_job,
        crawl_a_share_ipo_job,
    ],
    schedules=[
        daily_crawl_reports_schedule,
        daily_crawl_ipo_schedule,
    ],
    sensors=[
        manual_trigger_reports_sensor,
        manual_trigger_ipo_sensor,
    ],
)

# 为了向后兼容，仍然导出单个对象
__all__ = [
    "defs",  # Definitions 对象（Dagster UI 会使用这个）
    "crawl_a_share_reports_job",
    "crawl_a_share_ipo_job",
    "daily_crawl_reports_schedule",
    "daily_crawl_ipo_schedule",
    "manual_trigger_reports_sensor",
    "manual_trigger_ipo_sensor",
]
