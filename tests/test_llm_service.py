#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Service 单元测试
"""

import pytest
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.processing.ai.llm.llm_service import LLMService, get_llm_service


class TestLLMService:
    """LLMService 测试类"""

    @pytest.mark.skip(reason="需要配置 LLM API Key")
    def test_llm_service_init(self):
        """测试 LLMService 初始化"""
        # 注意：这个测试需要配置 LLM API Key
        try:
            service = LLMService()
            assert service is not None
            assert service.mode in ["cloud", "local"]
        except ValueError:
            # 如果没有配置 LLM，跳过测试
            pytest.skip("LLM 未配置")

    @pytest.mark.skip(reason="需要配置 LLM API Key")
    def test_generate(self):
        """测试文本生成（需要配置 LLM API Key）"""
        try:
            service = get_llm_service()
            answer = service.generate(
                prompt="什么是人工智能？",
                system_prompt="你是一个专业的AI助手。",
                temperature=0.7,
                max_tokens=200
            )
            
            assert isinstance(answer, str)
            assert len(answer) > 0
        except Exception:
            pytest.skip("LLM 服务不可用")

    def test_get_api_base(self):
        """测试获取 API 基础 URL"""
        service = LLMService.__new__(LLMService)  # 不调用 __init__
        
        assert service._get_api_base("openai") == "https://api.openai.com"
        assert service._get_api_base("deepseek") == "https://api.deepseek.com"
        assert service._get_api_base("dashscope") == "https://dashscope.aliyuncs.com"
        
        with pytest.raises(ValueError):
            service._get_api_base("unknown")
