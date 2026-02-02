# -*- coding: utf-8 -*-
"""
Document API Routes
提供文档查询接口
"""

from fastapi import APIRouter, HTTPException, status
from typing import Optional
import uuid
import time

from src.api.schemas.document import (
    DocumentQueryRequest, 
    DocumentQueryResponse,
    DocumentChunksResponse,
    ChunkListItem,
    CompanyNameSearchRequest,
    SimpleStockCodeResponse,
    ChunkByIdRequest,
    ChunkByIdResponse
)
from src.storage.metadata import get_postgres_client, crud
from src.common.logger import get_logger

router = APIRouter(prefix="/api/v1/document", tags=["Document"])
logger = get_logger(__name__)


@router.post("/query", response_model=DocumentQueryResponse)
async def query_document_id(request: DocumentQueryRequest) -> DocumentQueryResponse:
    """
    根据stock_code, year, quarter, doc_type查询document_id
    
    Args:
        request: 文档查询请求，包含：
            - stock_code: 股票代码
            - year: 年份
            - quarter: 季度（可选，如果为None则查询年度文档）
            - doc_type: 文档类型
    
    Returns:
        文档查询响应，包含：
            - document_id: 文档ID（UUID字符串），如果未找到则为None
            - found: 是否找到文档
            - message: 提示信息
    
    Example:
        POST /api/v1/document/query
        {
            "stock_code": "000001",
            "year": 2023,
            "quarter": 3,
            "doc_type": "quarterly_reports"
        }
        
        响应（找到）:
        {
            "document_id": "123e4567-e89b-12d3-a456-426614174000",
            "found": True,
            "message": null
        }
        
        响应（未找到）:
        {
            "document_id": null,
            "found": False,
            "message": "未找到匹配的文档"
        }
    """
    try:
        logger.info(
            f"收到文档查询请求: stock_code={request.stock_code}, "
            f"year={request.year}, quarter={request.quarter}, "
            f"doc_type={request.doc_type}"
        )
        
        # 获取PostgreSQL客户端
        pg_client = get_postgres_client()
        
        # 查询document_id
        with pg_client.get_session() as session:
            document_id = crud.get_document_id_by_filters(
                session=session,
                stock_code=request.stock_code,
                year=request.year,
                quarter=request.quarter,
                doc_type=request.doc_type
            )
        
        if document_id:
            logger.info(
                f"文档查询成功: stock_code={request.stock_code}, "
                f"year={request.year}, quarter={request.quarter}, "
                f"doc_type={request.doc_type}, "
                f"document_id={document_id}"
            )
            return DocumentQueryResponse(
                document_id=str(document_id),
                found=True,
                message=None
            )
        else:
            logger.info(
                f"文档查询未找到: stock_code={request.stock_code}, "
                f"year={request.year}, quarter={request.quarter}, "
                f"doc_type={request.doc_type}"
            )
            return DocumentQueryResponse(
                document_id=None,
                found=False,
                message="未找到匹配的文档"
            )
    
    except Exception as e:
        logger.error(f"文档查询失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文档查询过程中发生错误: {str(e)}"
        )


