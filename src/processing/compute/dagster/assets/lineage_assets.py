# -*- coding: utf-8 -*-
"""
Dagster Software-Defined Assets
定义完整的数据血缘资产，建立可交互的 Lineage 图

数据流：
    bronze_documents (爬虫)
        ↓
    silver_parsed_documents (解析)
        ↓
    silver_chunked_documents (分块)
        ├── silver_vectorized_chunks (向量化)
        ├── gold_graph_nodes (图构建)
        └── gold_elasticsearch_index (ES索引)
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
import uuid

from dagster import (
    asset,
    AssetKey,
    AssetIn,
    Output,
    MetadataValue,
    get_dagster_logger,
    Config,
    MaterializeResult,
    AssetExecutionContext,
)

# 导入业务逻辑模块
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.storage.metadata.models import Document, ParsedDocument, DocumentChunk
from src.common.constants import DocumentStatus, DocType, Market


# ==================== 配置类 ====================

class DocumentProcessingConfig(Config):
    """文档处理配置"""
    market: str = "a_share"
    doc_type: Optional[str] = None
    stock_codes: Optional[List[str]] = None
    limit: int = 100
    force_reprocess: bool = False


# ==================== Bronze 层资产 ====================

@asset(
    key_prefix=["bronze"],
    group_name="data_ingestion",
    description="原始文档数据（Bronze层）- 由爬虫作业产生",
    compute_kind="crawler",
    metadata={
        "layer": "bronze",
        "source": "cninfo/akshare",
    }
)
def bronze_documents(context: AssetExecutionContext) -> MaterializeResult:
    """
    Bronze 层资产：原始文档
    
    此资产代表爬虫作业产生的原始 PDF 文档。
    物化此资产时，会统计当前 Bronze 层的文档数量。
    
    注意：实际的爬取逻辑仍在 crawl_jobs.py 中执行。
    此资产主要用于建立数据血缘关系。
    """
    logger = get_dagster_logger()
    
    pg_client = get_postgres_client()
    
    with pg_client.get_session() as session:
        # 统计 Bronze 层文档数量（状态为 crawled 或更高）
        total_docs = session.query(Document).count()
        crawled_docs = session.query(Document).filter(
            Document.status.in_([
                DocumentStatus.CRAWLED.value,
                DocumentStatus.PARSED.value,
                DocumentStatus.CHUNKED.value,
                DocumentStatus.VECTORIZED.value,
            ])
        ).count()
        
        # 按市场和文档类型统计
        market_stats = {}
        for market in [Market.A_SHARE.value]:
            count = session.query(Document).filter(
                Document.market == market
            ).count()
            market_stats[market] = count
        
        logger.info(f"Bronze 层文档统计: 总数={total_docs}, 已爬取={crawled_docs}")
    
    return MaterializeResult(
        metadata={
            "total_documents": MetadataValue.int(total_docs),
            "crawled_documents": MetadataValue.int(crawled_docs),
            "market_stats": MetadataValue.json(market_stats),
            "materialized_at": MetadataValue.text(datetime.now().isoformat()),
        }
    )


# ==================== Silver 层资产 ====================

@asset(
    key_prefix=["silver"],
    deps=[AssetKey(["bronze", "bronze_documents"])],
    group_name="data_processing",
    description="解析后的文档（Silver层）- 由 PDF 解析作业产生",
    compute_kind="mineru",
    metadata={
        "layer": "silver",
        "stage": "parsed",
    }
)
def silver_parsed_documents(context: AssetExecutionContext) -> MaterializeResult:
    """
    Silver 层资产：解析后的文档
    
    此资产依赖 bronze_documents，代表 PDF 解析后的文档。
    物化此资产时，会统计当前解析完成的文档数量。
    
    注意：实际的解析逻辑仍在 parse_jobs.py 中执行。
    """
    logger = get_dagster_logger()
    
    pg_client = get_postgres_client()
    
    with pg_client.get_session() as session:
        # 统计已解析的文档数量
        parsed_docs = session.query(ParsedDocument).count()
        
        # 统计有 markdown 的文档
        with_markdown = session.query(ParsedDocument).filter(
            ParsedDocument.markdown_path.isnot(None),
            ParsedDocument.markdown_path != ""
        ).count()
        
        # 统计待解析的文档（status=crawled）
        pending_parse = session.query(Document).filter(
            Document.status == DocumentStatus.CRAWLED.value
        ).count()
        
        logger.info(f"Silver 层解析统计: 已解析={parsed_docs}, 有markdown={with_markdown}, 待解析={pending_parse}")
    
    return MaterializeResult(
        metadata={
            "parsed_documents": MetadataValue.int(parsed_docs),
            "with_markdown": MetadataValue.int(with_markdown),
            "pending_parse": MetadataValue.int(pending_parse),
            "materialized_at": MetadataValue.text(datetime.now().isoformat()),
        }
    )


@asset(
    key_prefix=["silver"],
    deps=[AssetKey(["silver", "silver_parsed_documents"])],
    group_name="data_processing",
    description="分块后的文档（Silver层）- 由文本分块作业产生",
    compute_kind="chunker",
    metadata={
        "layer": "silver",
        "stage": "chunked",
    }
)
def silver_chunked_documents(context: AssetExecutionContext) -> MaterializeResult:
    """
    Silver 层资产：分块后的文档
    
    此资产依赖 silver_parsed_documents，代表分块完成的文档。
    物化此资产时，会统计当前分块完成的文档和分块数量。
    
    注意：实际的分块逻辑仍在 chunk_jobs.py 中执行。
    """
    logger = get_dagster_logger()
    
    pg_client = get_postgres_client()
    
    with pg_client.get_session() as session:
        # 统计分块数量
        total_chunks = session.query(DocumentChunk).count()
        
        # 统计有分块的文档数量
        from sqlalchemy import func, distinct, exists, and_
        docs_with_chunks = session.query(
            func.count(distinct(DocumentChunk.document_id))
        ).scalar() or 0
        
        # 统计待分块的文档（有 markdown 但没有对应 chunks）
        pending_chunk = session.query(ParsedDocument).filter(
            ParsedDocument.markdown_path.isnot(None),
            ~exists().where(DocumentChunk.parsed_document_id == ParsedDocument.id)
        ).count()
        
        # 计算平均分块数
        avg_chunks_per_doc = total_chunks / docs_with_chunks if docs_with_chunks > 0 else 0
        
        logger.info(f"Silver 层分块统计: 总分块={total_chunks}, 有分块的文档={docs_with_chunks}, 待分块={pending_chunk}")
    
    return MaterializeResult(
        metadata={
            "total_chunks": MetadataValue.int(total_chunks),
            "documents_with_chunks": MetadataValue.int(docs_with_chunks),
            "pending_chunk": MetadataValue.int(pending_chunk),
            "avg_chunks_per_doc": MetadataValue.float(avg_chunks_per_doc),
            "materialized_at": MetadataValue.text(datetime.now().isoformat()),
        }
    )


@asset(
    key_prefix=["silver"],
    deps=[AssetKey(["silver", "silver_chunked_documents"])],
    group_name="data_processing",
    description="向量化的分块（Silver层）- 由向量化作业产生",
    compute_kind="embedding",
    metadata={
        "layer": "silver",
        "stage": "vectorized",
    }
)
def silver_vectorized_chunks(context: AssetExecutionContext) -> MaterializeResult:
    """
    Silver 层资产：向量化的分块
    
    此资产依赖 silver_chunked_documents，代表向量化完成的分块。
    物化此资产时，会统计当前向量化完成的分块数量。
    
    注意：实际的向量化逻辑仍在 vectorize_jobs.py 中执行。
    """
    logger = get_dagster_logger()
    
    pg_client = get_postgres_client()
    
    with pg_client.get_session() as session:
        # 统计已向量化的分块
        vectorized_chunks = session.query(DocumentChunk).filter(
            DocumentChunk.vectorized_at.isnot(None)
        ).count()
        
        # 统计未向量化的分块
        pending_vectorize = session.query(DocumentChunk).filter(
            DocumentChunk.vectorized_at.is_(None)
        ).count()
        
        # 计算向量化率
        total_chunks = vectorized_chunks + pending_vectorize
        vectorization_rate = vectorized_chunks / total_chunks if total_chunks > 0 else 0
        
        logger.info(f"Silver 层向量化统计: 已向量化={vectorized_chunks}, 待向量化={pending_vectorize}, 向量化率={vectorization_rate:.2%}")
    
    return MaterializeResult(
        metadata={
            "vectorized_chunks": MetadataValue.int(vectorized_chunks),
            "pending_vectorize": MetadataValue.int(pending_vectorize),
            "vectorization_rate": MetadataValue.float(vectorization_rate),
            "materialized_at": MetadataValue.text(datetime.now().isoformat()),
        }
    )


# ==================== Gold 层资产 ====================

@asset(
    key_prefix=["gold"],
    deps=[AssetKey(["silver", "silver_chunked_documents"])],
    group_name="data_application",
    description="Neo4j 图节点（Gold层）- 由图构建作业产生",
    compute_kind="neo4j",
    metadata={
        "layer": "gold",
        "stage": "graph",
    }
)
def gold_graph_nodes(context: AssetExecutionContext) -> MaterializeResult:
    """
    Gold 层资产：图节点
    
    此资产依赖 silver_chunked_documents（直接依赖，不依赖 parsed），
    代表在 Neo4j 中构建的图结构。
    
    注意：实际的图构建逻辑仍在 graph_jobs.py 中执行。
    """
    logger = get_dagster_logger()
    
    try:
        from src.processing.graph.graph_builder import GraphBuilder
        builder = GraphBuilder()
        graph_stats = builder.get_graph_stats()
        
        document_nodes = graph_stats.get("document_nodes", 0)
        chunk_nodes = graph_stats.get("chunk_nodes", 0)
        company_nodes = graph_stats.get("company_nodes", 0)
        belongs_to_edges = graph_stats.get("belongs_to_edges", 0)
        has_child_edges = graph_stats.get("has_child_edges", 0)
        
        logger.info(f"Gold 层图统计: 文档节点={document_nodes}, 分块节点={chunk_nodes}, 公司节点={company_nodes}")
        
        return MaterializeResult(
            metadata={
                "document_nodes": MetadataValue.int(document_nodes),
                "chunk_nodes": MetadataValue.int(chunk_nodes),
                "company_nodes": MetadataValue.int(company_nodes),
                "belongs_to_edges": MetadataValue.int(belongs_to_edges),
                "has_child_edges": MetadataValue.int(has_child_edges),
                "materialized_at": MetadataValue.text(datetime.now().isoformat()),
            }
        )
    except Exception as e:
        logger.error(f"获取图统计失败: {e}")
        return MaterializeResult(
            metadata={
                "error": MetadataValue.text(str(e)),
                "materialized_at": MetadataValue.text(datetime.now().isoformat()),
            }
        )


@asset(
    key_prefix=["gold"],
    deps=[AssetKey(["silver", "silver_chunked_documents"])],
    group_name="data_application",
    description="Elasticsearch 索引（Gold层）- 由索引作业产生",
    compute_kind="elasticsearch",
    metadata={
        "layer": "gold",
        "stage": "indexed",
    }
)
def gold_elasticsearch_index(context: AssetExecutionContext) -> MaterializeResult:
    """
    Gold 层资产：Elasticsearch 索引
    
    此资产依赖 silver_chunked_documents（直接依赖，不依赖 parsed），
    代表在 Elasticsearch 中建立的全文索引。
    
    注意：实际的索引逻辑仍在 elasticsearch_jobs.py 中执行。
    """
    logger = get_dagster_logger()
    
    pg_client = get_postgres_client()
    
    with pg_client.get_session() as session:
        # 统计已索引到 ES 的分块
        indexed_chunks = session.query(DocumentChunk).filter(
            DocumentChunk.es_indexed_at.isnot(None)
        ).count()
        
        # 统计未索引的分块
        pending_index = session.query(DocumentChunk).filter(
            DocumentChunk.es_indexed_at.is_(None),
            DocumentChunk.chunk_text.isnot(None),
            DocumentChunk.chunk_text != ""
        ).count()
        
        # 计算索引率
        total = indexed_chunks + pending_index
        index_rate = indexed_chunks / total if total > 0 else 0
        
        logger.info(f"Gold 层 ES 索引统计: 已索引={indexed_chunks}, 待索引={pending_index}, 索引率={index_rate:.2%}")
    
    # 尝试获取 ES 索引信息
    try:
        from src.storage.elasticsearch import get_elasticsearch_client
        es_client = get_elasticsearch_client()
        
        # 获取索引文档数量
        index_name = "chunks"
        doc_count = es_client.get_document_count(index_name)
        
        return MaterializeResult(
            metadata={
                "indexed_chunks_db": MetadataValue.int(indexed_chunks),
                "indexed_chunks_es": MetadataValue.int(doc_count),
                "pending_index": MetadataValue.int(pending_index),
                "index_rate": MetadataValue.float(index_rate),
                "materialized_at": MetadataValue.text(datetime.now().isoformat()),
            }
        )
    except Exception as e:
        logger.warning(f"获取 ES 统计失败: {e}")
        return MaterializeResult(
            metadata={
                "indexed_chunks_db": MetadataValue.int(indexed_chunks),
                "pending_index": MetadataValue.int(pending_index),
                "index_rate": MetadataValue.float(index_rate),
                "es_error": MetadataValue.text(str(e)),
                "materialized_at": MetadataValue.text(datetime.now().isoformat()),
            }
        )


# ==================== 质量指标资产 ====================

@asset(
    key_prefix=["quality_metrics"],
    deps=[
        AssetKey(["bronze", "bronze_documents"]),
        AssetKey(["silver", "silver_parsed_documents"]),
        AssetKey(["silver", "silver_chunked_documents"]),
        AssetKey(["silver", "silver_vectorized_chunks"]),
        AssetKey(["gold", "gold_graph_nodes"]),
        AssetKey(["gold", "gold_elasticsearch_index"]),
    ],
    group_name="quality",
    description="数据处理流水线质量指标汇总",
    compute_kind="metrics",
)
def pipeline_quality_metrics(context: AssetExecutionContext) -> MaterializeResult:
    """
    质量指标资产：汇总整个数据处理流水线的质量指标
    
    此资产依赖所有层的资产，用于生成整体质量报告。
    """
    logger = get_dagster_logger()
    
    pg_client = get_postgres_client()
    
    with pg_client.get_session() as session:
        # 汇总各层统计
        total_docs = session.query(Document).count()
        parsed_docs = session.query(ParsedDocument).count()
        total_chunks = session.query(DocumentChunk).count()
        vectorized_chunks = session.query(DocumentChunk).filter(
            DocumentChunk.vectorized_at.isnot(None)
        ).count()
        indexed_chunks = session.query(DocumentChunk).filter(
            DocumentChunk.es_indexed_at.isnot(None)
        ).count()
        
        # 计算各阶段转化率
        parse_rate = parsed_docs / total_docs if total_docs > 0 else 0
        vectorize_rate = vectorized_chunks / total_chunks if total_chunks > 0 else 0
        index_rate = indexed_chunks / total_chunks if total_chunks > 0 else 0
        
        logger.info(f"流水线质量指标: 解析率={parse_rate:.2%}, 向量化率={vectorize_rate:.2%}, 索引率={index_rate:.2%}")
    
    return MaterializeResult(
        metadata={
            "total_documents": MetadataValue.int(total_docs),
            "parsed_documents": MetadataValue.int(parsed_docs),
            "total_chunks": MetadataValue.int(total_chunks),
            "vectorized_chunks": MetadataValue.int(vectorized_chunks),
            "indexed_chunks": MetadataValue.int(indexed_chunks),
            "parse_rate": MetadataValue.float(parse_rate),
            "vectorize_rate": MetadataValue.float(vectorize_rate),
            "index_rate": MetadataValue.float(index_rate),
            "materialized_at": MetadataValue.text(datetime.now().isoformat()),
        }
    )


# 导出所有资产
__all__ = [
    "bronze_documents",
    "silver_parsed_documents",
    "silver_chunked_documents",
    "silver_vectorized_chunks",
    "gold_graph_nodes",
    "gold_elasticsearch_index",
    "pipeline_quality_metrics",
]
