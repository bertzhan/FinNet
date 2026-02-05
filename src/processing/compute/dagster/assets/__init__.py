# -*- coding: utf-8 -*-
"""
Dagster Assets 模块
导出所有 Software-Defined Assets
"""

from .lineage_assets import (
    bronze_documents,
    silver_parsed_documents,
    silver_chunked_documents,
    silver_vectorized_chunks,
    gold_graph_nodes,
    gold_elasticsearch_index,
    pipeline_quality_metrics,
)

# 所有资产列表
all_assets = [
    bronze_documents,
    silver_parsed_documents,
    silver_chunked_documents,
    silver_vectorized_chunks,
    gold_graph_nodes,
    gold_elasticsearch_index,
    pipeline_quality_metrics,
]

__all__ = [
    "bronze_documents",
    "silver_parsed_documents",
    "silver_chunked_documents",
    "silver_vectorized_chunks",
    "gold_graph_nodes",
    "gold_elasticsearch_index",
    "pipeline_quality_metrics",
    "all_assets",
]
