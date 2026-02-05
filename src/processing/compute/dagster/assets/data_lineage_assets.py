# -*- coding: utf-8 -*-
"""
Dagster 数据血缘资产定义
定义关键数据资产和依赖关系，用于数据血缘追踪和可视化

注意：
- 实际的资产物化通过 AssetMaterialization 在各个 jobs 中记录
- 此文件主要用于文档说明和未来可能的 @asset 装饰器定义
- 当前依赖关系通过 AssetMaterialization 的 parent_asset_key 字段建立
"""

from typing import Dict, Optional
from dagster import (
    asset,
    AssetKey,
    MetadataValue,
    get_dagster_logger,
)

# 注意：以下资产定义是概念性的，用于文档说明
# 实际的资产物化在对应的 jobs 中通过 AssetMaterialization 记录

"""
数据血缘关系：

Bronze层（原始数据）
├── bronze/a_share/annual_report/2023/Q4
├── bronze/a_share/quarterly_report/2023/Q3
└── bronze/a_share/ipo_prospectus

Silver层（加工数据）
├── silver/parsed_documents/a_share/annual_report/000001/2023/Q4
│   └── 依赖: bronze/a_share/annual_report/2023/Q4
├── silver/chunked_documents/a_share/annual_report/000001
│   └── 依赖: silver/parsed_documents/a_share/annual_report/000001/2023/Q4
├── silver/vectorized_chunks/a_share/annual_report/000001
│   └── 依赖: silver/chunked_documents/a_share/annual_report/000001
└── ...

Gold层（应用数据）
├── gold/graph_nodes/a_share/annual_report/000001
│   └── 依赖: silver/chunked_documents/a_share/annual_report/000001
└── gold/elasticsearch_index/a_share/annual_report/000001
    └── 依赖: silver/chunked_documents/a_share/annual_report/000001

质量指标
├── quality_metrics/crawl_validation
├── quality_metrics/parse_validation
├── quality_metrics/chunk_validation
├── quality_metrics/vectorize_validation
├── quality_metrics/graph_validation
└── quality_metrics/elasticsearch_validation
"""

# 资产命名规范说明
ASSET_KEY_FORMAT = """
资产key格式: [layer, category, market?, doc_type?, stock_code?, year?, quarter?]

层级说明:
- bronze: 原始数据层（爬虫）
- silver: 加工数据层（解析、分块、向量化）
- gold: 应用数据层（图、索引）
- quality_metrics: 质量指标

示例:
- Bronze层: ["bronze", "a_share", "annual_report", "2023", "Q4"]
- Silver层: ["silver", "parsed_documents", "a_share", "annual_report", "000001", "2023", "Q4"]
- Gold层: ["gold", "graph_nodes", "a_share", "annual_report", "000001"]
"""

# 依赖关系说明
DEPENDENCY_RELATIONS = """
数据流依赖关系:

1. crawl_jobs (Bronze)
   ↓
2. parse_jobs (Silver: parsed_documents)
   ↓
3. chunk_jobs (Silver: chunked_documents)
   ├─→ vectorize_jobs (Silver: vectorized_chunks)
   ├─→ graph_jobs (Gold: graph_nodes)
   └─→ elasticsearch_jobs (Gold: elasticsearch_index)

关键依赖关系:
- parse_jobs 依赖 crawl_jobs (bronze → silver/parsed_documents)
- chunk_jobs 依赖 parse_jobs (silver/parsed_documents → silver/chunked_documents)
- vectorize_jobs 依赖 chunk_jobs (silver/chunked_documents → silver/vectorized_chunks)
- graph_jobs 直接依赖 chunk_jobs (silver/chunked_documents → gold/graph_nodes)
- elasticsearch_jobs 直接依赖 chunk_jobs (silver/chunked_documents → gold/elasticsearch_index)

注意: graph_jobs 和 elasticsearch_jobs 都直接依赖 chunk_jobs，不依赖 parsed_documents
"""

__all__ = [
    "ASSET_KEY_FORMAT",
    "DEPENDENCY_RELATIONS",
]
