# -*- coding: utf-8 -*-
"""
Job 1: 获取美股公司列表
从 SEC API 获取所有 13,000+ 上市公司，写入 us_listed_companies 表

功能：
1. 调用 SEC company_tickers.json API 获取公司列表
2. 调用 submissions API 获取 entityType、sic、exchanges 等详情
3. Upsert 到 us_listed_companies 表（org_id 为主键，同一 CIK 多 ticker 合并为一行）
4. 返回新增/更新统计
"""
from datetime import datetime
from typing import Dict, Any, Optional, Callable

from src.common.logger import get_logger
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.storage.metadata.models import USListedCompany
from src.ingestion.us_stock.crawlers.sec_api_client import SECAPIClient

logger = get_logger(__name__)


def _extract_submissions_fields(submissions: Dict) -> Dict[str, Any]:
    """
    从 SEC submissions API 响应中提取公司详情字段

    Args:
        submissions: fetch_company_submissions 返回的 JSON

    Returns:
        {entity_type, sic, industry, exchanges, fiscal_year_end, state_of_incorporation,
         state_of_incorporation_description, tickers}
    """
    result = {
        'entity_type': None,
        'sic': None,
        'industry': None,
        'exchanges': None,
        'fiscal_year_end': None,
        'state_of_incorporation': None,
        'state_of_incorporation_description': None,
        'tickers': None,
    }
    if not submissions:
        return result

    result['entity_type'] = (submissions.get('entityType') or '').strip() or None
    result['sic'] = (submissions.get('sic') or '').strip() or None
    result['industry'] = (submissions.get('sicDescription') or '').strip() or None
    result['fiscal_year_end'] = (submissions.get('fiscalYearEnd') or '').strip() or None
    result['state_of_incorporation'] = (submissions.get('stateOfIncorporation') or '').strip() or None
    result['state_of_incorporation_description'] = (submissions.get('stateOfIncorporationDescription') or '').strip() or None

    # exchanges: 数组转逗号分隔字符串
    exchanges_list = submissions.get('exchanges') or []
    if isinstance(exchanges_list, list) and exchanges_list:
        result['exchanges'] = ','.join(str(x).strip() for x in exchanges_list if x) or None
    elif exchanges_list:
        result['exchanges'] = str(exchanges_list).strip()

    # tickers: 数组转逗号分隔字符串，去重
    tickers_list = submissions.get('tickers') or []
    if isinstance(tickers_list, list) and tickers_list:
        result['tickers'] = ','.join(dict.fromkeys(str(x).strip() for x in tickers_list if x)) or None
    elif tickers_list:
        result['tickers'] = str(tickers_list).strip()

    return result


