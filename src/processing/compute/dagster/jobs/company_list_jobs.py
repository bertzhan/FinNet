# -*- coding: utf-8 -*-
"""
Dagster 上市公司列表更新作业定义
使用 akshare 获取 A 股上市公司信息并更新数据库

按照 plan.md 设计：
- 数据采集层（Ingestion Layer）→ Dagster 调度
- 支持定时调度、手动触发
"""

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
        description="是否在更新前清空表（默认 False，使用 upsert 策略）"
    ),
    "only_missing_full_names": Field(
        bool,
        default_value=True,
        description="是否只获取缺少全称的公司（默认 True，只更新缺少全称的公司）"
    ),
    "force_update_company_info": Field(
        bool,
        default_value=False,
        description="是否强制更新公司详细信息（默认 False）。如果为 True，code 存在时也强制更新公司所有信息；如果为 False，code 存在时只更新 name"
    ),
    "fetch_delay_seconds": Field(
        float,
        default_value=0.0,
        description="获取全称时每次请求的延迟秒数（默认 0 秒，无延迟）"
    ),
    "max_retries": Field(
        int,
        default_value=3,
        description="获取全称失败时的最大重试次数（默认 3 次）"
    ),
    "retry_delay_seconds": Field(
        float,
        default_value=2.0,
        description="重试时的延迟秒数（默认 2.0 秒）"
    ),
}


# ==================== Dagster Ops ====================

