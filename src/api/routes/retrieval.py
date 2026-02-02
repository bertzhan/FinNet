# -*- coding: utf-8 -*-
"""
Retrieval API Routes
提供检索接口（向量检索、全文检索、图检索）
"""

import time
from fastapi import APIRouter, HTTPException, status
from typing import Optional

from src.api.schemas.retrieval import (
    VectorRetrievalRequest,
    FulltextRetrievalRequest,
    HybridRetrievalRequest,
    RetrievalResponse,
    RetrievalResultResponse,
    RetrievalHealthResponse,
    ChunkChildrenRequest,
    ChunkChildrenResponse,
    ChunkChildResponse
)
from src.application.rag.retriever import Retriever
from src.application.rag.elasticsearch_retriever import ElasticsearchRetriever
from src.application.rag.graph_retriever import GraphRetriever
from src.application.rag.hybrid_retriever import HybridRetriever
from src.processing.ai.embedding.embedder_factory import get_embedder_by_mode
from src.storage.vector.milvus_client import get_milvus_client
from src.common.constants import MilvusCollection
from src.common.logger import get_logger

router = APIRouter(prefix="/api/v1/retrieval", tags=["Retrieval"])
logger = get_logger(__name__)

# 全局检索器实例（单例）
_vector_retriever: Optional[Retriever] = None
_fulltext_retriever: Optional[ElasticsearchRetriever] = None
_graph_retriever: Optional[GraphRetriever] = None


def get_vector_retriever() -> Retriever:
    """获取向量检索器实例（单例）"""
    global _vector_retriever
    if _vector_retriever is None:
        _vector_retriever = Retriever()
    return _vector_retriever


def get_fulltext_retriever() -> ElasticsearchRetriever:
    """获取全文检索器实例（单例）"""
    global _fulltext_retriever
    if _fulltext_retriever is None:
        _fulltext_retriever = ElasticsearchRetriever()
    return _fulltext_retriever


def get_graph_retriever() -> GraphRetriever:
    """获取图检索器实例（单例）"""
    global _graph_retriever
    if _graph_retriever is None:
        _graph_retriever = GraphRetriever()
    return _graph_retriever


def _convert_retrieval_results_to_response(
    results,
    retrieval_type: str,
    query: str,
    top_k: int,
    retrieval_time: float
) -> RetrievalResponse:
    """
    将检索结果转换为响应格式

    Args:
        results: RetrievalResult 列表
        retrieval_type: 检索类型
        query: 查询文本
        top_k: 请求的 top_k
        retrieval_time: 检索耗时

    Returns:
        RetrievalResponse
    """
    response_results = []
    for result in results:
        response_results.append(
            RetrievalResultResponse(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                chunk_text=result.chunk_text,
                title=result.title,
                title_level=result.title_level,
                score=result.score,
                metadata=result.metadata
            )
        )

    return RetrievalResponse(
        results=response_results,
        total=len(response_results),
        metadata={
            "retrieval_type": retrieval_type,
            "query": query[:100] if query else "",  # 限制长度
            "retrieval_time": retrieval_time,
            "top_k": top_k,
            "requested_top_k": top_k
        }
    )


@router.post("/vector", response_model=RetrievalResponse)
async def vector_retrieval(request: VectorRetrievalRequest) -> RetrievalResponse:
    """
    向量检索接口

    Args:
        request: 向量检索请求

    Returns:
        检索响应

    Example:
        POST /api/v1/retrieval/vector
        {
            "query": "平安银行2023年第三季度的营业收入",
            "filters": {
                "stock_code": "000001",
                "year": 2023,
                "quarter": 3,
                "doc_type": "quarterly_reports"
            },
            "top_k": 5
        }
    """
    start_time = time.time()
    try:
        logger.info(f"收到向量检索请求: query='{request.query[:50]}...', top_k={request.top_k}")

        # 获取检索器
        retriever = get_vector_retriever()

        # 转换过滤条件
        filters = None
        if request.filters:
            filters = request.filters.dict(exclude_none=True)
            # 处理 doc_type（可能是字符串或列表）
            if "doc_type" in filters and filters["doc_type"] is not None:
                # 如果 doc_type 是列表，需要特殊处理
                # 但 Milvus 过滤表达式可能不支持 IN 操作，需要检查
                pass

        # 执行检索
        results = retriever.retrieve(
            query=request.query,
            top_k=request.top_k,
            filters=filters
        )

        retrieval_time = time.time() - start_time
        logger.info(f"向量检索完成: 返回 {len(results)} 个结果, 耗时={retrieval_time:.3f}s")

        # 转换为响应格式
        return _convert_retrieval_results_to_response(
            results=results,
            retrieval_type="vector",
            query=request.query,
            top_k=request.top_k,
            retrieval_time=retrieval_time
        )

    except Exception as e:
        logger.error(f"向量检索失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"向量检索过程中发生错误: {str(e)}"
        )


