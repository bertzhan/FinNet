# -*- coding: utf-8 -*-
"""
Retrieval API Schemas
定义检索接口的请求/响应模型
"""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, validator
from src.common.constants import DocType


class FilterParams(BaseModel):
    """过滤条件模型（共享）"""
    stock_code: Optional[str] = Field(None, description="股票代码")
    year: Optional[int] = Field(None, description="年份")
    quarter: Optional[int] = Field(None, ge=1, le=4, description="季度（1-4）")
    doc_type: Optional[Union[str, List[str]]] = Field(
        None, 
        description="文档类型（单个字符串或字符串列表）。支持的文档类型：年报(annual_reports)、季报(quarterly_reports)、半年报(interim_reports)、招股书(ipo_prospectus)、公告(announcements)等"
    )
    market: Optional[str] = Field(None, description="市场（a_share/hk_stock/us_stock）")
    company_name: Optional[str] = Field(None, description="公司名称")

    @validator('doc_type')
    def validate_doc_type(cls, v):
        """验证文档类型是否有效"""
        if v is None:
            return v
        
        # 获取所有有效的文档类型值
        valid_doc_types = [dt.value for dt in DocType]
        
        # 如果是字符串，转换为列表
        if isinstance(v, str):
            if v not in valid_doc_types:
                raise ValueError(f"无效的文档类型: {v}。支持的文档类型: {', '.join(valid_doc_types)}")
            return v
        
        # 如果是列表，验证每个元素
        if isinstance(v, list):
            invalid_types = [dt for dt in v if dt not in valid_doc_types]
            if invalid_types:
                raise ValueError(f"无效的文档类型: {invalid_types}。支持的文档类型: {', '.join(valid_doc_types)}")
            return v
        
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "stock_code": "000001",
                "year": 2023,
                "quarter": 3,
                "doc_type": "quarterly_reports",
                "market": "a_share"
            }
        }


class VectorRetrievalRequest(BaseModel):
    """向量检索请求模型"""
    query: str = Field(..., description="查询文本", min_length=1, max_length=2000)
    filters: Optional[FilterParams] = Field(None, description="过滤条件")
    top_k: int = Field(5, ge=1, le=100, description="返回数量")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "平安银行2023年第三季度的营业收入",
                "filters": {
                    "stock_code": "000001",
                    "year": 2023,
                    "quarter": 3,
                    "doc_type": "quarterly_reports"
                },
                "top_k": 5
            }
        }


class FulltextRetrievalRequest(BaseModel):
    """全文检索请求模型"""
    query: str = Field(..., description="查询文本", min_length=1, max_length=2000)
    filters: Optional[FilterParams] = Field(None, description="过滤条件")
    top_k: int = Field(5, ge=1, le=100, description="返回数量")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "营业收入 净利润",
                "filters": {
                    "stock_code": "000001",
                    "doc_type": "ipo_prospectus"
                },
                "top_k": 10
            }
        }


class GraphRetrievalRequest(BaseModel):
    """图检索请求模型"""
    query: Optional[str] = Field(None, description="查询文本或节点ID（用于 document/chunk/hierarchy 查询类型）")
    query_type: str = Field(
        "document",
        description="查询类型：document（文档检索）、chunk（分块检索）、hierarchy（层级遍历）、cypher（自定义Cypher查询）"
    )
    filters: Optional[FilterParams] = Field(None, description="过滤条件")
    max_depth: Optional[int] = Field(None, ge=1, le=10, description="最大遍历深度（用于层级查询）")
    top_k: int = Field(10, ge=1, le=100, description="返回数量")
    cypher_query: Optional[str] = Field(None, description="自定义 Cypher 查询（当 query_type 为 'cypher' 时必填）")
    cypher_parameters: Optional[Dict[str, Any]] = Field(None, description="Cypher 查询参数")

    @validator('query_type')
    def validate_query_type(cls, v):
        """验证查询类型"""
        valid_types = ["document", "chunk", "hierarchy", "cypher"]
        if v not in valid_types:
            raise ValueError(f"无效的查询类型: {v}。支持的查询类型: {', '.join(valid_types)}")
        return v

    @validator('cypher_query')
    def validate_cypher_query(cls, v, values):
        """验证 Cypher 查询"""
        if values.get('query_type') == 'cypher' and not v:
            raise ValueError("当 query_type 为 'cypher' 时，cypher_query 字段必填")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "query": "000001",
                "query_type": "document",
                "filters": {
                    "stock_code": "000001",
                    "year": 2023,
                    "doc_type": "annual_reports"
                },
                "top_k": 10
            }
        }


class HybridRetrievalRequest(BaseModel):
    """混合检索请求模型（可选）"""
    query: str = Field(..., description="查询文本", min_length=1, max_length=2000)
    filters: Optional[FilterParams] = Field(None, description="过滤条件")
    top_k: int = Field(10, ge=1, le=100, description="返回数量")
    hybrid_weights: Optional[Dict[str, float]] = Field(
        None,
        description="混合检索权重（vector, fulltext, graph）。默认值：vector=0.5, fulltext=0.3, graph=0.2"
    )

    @validator('hybrid_weights')
    def validate_hybrid_weights(cls, v):
        """验证混合检索权重"""
        if v is None:
            return {"vector": 0.5, "fulltext": 0.3, "graph": 0.2}
        
        valid_keys = ["vector", "fulltext", "graph"]
        invalid_keys = [k for k in v.keys() if k not in valid_keys]
        if invalid_keys:
            raise ValueError(f"无效的权重键: {invalid_keys}。支持的键: {', '.join(valid_keys)}")
        
        # 验证权重值范围
        for key, weight in v.items():
            if not (0.0 <= weight <= 1.0):
                raise ValueError(f"权重值必须在 0.0 到 1.0 之间: {key}={weight}")
        
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "query": "平安银行营业收入",
                "filters": {
                    "year": 2023,
                    "doc_type": ["annual_reports", "quarterly_reports"]
                },
                "top_k": 10,
                "hybrid_weights": {
                    "vector": 0.5,
                    "fulltext": 0.3,
                    "graph": 0.2
                }
            }
        }


