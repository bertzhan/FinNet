#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移脚本：为 listed_companies 表添加 stock_individual_basic_info_xq 接口的所有字段

新增字段来自 akshare stock_individual_basic_info_xq 接口返回的所有字段
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.storage.metadata import get_postgres_client
from src.common.logger import get_logger

logger = get_logger(__name__)


def migrate():
    """执行迁移"""
    print("=" * 60)
    print("数据库迁移：为 listed_companies 表添加 stock_individual_basic_info_xq 字段")
    print("=" * 60)
    print()
    
    pg_client = get_postgres_client()
    
    # 检查表是否存在
    if not pg_client.table_exists('listed_companies'):
        print("❌ listed_companies 表不存在")
        print("   请先运行: python scripts/migrate_listed_companies_table.py")
        return False
    
    print("✅ listed_companies 表存在")
    
    # 要添加的字段（来自 stock_individual_basic_info_xq 接口）
    new_columns = [
        # 公司名称信息
        ("org_id", "VARCHAR(50)", "机构ID"),
        ("org_name_cn", "VARCHAR(500)", "公司全称（中文）"),
        ("org_short_name_cn", "VARCHAR(200)", "公司简称（中文）"),
        ("org_name_en", "VARCHAR(500)", "公司全称（英文）"),
        ("org_short_name_en", "VARCHAR(200)", "公司简称（英文）"),
        ("pre_name_cn", "VARCHAR(500)", "曾用名"),
        
        # 业务信息
        ("main_operation_business", "TEXT", "主营业务"),
        ("operating_scope", "TEXT", "经营范围"),
        ("org_cn_introduction", "TEXT", "公司简介"),
        
        # 联系信息
        ("telephone", "VARCHAR(50)", "电话"),
        ("postcode", "VARCHAR(20)", "邮编"),
        ("fax", "VARCHAR(50)", "传真"),
        ("email", "VARCHAR(500)", "邮箱"),
        ("org_website", "VARCHAR(500)", "网站"),
        ("reg_address_cn", "VARCHAR(500)", "注册地址（中文）"),
        ("reg_address_en", "VARCHAR(500)", "注册地址（英文）"),
        ("office_address_cn", "VARCHAR(500)", "办公地址（中文）"),
        ("office_address_en", "VARCHAR(500)", "办公地址（英文）"),
        
        # 管理信息
        ("legal_representative", "VARCHAR(100)", "法定代表人"),
        ("general_manager", "VARCHAR(100)", "总经理"),
        ("secretary", "VARCHAR(100)", "董事会秘书"),
        ("chairman", "VARCHAR(100)", "董事长"),
        ("executives_nums", "INTEGER", "高管人数"),
        
        # 地区信息
        ("district_encode", "VARCHAR(50)", "地区编码"),
        ("provincial_name", "VARCHAR(100)", "省份名称"),
        ("actual_controller", "VARCHAR(500)", "实际控制人"),
        ("classi_name", "VARCHAR(100)", "分类名称"),
        
        # 财务信息
        ("established_date", "BIGINT", "成立日期（时间戳）"),
        ("listed_date", "BIGINT", "上市日期（时间戳）"),
        ("reg_asset", "DOUBLE PRECISION", "注册资本"),
        ("staff_num", "INTEGER", "员工人数"),
        ("actual_issue_vol", "DOUBLE PRECISION", "实际发行量"),
        ("issue_price", "DOUBLE PRECISION", "发行价格"),
        ("actual_rc_net_amt", "DOUBLE PRECISION", "实际募集资金净额"),
        ("pe_after_issuing", "DOUBLE PRECISION", "发行后市盈率"),
        ("online_success_rate_of_issue", "DOUBLE PRECISION", "网上发行中签率"),
        
        # 其他信息
        ("currency_encode", "VARCHAR(50)", "货币编码"),
        ("currency", "VARCHAR(10)", "货币"),
        ("affiliate_industry", "JSONB", "所属行业（JSON格式）"),
    ]
    
    with pg_client.get_session() as session:
        for col_name, col_type, col_desc in new_columns:
            try:
                # 检查字段是否已存在
                check_sql = text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'listed_companies' 
                    AND column_name = :col_name
                """)
                result = session.execute(check_sql, {"col_name": col_name})
                
                if result.fetchone():
                    print(f"⏭️  字段 {col_name} 已存在，跳过")
                    continue
                
                # 添加字段
                alter_sql = text(f"""
                    ALTER TABLE listed_companies 
                    ADD COLUMN {col_name} {col_type}
                """)
                session.execute(alter_sql)
                print(f"✅ 添加字段: {col_name} ({col_desc})")
                
            except Exception as e:
                print(f"❌ 添加字段 {col_name} 失败: {e}")
                return False
        
        session.commit()
    
    print()
    print("✅ 迁移完成！")
    print()
    print("新增字段：")
    print("  - 公司名称信息：org_id, org_name_cn, org_short_name_cn, org_name_en, org_short_name_en, pre_name_cn")
    print("  - 业务信息：main_operation_business, operating_scope, org_cn_introduction")
    print("  - 联系信息：telephone, postcode, fax, email, org_website, reg_address_cn, office_address_cn")
    print("  - 管理信息：legal_representative, general_manager, secretary, chairman, executives_nums")
    print("  - 地区信息：district_encode, provincial_name, actual_controller, classi_name")
    print("  - 财务信息：established_date, listed_date, reg_asset, staff_num, 等")
    print("  - 其他信息：currency_encode, currency, affiliate_industry")
    print()
    print("下一步：运行 update_listed_companies_job 来填充这些字段")
    print("  dagster job execute -j update_listed_companies_job -m src.processing.compute.dagster")
    
    return True


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
