# -*- coding: utf-8 -*-
"""
港股公司列表更新 Job
从披露易获取最新的股票列表并同步到数据库

纯业务逻辑，无 Dagster 依赖
"""

from datetime import datetime
from typing import Dict, Optional, Callable

from src.ingestion.hk_stock import HKEXClient
from src.storage.metadata import get_postgres_client, crud
from src.common.logger import get_logger

logger = get_logger(__name__)


def get_hk_companies_job(
    clear_before_update: bool = False,
    basic_info_only: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Dict:
    """
    更新港股公司列表

    Args:
        clear_before_update: 是否在更新前清空除 org_id 外的所有字段
        basic_info_only: 是否仅获取基础信息，跳过 akshare 详情拉取
        progress_callback: 进度回调 (current, total, code) -> None

    Returns:
        {"success": bool, "count": int, "message": str, "error": str (if failed)}
    """
    start_time = datetime.now()

    logger.info(
        f"[get_hk_companies] 开始更新港股公司列表 | "
        f"clear_before_update={clear_before_update}, basic_info_only={basic_info_only}"
    )

    try:
        hkex_client = HKEXClient()
        stocks = hkex_client.get_stock_list(include_inactive=False, equity_only=True)

        if not stocks:
            logger.error("[get_hk_companies] 更新失败: 未获取到港股公司列表")
            return {"success": False, "error": "未获取到港股公司列表", "count": 0}

        logger.info(f"从披露易获取了 {len(stocks)} 家股本证券公司")

        pg_client = get_postgres_client()

        if not basic_info_only:
            from src.ingestion.hk_stock.utils.akshare_helper import batch_get_company_profiles

            with pg_client.get_session() as session:
                existing_list = crud.get_all_hk_listed_companies(session)
                existing_by_code = {
                    c.code: {"org_name_cn": c.org_name_cn, "name": c.name}
                    for c in existing_list if c.code
                }

            def _need_fetch_profile(stock: dict, existing: dict | None) -> bool:
                if existing is None:
                    return True
                if not (existing.get("org_name_cn") or "").strip():
                    return True
                return (existing.get("name") or "").strip() != (stock.get("name") or "").strip()

            stocks_to_fetch = [
                s for s in stocks
                if _need_fetch_profile(s, existing_by_code.get(s.get("code")))
            ]
            stock_codes_to_fetch = [s["code"] for s in stocks_to_fetch]
            skipped_count = len(stocks) - len(stock_codes_to_fetch)

            if stock_codes_to_fetch:
                logger.info(
                    f"增量拉取 akshare 详情: {len(stock_codes_to_fetch)} 家（跳过 {skipped_count} 家 org_name_cn 未变）"
                )

                def _progress_cb(current: int, total: int, code: str) -> None:
                    if progress_callback:
                        try:
                            progress_callback(current, total, code)
                        except Exception:
                            pass

                profiles = batch_get_company_profiles(
                    stock_codes_to_fetch,
                    delay=0.1,
                    max_workers=10,
                    progress_callback=_progress_cb,
                )
            else:
                profiles = {}
                logger.info(f"无需拉取 akshare 详情（{len(stocks)} 家 org_name_cn 均未变）")

            enriched_count = 0
            company_info_count = 0
            security_info_count = 0

            for stock in stocks:
                code = stock["code"]
                profile = profiles.get(code)
                if profile is not None:
                    company_fields = [
                        "org_name_cn",
                        "org_name_en",
                        "org_cn_introduction",
                        "established_date",
                        "staff_num",
                        "industry",
                    ]
                    security_fields = [
                        "listed_date",
                        "fiscal_year_end",
                        "is_sh_hk_connect",
                        "is_sz_hk_connect",
                    ]
                    has_company_info = any(k in profile for k in company_fields)
                    has_security_info = any(k in profile for k in security_fields)
                    if has_company_info:
                        company_info_count += 1
                    if has_security_info:
                        security_info_count += 1
                    stock.update(profile)
                    if len(profile) > 0:
                        enriched_count += 1

            if enriched_count > 0:
                logger.info(
                    f"获取详情完成: {enriched_count}/{len(stocks)} 家 "
                    f"（公司信息 {company_info_count} 家，证券信息 {security_info_count} 家）"
                )

        if clear_before_update:
            with pg_client.get_session() as session:
                count = crud.clear_hk_listed_companies_except_org_id(session)
                session.commit()
            logger.info(f"已清空 hk_listed_companies 中 {count} 条记录的非主键字段")

        with pg_client.get_session() as session:
            count = crud.batch_upsert_hk_listed_companies(session, stocks)
            session.commit()

        duration_seconds = int((datetime.now() - start_time).total_seconds())
        logger.info(f"[get_hk_companies] 更新完成 | 总={len(stocks)}, 耗时={duration_seconds}s")

        return {
            "success": True,
            "count": len(stocks),
            "message": f"成功更新 {len(stocks)} 家港股股本证券公司",
        }

    except Exception as e:
        logger.error(f"[get_hk_companies] 更新失败: {e}", exc_info=True)
        return {"success": False, "error": str(e), "count": 0}
