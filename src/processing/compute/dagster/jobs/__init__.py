# -*- coding: utf-8 -*-
"""
Dagster Jobs 模块
导出所有爬虫相关的 Jobs、Schedules 和 Sensors
"""

from .crawl_jobs import (
    # Jobs
    crawl_a_share_reports_job,
    crawl_a_share_ipo_job,
    
    # Ops
    crawl_a_share_reports_op,
    crawl_a_share_ipo_op,
    validate_crawl_results_op,
    
    # Schedules
    daily_crawl_reports_schedule,
    daily_crawl_ipo_schedule,
    
    # Sensors
    manual_trigger_reports_sensor,
    manual_trigger_ipo_sensor,
)

from .parse_jobs import (
    # Jobs
    parse_pdf_job,
    
    # Ops
    scan_pending_documents_op,
    parse_documents_op,
    validate_parse_results_op,
    
    # Schedules
    hourly_parse_schedule,
    daily_parse_schedule,
    
    # Sensors
    manual_trigger_parse_sensor,
)

from .chunk_jobs import (
    # Jobs
    chunk_documents_job,
    
    # Ops
    scan_parsed_documents_op,
    chunk_documents_op,
    validate_chunk_results_op,
    
    # Schedules
    hourly_chunk_schedule,
    daily_chunk_schedule,
    
    # Sensors
    manual_trigger_chunk_sensor,
)

__all__ = [
    # Jobs
    "crawl_a_share_reports_job",
    "crawl_a_share_ipo_job",
    "parse_pdf_job",
    "chunk_documents_job",
    
    # Ops
    "crawl_a_share_reports_op",
    "crawl_a_share_ipo_op",
    "validate_crawl_results_op",
    "scan_pending_documents_op",
    "parse_documents_op",
    "validate_parse_results_op",
    "scan_parsed_documents_op",
    "chunk_documents_op",
    "validate_chunk_results_op",
    
    # Schedules
    "daily_crawl_reports_schedule",
    "daily_crawl_ipo_schedule",
    "hourly_parse_schedule",
    "daily_parse_schedule",
    "hourly_chunk_schedule",
    "daily_chunk_schedule",
    
    # Sensors
    "manual_trigger_reports_sensor",
    "manual_trigger_ipo_sensor",
    "manual_trigger_parse_sensor",
    "manual_trigger_chunk_sensor",
]
