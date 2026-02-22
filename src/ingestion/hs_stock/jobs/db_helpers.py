# -*- coding: utf-8 -*-
"""
A股数据库辅助函数
"""

from typing import List, Dict, Optional

from src.storage.metadata import get_postgres_client, crud
from src.storage.metadata.models import ListedCompany


def load_company_list_from_db(
    limit: Optional[int] = None,
    stock_codes: Optional[List[str]] = None,
    industry: Optional[str] = None,  # 已废弃，忽略（向后兼容测试）
    logger=None,
) -> List[Dict[str, str]]:
    """
    从数据库加载A股公司列表

    Returns:
        公司列表 [{'code': '000001', 'name': '平安银行'}, ...]
    """
    if logger is None:
        import logging
        logger = logging.getLogger(__name__)

    companies = []
    try:
        # 空列表明确表示不返回任何公司
        if stock_codes is not None and len(stock_codes) == 0:
            logger.info("股票代码列表为空，返回空结果")
            return []

        pg_client = get_postgres_client()
        with pg_client.get_session() as session:
            if stock_codes:
                listed_companies = session.query(ListedCompany).filter(
                    ListedCompany.code.in_(stock_codes)
                ).all()
                logger.info(f"按股票代码过滤: 指定 {len(stock_codes)} 个代码，找到 {len(listed_companies)} 家公司")
            else:
                listed_companies = crud.get_all_listed_companies(session, limit=limit)

            for company in listed_companies:
                companies.append({"code": company.code, "name": company.name})

        if stock_codes:
            logger.info(f"从数据库加载了 {len(companies)} 家公司（按股票代码: {stock_codes}）")
        else:
            logger.info(f"从数据库加载了 {len(companies)} 家公司")
    except Exception as e:
        logger.error(f"从数据库加载公司列表失败: {e}", exc_info=True)
        raise

    return companies