@op(config_schema=COMPANY_LIST_UPDATE_CONFIG_SCHEMA)
def update_listed_companies_op(context) -> Dict:
    """
    更新A股上市公司列表
    
    使用 akshare 获取最新的A股上市公司信息（code, name），
    并更新到数据库的 listed_companies 表中。
    
    更新策略：
    - 默认使用 upsert：如果 code 已存在则只更新 name，否则插入新记录
    - 如果 clear_before_update=True，则先清空表再插入
    - 如果 force_update_company_info=True，code 存在时也强制更新公司所有信息
    - 如果 code 不存在，总是新增 name 和公司所有信息
    """
    import time
    
    config = context.op_config
    logger = get_dagster_logger()
    
    clear_before_update = config.get("clear_before_update", False)
    only_missing_full_names = config.get("only_missing_full_names", True)
    force_update_company_info = config.get("force_update_company_info", False)
    fetch_delay_seconds = config.get("fetch_delay_seconds", 0.5)
    max_retries = config.get("max_retries", 3)
    retry_delay_seconds = config.get("retry_delay_seconds", 2.0)
    
    logger.info("开始更新A股上市公司列表...")
    logger.info(f"配置: clear_before_update={clear_before_update}, "
                f"force_update_company_info={force_update_company_info}, "
                f"only_missing_full_names={only_missing_full_names}")
    logger.info(f"将同时获取公司详细信息（only_missing={only_missing_full_names}, delay={fetch_delay_seconds}s, max_retries={max_retries}）")
    
    try:
        # 使用 akshare 获取A股上市公司列表
        logger.info("正在获取A股上市公司数据...")
        stock_df = ak.stock_info_a_code_name()
        
        # 检查数据格式
        if stock_df is None or stock_df.empty:
            logger.error("获取的数据为空")
            return {
                "success": False,
                "error": "获取的数据为空",
                "total": 0,
                "inserted": 0,
                "updated": 0,
            }
        
        # 确保包含 code 和 name 列
        if 'code' not in stock_df.columns or 'name' not in stock_df.columns:
            logger.error(f"数据格式不正确，列名: {stock_df.columns.tolist()}")
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
        
        # 如果需要清空表
        if clear_before_update:
            logger.info("清空现有数据...")
            with pg_client.get_session() as session:
                from src.storage.metadata.models import ListedCompany
                session.query(ListedCompany).delete()
                session.commit()
            logger.info("表已清空")
        
        # 批量更新数据库
        inserted_count = 0
        updated_count = 0
        new_codes = set()  # 记录新插入的 code
        
        with pg_client.get_session() as session:
            # 获取现有公司信息（用于统计和判断是否需要获取全称）
            existing_companies = {
                company.code: company
                for company in crud.get_all_listed_companies(session)
            }
            existing_codes = set(existing_companies.keys())
            
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
        
        logger.info(f"基础信息更新完成: 总计 {total_count} 家，新增 {inserted_count} 家，更新 {updated_count} 家")
        
        # 获取公司详细信息
        logger.info("开始获取公司详细信息...")
        full_names_success = 0
        full_names_error = 0
        
        with pg_client.get_session() as session:
            # 获取所有公司（已按 code 排序）
            all_companies = crud.get_all_listed_companies(session)
            
            # 决定哪些公司需要获取全称信息
            companies_to_fetch = []
            
            for c in all_companies:
                is_new_company = c.code in new_codes
                
                if is_new_company:
                    # 新插入的公司：总是获取全称信息
                    companies_to_fetch.append((c.code, c.name))
                else:
                    # 已存在的公司
                    if force_update_company_info:
                        # 强制更新：总是获取全称信息
                        companies_to_fetch.append((c.code, c.name))
                    else:
                        # 默认：根据 only_missing_full_names 决定
                        if only_missing_full_names:
                            # 只获取缺少全称的公司
                            if not c.org_name_cn:
                                companies_to_fetch.append((c.code, c.name))
                        # 如果 only_missing_full_names=False，跳过已存在的公司
            
            # 确保按 code 排序
            companies_to_fetch = sorted(companies_to_fetch, key=lambda x: x[0])
        
        fetch_total = len(companies_to_fetch)
        logger.info(f"需要获取全称的公司数: {fetch_total}")
        
        if fetch_total > 0:
            for i, (code, name) in enumerate(companies_to_fetch):
                success = False
                last_error = None
                
                # 重试机制
                for retry in range(max_retries + 1):
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
                            if retry < max_retries:
                                logger.info(f"  重试 {retry + 1}/{max_retries}...")
                                time.sleep(retry_delay_seconds)
                                continue
                            else:
                                full_names_error += 1
                                break
                        
                        # 将 DataFrame 转换为字典（item 列是字段名，value 列是值）
                        info_dict = {}
                        for idx, row in info_df.iterrows():
                            item = str(row['item']).strip()
                            value = row['value']
                            
                            # 处理 None 和 NaN
                            if value is None:
                                value = None
                            elif isinstance(value, float):
                                # 检查是否是 NaN
                                import math
                                if math.isnan(value):
                                    value = None
                                else:
                                    # 保留浮点数类型
                                    value = value
                            elif isinstance(value, (int, bool)):
                                # 保留整数和布尔类型
                                value = value
                            elif isinstance(value, dict):
                                # 保留字典类型
                                value = value
                            else:
                                # 字符串类型，去除首尾空格
                                value_str = str(value).strip()
                                if value_str in ('', 'None', 'nan', 'NaN'):
                                    value = None
                                else:
                                    value = value_str
                            
                            info_dict[item] = value
                        
                        # 提取所有字段（映射到数据库字段）
                        update_kwargs = {
                            'code': code,
                            'name': name,
                            # 公司名称信息
                            'org_id': info_dict.get('org_id'),
                            'org_name_cn': info_dict.get('org_name_cn'),
                            'org_short_name_cn': info_dict.get('org_short_name_cn'),
                            'org_name_en': info_dict.get('org_name_en'),
                            'org_short_name_en': info_dict.get('org_short_name_en'),
                            'pre_name_cn': info_dict.get('pre_name_cn'),
                            # 业务信息
                            'main_operation_business': info_dict.get('main_operation_business'),
                            'operating_scope': info_dict.get('operating_scope'),
                            'org_cn_introduction': info_dict.get('org_cn_introduction'),
                            # 联系信息
                            'telephone': info_dict.get('telephone'),
                            'postcode': info_dict.get('postcode'),
                            'fax': info_dict.get('fax'),
                            'email': info_dict.get('email'),
                            'org_website': info_dict.get('org_website'),
                            'reg_address_cn': info_dict.get('reg_address_cn'),
                            'reg_address_en': info_dict.get('reg_address_en'),
                            'office_address_cn': info_dict.get('office_address_cn'),
                            'office_address_en': info_dict.get('office_address_en'),
                            # 管理信息
                            'legal_representative': info_dict.get('legal_representative'),
                            'general_manager': info_dict.get('general_manager'),
                            'secretary': info_dict.get('secretary'),
                            'chairman': info_dict.get('chairman'),
                            'executives_nums': _safe_int(info_dict.get('executives_nums')),
                            # 地区信息
                            'district_encode': info_dict.get('district_encode'),
                            'provincial_name': info_dict.get('provincial_name'),
                            'actual_controller': info_dict.get('actual_controller'),
                            'classi_name': info_dict.get('classi_name'),
                            # 财务信息
                            'established_date': _safe_int(info_dict.get('established_date')),
                            'listed_date': _safe_int(info_dict.get('listed_date')),
                            'reg_asset': _safe_float(info_dict.get('reg_asset')),
                            'staff_num': _safe_int(info_dict.get('staff_num')),
                            'actual_issue_vol': _safe_float(info_dict.get('actual_issue_vol')),
                            'issue_price': _safe_float(info_dict.get('issue_price')),
                            'actual_rc_net_amt': _safe_float(info_dict.get('actual_rc_net_amt')),
                            'pe_after_issuing': _safe_float(info_dict.get('pe_after_issuing')),
                            'online_success_rate_of_issue': _safe_float(info_dict.get('online_success_rate_of_issue')),
                            # 其他信息
                            'currency_encode': info_dict.get('currency_encode'),
                            'currency': info_dict.get('currency'),
                            'affiliate_industry': _parse_affiliate_industry(info_dict.get('affiliate_industry')),
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
                        
                        if retry < max_retries:
                            if is_network_error:
                                logger.warning(
                                    f"获取 {code} ({name}) 失败（网络错误）: {error_msg[:100]}... "
                                    f"重试 {retry + 1}/{max_retries}（{retry_delay_seconds}s后）"
                                )
                            else:
                                logger.warning(
                                    f"获取 {code} ({name}) 失败: {error_msg[:100]}... "
                                    f"重试 {retry + 1}/{max_retries}（{retry_delay_seconds}s后）"
                                )
                            time.sleep(retry_delay_seconds)
                        else:
                            # 最后一次重试也失败
                            if is_network_error:
                                logger.warning(
                                    f"获取 {code} ({name}) 失败（网络错误，已重试{max_retries}次）: {error_msg[:100]}..."
                                )
                            else:
                                logger.warning(
                                    f"获取 {code} ({name}) 失败（已重试{max_retries}次）: {error_msg[:100]}..."
                                )
                            full_names_error += 1
                
                # 每处理100家输出一次日志
                if (i + 1) % 100 == 0:
                    logger.info(
                        f"已获取全称 {i + 1}/{fetch_total} 家公司 "
                        f"（成功: {full_names_success}, 失败: {full_names_error}）"
                    )
                
                # 延迟，避免请求过快（无论成功或失败都延迟）
                time.sleep(fetch_delay_seconds)
            
            logger.info(f"全称获取完成: 成功 {full_names_success} 家，失败 {full_names_error} 家")
        else:
            logger.info("所有公司都已包含全称信息，跳过获取步骤")
        
        # 记录资产物化
        context.log_event(
            AssetMaterialization(
                asset_key=["metadata", "listed_companies"],
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
        logger.error(f"更新上市公司列表失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "total": 0,
            "inserted": 0,
            "updated": 0,
        }


# ==================== Dagster Jobs ====================

@job
def update_listed_companies_job():
    """
    A股上市公司列表更新作业
    
    完整流程：
    1. 获取最新的A股上市公司列表（代码、简称）
    2. 更新到数据库的 listed_companies 表
    3. 获取公司全称、曾用名、英文名等详细信息（默认总是执行）
    
    配置选项：
    - only_missing_full_names: 是否只获取缺少全称的公司（默认 True，只更新缺少全称的公司）
    - fetch_delay_seconds: 获取全称时的请求延迟（默认 0.5 秒）
    - clear_before_update: 是否在更新前清空表（默认 False）
    
    注意：获取全称耗时较长，约5000家公司需要约40分钟
    """
    update_listed_companies_op()


# ==================== Schedules ====================

@schedule(
    job=update_listed_companies_job,
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
    job=update_listed_companies_job,
    default_status=DefaultSensorStatus.STOPPED,
)
def manual_trigger_companies_sensor(context):
    """
    手动触发更新上市公司列表传感器
    可以通过Dagster UI手动触发
    """
    return RunRequest()
