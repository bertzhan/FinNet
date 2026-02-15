# -*- coding: utf-8 -*-
"""
Dagster 调度模块
统一导出所有 Jobs、Schedules、Sensors 和 Assets

使用 Definitions 对象来管理所有定义，这是 Dagster 推荐的方式
注：本模块现在包含 Software-Defined Assets 以支持完整的数据血缘追踪
"""

from dagster import Definitions

from .jobs import (
    # A股 Jobs
    crawl_a_share_reports_job,
    crawl_a_share_ipo_job,
    # 港股 Jobs
    update_hk_companies_job,
    crawl_hk_reports_job,
    # 其他 Jobs
    parse_pdf_job,
    chunk_documents_job,
    vectorize_documents_job,
    build_graph_job,
    elasticsearch_index_job,
    update_listed_companies_job,
    # A股 Schedules
    daily_crawl_reports_schedule,
    daily_crawl_ipo_schedule,
    # 港股 Schedules
    weekly_update_hk_companies_schedule,
    daily_crawl_hk_reports_schedule,
    # 其他 Schedules
    hourly_parse_schedule,
    daily_parse_schedule,
    hourly_chunk_schedule,
    daily_chunk_schedule,
    hourly_vectorize_schedule,
    daily_vectorize_schedule,
    hourly_graph_schedule,
    daily_graph_schedule,
    hourly_elasticsearch_schedule,
    daily_elasticsearch_schedule,
    daily_update_companies_schedule,
    # A股 Sensors
    manual_trigger_reports_sensor,
    manual_trigger_ipo_sensor,
    # 港股 Sensors
    manual_trigger_update_hk_companies_sensor,
    manual_trigger_hk_reports_sensor,
    # 其他 Sensors
    manual_trigger_parse_sensor,
    manual_trigger_chunk_sensor,
    manual_trigger_vectorize_sensor,
    manual_trigger_graph_sensor,
    manual_trigger_elasticsearch_sensor,
    manual_trigger_companies_sensor,
)

# 导入美股 Jobs、Schedules、Sensors
from src.ingestion.us_stock.dagster_assets import (
    update_us_companies_job_dagster,
    crawl_us_reports_job,
    weekly_update_us_companies_schedule,
    weekly_crawl_us_reports_schedule,
    manual_trigger_update_us_companies_sensor,
    manual_trigger_crawl_us_reports_sensor,
)

# 导入 Software-Defined Assets（数据血缘）
from .assets import all_assets

# 创建 Definitions 对象（Dagster 1.5+ 推荐方式）
# 这允许模块中有多个 Jobs、Schedules、Sensors 和 Assets
jobs_list = [
    # A股
    crawl_a_share_reports_job,
    crawl_a_share_ipo_job,
    # 港股
    update_hk_companies_job,
    crawl_hk_reports_job,
    # 美股
    update_us_companies_job_dagster,
    crawl_us_reports_job,
    # 其他
    parse_pdf_job,
    chunk_documents_job,
    vectorize_documents_job,
    build_graph_job,
    elasticsearch_index_job,
    update_listed_companies_job,
]

schedules_list = [
    # A股
    daily_crawl_reports_schedule,
    daily_crawl_ipo_schedule,
    # 港股
    weekly_update_hk_companies_schedule,
    daily_crawl_hk_reports_schedule,
    # 美股
    weekly_update_us_companies_schedule,
    weekly_crawl_us_reports_schedule,
    # 其他
    hourly_parse_schedule,
    daily_parse_schedule,
    hourly_chunk_schedule,
    daily_chunk_schedule,
    hourly_vectorize_schedule,
    daily_vectorize_schedule,
    hourly_graph_schedule,
    daily_graph_schedule,
    hourly_elasticsearch_schedule,
    daily_elasticsearch_schedule,
    daily_update_companies_schedule,
]

sensors_list = [
    # A股
    manual_trigger_reports_sensor,
    manual_trigger_ipo_sensor,
    # 港股
    manual_trigger_update_hk_companies_sensor,
    manual_trigger_hk_reports_sensor,
    # 美股
    manual_trigger_update_us_companies_sensor,
    manual_trigger_crawl_us_reports_sensor,
    # 其他
    manual_trigger_parse_sensor,
    manual_trigger_chunk_sensor,
    manual_trigger_vectorize_sensor,
    manual_trigger_graph_sensor,
    manual_trigger_elasticsearch_sensor,
    manual_trigger_companies_sensor,
]

# 创建 Definitions 对象，包含 Jobs、Schedules、Sensors 和 Assets
# Assets 用于建立完整的数据血缘追踪
defs = Definitions(
    jobs=jobs_list,
    schedules=schedules_list,
    sensors=sensors_list,
    assets=all_assets,  # Software-Defined Assets 支持 Lineage
)

# 为了向后兼容，仍然导出单个对象
__all__ = [
    "defs",  # Definitions 对象（Dagster UI 会使用这个）
    # A股 Jobs
    "crawl_a_share_reports_job",
    "crawl_a_share_ipo_job",
    # 港股 Jobs
    "update_hk_companies_job",
    "crawl_hk_reports_job",
    # 美股 Jobs
    "update_us_companies_job_dagster",
    "crawl_us_reports_job",
    # 其他 Jobs
    "parse_pdf_job",
    "chunk_documents_job",
    "vectorize_documents_job",
    "build_graph_job",
    "elasticsearch_index_job",
    "update_listed_companies_job",
    # A股 Schedules
    "daily_crawl_reports_schedule",
    "daily_crawl_ipo_schedule",
    # 港股 Schedules
    "weekly_update_hk_companies_schedule",
    "daily_crawl_hk_reports_schedule",
    # 美股 Schedules
    "weekly_update_us_companies_schedule",
    "weekly_crawl_us_reports_schedule",
    # 其他 Schedules
    "hourly_parse_schedule",
    "daily_parse_schedule",
    "hourly_chunk_schedule",
    "daily_chunk_schedule",
    "hourly_vectorize_schedule",
    "daily_vectorize_schedule",
    "hourly_graph_schedule",
    "daily_graph_schedule",
    "hourly_elasticsearch_schedule",
    "daily_elasticsearch_schedule",
    "daily_update_companies_schedule",
    # A股 Sensors
    "manual_trigger_reports_sensor",
    "manual_trigger_ipo_sensor",
    # 港股 Sensors
    "manual_trigger_update_hk_companies_sensor",
    "manual_trigger_hk_reports_sensor",
    # 美股 Sensors
    "manual_trigger_update_us_companies_sensor",
    "manual_trigger_crawl_us_reports_sensor",
    # 其他 Sensors
    "manual_trigger_parse_sensor",
    "manual_trigger_chunk_sensor",
    "manual_trigger_vectorize_sensor",
    "manual_trigger_graph_sensor",
    "manual_trigger_elasticsearch_sensor",
    "manual_trigger_companies_sensor",
    # Assets（数据血缘）
    "all_assets",
]