@router.get("/{document_id}/chunks", response_model=DocumentChunksResponse)
async def get_document_chunks(document_id: str) -> DocumentChunksResponse:
    """
    根据document_id获取该文档的所有chunk列表
    
    Args:
        document_id: 文档ID（UUID字符串）
    
    Returns:
        文档Chunks列表响应，包含：
            - document_id: 文档ID
            - chunks: Chunk列表，每个chunk包含chunk_id, title, title_level, parent_chunk_id
            - total: Chunk总数
    
    Example:
        GET /api/v1/document/123e4567-e89b-12d3-a456-426614174000/chunks
        
        响应:
        {
            "document_id": "123e4567-e89b-12d3-a456-426614174000",
            "chunks": [
                {
                    "chunk_id": "223e4567-e89b-12d3-a456-426614174001",
                    "title": "第一章 公司基本情况",
                    "title_level": 1,
                    "parent_chunk_id": null
                },
                {
                    "chunk_id": "323e4567-e89b-12d3-a456-426614174002",
                    "title": "1.1 公司简介",
                    "title_level": 2,
                    "parent_chunk_id": "223e4567-e89b-12d3-a456-426614174001"
                }
            ],
            "total": 2
        }
    """
    try:
        logger.info(f"收到获取文档chunks请求: document_id={document_id}")
        
        # 验证document_id格式
        try:
            uuid.UUID(document_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的document_id格式: {document_id}"
            )
        
        # 获取PostgreSQL客户端
        pg_client = get_postgres_client()
        
        # 查询chunks
        with pg_client.get_session() as session:
            # 验证document是否存在
            document = crud.get_document_by_id(session, document_id)
            if not document:
                logger.warning(f"文档不存在: document_id={document_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"文档不存在: document_id={document_id}"
                )
            
            # 获取chunks
            chunks = crud.get_document_chunks(session, document_id)
            
            # 构建响应
            chunk_items = []
            for chunk in chunks:
                chunk_items.append(
                    ChunkListItem(
                        chunk_id=str(chunk.id),
                        title=chunk.title,
                        title_level=chunk.title_level,
                        parent_chunk_id=str(chunk.parent_chunk_id) if chunk.parent_chunk_id else None
                    )
                )
            
            logger.info(
                f"获取文档chunks成功: document_id={document_id}, "
                f"chunks_count={len(chunk_items)}"
            )
            
            return DocumentChunksResponse(
                document_id=document_id,
                chunks=chunk_items,
                total=len(chunk_items)
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文档chunks失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文档chunks过程中发生错误: {str(e)}"
        )


@router.post("/company-code-search", response_model=SimpleStockCodeResponse)
async def company_code_search(request: CompanyNameSearchRequest) -> SimpleStockCodeResponse:
    """
    根据公司名称搜索股票代码接口
    进行精确和模糊匹配搜索。

    搜索策略（按优先级）：
    1. 精确匹配简称（name）
    2. 精确匹配全称（full_name）
    3. 简称包含查询词
    4. 全称包含查询词
    5. 查询词包含简称（用户输入全称的情况）
    6. 曾用名匹配

    优势：
    - 响应快速：简单字符串匹配，约 1-5ms
    - 无额外依赖：仅需 PostgreSQL
    - 支持全称、简称、曾用名多种匹配

    Args:
        request: 公司名称搜索请求，包含公司名称（company_name）

    Returns:
        股票代码搜索结果，包含：
        - stock_code: 匹配的股票代码（如果唯一匹配）或 None
        - message: 提示信息（如果有多个候选或未找到）

    Example:
        POST /api/v1/document/company-code-search
        {
            "company_name": "平安银行"
        }
        
        响应（唯一匹配）:
        {
            "stock_code": "000001",
            "message": null
        }
        
        响应（多个候选）:
        {
            "stock_code": null,
            "message": "找到 3 个可能的公司，请选择：..."
        }
    """
    start_time = time.time()
    try:
        logger.info(f"收到公司代码搜索请求: company_name='{request.company_name}'")

        # 预处理
        company_name_query = request.company_name.strip()
        
        if not company_name_query:
            logger.warning("公司名称为空")
            return SimpleStockCodeResponse(stock_code=None)
        
        # 获取PostgreSQL客户端
        pg_client = get_postgres_client()
        
        stock_code = None
        matched_name = None
        message = None
        
        with pg_client.get_session() as session:
            # 使用统一的搜索函数
            companies = crud.search_listed_company(session, company_name_query, max_candidates=30)
            
            if len(companies) == 1:
                # 唯一匹配
                stock_code = companies[0].code
                matched_name = companies[0].name
            elif 1 < len(companies) <= 5:
                # 少量候选（2-5个），显示列表让用户选择
                message_parts = [f"找到 {len(companies)} 个可能的公司，请选择："]
                for i, c in enumerate(companies, 1):
                    company_info = f"{i}. {c.name} ({c.code})"
                    if c.org_name_cn:
                        company_info += f" - {c.org_name_cn}"
                    message_parts.append(company_info)
                    if c.main_operation_business:
                        business = c.main_operation_business
                        message_parts.append(f"   主营业务: {business}")
                
                message = "\n".join(message_parts)
                logger.info(
                    f"公司代码搜索找到少量匹配: query='{request.company_name}', "
                    f"候选数量={len(companies)}"
                )
            elif len(companies) > 5:
                # 候选过多，提示用户进一步明确
                message = f"找到 {len(companies)} 个可能的公司，匹配结果过多，请进一步明确公司名称。"
                logger.info(
                    f"公司代码搜索匹配过多: query='{request.company_name}', "
                    f"候选数量={len(companies)}"
                )
        
        retrieval_time = time.time() - start_time
        
        if stock_code:
            logger.info(
                f"公司代码搜索成功: query='{request.company_name}', "
                f"匹配公司={matched_name}, "
                f"股票代码={stock_code}, "
                f"耗时={retrieval_time:.3f}s"
            )
            return SimpleStockCodeResponse(
                stock_code=stock_code,
                message=message
            )
        else:
            if message:
                # 有多个候选但没有唯一结果
                logger.info(
                    f"公司代码搜索找到多个匹配: query='{request.company_name}', "
                    f"耗时={retrieval_time:.3f}s"
                )
                return SimpleStockCodeResponse(
                    stock_code=None,
                    message=message
                )
            else:
                # 完全没有匹配
                logger.info(
                    f"公司代码搜索未找到: query='{request.company_name}', "
                    f"耗时={retrieval_time:.3f}s"
                )
                return SimpleStockCodeResponse(
                    stock_code=None,
                    message=None
                )

    except Exception as e:
        logger.error(f"公司代码搜索失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"公司代码搜索过程中发生错误: {str(e)}"
        )


