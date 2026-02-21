#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试多家公司的财年/季度解析逻辑

用法：
    python scripts/test_fiscal_period_companies.py              # 测试默认公司列表
    python scripts/test_fiscal_period_companies.py AAPL NVDA MSFT  # 指定公司

从 SEC API 拉取真实财报数据，验证 _parse_fiscal_period 的解析结果。
"""
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 默认测试公司（覆盖不同财年结束月：1月、9月、12月等）
DEFAULT_TICKERS = ['AAPL', 'NVDA', 'MSFT', 'GOOGL', 'META', 'AMZN', 'TSLA', 'JPM']


def fetch_and_test(tickers: list[str], limit_per_company: int = 5):
    """从 SEC 获取真实财报，测试财年解析"""
    from src.ingestion.us_stock.crawlers.sec_api_client import SECAPIClient
    from src.ingestion.us_stock.jobs.crawl_us_reports_job import _parse_fiscal_period
    from src.storage.metadata.postgres_client import get_postgres_client
    from sqlalchemy import text

    sec_client = SECAPIClient()
    pg = get_postgres_client()

    # 获取公司 CIK
    with pg.get_session() as session:
        result = session.execute(
            text("SELECT code, cik FROM us_listed_companies WHERE code = ANY(:codes)"),
            {"codes": tickers}
        )
        companies = {row[0]: row[1] for row in result}

    missing = [t for t in tickers if t not in companies]
    if missing:
        print(f"⚠️ 未找到公司: {missing}，请先运行 update_us_companies_job")
        tickers = [t for t in tickers if t in companies]

    form_types = ['10-K', '10-Q']
    all_results = []

    for ticker in tickers:
        cik = companies[ticker]
        try:
            data = sec_client.fetch_company_submissions(cik=cik)
        except Exception as e:
            print(f"❌ {ticker}: 获取 SEC 数据失败 - {e}")
            continue

        fye = data.get('fiscalYearEnd') or '1231'
        recent = data.get('filings', {}).get('recent', {})
        if not recent:
            print(f"⚠️ {ticker}: 无 filings 数据")
            continue

        count = 0
        for i in range(len(recent.get('form', []))):
            if count >= limit_per_company:
                break
            form = recent['form'][i]
            if not any(ft in form for ft in form_types) or form.endswith('/A'):
                continue

            rdate_str = recent.get('reportDate', [None] * 10000)[i]
            fdate_str = recent.get('filingDate', [None] * 10000)[i]
            if not rdate_str:
                continue

            try:
                report_date = datetime.strptime(rdate_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                continue

            filing = {
                'form_type': form,
                'report_date': report_date,
                'filing_date': datetime.strptime(fdate_str, '%Y-%m-%d').date() if fdate_str else report_date,
            }
            year, quarter = _parse_fiscal_period(filing, fiscal_year_end=fye)

            q_str = f"Q{quarter}" if quarter else "FY"
            all_results.append({
                'ticker': ticker,
                'fye': fye,
                'form': form,
                'report_date': rdate_str,
                'parsed': f"{year} {q_str}",
            })
            count += 1

    return all_results


def main():
    tickers = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_TICKERS
    tickers = [t.upper() for t in tickers]

    print("=" * 90)
    print(f"财年/季度解析测试 - 公司: {', '.join(tickers)}")
    print("=" * 90)

    results = fetch_and_test(tickers, limit_per_company=6)

    # 按公司分组输出
    by_ticker = {}
    for r in results:
        by_ticker.setdefault(r['ticker'], []).append(r)

    for ticker in tickers:
        if ticker not in by_ticker:
            print(f"\n{ticker}: 无数据")
            continue
        rows = by_ticker[ticker]
        fye = rows[0]['fye'] if rows else '-'
        print(f"\n{ticker} (fiscalYearEnd={fye})")
        print("-" * 70)
        for r in rows:
            print(f"  {r['form']:8} report_date={r['report_date']}  →  {r['parsed']}")
        print()

    print("=" * 90)
    print(f"共解析 {len(results)} 条财报，请人工核对上述结果是否符合预期")
    print("=" * 90)


if __name__ == '__main__':
    main()
