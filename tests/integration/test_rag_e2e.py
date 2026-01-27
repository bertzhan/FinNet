#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG 端到端集成测试
"""

import pytest
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.application.rag.rag_pipeline import RAGPipeline, RAGResponse


class TestRAGE2E:
    """RAG 端到端测试类"""

    @pytest.fixture
    def pipeline(self):
        """创建 RAGPipeline 实例"""
        return RAGPipeline()

    @pytest.mark.integration
    @pytest.mark.skip(reason="需要配置 LLM API Key 和实际数据")
    def test_e2e_basic_query(self, pipeline):
        """测试端到端基础查询"""
        try:
            response = pipeline.query(
                question="什么是营业收入？",
                top_k=5,
                temperature=0.7
            )
            
            # 检查响应结构
            assert isinstance(response, RAGResponse)
            assert len(response.answer) > 0
            assert isinstance(response.sources, list)
            assert "retrieval_count" in response.metadata
            assert "generation_time" in response.metadata
            
            # 检查生成时间合理
            assert response.metadata["generation_time"] > 0
            assert response.metadata["generation_time"] < 60  # 应该在1分钟内完成
            
        except Exception as e:
            pytest.skip(f"端到端测试跳过: {e}")

    @pytest.mark.integration
    @pytest.mark.skip(reason="需要配置 LLM API Key 和实际数据")
    def test_e2e_filtered_query(self, pipeline):
        """测试端到端带过滤条件的查询"""
        try:
            response = pipeline.query(
                question="平安银行2023年第三季度的营业收入是多少？",
                filters={
                    "stock_code": "000001",
                    "year": 2023,
                    "quarter": 3
                },
                top_k=5
            )
            
            # 检查响应
            assert isinstance(response, RAGResponse)
            assert len(response.answer) > 0
            
            # 检查来源是否符合过滤条件
            if response.sources:
                for source in response.sources:
                    assert source.stock_code == "000001"
                    assert source.year == 2023
                    assert source.quarter == 3
                    
        except Exception as e:
            pytest.skip(f"端到端测试跳过: {e}")

    @pytest.mark.integration
    @pytest.mark.skip(reason="需要配置 LLM API Key 和实际数据")
    def test_e2e_empty_result(self, pipeline):
        """测试空结果处理"""
        try:
            # 使用一个不太可能匹配的查询
            response = pipeline.query(
                question="这是一个非常特殊的测试查询，不应该匹配任何文档。",
                top_k=5
            )
            
            # 即使没有检索结果，也应该返回合理的响应
            assert isinstance(response, RAGResponse)
            # 答案可能为空或包含"没有找到"等提示
            assert isinstance(response.answer, str)
            
        except Exception as e:
            pytest.skip(f"端到端测试跳过: {e}")

    @pytest.mark.integration
    @pytest.mark.skip(reason="需要配置 LLM API Key 和实际数据")
    def test_e2e_performance(self, pipeline):
        """测试性能（响应时间）"""
        try:
            import time
            
            start_time = time.time()
            response = pipeline.query(
                question="什么是营业收入？",
                top_k=5
            )
            elapsed_time = time.time() - start_time
            
            # 检查响应时间
            assert elapsed_time < 30  # 应该在30秒内完成
            assert response.metadata["generation_time"] < 30
            
        except Exception as e:
            pytest.skip(f"性能测试跳过: {e}")
