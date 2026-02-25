# -*- coding: utf-8 -*-
"""测试 resolve_chunk_mode 根据市场与文档内容解析分块模式"""

import pytest
from src.processing.text.chunker import resolve_chunk_mode


def test_hs_stock_with_section():
    """hs_stock 文档包含 # 第X节 -> chinese"""
    content = "# 第一节 重要提示\n\n## 第二节 公司简介"
    assert resolve_chunk_mode("hs_stock", content) == "chinese"


def test_hs_stock_without_section():
    """hs_stock 文档不包含 # 第X节 -> simple"""
    content = "# 概述\n\n## 公司简介\n\n无第X节格式"
    assert resolve_chunk_mode("hs_stock", content) == "simple"


def test_hs_stock_section_with_digit():
    """hs_stock 文档包含 # 第1节 等数字格式 -> chinese"""
    content = "# 第1节 重要提示\n\n# 第2节 公司简介"
    assert resolve_chunk_mode("hs_stock", content) == "chinese"


def test_hk_stock_always_simple():
    """hk_stock 始终用 simple"""
    assert resolve_chunk_mode("hk_stock", "# 第一节 重要提示") == "simple"
    assert resolve_chunk_mode("hk_stock", "# PART I\n\nContent") == "simple"
    assert resolve_chunk_mode("hk_stock", "plain content") == "simple"


def test_us_stock_with_part():
    """us_stock 文档包含 # PART X -> english"""
    content = "# PART I\n\n## ITEM 1. Identity"
    assert resolve_chunk_mode("us_stock", content) == "english"


def test_us_stock_with_part_roman():
    """us_stock 文档包含 # PART II, PART III -> english"""
    content = "# PART II\n\n# PART III"
    assert resolve_chunk_mode("us_stock", content) == "english"


def test_us_stock_without_part():
    """us_stock 文档不包含 # PART X -> simple"""
    content = "# Overview\n\n## Company Info\n\nNo PART format"
    assert resolve_chunk_mode("us_stock", content) == "simple"


def test_empty_content():
    """空内容 -> simple"""
    assert resolve_chunk_mode("hs_stock", "") == "simple"
    assert resolve_chunk_mode("us_stock", "") == "simple"


def test_unknown_market():
    """未知市场 -> simple"""
    assert resolve_chunk_mode("other", "# 第一节") == "simple"
    assert resolve_chunk_mode("", "# PART I") == "simple"
