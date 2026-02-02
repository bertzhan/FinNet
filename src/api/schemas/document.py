# -*- coding: utf-8 -*-
"""
Document API Schemas
定义文档查询接口的请求/响应模型
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from uuid import UUID


class DocumentQueryRequest(BaseModel):
    """文档查询请求模型"""
    stock_code: str = Field(..., description="股票代码", min_length=1, max_length=20)
    year: int = Field(..., description="年份", ge=2000, le=2100)
    quarter: Optional[int] = Field(None, description="季度（1-4），如果为None则查询年度文档", ge=1, le=4)
    doc_type: str = Field(..., description="文档类型（如：annual_reports, quarterly_reports, interim_reports, ipo_prospectus等）", min_length=1)

    class Config:
        json_schema_extra = {
            "example": {
                "stock_code": "000001",
                "year": 2023,
                "quarter": 3,
                "doc_type": "quarterly_reports"
            }
        }


class DocumentQueryResponse(BaseModel):
    """文档查询响应模型"""
    document_id: Optional[str] = Field(None, description="文档ID（UUID字符串），如果未找到则为None")
    found: bool = Field(..., description="是否找到文档")
    message: Optional[str] = Field(None, description="提示信息")

    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "123e4567-e89b-12d3-a456-426614174000",
                "found": True,
                "message": None
            }
        }


class ChunkListItem(BaseModel):
    """Chunk列表项模型"""
    chunk_id: str = Field(..., description="Chunk ID（UUID字符串）")
    title: Optional[str] = Field(None, description="Chunk标题")
    title_level: Optional[int] = Field(None, description="标题层级（1-5），如果为None则表示没有标题层级")
    parent_chunk_id: Optional[str] = Field(None, description="父Chunk ID（UUID字符串），如果为None则表示顶级chunk")

    class Config:
        json_schema_extra = {
            "example": {
                "chunk_id": "123e4567-e89b-12d3-a456-426614174000",
                "title": "第一章 公司基本情况",
                "title_level": 1,
                "parent_chunk_id": None
            }
        }


class DocumentChunksResponse(BaseModel):
    """文档Chunks列表响应模型"""
    document_id: str = Field(..., description="文档ID（UUID字符串）")
    chunks: List[ChunkListItem] = Field(..., description="Chunk列表")
    total: int = Field(..., description="Chunk总数")

    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "123e4567-e89b-12d3-a456-426614174000",
                "chunks": [
                    {
                        "chunk_id": "223e4567-e89b-12d3-a456-426614174001",
                        "title": "第一章 公司基本情况",
                        "title_level": 1,
                        "parent_chunk_id": None
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
        }


class CompanyNameSearchRequest(BaseModel):
    """根据公司名称搜索股票代码请求模型"""
    company_name: str = Field(..., description="公司名称", min_length=1, max_length=200)

    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "平安银行"
            }
        }


class SimpleStockCodeResponse(BaseModel):
    """简化的股票代码响应模型（只返回股票代码）"""
    stock_code: Optional[str] = Field(None, description="股票代码（如果未找到则为 null）")
    message: Optional[str] = Field(None, description="提示消息（如有多个匹配时显示，包含公司信息和主营业务）")

    class Config:
        json_schema_extra = {
            "example": {
                "stock_code": "000001",
                "message": None
            }
        }


class ChunkByIdRequest(BaseModel):
    """根据 chunk_id 查询请求模型"""
    chunk_id: str = Field(..., description="分块 ID", min_length=1)

    class Config:
        json_schema_extra = {
            "example": {
                "chunk_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }


class ChunkByIdResponse(BaseModel):
    """根据 chunk_id 查询响应模型"""
    chunk_id: str = Field(..., description="分块 ID")
    document_id: str = Field(..., description="文档 ID")
    chunk_text: str = Field(..., description="分块文本")
    title: Optional[str] = Field(None, description="标题")
    title_level: Optional[int] = Field(None, description="标题层级")
    parent_chunk_id: Optional[str] = Field(None, description="父分块 ID")
    is_table: bool = Field(False, description="是否是表格分块")

    class Config:
        json_schema_extra = {
            "example": {
                "chunk_id": "123e4567-e89b-12d3-a456-426614174000",
                "document_id": "123e4567-e89b-12d3-a456-426614174001",
                "chunk_text": "2023年第三季度，公司实现营业收入XXX亿元...",
                "title": "一、公司基本情况",
                "title_level": 1,
                "parent_chunk_id": "123e4567-e89b-12d3-a456-426614174002",
                "is_table": False
            }
        }
