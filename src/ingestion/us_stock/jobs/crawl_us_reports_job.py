# -*- coding: utf-8 -*-
"""
Job 2: 爬取SEC财报
从us_listed_companies表读取公司，爬取10-K/10-Q等财报

功能：
1. 查询us_listed_companies获取目标公司列表
2. 对每个公司调用SEC API获取财报列表
3. 过滤已存在的文档（通过source_url去重）
4. 创建CrawlTask列表
5. 批量执行爬虫
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import text

from src.common.logger import get_logger
from src.common.constants import Market, DocType
from src.storage.metadata.postgres_client import get_postgres_client
from src.ingestion.base.base_crawler import CrawlTask
from src.ingestion.us_stock.crawlers.sec_api_client import SECAPIClient
from src.ingestion.us_stock.crawlers.sec_filings_crawler import SECFilingsCrawler

logger = get_logger(__name__)


# 表单类型映射（SEC表单类型 -> DocType枚举）
FORM_TYPE_MAPPING = {
    '10-K': DocType.FORM_10K,
    '10-K/A': DocType.FORM_10K,  # 修正版
    '10-Q': DocType.FORM_10Q,
    '10-Q/A': DocType.FORM_10Q,
    '20-F': DocType.FORM_20F,
    '20-F/A': DocType.FORM_20F,
    '40-F': DocType.FORM_40F,
    '40-F/A': DocType.FORM_40F,
    '6-K': DocType.FORM_6K,
    '6-K/A': DocType.FORM_6K,
}


def crawl_us_reports_job(
    mode: str = "incremental",
    limit: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    tickers: Optional[List[str]] = None,
    enable_minio: bool = True,
    enable_postgres: bool = True,
) -> Dict:
    """
    爬取SEC财报

    Args:
        mode: 模式
            - 'incremental': 增量更新（最近7天）
            - 'backfill': 回填（指定日期范围）
        limit: 限制公司数量（用于测试）
        start_date: 开始日期（回填模式，格式：'2023-01-01'）
        end_date: 结束日期（回填模式，格式：'2024-12-31'）
        tickers: 指定股票代码列表（如：['AAPL', 'MSFT']）

    Returns:
        {
            'companies_processed': 100,
            'filings_discovered': 500,
            'filings_downloaded': 480,
            'filings_failed': 20,
            'duration_seconds': 1800
        }
    """
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info(f"开始爬取SEC财报（模式: {mode}）")
    logger.info("=" * 80)

    # 1. 确定日期范围
    if mode == "incremental":
        # 增量模式：最近7天
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=7)
        start_date = start_dt.strftime('%Y-%m-%d')
        end_date = end_dt.strftime('%Y-%m-%d')
        logger.info(f"增量模式：日期范围 {start_date} 到 {end_date}")
    elif mode == "backfill":
        # 回填模式：使用提供的日期
        if not start_date or not end_date:
            start_date = "2023-01-01"
            end_date = datetime.now().strftime('%Y-%m-%d')
        logger.info(f"回填模式：日期范围 {start_date} 到 {end_date}")
    else:
        raise ValueError(f"不支持的模式: {mode}")

    # 2. 确定表单类型（固定为所有主要表单）
    form_types = ['10-K', '10-Q', '20-F', '40-F']
    logger.info(f"表单类型: {form_types}")

    # 3. 查询目标公司列表
    logger.info("步骤1: 查询目标公司列表...")
    companies = _get_target_companies(
        tickers=tickers,
        limit=limit
    )
    logger.info(f"目标公司数: {len(companies)}")

    # 4. 初始化爬虫
    sec_client = SECAPIClient()
    crawler = SECFilingsCrawler(
        enable_minio=enable_minio,
        enable_postgres=enable_postgres,
        download_images=True  # 下载并上传 HTML 中的图片到 MinIO
    )

    # 5. 爬取财报
    logger.info("步骤2: 开始爬取财报...")
    filings_discovered = 0
    filings_downloaded = 0
    filings_failed = 0
    filings_skipped = 0

    for idx, company in enumerate(companies, 1):
        ticker = company['code']
        company_name = company['name']
        cik = company['cik']

        logger.info(f"\n[{idx}/{len(companies)}] 处理公司: {ticker} ({company_name})")

        try:
            # 5.1 获取公司的所有提交记录
            submissions_data = sec_client.fetch_company_submissions(cik=cik)

            # 5.2 解析财报列表
            filings = sec_client.parse_filings(
                submissions_data=submissions_data,
                form_types=form_types,
                start_date=datetime.strptime(start_date, '%Y-%m-%d'),
                end_date=datetime.strptime(end_date, '%Y-%m-%d')
            )

            filings_discovered += len(filings)
            logger.info(f"  发现财报数: {len(filings)}")

            if not filings:
                continue

            # 5.3 创建爬取任务
            tasks = []
            for filing in filings:
                # 检查是否已存在（通过source_url去重）
                accession = filing['accession_number']
                source_url = sec_client.construct_primary_html_url(
                    cik=cik,
                    accession=accession,
                    primary_document=filing['primary_document']
                )

                if _document_exists(source_url):
                    filings_skipped += 1
                    logger.debug(f"  跳过已存在: {accession}")
                    continue

                # 映射表单类型到DocType
                form_type = filing['form_type']
                doc_type = FORM_TYPE_MAPPING.get(form_type)
                if not doc_type:
                    logger.warning(f"  未知表单类型: {form_type}，跳过")
                    continue

                # 确定年份和季度（使用公司财年结束日正确映射季度）
                fiscal_year_end = submissions_data.get('fiscalYearEnd') or '1231'
                year, quarter = _parse_fiscal_period(filing, fiscal_year_end=fiscal_year_end)

                # 创建任务
                task = CrawlTask(
                    stock_code=ticker,
                    company_name=company_name,
                    market=Market.US_STOCK,
                    doc_type=doc_type,
                    year=year,
                    quarter=quarter,
                    metadata={
                        'accession_number': accession,
                        'primary_document': filing['primary_document'],
                        'filing_date': filing['filing_date'],
                        'cik': cik
                    }
                )
                tasks.append(task)

            # 5.4 批量爬取
            if tasks:
                logger.info(f"  开始爬取 {len(tasks)} 个财报...")
                results = crawler.crawl_batch(tasks)

                # 统计结果
                for result in results:
                    if result.success:
                        filings_downloaded += 1
                    else:
                        filings_failed += 1

                logger.info(
                    f"  完成: 成功 {sum(1 for r in results if r.success)}, "
                    f"失败 {sum(1 for r in results if not r.success)}"
                )

        except Exception as e:
            logger.error(
                f"处理公司失败: {ticker}",
                extra={
                    "ticker": ticker,
                    "cik": cik,
                    "error": str(e)
                },
                exc_info=True
            )
            continue

    # 6. 统计结果
    duration = (datetime.now() - start_time).total_seconds()

    result = {
        'companies_processed': len(companies),
        'filings_discovered': filings_discovered,
        'filings_downloaded': filings_downloaded,
        'filings_failed': filings_failed,
        'filings_skipped': filings_skipped,
        'duration_seconds': int(duration)
    }

    logger.info("=" * 80)
    logger.info("✅ SEC财报爬取完成")
    logger.info(f"  处理公司数: {result['companies_processed']}")
    logger.info(f"  发现财报数: {result['filings_discovered']}")
    logger.info(f"  下载成功: {result['filings_downloaded']}")
    logger.info(f"  下载失败: {result['filings_failed']}")
    logger.info(f"  已跳过: {result['filings_skipped']}")
    logger.info(f"  耗时: {duration:.1f}秒")
    logger.info("=" * 80)

    return result


def _get_target_companies(
    tickers: Optional[List[str]] = None,
    limit: Optional[int] = None
) -> List[Dict]:
    """
    查询目标公司列表

    Args:
        tickers: 指定股票代码列表
        limit: 限制数量

    Returns:
        公司信息列表 [{'code': 'AAPL', 'name': 'Apple Inc.', 'cik': '0000320193'}, ...]
    """
    pg_client = get_postgres_client()

    # 构造SQL
    sql = "SELECT code, name, cik FROM us_listed_companies WHERE is_active = true"

    params = {}

    # 条件：指定股票代码
    if tickers:
        sql += " AND code = ANY(:tickers)"
        params['tickers'] = tickers

    # 排序和限制
    sql += " ORDER BY code"
    if limit:
        sql += " LIMIT :limit"
        params['limit'] = limit

    # 执行查询
    with pg_client.get_session() as session:
        result = session.execute(text(sql), params)
        companies = [
            {'code': row[0], 'name': row[1], 'cik': row[2]}
            for row in result
        ]

    return companies


def _document_exists(source_url: str) -> bool:
    """
    检查文档是否已存在（通过source_url去重）

    Args:
        source_url: 文档来源URL

    Returns:
        True表示已存在
    """
    pg_client = get_postgres_client()

    sql = text("SELECT 1 FROM documents WHERE source_url = :source_url LIMIT 1")

    with pg_client.get_session() as session:
        result = session.execute(sql, {'source_url': source_url})
        return result.fetchone() is not None


def _parse_fiscal_period(
    filing: Dict,
    fiscal_year_end: str = '1231'
) -> tuple:
    """
    从财报元数据解析财年和季度

    根据公司财年结束日（fiscalYearEnd）正确映射 10-Q 的季度和财年，解决非日历年公司
    （如 AAPL 财年 9 月结束、NVDA 财年 1 月结束）的季度/年份错配问题。

    Args:
        filing: 财报元数据字典
        fiscal_year_end: SEC fiscalYearEnd 格式 "MMDD"，如 "0926"=9 月 26 日,
                        "1231"=12 月 31 日, "0125"=1 月 25 日

    Returns:
        (year, quarter) 元组，year 为财年（如 FY2026）
    """
    report_date = filing.get('report_date')
    form_type = filing['form_type']

    if '10-K' in form_type or '20-F' in form_type or '40-F' in form_type:
        # 年报：report_date 为财年结束日，财年命名规则：
        # - 财年结束于 4-12 月（如 12/31、9/30）→ 财年 = report_date.year
        # - 财年结束于 1-3 月（如 NVDA 1/25）→ 财年 = report_date.year - 1
        #   例：NVDA 10-K report_date=2025-01-26，财年主体在 2024，应为 FY2024
        quarter = None
        if report_date:
            fye_month = int(fiscal_year_end[:2]) if len(fiscal_year_end) >= 2 else 12
            if fye_month <= 3:
                year = report_date.year - 1
            else:
                year = report_date.year
        else:
            year = filing['filing_date'].year
    elif '10-Q' in form_type:
        # 季报：需根据 fiscal_year_end 推断财年和季度
        # 财年命名：FY2026 表示该财年结束于 2026 年
        # 例：AAPL 财年 9 月结束，Dec 2025 的 10-Q 是 FY2026 Q1（非 2025 Q1）
        if report_date:
            fye_month = int(fiscal_year_end[:2]) if len(fiscal_year_end) >= 2 else 12
            fy_start_month = (fye_month % 12) + 1
            month = report_date.month

            # Q1/Q2/Q3 的 report_date 结束月份（1-12）
            q1_end = ((fy_start_month + 2 - 1) % 12) + 1
            q2_end = ((fy_start_month + 5 - 1) % 12) + 1
            q3_end = ((fy_start_month + 8 - 1) % 12) + 1

            if month == q1_end:
                quarter = 1
            elif month == q2_end:
                quarter = 2
            elif month == q3_end:
                quarter = 3
            else:
                dist_q1 = min(abs(month - q1_end), 12 - abs(month - q1_end))
                dist_q2 = min(abs(month - q2_end), 12 - abs(month - q2_end))
                dist_q3 = min(abs(month - q3_end), 12 - abs(month - q3_end))
                min_dist = min(dist_q1, dist_q2, dist_q3)
                if min_dist <= 1:
                    quarter = 1 if dist_q1 == min_dist else (2 if dist_q2 == min_dist else 3)
                else:
                    logger.warning(
                        f"无法从 report_date.month={month} 推断季度 (fye={fiscal_year_end})，默认 Q1"
                    )
                    quarter = 1

            # 财年计算（需区分两类公司）：
            # 1) fye_month <= 3（1-3 月年结，如 NVDA）：10-Q 的 report_date 在 4/7/10 月，均 > fye_month，
            #    但财年主体在 report_date.year（例：NVDA Apr 2025 = FY2025 Q1）
            # 2) fye_month > 3（4-12 月年结，如 AAPL）：month > fye_month 表示下一财年的 Q1/Q2/Q3
            #    例：AAPL Dec 2025 (month=12>9) → FY2026 Q1
            if fye_month <= 3:
                year = report_date.year
            elif month > fye_month:
                year = report_date.year + 1
            else:
                year = report_date.year
        else:
            year = filing['filing_date'].year
            quarter = 1
    else:
        quarter = None
        if report_date:
            year = report_date.year
        else:
            year = filing['filing_date'].year

    return year, quarter


if __name__ == '__main__':
    """命令行直接运行（用于测试）"""
    import sys

    # 示例：测试爬取3家公司的最近财报
    result = crawl_us_reports_job(
        mode='incremental',
        limit=3,
        tickers=['AAPL', 'MSFT', 'GOOGL'] if len(sys.argv) == 1 else None
    )
    print(f"\n爬取结果: {result}")