@router.post("/fulltext", response_model=RetrievalResponse)
async def fulltext_retrieval(request: FulltextRetrievalRequest) -> RetrievalResponse:
    """
    全文检索接口

    Args:
        request: 全文检索请求

    Returns:
        检索响应

    Example:
        POST /api/v1/retrieval/fulltext
        {
            "query": "营业收入 净利润",
            "filters": {
                "stock_code": "000001",
                "year": 2023,
                "quarter": 3,
                "doc_type": "quarterly_reports"
            },
            "top_k": 10
        }
    """
    start_time = time.time()
    try:
        logger.info(f"收到全文检索请求: query='{request.query[:50]}...', top_k={request.top_k}")

        # 获取检索器
        retriever = get_fulltext_retriever()

        # 转换过滤条件
        filters = None
        if request.filters:
            filters = request.filters.dict(exclude_none=True)

        # 执行检索
        results = retriever.retrieve(
            query=request.query,
            top_k=request.top_k,
            filters=filters
        )

        retrieval_time = time.time() - start_time
        logger.info(f"全文检索完成: 返回 {len(results)} 个结果, 耗时={retrieval_time:.3f}s")

        # 转换为响应格式
        return _convert_retrieval_results_to_response(
            results=results,
            retrieval_type="fulltext",
            query=request.query,
            top_k=request.top_k,
            retrieval_time=retrieval_time
        )

    except Exception as e:
        logger.error(f"全文检索失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"全文检索过程中发生错误: {str(e)}"
        )


@router.post("/graph/children", response_model=ChunkChildrenResponse)
async def get_chunk_children(request: ChunkChildrenRequest) -> ChunkChildrenResponse:
    """
    查询 chunk 的子节点（children）

    Args:
        request: 查询请求，包含 chunk_id、recursive（是否递归，默认 true）和 max_depth（最大深度，可选）

    Returns:
        子节点列表响应，包含 chunk_id 和 title

    Example:
        POST /api/v1/retrieval/graph/children
        {
            "chunk_id": "123e4567-e89b-12d3-a456-426614174000",
            "recursive": true,
            "max_depth": null
        }
    """
    start_time = time.time()
    try:
        logger.info(
            f"收到查询子节点请求: chunk_id={request.chunk_id}, "
            f"recursive={request.recursive}, max_depth={request.max_depth}"
        )

        # 获取图检索器
        retriever = get_graph_retriever()

        # 查询子节点（支持递归查询）
        children_data = retriever.get_children(
            request.chunk_id,
            recursive=request.recursive,
            max_depth=request.max_depth
        )

        # 转换为响应格式
        children_response = [
            ChunkChildResponse(
                chunk_id=child["chunk_id"],
                title=child.get("title")
            )
            for child in children_data
        ]

        retrieval_time = time.time() - start_time
        logger.info(
            f"查询子节点完成: chunk_id={request.chunk_id}, "
            f"返回 {len(children_response)} 个子节点, 耗时={retrieval_time:.3f}s"
        )

        return ChunkChildrenResponse(
            children=children_response,
            total=len(children_response),
            metadata={
                "parent_chunk_id": request.chunk_id,
                "query_time": retrieval_time,
                "recursive": request.recursive,
                "max_depth": request.max_depth
            }
        )

    except Exception as e:
        logger.error(f"查询子节点失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询子节点过程中发生错误: {str(e)}"
        )


