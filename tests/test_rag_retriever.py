#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG Retriever 单元测试
"""

import pytest
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.application.rag.retriever import Retriever, RetrievalResult


class TestRetriever:
    """Retriever 测试类"""

    @pytest.fixture
    def retriever(self):
        """创建 Retriever 实例"""
        return Retriever()

    def test_retriever_init(self, retriever):
        """测试 Retriever 初始化"""
        assert retriever is not None
        assert retriever.collection_name == "financial_documents"
        assert retriever.embedder is not None
        assert retriever.milvus_client is not None
        assert retriever.pg_client is not None

    def test_build_filter_expr(self, retriever):
        """测试过滤表达式构建"""
        # 测试基本过滤
        filters = {"stock_code": "000001", "year": 2023}
        expr = retriever._build_filter_expr(filters)
        assert "stock_code == '000001'" in expr
        assert "year == 2023" in expr

        # 测试季度过滤
        filters = {"stock_code": "000001", "year": 2023, "quarter": 3}
        expr = retriever._build_filter_expr(filters)
        assert "quarter == 3" in expr

        # 测试空过滤
        expr = retriever._build_filter_expr({})
        assert expr is None

    def test_distance_to_score(self, retriever):
        """测试距离转相似度分数"""
        # 距离为0，相似度应该为1
        score = retriever._distance_to_score(0.0)
        assert score == 1.0

        # 距离越大，相似度越小
        score1 = retriever._distance_to_score(0.5)
        score2 = retriever._distance_to_score(1.0)
        assert score1 > score2

        # 分数应该在 [0, 1] 范围内
        score = retriever._distance_to_score(100.0)
        assert 0.0 <= score <= 1.0

    @pytest.mark.integration
    def test_retrieve_basic(self, retriever):
        """测试基础检索功能（需要实际数据）"""
        # 注意：这个测试需要 Milvus 和 PostgreSQL 中有实际数据
        results = retriever.retrieve("营业收入", top_k=5)
        
        # 检查返回类型
        assert isinstance(results, list)
        
        # 如果返回结果，检查结构
        if results:
            assert isinstance(results[0], RetrievalResult)
            assert results[0].chunk_id is not None
            assert results[0].chunk_text is not None
            assert 0.0 <= results[0].score <= 1.0

    @pytest.mark.integration
    def test_retrieve_with_filters(self, retriever):
        """测试带过滤条件的检索（需要实际数据）"""
        filters = {"stock_code": "000001", "year": 2023}
        results = retriever.retrieve("营业收入", top_k=5, filters=filters)
        
        # 检查返回类型
        assert isinstance(results, list)
        
        # 如果返回结果，检查过滤条件
        if results:
            for result in results:
                assert result.metadata.get("stock_code") == "000001"
                assert result.metadata.get("year") == 2023
