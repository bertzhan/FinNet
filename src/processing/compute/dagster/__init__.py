# -*- coding: utf-8 -*-
"""
Dagster 调度模块
统一导出所有 Jobs、Schedules、Sensors 和 Assets

使用 Definitions 对象来管理所有定义，这是 Dagster 推荐的方式
注：本模块现在包含 Software-Defined Assets 以支持完整的数据血缘追踪
"""

from dagster import Definitions

from .jobs import (
    crawl_a_share_reports_job,
    crawl_a_share_ipo_job,
    parse_pdf_job,
    chunk_documents_job,
    vectorize_documents_job,
    build_graph_job,
    elasticsearch_index_job,
    update_listed_companies_job,
    daily_crawl_reports_schedule,
    daily_crawl_ipo_schedule,
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
    manual_trigger_reports_sensor,
    manual_trigger_ipo_sensor,
    manual_trigger_parse_sensor,
    manual_trigger_chunk_sensor,
    manual_trigger_vectorize_sensor,
    manual_trigger_graph_sensor,
    manual_trigger_elasticsearch_sensor,
    manual_trigger_companies_sensor,
)

# 导入 Software-Defined Assets（数据血缘）
from .assets import all_assets

# 创建 Definitions 对象（Dagster 1.5+ 推荐方式）
# 这允许模块中有多个 Jobs、Schedules、Sensors 和 Assets
jobs_list = [
    crawl_a_share_reports_job,
    crawl_a_share_ipo_job,
    parse_pdf_job,
    chunk_documents_job,
    vectorize_documents_job,
    build_graph_job,
    elasticsearch_index_job,
    update_listed_companies_job,
]

schedules_list = [
    daily_crawl_reports_schedule,
    daily_crawl_ipo_schedule,
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
    manual_trigger_reports_sensor,
    manual_trigger_ipo_sensor,
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
    # Jobs
    "crawl_a_share_reports_job",
    "crawl_a_share_ipo_job",
    "parse_pdf_job",
    "chunk_documents_job",
    "vectorize_documents_job",
    "build_graph_job",
    "elasticsearch_index_job",
    "update_listed_companies_job",
    # Schedules
    "daily_crawl_reports_schedule",
    "daily_crawl_ipo_schedule",
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
    # Sensors
    "manual_trigger_reports_sensor",
    "manual_trigger_ipo_sensor",
    "manual_trigger_parse_sensor",
    "manual_trigger_chunk_sensor",
    "manual_trigger_vectorize_sensor",
    "manual_trigger_graph_sensor",
    "manual_trigger_elasticsearch_sensor",
    "manual_trigger_companies_sensor",
    # Assets（数据血缘）
    "all_assets",
]
