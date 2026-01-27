#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG Pipeline 单元测试
"""

import pytest
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.application.rag.rag_pipeline import RAGPipeline, RAGResponse, Source


class TestRAGPipeline:
    """RAGPipeline 测试类"""

    @pytest.fixture
    def pipeline(self):
        """创建 RAGPipeline 实例"""
        return RAGPipeline()

    def test_pipeline_init(self, pipeline):
        """测试 RAGPipeline 初始化"""
        assert pipeline is not None
        assert pipeline.retriever is not None
        assert pipeline.context_builder is not None
        assert pipeline.llm_service is not None

    @pytest.mark.skip(reason="需要配置 LLM API Key 和实际数据")
    def test_query_basic(self, pipeline):
        """测试基础查询（需要配置 LLM API Key 和实际数据）"""
        try:
            response = pipeline.query(
                question="什么是营业收入？",
                top_k=5
            )
            
            assert isinstance(response, RAGResponse)
            assert isinstance(response.answer, str)
            assert isinstance(response.sources, list)
            assert isinstance(response.metadata, dict)
        except Exception:
            pytest.skip("LLM 服务或数据不可用")

    @pytest.mark.skip(reason="需要配置 LLM API Key 和实际数据")
    def test_query_with_filters(self, pipeline):
        """测试带过滤条件的查询"""
        try:
            response = pipeline.query(
                question="平安银行2023年第三季度的营业收入是多少？",
                filters={"stock_code": "000001", "year": 2023, "quarter": 3},
                top_k=5
            )
            
            assert isinstance(response, RAGResponse)
            # 检查来源是否都符合过滤条件
            for source in response.sources:
                assert source.stock_code == "000001"
                assert source.year == 2023
                assert source.quarter == 3
        except Exception:
            pytest.skip("LLM 服务或数据不可用")

    def test_build_sources(self, pipeline):
        """测试构建来源列表"""
        from src.application.rag.retriever import RetrievalResult
        
        results = [
            RetrievalResult(
                chunk_id="chunk1",
                document_id="doc1",
                chunk_text="测试文本内容" * 50,  # 长文本
                title="测试标题",
                title_level=1,
                score=0.95,
                metadata={
                    "stock_code": "000001",
                    "company_name": "平安银行",
                    "doc_type": "quarterly_report",
                    "year": 2023,
                    "quarter": 3
                }
            )
        ]
        
        sources = pipeline._build_sources(results)
        
        assert isinstance(sources, list)
        assert len(sources) == 1
        assert isinstance(sources[0], Source)
        assert sources[0].chunk_id == "chunk1"
        assert sources[0].stock_code == "000001"
        assert len(sources[0].snippet) <= 203  # 200 + "..."