def get_us_companies_job(
    clear_before_update: bool = False,
    basic_info_only: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Dict:
    """
    获取美股公司列表

    从 SEC EDGAR API 获取所有上市公司（约 13,000+），
    写入 us_listed_companies 表。

    Args:
        clear_before_update: 是否在更新前清空表
        basic_info_only: 是否仅获取基础信息（code/name/org_id），跳过 submissions API
        progress_callback: 可选进度回调 (current, total, code) -> None，每 5% 或每 500 条调用

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
    logger.info("开始获取美股公司列表")
    logger.info("=" * 80)

    # 1. 从 SEC 获取公司列表
    sec_client = SECAPIClient()
    tickers_data = sec_client.fetch_company_tickers()

    total_from_api = len(tickers_data)
    logger.info(f"SEC API 返回公司数: {total_from_api}")

    # 2. 按 org_id 分组（同一 CIK 可对应多个 ticker）
    org_id_to_data: Dict[str, Dict] = {}
    for key, company_data in tickers_data.items():
        org_id = str(company_data['cik_str']).zfill(10)
        code = company_data['ticker'].upper().strip()
        name = (company_data.get('title') or '').strip()

        if not code or not name:
            logger.debug(f"跳过无效记录: {company_data}")
            continue

        if org_id not in org_id_to_data:
            org_id_to_data[org_id] = {
                'codes': [],
                'name': name,
                'first_code': code,
            }
        org_id_to_data[org_id]['codes'].append(code)
        # 取第一个 ticker 的 name
        if len(org_id_to_data[org_id]['codes']) == 1:
            org_id_to_data[org_id]['name'] = name

    # 3. Upsert 到数据库（含 submissions 详情）
    pg_client = get_postgres_client()
    companies_added = 0
    companies_updated = 0
    submissions_cache = {}  # org_id -> extra_fields，避免同一 CIK 重复请求
    submissions_skipped = 0  # fiscal_year_end 已有值时跳过的 submissions 调用数

    if clear_before_update:
        with pg_client.get_session() as session:
            count = crud.clear_us_listed_companies_except_org_id(session)
            session.commit()
        logger.info(f"已清空 us_listed_companies 中 {count} 条记录的非主键字段（保留 org_id）")

    total_orgs = len(org_id_to_data)
    last_progress_pct = -1

    with pg_client.get_session() as session:
        for idx, (org_id, data) in enumerate(org_id_to_data.items()):
            codes = data['codes']
            code = codes[0]  # 主 ticker
            tickers_str = ','.join(sorted(set(codes)))
            name = data['name']

            # 先查 existing，用于判断是否需要拉取 submissions
            existing = session.get(USListedCompany, org_id)

            # 增量更新：fiscal_year_end 为空时拉取 submissions
            need_submissions = (
                existing is None  # 新公司
                or (existing and not (existing.fiscal_year_end or '').strip())  # fiscal_year_end 为空
            )

            if basic_info_only:
                extra_fields = {}
            elif need_submissions:
                if org_id not in submissions_cache:
                    try:
                        submissions = sec_client.fetch_company_submissions(cik=org_id)
                        submissions_cache[org_id] = _extract_submissions_fields(submissions)
                    except Exception as e:
                        logger.debug(f"获取 submissions 失败 {code}: {e}")
                        submissions_cache[org_id] = {}
                extra_fields = submissions_cache[org_id]
                # 若 submissions 返回 tickers，优先使用
                if extra_fields.get('tickers'):
                    tickers_str = extra_fields['tickers']
            else:
                # fiscal_year_end 已有值，沿用 DB 已有详情字段
                extra_fields = {
                    'entity_type': existing.entity_type,
                    'sic': existing.sic,
                    'industry': existing.industry,
                    'exchanges': existing.exchanges,
                    'fiscal_year_end': existing.fiscal_year_end,
                    'state_of_incorporation': existing.state_of_incorporation,
                    'state_of_incorporation_description': existing.state_of_incorporation_description,
                    'tickers': existing.tickers,
                } if existing else {}
                submissions_skipped += 1

            if existing:
                # 更新：code/tickers/name 始终更新；详情字段仅拉取过 submissions 时覆盖
                existing.code = code
                existing.tickers = tickers_str
                existing.name = name
                if not basic_info_only and need_submissions:
                    existing.entity_type = extra_fields.get('entity_type')
                    existing.sic = extra_fields.get('sic')
                    existing.industry = extra_fields.get('industry')
                    existing.exchanges = extra_fields.get('exchanges')
                    existing.fiscal_year_end = extra_fields.get('fiscal_year_end')
                    existing.state_of_incorporation = extra_fields.get('state_of_incorporation')
                    existing.state_of_incorporation_description = extra_fields.get('state_of_incorporation_description')
                existing.updated_at = datetime.now()
                companies_updated += 1
            else:
                # 新增
                company = USListedCompany(
                    org_id=org_id,
                    code=code,
                    tickers=tickers_str,
                    name=name,
                    entity_type=extra_fields.get('entity_type'),
                    sic=extra_fields.get('sic'),
                    industry=extra_fields.get('industry'),
                    exchanges=extra_fields.get('exchanges'),
                    fiscal_year_end=extra_fields.get('fiscal_year_end'),
                    state_of_incorporation=extra_fields.get('state_of_incorporation'),
                    state_of_incorporation_description=extra_fields.get('state_of_incorporation_description'),
                )
                session.add(company)
                companies_added += 1

            # 批量提交与进度
            processed = idx + 1
            if (companies_added + companies_updated) % 500 == 0:
                session.commit()
            if progress_callback:
                progress_pct = (processed / total_orgs) * 100
                if progress_pct >= last_progress_pct + 5 or processed == total_orgs:
                    progress_callback(processed, total_orgs, code)
                    last_progress_pct = int(progress_pct)
            elif processed % 500 == 0 or processed == total_orgs:
                logger.info(f"  已处理: 新增 {companies_added}, 更新 {companies_updated}")

        session.commit()

    if not basic_info_only:
        logger.info(
            f"submissions API 调用: {len(submissions_cache)} 次"
            + (f"（跳过 {submissions_skipped} 个 fiscal_year_end 已有值的记录）" if submissions_skipped else "")
        )

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
    logger.info("✅ 美股公司列表获取完成")
    logger.info(f"  总公司数: {result['total_companies']}")
    logger.info(f"  新增: {result['companies_added']}")
    logger.info(f"  更新: {result['companies_updated']}")
    logger.info(f"  耗时: {duration:.1f}秒")
    logger.info("=" * 80)

    return result


if __name__ == '__main__':
    """命令行直接运行（用于测试）"""
    result = get_us_companies_job()
    print(f"\n获取结果: {result}")