@router.post("/chunk-by-id", response_model=ChunkByIdResponse)
async def get_chunk_by_id(request: ChunkByIdRequest) -> ChunkByIdResponse:
    """
    根据 chunk_id 查询分块详细信息

    Args:
        request: 查询请求，包含 chunk_id

    Returns:
        分块详细信息，包含：
        - chunk_id: 分块 ID
        - document_id: 文档 ID
        - chunk_text: 分块文本
        - title: 标题
        - title_level: 标题层级
        - parent_chunk_id: 父分块 ID
        - is_table: 是否是表格分块

    Example:
        POST /api/v1/document/chunk-by-id
        {
            "chunk_id": "123e4567-e89b-12d3-a456-426614174000"
        }
    """
    start_time = time.time()
    try:
        logger.info(f"收到根据 chunk_id 查询请求: chunk_id={request.chunk_id}")

        # 导入必要的模块
        from src.storage.metadata.models import DocumentChunk

        # 验证并转换 chunk_id
        try:
            chunk_uuid = uuid.UUID(request.chunk_id)
        except ValueError:
            logger.error(f"无效的 chunk_id 格式: {request.chunk_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的 chunk_id 格式: {request.chunk_id}"
            )

        # 查询数据库
        pg_client = get_postgres_client()
        with pg_client.get_session() as session:
            chunk = session.query(DocumentChunk).filter(
                DocumentChunk.id == chunk_uuid
            ).first()

            if not chunk:
                logger.warning(f"未找到 chunk_id: {request.chunk_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"未找到 chunk_id: {request.chunk_id}"
                )

            # 构建响应
            response = ChunkByIdResponse(
                chunk_id=str(chunk.id),
                document_id=str(chunk.document_id),
                chunk_text=chunk.chunk_text or "",
                title=chunk.title,
                title_level=chunk.title_level,
                parent_chunk_id=str(chunk.parent_chunk_id) if chunk.parent_chunk_id else None,
                is_table=chunk.is_table or False
            )

        query_time = time.time() - start_time
        logger.info(
            f"根据 chunk_id 查询完成: chunk_id={request.chunk_id}, "
            f"耗时={query_time:.3f}s"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"根据 chunk_id 查询失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询过程中发生错误: {str(e)}"
        )
