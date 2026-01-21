# -*- coding: utf-8 -*-
"""
QA API Schemas
定义问答接口的请求/响应模型
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class FilterParams(BaseModel):
    """过滤参数"""
    stock_code: Optional[str] = Field(None, description="股票代码")
    year: Optional[int] = Field(None, description="年份")
    quarter: Optional[int] = Field(None, ge=1, le=4, description="季度（1-4）")
    doc_type: Optional[str] = Field(None, description="文档类型")
    market: Optional[str] = Field(None, description="市场")


class QueryRequest(BaseModel):
    """查询请求"""
    question: str = Field(..., description="用户问题", min_length=1, max_length=1000)
    filters: Optional[FilterParams] = Field(None, description="过滤条件")
    top_k: int = Field(5, ge=1, le=20, description="检索数量")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="LLM 温度参数")
    max_tokens: int = Field(1000, ge=1, le=4000, description="最大生成长度")

    class Config:
        json_schema_extra = {
            "example": {
                "question": "平安银行2023年第三季度的营业收入是多少？",
                "filters": {
                    "stock_code": "000001",
                    "year": 2023,
                    "quarter": 3
                },
                "top_k": 5,
                "temperature": 0.7
            }
        }


class SourceResponse(BaseModel):
    """来源信息响应"""
    chunk_id: str = Field(..., description="分块ID")
    document_id: str = Field(..., description="文档ID")
    title: Optional[str] = Field(None, description="标题")
    stock_code: str = Field(..., description="股票代码")
    company_name: str = Field(..., description="公司名称")
    doc_type: str = Field(..., description="文档类型")
    year: int = Field(..., description="年份")
    quarter: Optional[int] = Field(None, description="季度")
    score: float = Field(..., ge=0.0, le=1.0, description="相似度分数")
    snippet: str = Field(..., description="相关文本片段")


class QueryResponse(BaseModel):
    """查询响应"""
    answer: str = Field(..., description="生成的答案")
    sources: List[SourceResponse] = Field(default_factory=list, description="引用来源列表")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")

    class Config:
        json_schema_extra = {
            "example": {
                "answer": "根据2023年第三季度报告，平安银行营业收入为XXX亿元...",
                "sources": [
                    {
                        "chunk_id": "xxx",
                        "document_id": "yyy",
                        "title": "一、公司基本情况",
                        "stock_code": "000001",
                        "company_name": "平安银行",
                        "doc_type": "quarterly_report",
                        "year": 2023,
                        "quarter": 3,
                        "score": 0.95,
                        "snippet": "营业收入为XXX亿元..."
                    }
                ],
                "metadata": {
                    "retrieval_count": 5,
                    "generation_time": 1.2,
                    "model": "deepseek-chat"
                }
            }
        }


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="状态")
    message: str = Field(..., description="消息")
    components: Dict[str, str] = Field(default_factory=dict, description="组件状态")
