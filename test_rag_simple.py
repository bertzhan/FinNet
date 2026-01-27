#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的 RAG 组件测试脚本
不依赖外部服务，只测试代码逻辑
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("RAG 组件简单测试")
print("=" * 80)
print()

# 测试1: LLM Service URL 识别
print("测试1: LLM Service URL 识别")
print("-" * 80)

class TestLLMService:
    def _identify_provider_from_url(self, url: str) -> str:
        url_lower = url.lower()
        if "openai.com" in url_lower:
            return "openai"
        elif "deepseek.com" in url_lower:
            return "deepseek"
        elif "dashscope" in url_lower or "aliyuncs.com" in url_lower:
            return "dashscope"
        elif "localhost" in url_lower or "127.0.0.1" in url_lower:
            return "local"
        else:
            return "custom"

test_llm = TestLLMService()
test_cases = [
    ("https://api.openai.com", "openai"),
    ("https://api.deepseek.com", "deepseek"),
    ("http://localhost:8000", "local"),
    ("http://127.0.0.1:11434", "local"),
    ("https://custom-proxy.com", "custom"),
]

all_passed = True
for url, expected in test_cases:
    result = test_llm._identify_provider_from_url(url)
    status = "✅" if result == expected else "❌"
    print(f"  {status} {url} -> {result} (期望: {expected})")
    if result != expected:
        all_passed = False

print(f"\n测试1结果: {'通过' if all_passed else '失败'}\n")

# 测试2: ContextBuilder 基本功能
print("测试2: ContextBuilder 基本功能")
print("-" * 80)

from dataclasses import dataclass
from typing import Optional, Dict, Any, List

@dataclass
class MockRetrievalResult:
    chunk_id: str
    document_id: str
    chunk_text: str
    title: Optional[str]
    title_level: Optional[int]
    score: float
    metadata: Dict[str, Any]

class MockContextBuilder:
    def __init__(self, max_length: int = 4000):
        self.max_length = max_length

    def build_context(
        self,
        retrieval_results: List[MockRetrievalResult],
        max_length: Optional[int] = None
    ) -> str:
        max_len = max_length or self.max_length
        if not retrieval_results:
            return ""

        formatted_chunks = []
        current_length = 0

        for i, result in enumerate(retrieval_results):
            formatted_chunk = self._format_chunk(result, index=i + 1)
            chunk_length = len(formatted_chunk)

            if current_length + chunk_length > max_len:
                break

            formatted_chunks.append(formatted_chunk)
            current_length += chunk_length

        return "\n\n".join(formatted_chunks) if formatted_chunks else ""

    def _format_chunk(self, result: MockRetrievalResult, index: int) -> str:
        metadata = result.metadata
        company_name = metadata.get("company_name", "N/A")
        year = metadata.get("year", "N/A")

        lines = [f"文档{index}: {company_name} {year}年报告"]
        if result.title:
            lines.append(f"标题: {result.title}")
        lines.append("内容:")
        lines.append(result.chunk_text)
        return "\n".join(lines)

builder = MockContextBuilder(max_length=200)
results = [
    MockRetrievalResult(
        chunk_id="1",
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
    MockRetrievalResult(
        chunk_id="2",
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

context = builder.build_context(results)
assert len(context) > 0, "上下文不应为空"
assert "平安银行" in context, "应包含公司名称"
assert "2023年" in context, "应包含年份"
assert "第一个分块" in context, "应包含第一个分块内容"
print(f"  ✅ 上下文生成成功，长度: {len(context)} 字符")
print(f"  ✅ 包含文档数: {context.count('文档')}")
print(f"  ✅ 包含公司名称: {'平安银行' in context}")
print(f"\n测试2结果: 通过\n")

# 测试3: Retriever 过滤表达式构建
print("测试3: Retriever 过滤表达式构建")
print("-" * 80)

def build_filter_expr(filters: Dict[str, Any]) -> Optional[str]:
    conditions = []
    if filters.get("stock_code"):
        stock_code = filters["stock_code"]
        conditions.append(f"stock_code == '{stock_code}'")
    if filters.get("year"):
        year = filters["year"]
        conditions.append(f"year == {year}")
    if filters.get("quarter"):
        quarter = filters["quarter"]
        conditions.append(f"quarter == {quarter}")
    return " and ".join(conditions) if conditions else None

test_filters = [
    ({"stock_code": "000001", "year": 2023}, "stock_code == '000001' and year == 2023"),
    ({"stock_code": "000001", "year": 2023, "quarter": 3}, "stock_code == '000001' and year == 2023 and quarter == 3"),
    ({}, None),
]

all_passed = True
for filters, expected in test_filters:
    result = build_filter_expr(filters)
    status = "✅" if result == expected else "❌"
    print(f"  {status} {filters} -> {result}")
    if result != expected:
        all_passed = False

print(f"\n测试3结果: {'通过' if all_passed else '失败'}\n")

# 测试4: 距离转相似度分数
print("测试4: 距离转相似度分数")
print("-" * 80)

def distance_to_score(distance: float) -> float:
    score = 1.0 / (1.0 + distance)
    return min(max(score, 0.0), 1.0)

test_distances = [
    (0.0, 1.0),
    (0.5, 1.0 / 1.5),
    (1.0, 0.5),
    (100.0, 1.0 / 101.0),
]

all_passed = True
for distance, expected in test_distances:
    result = distance_to_score(distance)
    # 允许小的浮点误差
    passed = abs(result - expected) < 0.0001
    status = "✅" if passed else "❌"
    print(f"  {status} distance={distance} -> score={result:.4f} (期望: {expected:.4f})")
    if not passed:
        all_passed = False

print(f"\n测试4结果: {'通过' if all_passed else '失败'}\n")

print("=" * 80)
print("所有测试完成!")
print("=" * 80)
