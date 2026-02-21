# -*- coding: utf-8 -*-
"""
财年/季度解析单元测试 (_parse_fiscal_period)
"""
import pytest
from datetime import date

from src.ingestion.us_stock.jobs.crawl_us_reports_job import _parse_fiscal_period


# ==================== 10-K 年报 ====================

def test_10k_nvda_jan_year_end():
    """NVDA 1月年结：report_date=2025-01-26 应为 FY2024"""
    f = {'form_type': '10-K', 'report_date': date(2025, 1, 26), 'filing_date': date(2025, 2, 26)}
    y, q = _parse_fiscal_period(f, '0125')
    assert y == 2024 and q is None


def test_10k_aapl_sep_year_end():
    """AAPL 9月年结：report_date=2026-09-30 应为 FY2026"""
    f = {'form_type': '10-K', 'report_date': date(2026, 9, 30), 'filing_date': date(2026, 10, 1)}
    y, q = _parse_fiscal_period(f, '0926')
    assert y == 2026 and q is None


def test_10k_calendar_year_end():
    """日历年 12/31：report_date=2024-12-31 应为 FY2024"""
    f = {'form_type': '10-K', 'report_date': date(2024, 12, 31), 'filing_date': date(2025, 1, 15)}
    y, q = _parse_fiscal_period(f, '1231')
    assert y == 2024 and q is None


def test_10k_feb_year_end():
    """2月年结：report_date=2025-02-28 应为 FY2024"""
    f = {'form_type': '10-K', 'report_date': date(2025, 2, 28), 'filing_date': date(2025, 3, 1)}
    y, q = _parse_fiscal_period(f, '0228')
    assert y == 2024 and q is None


# ==================== 10-Q 季报 ====================

def test_10q_nvda_jan_year_end():
    """NVDA 1月年结：Apr/Jul/Oct 的 10-Q 应为当年"""
    for month, exp_q in [(4, 1), (7, 2), (10, 3)]:
        f = {'form_type': '10-Q', 'report_date': date(2025, month, 28), 'filing_date': date(2025, month + 1, 1)}
        y, q = _parse_fiscal_period(f, '0125')
        assert y == 2025 and q == exp_q, f"month={month} failed: got {y} Q{q}"


def test_10q_aapl_sep_year_end():
    """AAPL 9月年结：Dec 2025=2026Q1, Mar/Jun 2026=2026Q2/Q3"""
    tests = [(date(2025, 12, 27), 2026, 1), (date(2026, 3, 28), 2026, 2), (date(2026, 6, 29), 2026, 3)]
    for rdate, exp_y, exp_q in tests:
        f = {'form_type': '10-Q', 'report_date': rdate, 'filing_date': rdate}
        y, q = _parse_fiscal_period(f, '0926')
        assert y == exp_y and q == exp_q, f"rdate={rdate} failed: got {y} Q{q}"


def test_10q_msft_jun_year_end():
    """MSFT 6月年结：Sep 2025=2026Q1, Dec 2025=2026Q2"""
    f1 = {'form_type': '10-Q', 'report_date': date(2025, 9, 30), 'filing_date': date(2025, 10, 1)}
    y1, q1 = _parse_fiscal_period(f1, '0630')
    assert y1 == 2026 and q1 == 1

    f2 = {'form_type': '10-Q', 'report_date': date(2025, 12, 31), 'filing_date': date(2026, 1, 1)}
    y2, q2 = _parse_fiscal_period(f2, '0630')
    assert y2 == 2026 and q2 == 2


def test_10q_calendar_year_end():
    """日历年 12/31：Mar/Jun/Sep 2026 应为 2026 Q1/Q2/Q3"""
    for month, exp_q in [(3, 1), (6, 2), (9, 3)]:
        f = {'form_type': '10-Q', 'report_date': date(2026, month, 30), 'filing_date': date(2026, month + 1, 1)}
        y, q = _parse_fiscal_period(f, '1231')
        assert y == 2026 and q == exp_q
