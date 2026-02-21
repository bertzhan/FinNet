# -*- coding: utf-8 -*-
"""
Dagster 上市公司列表更新作业定义
使用 akshare 获取 A 股上市公司信息并更新数据库

按照 plan.md 设计：
- 数据采集层（Ingestion Layer）→ Dagster 调度
- 支持定时调度、手动触发
"""

import pandas as pd
import akshare as ak
from datetime import datetime
from typing import Dict

from dagster import (
    job,
    op,
    schedule,
    sensor,
    DefaultSensorStatus,
    DefaultScheduleStatus,
    RunRequest,
    Field,
    get_dagster_logger,
    AssetMaterialization,
    MetadataValue,
)

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud


# ==================== 辅助函数 ====================

def _df_to_info_dict(info_df) -> dict:
    """将 akshare 返回的 DataFrame（item/value 列）转为字典"""
    import math
    from datetime import datetime, date
    info_dict = {}
    for idx, row in info_df.iterrows():
        item = str(row['item']).strip()
        value = row['value']
        if value is None:
            value = None
        elif isinstance(value, float):
            value = None if math.isnan(value) else value
        elif isinstance(value, (int, bool)):
            value = value
        elif isinstance(value, dict):
            value = value
        elif isinstance(value, (datetime, date)) or (hasattr(value, 'date') and callable(getattr(value, 'date', None))):
            # 保留 datetime/date/pandas.Timestamp，便于 crud 正确解析日期
            value = value
        else:
            value_str = str(value).strip()
            value = None if value_str in ('', 'None', 'nan', 'NaN') else value_str
        info_dict[item] = value
    return info_dict


def _safe_int(value):
    """安全地将值转换为整数"""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return int(value) if not (isinstance(value, float) and (value != value or value == float('inf'))) else None
        value_str = str(value).strip()
        if value_str in ('', 'None', 'nan', 'NaN'):
            return None
        return int(float(value_str))
    except (ValueError, TypeError):
        return None


def _safe_float(value):
    """安全地将值转换为浮点数"""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return float(value) if value == value else None  # 检查 NaN
        value_str = str(value).strip()
        if value_str in ('', 'None', 'nan', 'NaN'):
            return None
        return float(value_str)
    except (ValueError, TypeError):
        return None


def _industry_from_affiliate(value):
    """从 affiliate_industry 解析出 industry_code、industry，返回供 upsert 的 kwargs"""
    parsed = _parse_affiliate_industry(value)
    if not parsed or not isinstance(parsed, dict):
        return {}
    return {
        'industry_code': parsed.get('ind_code'),
        'industry': parsed.get('ind_name'),
    }


def _parse_affiliate_industry(value):
    """解析所属行业字段（可能是字符串、字典或 Python dict 字符串）"""
    if value is None:
        return None
    try:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            value_str = value.strip()
            if not value_str or value_str == 'None':
                return None
            
            # 尝试解析 JSON 字符串
            import json
            if value_str.startswith('{'):
                try:
                    # 先尝试 JSON 格式
                    return json.loads(value_str)
                except json.JSONDecodeError:
                    # 如果不是标准 JSON，可能是 Python dict 格式（如 "{'key': 'value'}"）
                    # 尝试使用 ast.literal_eval
                    try:
                        import ast
                        return ast.literal_eval(value_str)
                    except:
                        # 如果都失败，返回原始字符串包装成字典
                        return {'raw': value_str}
            return {'raw': value_str}
        return None
    except Exception:
        return None


# ==================== 配置 Schema ====================

COMPANY_LIST_UPDATE_CONFIG_SCHEMA = {
    "clear_before_update": Field(
        bool,
        default_value=False,
        description="是否在更新前清空除 org_id 外的所有字段（默认 False，使用 upsert 策略；org_id 为主键）"
    ),
    "basic_info_only": Field(
        bool,
        default_value=False,
        description="是否仅获取基础信息（code/name），跳过详细信息的拉取"
    ),
}


# 获取公司详细信息时的后台参数（不暴露给 Dagster 配置）
_FETCH_DELAY_SECONDS = 0.5
_MAX_RETRIES = 3
_RETRY_DELAY_SECONDS = 2.0


# ==================== Dagster Ops ====================

