# -*- coding: utf-8 -*-
"""
API测试配置文件
包含测试公司、测试周期等通用配置
"""

# API基础URL
BASE_URL = "http://localhost:8000"

# 测试公司
TEST_COMPANIES = [
    {"name": "平安银行", "code": "000001"},
    {"name": "万科A", "code": "000002"},
    {"name": "神州高铁", "code": "000008"},
]

# 测试年份
TEST_YEAR = 2024

# 测试周期（覆盖四种报告类型）
TEST_CASES = [
    {"period": "Q1", "quarter": 1, "doc_type": "quarterly_reports"},
    {"period": "Q2", "quarter": 2, "doc_type": "interim_reports"},  # 半年报
    {"period": "Q3", "quarter": 3, "doc_type": "quarterly_reports"},
    {"period": "Year", "quarter": None, "doc_type": "annual_reports"},  # 年报
]

# 仅用于retrieval接口的测试（不测试年报，因为年报没有quarter字段）
RETRIEVAL_TEST_CASES = [
    {"period": "Q1", "quarter": 1, "doc_type": "quarterly_reports"},
    {"period": "Q2", "quarter": 2, "doc_type": "interim_reports"},
    {"period": "Q3", "quarter": 3, "doc_type": "quarterly_reports"},
]
