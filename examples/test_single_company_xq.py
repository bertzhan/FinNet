#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试单个公司的 stock_individual_basic_info_xq 接口
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import akshare as ak
from src.storage.metadata import get_postgres_client, crud


def test_single_company(code: str = "000488"):
    """测试单个公司的数据获取和存储"""
    print("=" * 60)
    print(f"测试单个公司: {code}")
    print("=" * 60)
    print()
    
    # 确定市场前缀
    if code.startswith('6'):
        symbol_with_prefix = f"SH{code}"
        market = "上海"
    elif code.startswith(('0', '3')):
        symbol_with_prefix = f"SZ{code}"
        market = "深圳"
    else:
        print(f"❌ 无法确定股票代码 {code} 的市场")
        return False
    
    print(f"股票代码: {code}")
    print(f"市场: {market}")
    print(f"完整代码: {symbol_with_prefix}")
    print()
    
    try:
        # 1. 获取公司基本信息（简称）
        print("1. 获取公司基本信息（简称）...")
        stock_df = ak.stock_info_a_code_name()
        company_info = stock_df[stock_df['code'] == code]
        
        if company_info.empty:
            print(f"   ❌ 未找到股票代码 {code}")
            return False
        
        company_name = company_info.iloc[0]['name']
        print(f"   ✅ 公司简称: {company_name}")
        print()
        
        # 2. 获取详细信息
        print("2. 获取公司详细信息（stock_individual_basic_info_xq）...")
        info_df = ak.stock_individual_basic_info_xq(symbol=symbol_with_prefix)
        
        if info_df is None or info_df.empty:
            print(f"   ❌ 获取详细信息失败")
            return False
        
        print(f"   ✅ 获取成功，共 {len(info_df)} 条信息")
        print()
        
        # 3. 显示所有字段
        print("3. 返回的所有字段:")
        print("-" * 60)
        info_dict = {}
        for idx, row in info_df.iterrows():
            item = str(row['item']).strip()
            value = row['value']
            if value is None or (isinstance(value, float) and str(value) == 'nan'):
                value_str = "None"
            else:
                value_str = str(value).strip()
                if len(value_str) > 100:
                    value_str = value_str[:100] + "..."
            info_dict[item] = value
            print(f"   {item:30s}: {value_str}")
        
        print()
        
        # 4. 显示关键字段
        print("4. 关键字段:")
        print("-" * 60)
        key_fields = [
            'org_name_cn', 'org_short_name_cn', 'org_name_en', 
            'pre_name_cn', 'provincial_name', 'legal_representative',
            'main_operation_business', 'telephone', 'org_website'
        ]
        
        for field in key_fields:
            value = info_dict.get(field)
            if value:
                value_str = str(value)
                if len(value_str) > 80:
                    value_str = value_str[:80] + "..."
                print(f"   {field:30s}: {value_str}")
        
        print()
        
        # 5. 存储到数据库
        print("5. 存储到数据库...")
        pg_client = get_postgres_client()
        
        # 数据类型转换辅助函数
        def safe_int(v):
            if v is None or (isinstance(v, float) and str(v) == 'nan'):
                return None
            try:
                return int(float(str(v)))
            except:
                return None
        
        def safe_float(v):
            if v is None or (isinstance(v, float) and str(v) == 'nan'):
                return None
            try:
                return float(str(v))
            except:
                return None
        
        def parse_industry(v):
            if v is None:
                return None
            if isinstance(v, dict):
                return v
            if isinstance(v, str) and v.startswith('{'):
                import json
                try:
                    return json.loads(v)
                except:
                    return {'raw': v}
            return None
        
        with pg_client.get_session() as session:
            company = crud.upsert_listed_company(
                session,
                code=code,
                name=company_name,
                # 公司名称信息
                org_id=info_dict.get('org_id'),
                org_name_cn=info_dict.get('org_name_cn'),
                org_short_name_cn=info_dict.get('org_short_name_cn'),
                org_name_en=info_dict.get('org_name_en'),
                org_short_name_en=info_dict.get('org_short_name_en'),
                pre_name_cn=info_dict.get('pre_name_cn'),
                # 业务信息
                main_operation_business=info_dict.get('main_operation_business'),
                operating_scope=info_dict.get('operating_scope'),
                org_cn_introduction=info_dict.get('org_cn_introduction'),
                # 联系信息
                telephone=info_dict.get('telephone'),
                postcode=info_dict.get('postcode'),
                fax=info_dict.get('fax'),
                email=info_dict.get('email'),
                org_website=info_dict.get('org_website'),
                reg_address_cn=info_dict.get('reg_address_cn'),
                reg_address_en=info_dict.get('reg_address_en'),
                office_address_cn=info_dict.get('office_address_cn'),
                office_address_en=info_dict.get('office_address_en'),
                # 管理信息
                legal_representative=info_dict.get('legal_representative'),
                general_manager=info_dict.get('general_manager'),
                secretary=info_dict.get('secretary'),
                chairman=info_dict.get('chairman'),
                executives_nums=safe_int(info_dict.get('executives_nums')),
                # 地区信息
                district_encode=info_dict.get('district_encode'),
                provincial_name=info_dict.get('provincial_name'),
                actual_controller=info_dict.get('actual_controller'),
                classi_name=info_dict.get('classi_name'),
                # 财务信息
                established_date=safe_int(info_dict.get('established_date')),
                listed_date=safe_int(info_dict.get('listed_date')),
                reg_asset=safe_float(info_dict.get('reg_asset')),
                staff_num=safe_int(info_dict.get('staff_num')),
                actual_issue_vol=safe_float(info_dict.get('actual_issue_vol')),
                issue_price=safe_float(info_dict.get('issue_price')),
                actual_rc_net_amt=safe_float(info_dict.get('actual_rc_net_amt')),
                pe_after_issuing=safe_float(info_dict.get('pe_after_issuing')),
                online_success_rate_of_issue=safe_float(info_dict.get('online_success_rate_of_issue')),
                # 其他信息
                currency_encode=info_dict.get('currency_encode'),
                currency=info_dict.get('currency'),
                affiliate_industry=parse_industry(info_dict.get('affiliate_industry')),
            )
            session.commit()
            
            print(f"   ✅ 存储成功")
            print()
            print(f"   数据库记录:")
            print(f"     股票代码: {company.code}")
            print(f"     公司简称: {company.name}")
            print(f"     公司全称: {company.org_name_cn}")
            print(f"     省份: {company.provincial_name}")
            print(f"     法定代表人: {company.legal_representative}")
            print(f"     主营业务: {company.main_operation_business[:80] if company.main_operation_business else None}...")
        
        print()
        print("=" * 60)
        print("✅ 测试成功！")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="测试单个公司的 stock_individual_basic_info_xq 接口")
    parser.add_argument("--code", type=str, default="000488", help="股票代码（默认：000488）")
    args = parser.parse_args()
    
    success = test_single_company(args.code)
    sys.exit(0 if success else 1)
