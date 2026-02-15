# -*- coding: utf-8 -*-
"""
Job 1: 更新美股公司列表
从 SEC API 获取所有 13,000+ 上市公司，写入 us_listed_companies 表

功能：
1. 调用 SEC company_tickers.json API 获取公司列表
2. Upsert 到 us_listed_companies 表（code 为主键）
3. 返回新增/更新统计
"""
from datetime import datetime
from typing import Dict

from src.common.logger import get_logger
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import USListedCompany
from src.ingestion.us_stock.crawlers.sec_api_client import SECAPIClient

logger = get_logger(__name__)


def update_us_companies_job(force_refresh: bool = False) -> Dict:
    """
    更新美股公司列表

    从 SEC EDGAR API 获取所有上市公司（约 13,000+），
    写入 us_listed_companies 表。

    Args:
        force_refresh: 是否强制刷新（暂未使用，预留）

    Returns:
        {
            'total_companies': 13000,
            'companies_added': 500,
            'companies_updated': 12500,
            'duration_seconds': 45
        }
    """
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info("开始更新美股公司列表")
    logger.info("=" * 80)

    # 1. 从 SEC 获取公司列表
    sec_client = SECAPIClient()
    tickers_data = sec_client.fetch_company_tickers()

    total_from_api = len(tickers_data)
    logger.info(f"SEC API 返回公司数: {total_from_api}")

    # 2. Upsert 到数据库
    pg_client = get_postgres_client()
    companies_added = 0
    companies_updated = 0

    with pg_client.get_session() as session:
        for key, company_data in tickers_data.items():
            cik = str(company_data['cik_str']).zfill(10)
            code = company_data['ticker'].upper().strip()
            name = (company_data.get('title') or '').strip()

            if not code or not name:
                logger.debug(f"跳过无效记录: {company_data}")
                continue

            existing = session.query(USListedCompany).filter(
                USListedCompany.code == code
            ).first()

            if existing:
                # 更新
                existing.name = name
                existing.cik = cik
                existing.is_active = True
                existing.updated_at = datetime.now()
                companies_updated += 1
            else:
                # 新增
                company = USListedCompany(
                    code=code,
                    name=name,
                    cik=cik,
                    is_active=True
                )
                session.add(company)
                companies_added += 1

            # 批量提交
            if (companies_added + companies_updated) % 500 == 0:
                session.commit()
                logger.info(f"  已处理: 新增 {companies_added}, 更新 {companies_updated}")

        session.commit()

    # 3. 统计结果
    duration = (datetime.now() - start_time).total_seconds()
    total_companies = companies_added + companies_updated

    result = {
        'total_companies': total_companies,
        'companies_added': companies_added,
        'companies_updated': companies_updated,
        'duration_seconds': int(duration)
    }

    logger.info("=" * 80)
    logger.info("✅ 美股公司列表更新完成")
    logger.info(f"  总公司数: {result['total_companies']}")
    logger.info(f"  新增: {result['companies_added']}")
    logger.info(f"  更新: {result['companies_updated']}")
    logger.info(f"  耗时: {duration:.1f}秒")
    logger.info("=" * 80)

    return result


if __name__ == '__main__':
    """命令行直接运行（用于测试）"""
    result = update_us_companies_job()
    print(f"\n更新结果: {result}")