@router.post("/hybrid", response_model=RetrievalResponse)
async def hybrid_retrieval(request: HybridRetrievalRequest) -> RetrievalResponse:
    """
    混合检索接口（可选）

    结合向量检索和全文检索，使用 RRF 算法融合结果

    Args:
        request: 混合检索请求

    Returns:
        检索响应

    Example:
        POST /api/v1/retrieval/hybrid
        {
            "query": "平安银行营业收入",
            "filters": {
                "year": 2023,
                "doc_type": ["annual_reports", "quarterly_reports"]
            },
            "top_k": 10,
            "hybrid_weights": {
                "vector": 0.5,
                "fulltext": 0.5
            }
        }
    """
    start_time = time.time()
    try:
        logger.info(f"收到混合检索请求: query='{request.query[:50]}...', top_k={request.top_k}")

        # 获取权重
        weights = request.hybrid_weights or {"vector": 0.5, "fulltext": 0.5}

        # 转换过滤条件
        filters = None
        if request.filters:
            filters = request.filters.dict(exclude_none=True)

        # 执行各种检索
        all_results = {}
        
        # 向量检索
        if weights.get("vector", 0) > 0:
            try:
                vector_retriever = get_vector_retriever()
                vector_results = vector_retriever.retrieve(
                    query=request.query,
                    top_k=request.top_k,
                    filters=filters
                )
                all_results["vector"] = vector_results
            except Exception as e:
                logger.warning(f"向量检索失败: {e}")
                all_results["vector"] = []

        # 全文检索
        if weights.get("fulltext", 0) > 0:
            try:
                fulltext_retriever = get_fulltext_retriever()
                fulltext_results = fulltext_retriever.retrieve(
                    query=request.query,
                    top_k=request.top_k,
                    filters=filters
                )
                all_results["fulltext"] = fulltext_results
            except Exception as e:
                logger.warning(f"全文检索失败: {e}")
                all_results["fulltext"] = []

        # 融合结果（使用 RRF 算法）
        hybrid_retriever = HybridRetriever()
        fused_results = hybrid_retriever.fuse_results(
            results_dict=all_results,
            weights=weights,
            top_k=request.top_k
        )

        retrieval_time = time.time() - start_time
        logger.info(f"混合检索完成: 返回 {len(fused_results)} 个结果, 耗时={retrieval_time:.3f}s")

        # 转换为响应格式
        return _convert_retrieval_results_to_response(
            results=fused_results,
            retrieval_type="hybrid",
            query=request.query,
            top_k=request.top_k,
            retrieval_time=retrieval_time
        )

    except Exception as e:
        logger.error(f"混合检索失败: {e}", exc_info=True)
        # 如果混合检索失败，尝试返回单个检索结果
        try:
            # 降级到向量检索
            vector_retriever = get_vector_retriever()
            filters = request.filters.dict(exclude_none=True) if request.filters else None
            results = vector_retriever.retrieve(
                query=request.query,
                top_k=request.top_k,
                filters=filters
            )
            retrieval_time = time.time() - start_time
            logger.warning(f"混合检索失败，降级到向量检索: 返回 {len(results)} 个结果")
            return _convert_retrieval_results_to_response(
                results=results,
                retrieval_type="hybrid_fallback_vector",
                query=request.query,
                top_k=request.top_k,
                retrieval_time=retrieval_time
            )
        except Exception as fallback_error:
            logger.error(f"降级检索也失败: {fallback_error}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"混合检索过程中发生错误: {str(e)}"
            )


@router.get("/health", response_model=RetrievalHealthResponse)
async def health() -> RetrievalHealthResponse:
    """
    健康检查接口

    Returns:
        健康状态

    Example:
        GET /api/v1/retrieval/health
    """
    try:
        components = {}
        status_str = "healthy"

        # 检查向量检索器（Milvus）
        try:
            vector_retriever = get_vector_retriever()
            if vector_retriever:
                # 尝试连接 Milvus 检查实际连接状态
                try:
                    milvus_client = get_milvus_client()
                    collections = milvus_client.list_collections()
                    components["vector_retriever"] = f"ok (collections: {len(collections)})"
                except Exception as e:
                    components["vector_retriever"] = f"error: Milvus连接失败 - {str(e)[:50]}"
                    status_str = "degraded"
        except Exception as e:
            logger.warning(f"向量检索器检查失败: {e}")
            components["vector_retriever"] = f"error: {str(e)[:50]}"
            status_str = "degraded"

        # 检查全文检索器（Elasticsearch）
        try:
            fulltext_retriever = get_fulltext_retriever()
            if fulltext_retriever:
                # 尝试连接 Elasticsearch 检查实际连接状态
                try:
                    es_client = fulltext_retriever.es_client
                    health = es_client.client.cluster.health()
                    es_status = health.get('status', 'unknown')
                    components["fulltext_retriever"] = f"ok (status: {es_status})"
                except Exception as e:
                    components["fulltext_retriever"] = f"error: ES连接失败 - {str(e)[:50]}"
                    status_str = "degraded"
        except Exception as e:
            logger.warning(f"全文检索器检查失败: {e}")
            components["fulltext_retriever"] = f"error: {str(e)[:50]}"
            status_str = "degraded"

        # 检查图检索器（Neo4j）
        try:
            graph_retriever = get_graph_retriever()
            if graph_retriever:
                components["graph_retriever"] = "ok"
        except Exception as e:
            logger.warning(f"图检索器检查失败: {e}")
            components["graph_retriever"] = f"error: {str(e)[:50]}"
            status_str = "degraded"

        return RetrievalHealthResponse(
            status=status_str,
            message="Retrieval service is running",
            components=components
        )

    except Exception as e:
        logger.error(f"健康检查失败: {e}", exc_info=True)
        return RetrievalHealthResponse(
            status="unhealthy",
            message=f"Health check failed: {str(e)}",
            components={}
        )
