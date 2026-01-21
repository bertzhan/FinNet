# -*- coding: utf-8 -*-
"""
QA API Routes
提供问答接口
"""

from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any, Optional

from src.api.schemas.qa import QueryRequest, QueryResponse, HealthResponse
from src.application.rag.rag_pipeline import RAGPipeline
from src.common.logger import get_logger

router = APIRouter(prefix="/api/v1/qa", tags=["QA"])
logger = get_logger(__name__)

# 全局 RAG Pipeline 实例
_pipeline: Optional[RAGPipeline] = None


def get_pipeline() -> RAGPipeline:
    """获取 RAG Pipeline 实例（单例）"""
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """
    问答接口

    Args:
        request: 查询请求

    Returns:
        查询响应

    Example:
        POST /api/v1/qa/query
        {
            "question": "平安银行2023年第三季度的营业收入是多少？",
            "filters": {
                "stock_code": "000001",
                "year": 2023,
                "quarter": 3
            },
            "top_k": 5
        }
    """
    try:
        logger.info(f"收到查询请求: question='{request.question[:50]}...'")

        # 获取 Pipeline
        pipeline = get_pipeline()

        # 转换过滤条件
        filters = None
        if request.filters:
            filters = request.filters.dict(exclude_none=True)

        # 执行查询
        rag_response = pipeline.query(
            question=request.question,
            filters=filters,
            top_k=request.top_k,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        # 转换为响应格式
        sources = [
            {
                "chunk_id": source.chunk_id,
                "document_id": source.document_id,
                "title": source.title,
                "stock_code": source.stock_code,
                "company_name": source.company_name,
                "doc_type": source.doc_type,
                "year": source.year,
                "quarter": source.quarter,
                "score": source.score,
                "snippet": source.snippet
            }
            for source in rag_response.sources
        ]

        response = QueryResponse(
            answer=rag_response.answer,
            sources=sources,
            metadata=rag_response.metadata
        )

        logger.info(f"查询完成: 检索数量={len(sources)}, 生成时间={rag_response.metadata.get('generation_time', 0):.2f}s")
        return response

    except Exception as e:
        logger.error(f"查询失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询过程中发生错误: {str(e)}"
        )


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """
    健康检查接口

    Returns:
        健康状态

    Example:
        GET /api/v1/qa/health
    """
    try:
        components = {}
        status_str = "healthy"

        # 检查各个组件
        try:
            pipeline = get_pipeline()
            # 简单检查：尝试获取 retriever
            if pipeline.retriever:
                components["retriever"] = "ok"
            if pipeline.context_builder:
                components["context_builder"] = "ok"
            if pipeline.llm_service:
                components["llm_service"] = "ok"
        except Exception as e:
            logger.warning(f"组件检查失败: {e}")
            components["pipeline"] = f"error: {str(e)}"
            status_str = "degraded"

        return HealthResponse(
            status=status_str,
            message="QA service is running",
            components=components
        )

    except Exception as e:
        logger.error(f"健康检查失败: {e}", exc_info=True)
        return HealthResponse(
            status="unhealthy",
            message=f"Health check failed: {str(e)}",
            components={}
        )
