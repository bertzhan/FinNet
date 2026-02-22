# -*- coding: utf-8 -*-
"""
港股数据库辅助函数
"""

from typing import List, Dict, Optional

from src.storage.metadata import get_postgres_client, crud
from src.storage.metadata.models import HKListedCompany


def load_hk_company_list_from_db(
    limit: Optional[int] = None,
    stock_codes: Optional[List[str]] = None,
    with_org_id_only: bool = True,
    logger=None,
) -> List[Dict]:
    """
    从数据库加载港股公司列表

    Returns:
        公司列表 [{'code': '00001', 'name': '長和', 'org_id': 1}, ...]
    """
    if logger is None:
        import logging
        logger = logging.getLogger(__name__)

    companies = []
    try:
        pg_client = get_postgres_client()
        with pg_client.get_session() as session:
            if stock_codes:
                listed_companies = session.query(HKListedCompany).filter(
                    HKListedCompany.code.in_(stock_codes)
                ).all()
                logger.info(f"港股按股票代码过滤: 指定 {len(stock_codes)} 个代码，找到 {len(listed_companies)} 家公司")
            else:
                listed_companies = crud.get_all_hk_listed_companies(
                    session,
                    limit=limit,
                    with_org_id_only=with_org_id_only,
                )

            for company in listed_companies:
                companies.append({
                    "code": company.code,
                    "name": company.name,
                    "org_id": company.org_id,
                })

        logger.info(f"从数据库加载了 {len(companies)} 家港股公司")
    except Exception as e:
        logger.error(f"从数据库加载港股公司列表失败: {e}", exc_info=True)
        raise

    return companies