@op(config_schema=COMPANY_LIST_UPDATE_CONFIG_SCHEMA)
def get_hs_companies_op(context) -> Dict:
    """
    更新A股上市公司列表
    
    使用 akshare 获取最新的A股上市公司信息（code, name），
    并更新到数据库的 hs_listed_companies 表中。
    
    更新策略：
    - 默认使用 upsert：如果 code 已存在则只更新 name，否则插入新记录
    - 如果 clear_before_update=True，则先清空除 org_id 外的所有字段再全量更新（org_id 为主键）
    - 如果 basic_info_only=False，会获取公司详细信息（全称等）；basic_info_only=True 则跳过
    """
    import time
    
    config = context.op_config
    logger = get_dagster_logger()
    start_time = datetime.now()

    clear_before_update = config.get("clear_before_update", False)
    basic_info_only = config.get("basic_info_only", False)

    logger.info(
        f"[get_hs_companies] 开始更新A股公司列表 | "
        f"clear_before_update={clear_before_update}, basic_info_only={basic_info_only}"
    )
    
    try:
        # 使用 akshare 获取A股上市公司列表
        logger.info("正在获取A股上市公司数据...")
        try:
            stock_df = ak.stock_info_a_code_name()
        except Exception as e:
            # 北交所 stock_info_bj_name_code 常因数据源变更/不可用而失败，fallback 到沪深+科创板
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
        
        # 检查数据格式
        if stock_df is None or stock_df.empty:
            logger.error("[get_hs_companies] 更新失败: 获取的数据为空")
            return {
                "success": False,
                "error": "获取的数据为空",
                "total": 0,
                "inserted": 0,
                "updated": 0,
            }
        
        # 确保包含 code 和 name 列
        if 'code' not in stock_df.columns or 'name' not in stock_df.columns:
            logger.error(f"[get_hs_companies] 更新失败: 数据格式不正确，列名: {stock_df.columns.tolist()}")
            return {
                "success": False,
                "error": f"数据格式不正确，期望包含 code 和 name 列",
                "total": 0,
                "inserted": 0,
                "updated": 0,
            }
        
        # 只保留 code 和 name 字段
        stock_df = stock_df[['code', 'name']].copy()
        
        # 清理数据：去除空值
        stock_df = stock_df.dropna(subset=['code', 'name'])
        
        # 去除 code 和 name 的前后空格
        stock_df['code'] = stock_df['code'].astype(str).str.strip()
        stock_df['name'] = stock_df['name'].astype(str).str.strip()
        
        # 过滤掉空字符串
        stock_df = stock_df[(stock_df['code'] != '') & (stock_df['name'] != '')]
        
        total_count = len(stock_df)
        logger.info(f"获取到 {total_count} 家上市公司")
        
        # 获取数据库客户端
        pg_client = get_postgres_client()
        
        # 如果 clear_before_update：仅清空除 org_id 外的所有字段（保留行）
        if clear_before_update:
            logger.info("清空 hs_listed_companies 表除 org_id 外的所有字段...")
            with pg_client.get_session() as session:
                count = crud.clear_listed_companies_except_org_id(session)
                session.commit()
            logger.info(f"已清空 {count} 条记录的非主键字段")
        
        # 批量更新数据库
        inserted_count = 0
        updated_count = 0
        new_codes = set()  # 记录新插入的 code
        
        # API 返回的 code -> name（用于增量判断 org_name_cn 是否变化，name 为代理）
        code_to_api_name = {}
        for _, row in stock_df.iterrows():
            c = str(row['code']).strip()
            n = str(row['name']).strip().replace(" ", "").replace("　", "")
            if c and n:
                code_to_api_name[c] = n

        with pg_client.get_session() as session:
            # 获取现有公司信息（用于统计和判断是否需要获取全称）
            existing_companies = {
                company.code: company
                for company in crud.get_all_listed_companies(session)
            }
            existing_codes = set(existing_companies.keys())
            # 保存更新前的 org_name_cn、name，用于增量判断
            code_to_old_org_name_cn = {c: (e.org_name_cn or "").strip() for c, e in existing_companies.items()}
            code_to_old_name = {c: (e.name or "").strip().replace(" ", "").replace("　", "") for c, e in existing_companies.items()}

            # 遍历 DataFrame 并更新数据库
            for _, row in stock_df.iterrows():
                code = str(row['code']).strip()
                name = str(row['name']).strip()
                
                # 去除 name 中的所有空格（包括中间的空格）
                if name:
                    name = name.replace(" ", "").replace("　", "")  # 去除半角和全角空格
                
                if not code or not name:
                    continue
                
                # 判断是插入还是更新（用于统计）
                is_new = code not in existing_codes
                
                # 更新或插入：总是更新 name（详细信息稍后根据规则获取）
                company = crud.upsert_listed_company(session, code, name)
                
                if is_new:
                    inserted_count += 1
                    new_codes.add(code)  # 记录新插入的 code，稍后获取详细信息
                else:
                    updated_count += 1
            
            session.commit()
        
        # 基础信息更新完成（无进度条，因批量写入较快）
        
        full_names_success = 0
        full_names_error = 0
        
        if not basic_info_only:
            # 获取公司详细信息（增量：org_name_cn 为空或 org_name_cn 变化时拉取，name 变化作为代理）
            logger.info("开始获取公司详细信息...")
            companies_to_fetch = []
            for code in code_to_api_name:
                api_name = code_to_api_name[code]
                old_org_name_cn = code_to_old_org_name_cn.get(code, "")
                old_name = code_to_old_name.get(code, "")
                need_fetch = (
                    code not in existing_codes  # 新公司（org_name_cn 为空）
                    or not old_org_name_cn  # org_name_cn 为空
                    or old_name != api_name  # org_name_cn 是否变化（代理：name 变化）
                )
                if need_fetch:
                    companies_to_fetch.append((code, api_name))
            companies_to_fetch = sorted(companies_to_fetch, key=lambda x: x[0])
            fetch_total = len(companies_to_fetch)
            skipped = len(code_to_api_name) - fetch_total
            logger.info(f"需要获取全称的公司数: {fetch_total}" + (f"（跳过 {skipped} 家 org_name_cn 未变）" if skipped else ""))
            last_progress_pct = -1
            if fetch_total > 0:
                for i, (code, name) in enumerate(companies_to_fetch):
                    success = False
                    last_error = None
                    
                    # 重试机制
                    for retry in range(_MAX_RETRIES + 1):
                        try:
                            # 确定股票代码的市场前缀（SZ=深圳，SH=上海，BJ=北京）
                            # 6开头是上海，0/3开头是深圳，9开头是北京
                            if code.startswith('6'):
                                symbol_with_prefix = f"SH{code}"
                            elif code.startswith(('0', '3')):
                                symbol_with_prefix = f"SZ{code}"
                            elif code.startswith('9'):
                                symbol_with_prefix = f"BJ{code}"
                            else:
                                logger.warning(f"无法确定 {code} 的市场前缀，跳过")
                                full_names_error += 1
                                break
                            
                            # 使用 stock_individual_basic_info_xq 获取公司详细信息
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
                            
                            # 提取保留字段（映射到数据库字段）
                            update_kwargs = {
                                'code': code,
                                'name': name,
                                'org_id': info_dict.get('org_id'),
                                'org_name_cn': info_dict.get('org_name_cn'),
                                'org_short_name_cn': info_dict.get('org_short_name_cn'),
                                'org_name_en': info_dict.get('org_name_en'),
                                'org_short_name_en': info_dict.get('org_short_name_en'),
                                'pre_name_cn': info_dict.get('pre_name_cn'),
                                'main_operation_business': info_dict.get('main_operation_business'),
                                'operating_scope': info_dict.get('operating_scope'),
                                'org_cn_introduction': info_dict.get('org_cn_introduction'),
                                'provincial_name': info_dict.get('provincial_name'),
                                'established_date': info_dict.get('established_date'),
                                'listed_date': info_dict.get('listed_date'),
                                'staff_num': _safe_int(info_dict.get('staff_num')),
                                **_industry_from_affiliate(info_dict.get('affiliate_industry')),
                            }
                            
                            # 更新数据库
                            with pg_client.get_session() as session:
                                crud.upsert_listed_company(session, **update_kwargs)
                                session.commit()
                            
                            full_names_success += 1
                            success = True
                            break  # 成功，退出重试循环
                            
                        except Exception as e:
                            last_error = e
                            error_msg = str(e)
                            
                            # 判断是否是网络相关错误
                            is_network_error = any(keyword in error_msg.lower() for keyword in [
                                'proxy', 'connection', 'timeout', 'max retries', 
                                'remote end closed', 'ssl', 'http'
                            ])
                            
                            if retry < _MAX_RETRIES:
                                if is_network_error:
                                    logger.warning(
                                        f"获取 {code} ({name}) 失败（网络错误）: {error_msg[:100]}... "
                                        f"重试 {retry + 1}/{_MAX_RETRIES}（{_RETRY_DELAY_SECONDS}s后）"
                                    )
                                else:
                                    logger.warning(
                                        f"获取 {code} ({name}) 失败: {error_msg[:100]}... "
                                        f"重试 {retry + 1}/{_MAX_RETRIES}（{_RETRY_DELAY_SECONDS}s后）"
                                    )
                                time.sleep(_RETRY_DELAY_SECONDS)
                            else:
                                # 最后一次重试也失败
                                if is_network_error:
                                    logger.warning(
                                        f"获取 {code} ({name}) 失败（网络错误，已重试{_MAX_RETRIES}次）: {error_msg[:100]}..."
                                    )
                                else:
                                    logger.warning(
                                        f"获取 {code} ({name}) 失败（已重试{_MAX_RETRIES}次）: {error_msg[:100]}..."
                                    )
                                full_names_error += 1
                    
                    # 每 5% 或每 100 家输出进度
                    current = i + 1
                    progress_pct = (current / fetch_total) * 100
                    progress_pct_int = int(progress_pct)
                    should_log = (
                        current % 100 == 0
                        or current == fetch_total
                        or (progress_pct_int % 5 == 0 and progress_pct_int != last_progress_pct)
                    )
                    if should_log:
                        logger.info(
                            f"📦 [{current}/{fetch_total}] {progress_pct:.1f}% | 获取公司详情 | {code}"
                        )
                        last_progress_pct = progress_pct_int

                    # 延迟，避免请求过快（无论成功或失败都延迟）
                    time.sleep(_FETCH_DELAY_SECONDS)
            else:
                logger.info("所有公司都已包含全称信息，跳过获取步骤")
        else:
            logger.info("basic_info_only=True，跳过获取公司详细信息")
        
        duration_seconds = int((datetime.now() - start_time).total_seconds())

        logger.info(
            f"[get_hs_companies] 更新完成 | "
            f"总={total_count}, 新增={inserted_count}, 更新={updated_count}, 耗时={duration_seconds}s"
        )

        # 记录资产物化
        context.log_event(
            AssetMaterialization(
                asset_key=["metadata", "hs_listed_companies"],
                description=f"A股上市公司列表已更新",
                metadata={
                    "total": MetadataValue.int(total_count),
                    "inserted": MetadataValue.int(inserted_count),
                    "updated": MetadataValue.int(updated_count),
                    "full_names_success": MetadataValue.int(full_names_success),
                    "full_names_error": MetadataValue.int(full_names_error),
                    "updated_at": MetadataValue.text(datetime.now().isoformat()),
                }
            )
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


# ==================== Dagster Jobs ====================

@job
def get_hs_companies_job():
    """
    A股上市公司列表更新作业
    
    完整流程：
    1. 获取最新的A股上市公司列表（代码、简称）
    2. 更新到数据库的 hs_listed_companies 表
    3. 获取公司全称、曾用名、英文名等详细信息（默认总是执行）
    
    配置选项：
    - clear_before_update: 是否在更新前清空表（默认 False）
    - basic_info_only: 是否仅获取基础信息，跳过详情拉取（默认 False）
    
    注意：获取全称耗时较长，约5000家公司需要约40分钟
    """
    get_hs_companies_op()


# ==================== Schedules ====================

@schedule(
    job=get_hs_companies_job,
    cron_schedule="0 1 * * *",  # 每天凌晨1点执行
    default_status=DefaultScheduleStatus.STOPPED,  # 默认停止，需要手动启用
)
def daily_update_companies_schedule(context):
    """
    每日定时更新A股上市公司列表
    """
    return RunRequest()


# ==================== Sensors ====================

@sensor(
    job=get_hs_companies_job,
    default_status=DefaultSensorStatus.STOPPED,
)
def manual_trigger_companies_sensor(context):
    """
    手动触发更新上市公司列表传感器
    可以通过Dagster UI手动触发
    """
    return RunRequest()
