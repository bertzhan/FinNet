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


# ==================== 配置 Schema ====================

COMPANY_LIST_UPDATE_CONFIG_SCHEMA = {
    "clear_before_update": Field(
        bool,
        default_value=False,
        description="是否在更新前清空表（默认 False，使用 upsert 策略）"
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
    - 默认使用 upsert：如果 code 已存在则更新 name，否则插入新记录
    - 如果 clear_before_update=True，则先清空表再插入
    """
    config = context.op_config
    logger = get_dagster_logger()
    
    clear_before_update = config.get("clear_before_update", False)
    
    logger.info("开始更新A股上市公司列表...")
    
    try:
        # 使用 akshare 获取A股上市公司列表
        logger.info("正在从 akshare 获取A股上市公司数据...")
        stock_df = ak.stock_info_a_code_name()
        
        # 检查数据格式
        if stock_df is None or stock_df.empty:
            logger.error("从 akshare 获取的数据为空")
            return {
                "success": False,
                "error": "从 akshare 获取的数据为空",
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
        logger.info(f"从 akshare 获取到 {total_count} 家上市公司")
        
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
        
        with pg_client.get_session() as session:
            # 获取现有公司的 code 集合（用于统计）
            existing_codes = {
                company.code
                for company in crud.get_all_listed_companies(session)
            }
            
            # 遍历 DataFrame 并更新数据库
            for _, row in stock_df.iterrows():
                code = str(row['code']).strip()
                name = str(row['name']).strip()
                
                if not code or not name:
                    continue
                
                # 判断是插入还是更新（用于统计）
                is_new = code not in existing_codes
                
                # 使用 upsert 函数更新或插入
                company = crud.upsert_listed_company(session, code, name)
                
                if is_new:
                    inserted_count += 1
                else:
                    updated_count += 1
            
            session.commit()
        
        logger.info(f"更新完成: 总计 {total_count} 家，新增 {inserted_count} 家，更新 {updated_count} 家")
        
        # 记录资产物化
        context.log_event(
            AssetMaterialization(
                asset_key=["metadata", "listed_companies"],
                description=f"A股上市公司列表已更新",
                metadata={
                    "total": MetadataValue.int(total_count),
                    "inserted": MetadataValue.int(inserted_count),
                    "updated": MetadataValue.int(updated_count),
                    "updated_at": MetadataValue.text(datetime.now().isoformat()),
                }
            )
        )
        
        return {
            "success": True,
            "total": total_count,
            "inserted": inserted_count,
            "updated": updated_count,
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
    1. 从 akshare 获取最新的A股上市公司列表
    2. 更新到数据库的 listed_companies 表
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
