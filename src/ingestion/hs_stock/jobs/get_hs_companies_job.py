# -*- coding: utf-8 -*-
"""
A股上市公司列表更新 Job
使用 akshare 获取 A 股上市公司信息并更新数据库

纯业务逻辑，无 Dagster 依赖
"""

import time
from datetime import datetime
from typing import Dict, Optional, Callable

import pandas as pd
import akshare as ak

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.common.logger import get_logger

logger = get_logger(__name__)

_FETCH_DELAY_SECONDS = 0.5
_MAX_RETRIES = 3
_RETRY_DELAY_SECONDS = 2.0


def _df_to_info_dict(info_df) -> dict:
    """将 akshare 返回的 DataFrame（item/value 列）转为字典"""
    import math
    from datetime import datetime, date

    info_dict = {}
    for idx, row in info_df.iterrows():
        item = str(row["item"]).strip()
        value = row["value"]
        if value is None:
            value = None
        elif isinstance(value, float):
            value = None if math.isnan(value) else value
        elif isinstance(value, (int, bool)):
            value = value
        elif isinstance(value, dict):
            value = value
        elif isinstance(value, (datetime, date)) or (
            hasattr(value, "date") and callable(getattr(value, "date", None))
        ):
            value = value
        else:
            value_str = str(value).strip()
            value = None if value_str in ("", "None", "nan", "NaN") else value_str
        info_dict[item] = value
    return info_dict


def _safe_int(value):
    """安全地将值转换为整数"""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return (
                int(value)
                if not (isinstance(value, float) and (value != value or value == float("inf")))
                else None
            )
        value_str = str(value).strip()
        if value_str in ("", "None", "nan", "NaN"):
            return None
        return int(float(value_str))
    except (ValueError, TypeError):
        return None


def _industry_from_affiliate(value):
    """从 affiliate_industry 解析出 industry_code、industry"""
    parsed = _parse_affiliate_industry(value)
    if not parsed or not isinstance(parsed, dict):
        return {}
    return {
        "industry_code": parsed.get("ind_code"),
        "industry": parsed.get("ind_name"),
    }


def _parse_affiliate_industry(value):
    """解析所属行业字段"""
    if value is None:
        return None
    try:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            value_str = value.strip()
            if not value_str or value_str == "None":
                return None
            import json
            import ast

            if value_str.startswith("{"):
                try:
                    return json.loads(value_str)
                except json.JSONDecodeError:
                    try:
                        return ast.literal_eval(value_str)
                    except Exception:
                        return {"raw": value_str}
            return {"raw": value_str}
        return None
    except Exception:
        return None