class RetrievalResultResponse(BaseModel):
    """检索结果响应模型"""
    chunk_id: str = Field(..., description="分块ID")
    document_id: str = Field(..., description="文档ID")
    chunk_text: str = Field(..., description="分块文本")
    title: Optional[str] = Field(None, description="标题")
    title_level: Optional[int] = Field(None, description="标题层级")
    score: float = Field(..., ge=0.0, le=1.0, description="相似度分数（0-1）")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="元数据（股票代码、公司名称、文档类型、年份、季度等）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "chunk_id": "123e4567-e89b-12d3-a456-426614174000",
                "document_id": "123e4567-e89b-12d3-a456-426614174001",
                "chunk_text": "2023年第三季度，公司实现营业收入XXX亿元...",
                "title": "一、公司基本情况",
                "title_level": 1,
                "score": 0.95,
                "metadata": {
                    "stock_code": "000001",
                    "company_name": "平安银行",
                    "doc_type": "quarterly_reports",
                    "year": 2023,
                    "quarter": 3,
                    "market": "a_share",
                    "chunk_index": 0
                }
            }
        }


class RetrievalResponse(BaseModel):
    """检索响应模型"""
    results: List[RetrievalResultResponse] = Field(default_factory=list, description="检索结果列表")
    total: int = Field(0, description="总数量")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="元数据（检索时间、检索类型、查询参数等）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "results": [
                    {
                        "chunk_id": "123e4567-e89b-12d3-a456-426614174000",
                        "document_id": "123e4567-e89b-12d3-a456-426614174001",
                        "chunk_text": "2023年第三季度，公司实现营业收入XXX亿元...",
                        "title": "一、公司基本情况",
                        "title_level": 1,
                        "score": 0.95,
                        "metadata": {
                            "stock_code": "000001",
                            "company_name": "平安银行",
                            "doc_type": "quarterly_reports",
                            "year": 2023,
                            "quarter": 3
                        }
                    }
                ],
                "total": 1,
                "metadata": {
                    "retrieval_type": "vector",
                    "query": "平安银行2023年第三季度的营业收入",
                    "retrieval_time": 0.123,
                    "top_k": 5
                }
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


class StockCodeVoteResult(BaseModel):
    """股票代码投票结果"""
    stock_code: str = Field(..., description="股票代码")
    votes: int = Field(..., description="投票数（出现次数）")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度（投票数/总文档数）")


class CompanyNameSearchResponse(BaseModel):
    """根据公司名称搜索股票代码响应模型"""
    company_name: str = Field(..., description="查询的公司名称")
    stock_code: Optional[str] = Field(None, description="最可能的股票代码（投票最多的）")
    all_candidates: List[StockCodeVoteResult] = Field(
        default_factory=list,
        description="所有候选股票代码及其投票结果（按投票数降序）"
    )
    total_documents: int = Field(0, description="检索到的文档总数")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="元数据（检索时间、检索到的文档列表等）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "平安银行",
                "stock_code": "000001",
                "all_candidates": [
                    {
                        "stock_code": "000001",
                        "votes": 8,
                        "confidence": 0.8
                    },
                    {
                        "stock_code": "600000",
                        "votes": 2,
                        "confidence": 0.2
                    }
                ],
                "total_documents": 10,
                "metadata": {
                    "retrieval_time": 0.123,
                    "top_k": 10
                }
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


class RetrievalHealthResponse(BaseModel):
    """检索服务健康检查响应"""
    status: str = Field(..., description="状态（healthy/degraded/unhealthy）")
    message: str = Field(..., description="消息")
    components: Dict[str, str] = Field(
        default_factory=dict,
        description="组件状态（vector_retriever, fulltext_retriever, graph_retriever等）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "message": "Retrieval service is running",
                "components": {
                    "vector_retriever": "ok",
                    "fulltext_retriever": "ok",
                    "graph_retriever": "ok"
                }
            }
        }


class ChunkChildrenRequest(BaseModel):
    """查询 chunk 子节点请求模型"""
    chunk_id: str = Field(..., description="父分块 ID", min_length=1)

    class Config:
        json_schema_extra = {
            "example": {
                "chunk_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }


class ChunkChildResponse(BaseModel):
    """子节点响应模型"""
    chunk_id: str = Field(..., description="子分块 ID")
    title: Optional[str] = Field(None, description="子分块标题")

    class Config:
        json_schema_extra = {
            "example": {
                "chunk_id": "123e4567-e89b-12d3-a456-426614174001",
                "title": "第一章 公司基本情况"
            }
        }


class ChunkChildrenResponse(BaseModel):
    """查询 chunk 子节点响应模型"""
    children: List[ChunkChildResponse] = Field(default_factory=list, description="子节点列表")
    total: int = Field(0, description="子节点总数")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="元数据（查询时间、父 chunk_id 等）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "children": [
                    {
                        "chunk_id": "123e4567-e89b-12d3-a456-426614174001",
                        "title": "第一章 公司基本情况"
                    },
                    {
                        "chunk_id": "123e4567-e89b-12d3-a456-426614174002",
                        "title": "第二章 财务数据"
                    }
                ],
                "total": 2,
                "metadata": {
                    "parent_chunk_id": "123e4567-e89b-12d3-a456-426614174000",
                    "query_time": 0.012
                }
            }
        }
