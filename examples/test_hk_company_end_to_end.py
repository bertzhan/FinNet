# -*- coding: utf-8 -*-
"""
端到端测试：从 akshare 获取数据到保存数据库
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import akshare as ak
import pandas as pd

def test_akshare_data_format():
    """测试 akshare 数据格式"""
    print("=" * 80)
    print("Step 1: 测试 akshare 原始数据格式")
    print("=" * 80)
    
    code = "00001"
    print(f"\n获取 {code} 的公司信息...")
    
    profile_df = ak.stock_hk_company_profile_em(symbol=code)
    
    print(f"\n数据类型: {type(profile_df)}")
    print(f"数据形状: {profile_df.shape}")
    print(f"列名: {list(profile_df.columns)}")
    
    if len(profile_df) > 0:
        row = profile_df.iloc[0]
        print(f"\n第一行数据:")
        for col in profile_df.columns:
            value = row.get(col)
            value_str = str(value)[:80] if value else "None"
            print(f"  {col}: {value_str}")
    
    return profile_df

def test_get_company_profile_from_akshare():
    """测试 get_company_profile_from_akshare 函数"""
    print("\n" + "=" * 80)
    print("Step 2: 测试 get_company_profile_from_akshare 函数")
    print("=" * 80)
    
    from src.ingestion.hk_stock.utils.akshare_helper import get_company_profile_from_akshare
    
    code = "00001"
    print(f"\n调用 get_company_profile_from_akshare('{code}')...")
    
    result = get_company_profile_from_akshare(code)
    
    if result is None:
        print("❌ 返回 None")
        return None
    
    if len(result) == 0:
        print("⚠️  返回空字典")
        return result
    
    print(f"\n✅ 返回 {len(result)} 个字段:")
    for key, value in result.items():
        value_str = str(value)[:80] if value else "None"
        print(f"  {key}: {value_str}")
    
    return result

def test_save_to_database(profile_data):
    """测试保存到数据库"""
    print("\n" + "=" * 80)
    print("Step 3: 测试保存到数据库")
    print("=" * 80)
    
    if not profile_data:
        print("❌ 没有数据可保存")
        return
    
    from src.storage.metadata import get_postgres_client, crud
    
    # 构造完整的公司数据
    company_data = {
        'code': '00001',
        'name': '长江和记实业有限公司',
        'org_id': 1,
        'category': '股本',
        'sub_category': '股本證券(主板)',
    }
    
    # 合并 profile 数据
    company_data.update(profile_data)
    
    print(f"\n准备保存的数据（共 {len(company_data)} 个字段）:")
    for key, value in company_data.items():
        value_str = str(value)[:60] if value else "None"
        print(f"  {key}: {value_str}")
    
    # 保存到数据库
    pg_client = get_postgres_client()
    with pg_client.get_session() as session:
        print("\n正在保存到数据库...")
        count = crud.batch_upsert_hk_listed_companies(session, [company_data])
        session.commit()
        print(f"✅ 保存完成: {count} 条记录")
        
        # 验证保存结果
        print("\n验证保存结果...")
        company = crud.get_hk_listed_company_by_code(session, '00001')
        if company:
            print(f"\n✅ 从数据库读取到的数据:")
            print(f"  code: {company.code}")
            print(f"  name: {company.name}")
            print(f"  org_name_cn: {company.org_name_cn}")
            print(f"  org_name_en: {company.org_name_en}")
            print(f"  category: {company.category}")
            print(f"  industry: {company.industry}")
            print(f"  staff_num: {company.staff_num}")
            print(f"  established_date: {company.established_date}")
        else:
            print("❌ 未找到记录")

if __name__ == "__main__":
    # Step 1: 测试原始数据
    raw_df = test_akshare_data_format()
    
    # Step 2: 测试解析函数
    profile = test_get_company_profile_from_akshare()
    
    # Step 3: 测试保存
    test_save_to_database(profile)
