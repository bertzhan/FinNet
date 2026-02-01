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

# 向量化作业（需要 sentence_transformers）
from .vectorize_jobs import (
    # Jobs
    vectorize_documents_job,
    
    # Ops
    scan_unvectorized_chunks_op,
    vectorize_chunks_op,
    validate_vectorize_results_op,
    
    # Schedules
    hourly_vectorize_schedule,
    daily_vectorize_schedule,
    
    # Sensors
    manual_trigger_vectorize_sensor,
)

# 图构建作业（需要 neo4j）
from .graph_jobs import (
    # Jobs
    build_graph_job,
    
    # Ops
    scan_chunked_documents_for_graph_op,
    build_graph_op,
    validate_graph_op,
    
    # Schedules
    hourly_graph_schedule,
    daily_graph_schedule,
    
    # Sensors
    manual_trigger_graph_sensor,
)

# Elasticsearch 索引作业（需要 elasticsearch）
from .elasticsearch_jobs import (
    # Jobs
    elasticsearch_index_job,
    
    # Ops
    scan_chunked_documents_op,
    index_chunks_to_elasticsearch_op,
    validate_elasticsearch_results_op,
    
    # Schedules
    hourly_elasticsearch_schedule,
    daily_elasticsearch_schedule,
    
    # Sensors
    manual_trigger_elasticsearch_sensor,
)

# 上市公司列表更新作业（需要 akshare）
from .company_list_jobs import (
    # Jobs
    update_listed_companies_job,
    
    # Ops
    update_listed_companies_op,
    
    # Schedules
    daily_update_companies_schedule,
    
    # Sensors
    manual_trigger_companies_sensor,
)

__all__ = [
    # Jobs
    "crawl_a_share_reports_job",
    "crawl_a_share_ipo_job",
    "parse_pdf_job",
    "chunk_documents_job",
    "vectorize_documents_job",
    "build_graph_job",
    "elasticsearch_index_job",
    "update_listed_companies_job",
    
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
    "scan_unvectorized_chunks_op",
    "vectorize_chunks_op",
    "validate_vectorize_results_op",
    "scan_chunked_documents_for_graph_op",
    "build_graph_op",
    "validate_graph_op",
    "scan_chunked_documents_op",
    "index_chunks_to_elasticsearch_op",
    "validate_elasticsearch_results_op",
    "update_listed_companies_op",
    
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
]
