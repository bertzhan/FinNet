#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG ContextBuilder 单元测试
"""

import pytest
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.application.rag.context_builder import ContextBuilder
from src.application.rag.retriever import RetrievalResult


class TestContextBuilder:
    """ContextBuilder 测试类"""

    @pytest.fixture
    def builder(self):
        """创建 ContextBuilder 实例"""
        return ContextBuilder(max_length=1000)

    @pytest.fixture
    def sample_results(self):
        """创建示例检索结果"""
        return [
            RetrievalResult(
                chunk_id="chunk1",
                document_id="doc1",
                chunk_text="这是第一个分块的文本内容。",
                title="一、公司基本情况",
                title_level=1,
                score=0.95,
                metadata={
                    "stock_code": "000001",
                    "company_name": "平安银行",
                    "doc_type": "quarterly_report",
                    "year": 2023,
                    "quarter": 3
                }
            ),
            RetrievalResult(
                chunk_id="chunk2",
                document_id="doc1",
                chunk_text="这是第二个分块的文本内容，包含更多信息。",
                title="二、主要财务数据",
                title_level=1,
                score=0.90,
                metadata={
                    "stock_code": "000001",
                    "company_name": "平安银行",
                    "doc_type": "quarterly_report",
                    "year": 2023,
                    "quarter": 3
                }
            )
        ]

    def test_builder_init(self, builder):
        """测试 ContextBuilder 初始化"""
        assert builder is not None
        assert builder.max_length == 1000

    def test_build_context(self, builder, sample_results):
        """测试上下文构建"""
        context = builder.build_context(sample_results)
        
        assert isinstance(context, str)
        assert len(context) > 0
        # 检查是否包含文档信息
        assert "平安银行" in context
        assert "2023年" in context
        # 检查是否包含分块内容
        assert "第一个分块" in context
        assert "第二个分块" in context

    def test_build_context_empty(self, builder):
        """测试空结果"""
        context = builder.build_context([])
        assert context == ""

    def test_format_chunks(self, builder, sample_results):
        """测试格式化分块"""
        formatted = builder.format_chunks(sample_results)
        
        assert isinstance(formatted, list)
        assert len(formatted) == 2
        assert all(isinstance(chunk, str) for chunk in formatted)

    def test_add_metadata(self, builder, sample_results):
        """测试添加元数据"""
        context = builder.build_context(sample_results)
        context_with_metadata = builder.add_metadata(context, sample_results)
        
        assert len(context_with_metadata) > len(context)
        assert "文档来源信息" in context_with_metadata