def get_hs_companies_job(
    clear_before_update: bool = False,
    basic_info_only: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Dict:
    """
    更新A股上市公司列表

    Args:
        clear_before_update: 是否在更新前清空除 org_id 外的所有字段
        basic_info_only: 是否仅获取基础信息，跳过详情拉取
        progress_callback: 进度回调 (current, total, code) -> None

    Returns:
        {
            "success": bool,
            "total": int,
            "inserted": int,
            "updated": int,
            "full_names_success": int,
            "full_names_error": int,
            "updated_at": str,
            "error": str (if failed),
        }
    """
    start_time = datetime.now()

    logger.info(
        f"[get_hs_companies] 开始更新A股公司列表 | "
        f"clear_before_update={clear_before_update}, basic_info_only={basic_info_only}"
    )

    try:
        logger.info("正在获取A股上市公司数据...")
        try:
            stock_df = ak.stock_info_a_code_name()
        except Exception as e:
            if "Expecting value" in str(e) or "JSONDecodeError" in str(e):
                logger.warning(f"stock_info_a_code_name 失败（{e}），改用沪深+科创板数据（不含北交所）")
                stock_sh = ak.stock_info_sh_name_code(symbol="主板A股")[["证券代码", "证券简称"]]
                stock_sz = ak.stock_info_sz_name_code(symbol="A股列表")
                stock_sz["A股代码"] = stock_sz["A股代码"].astype(str).str.zfill(6)
                stock_sz = stock_sz[["A股代码", "A股简称"]]
                stock_sz.columns = ["证券代码", "证券简称"]
                stock_kcb = ak.stock_info_sh_name_code(symbol="科创板")[["证券代码", "证券简称"]]
                stock_df = pd.concat([stock_sh, stock_sz, stock_kcb], ignore_index=True)
                stock_df.columns = ["code", "name"]
            else:
                raise

        if stock_df is None or stock_df.empty:
            logger.error("[get_hs_companies] 更新失败: 获取的数据为空")
            return {
                "success": False,
                "error": "获取的数据为空",
                "total": 0,
                "inserted": 0,
                "updated": 0,
            }

        if "code" not in stock_df.columns or "name" not in stock_df.columns:
            logger.error(f"[get_hs_companies] 更新失败: 数据格式不正确，列名: {stock_df.columns.tolist()}")
            return {
                "success": False,
                "error": "数据格式不正确，期望包含 code 和 name 列",
                "total": 0,
                "inserted": 0,
                "updated": 0,
            }

        stock_df = stock_df[["code", "name"]].copy()
        stock_df = stock_df.dropna(subset=["code", "name"])
        stock_df["code"] = stock_df["code"].astype(str).str.strip()
        stock_df["name"] = stock_df["name"].astype(str).str.strip()
        stock_df = stock_df[(stock_df["code"] != "") & (stock_df["name"] != "")]

        total_count = len(stock_df)
        logger.info(f"获取到 {total_count} 家上市公司")

        pg_client = get_postgres_client()

        if clear_before_update:
            logger.info("清空 hs_listed_companies 表除 org_id 外的所有字段...")
            with pg_client.get_session() as session:
                count = crud.clear_listed_companies_except_org_id(session)
                session.commit()
            logger.info(f"已清空 {count} 条记录的非主键字段")

        inserted_count = 0
        updated_count = 0
        new_codes = set()
        code_to_api_name = {}
        for _, row in stock_df.iterrows():
            c = str(row["code"]).strip()
            n = str(row["name"]).strip().replace(" ", "").replace("　", "")
            if c and n:
                code_to_api_name[c] = n

        with pg_client.get_session() as session:
            existing_companies = {
                company.code: company for company in crud.get_all_listed_companies(session)
            }
            existing_codes = set(existing_companies.keys())
            code_to_old_org_name_cn = {
                c: (e.org_name_cn or "").strip() for c, e in existing_companies.items()
            }
            code_to_old_name = {
                c: (e.name or "").strip().replace(" ", "").replace("　", "")
                for c, e in existing_companies.items()
            }

            for _, row in stock_df.iterrows():
                code = str(row["code"]).strip()
                name = str(row["name"]).strip()
                if name:
                    name = name.replace(" ", "").replace("　", "")
                if not code or not name:
                    continue

                is_new = code not in existing_codes
                crud.upsert_listed_company(session, code, name)

                if is_new:
                    inserted_count += 1
                    new_codes.add(code)
                else:
                    updated_count += 1

            session.commit()

        full_names_success = 0
        full_names_error = 0

        if not basic_info_only:
            logger.info("开始获取公司详细信息...")
            companies_to_fetch = []
            for code in code_to_api_name:
                api_name = code_to_api_name[code]
                old_org_name_cn = code_to_old_org_name_cn.get(code, "")
                old_name = code_to_old_name.get(code, "")
                need_fetch = (
                    code not in existing_codes
                    or not old_org_name_cn
                    or old_name != api_name
                )
                if need_fetch:
                    companies_to_fetch.append((code, api_name))
            companies_to_fetch = sorted(companies_to_fetch, key=lambda x: x[0])
            fetch_total = len(companies_to_fetch)
            skipped = len(code_to_api_name) - fetch_total
            logger.info(
                f"需要获取全称的公司数: {fetch_total}"
                + (f"（跳过 {skipped} 家 org_name_cn 未变）" if skipped else "")
            )
            last_progress_pct = -1

            if fetch_total > 0:
                for i, (code, name) in enumerate(companies_to_fetch):
                    success = False
                    last_error = None

                    for retry in range(_MAX_RETRIES + 1):
                        try:
                            if code.startswith("6"):
                                symbol_with_prefix = f"SH{code}"
                            elif code.startswith(("0", "3")):
                                symbol_with_prefix = f"SZ{code}"
                            elif code.startswith("9"):
                                symbol_with_prefix = f"BJ{code}"
                            else:
                                logger.warning(f"无法确定 {code} 的市场前缀，跳过")
                                full_names_error += 1
                                break

                            info_df = ak.stock_individual_basic_info_xq(symbol=symbol_with_prefix)

                            if info_df is None or info_df.empty:
                                logger.warning(f"获取 {code} ({name}) 的信息为空")
                                if retry < _MAX_RETRIES:
                                    logger.info(f"  重试 {retry + 1}/{_MAX_RETRIES}...")
                                    time.sleep(_RETRY_DELAY_SECONDS)
                                    continue
                                else:
                                    full_names_error += 1
                                    break

                            info_dict = _df_to_info_dict(info_df)
                            update_kwargs = {
                                "code": code,
                                "name": name,
                                "org_id": info_dict.get("org_id"),
                                "org_name_cn": info_dict.get("org_name_cn"),
                                "org_short_name_cn": info_dict.get("org_short_name_cn"),
                                "org_name_en": info_dict.get("org_name_en"),
                                "org_short_name_en": info_dict.get("org_short_name_en"),
                                "pre_name_cn": info_dict.get("pre_name_cn"),
                                "main_operation_business": info_dict.get("main_operation_business"),
                                "operating_scope": info_dict.get("operating_scope"),
                                "org_cn_introduction": info_dict.get("org_cn_introduction"),
                                "provincial_name": info_dict.get("provincial_name"),
                                "established_date": info_dict.get("established_date"),
                                "listed_date": info_dict.get("listed_date"),
                                "staff_num": _safe_int(info_dict.get("staff_num")),
                                **_industry_from_affiliate(info_dict.get("affiliate_industry")),
                            }

                            with pg_client.get_session() as session:
                                crud.upsert_listed_company(session, **update_kwargs)
                                session.commit()

                            full_names_success += 1
                            success = True
                            break

                        except Exception as e:
                            last_error = e
                            error_msg = str(e)
                            is_network_error = any(
                                kw in error_msg.lower()
                                for kw in ["proxy", "connection", "timeout", "max retries", "remote end closed", "ssl", "http"]
                            )
                            if retry < _MAX_RETRIES:
                                logger.warning(
                                    f"获取 {code} ({name}) 失败: {error_msg[:100]}... "
                                    f"重试 {retry + 1}/{_MAX_RETRIES}"
                                )
                                time.sleep(_RETRY_DELAY_SECONDS)
                            else:
                                logger.warning(
                                    f"获取 {code} ({name}) 失败（已重试{_MAX_RETRIES}次）: {error_msg[:100]}..."
                                )
                                full_names_error += 1

                    current = i + 1
                    progress_pct = (current / fetch_total) * 100
                    progress_pct_int = int(progress_pct)
                    should_log = (
                        current % 100 == 0
                        or current == fetch_total
                        or (progress_pct_int % 5 == 0 and progress_pct_int != last_progress_pct)
                    )
                    if should_log:
                        logger.info(f"📦 [{current}/{fetch_total}] {progress_pct:.1f}% | 获取公司详情 | {code}")
                        last_progress_pct = progress_pct_int
                    if progress_callback:
                        try:
                            progress_callback(current, fetch_total, code)
                        except Exception:
                            pass

                    time.sleep(_FETCH_DELAY_SECONDS)
        else:
            logger.info("basic_info_only=True，跳过获取公司详细信息")

        duration_seconds = int((datetime.now() - start_time).total_seconds())
        logger.info(
            f"[get_hs_companies] 更新完成 | "
            f"总={total_count}, 新增={inserted_count}, 更新={updated_count}, 耗时={duration_seconds}s"
        )

        return {
            "success": True,
            "total": total_count,
            "inserted": inserted_count,
            "updated": updated_count,
            "full_names_success": full_names_success,
            "full_names_error": full_names_error,
            "updated_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"[get_hs_companies] 更新失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "total": 0,
            "inserted": 0,
            "updated": 0,
        }
