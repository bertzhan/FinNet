# -*- coding: utf-8 -*-
"""
直接测试 akshare.stock_hk_company_profile_em 接口
查看实际返回的数据格式
"""

import sys

try:
    import akshare as ak
    import pandas as pd
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请运行: pip install akshare pandas")
    sys.exit(1)

def test_stock_hk_company_profile_em():
    """直接测试 akshare 接口"""
    test_codes = ["00001", "00700", "09988"]  # 长和、腾讯、阿里
    
    print("=" * 80)
    print("直接测试 ak.stock_hk_company_profile_em 接口")
    print("=" * 80)
    
    for code in test_codes:
        print(f"\n{'='*80}")
        print(f"测试股票代码: {code}")
        print(f"{'='*80}")
        
        try:
            # 调用接口
            print(f"\n调用 ak.stock_hk_company_profile_em(symbol='{code}')...")
            profile_df = ak.stock_hk_company_profile_em(symbol=code)
            
            if profile_df is None:
                print(f"❌ 返回 None")
                continue
            
            if profile_df.empty:
                print(f"❌ 返回空 DataFrame")
                continue
            
            print(f"\n✅ 返回数据类型: {type(profile_df)}")
            print(f"✅ 数据形状: {profile_df.shape}")
            print(f"✅ 列数: {len(profile_df.columns)}")
            print(f"✅ 行数: {len(profile_df)}")
            
            # 打印列名
            print(f"\n列名:")
            for i, col in enumerate(profile_df.columns, 1):
                print(f"  {i:2d}. {col}")
            
            # 打印完整数据
            print(f"\n完整数据内容:")
            print(profile_df.to_string())
            
            # 解析 key-value 格式
            print(f"\n{'='*80}")
            print("Key-Value 格式解析:")
            print(f"{'='*80}")
            profile_dict = {}
            
            if len(profile_df.columns) >= 2:
                # 第一列是 key，第二列是 value
                for idx, row in profile_df.iterrows():
                    key = str(row.iloc[0]).strip() if len(row) > 0 else None
                    value = row.iloc[1] if len(row) > 1 else None
                    
                    # 处理空值
                    if pd.isna(value) or value == '' or str(value).strip() == '':
                        continue
                    
                    if key:
                        profile_dict[key] = value
                        print(f"  {key:20s} = {value}")
            
            print(f"\n解析后的字典（共 {len(profile_dict)} 个字段）:")
            for key, value in profile_dict.items():
                print(f"  {key}: {value}")
            
            # 检查我们需要的字段
            print(f"\n需要的字段检查:")
            needed_fields = {
                '公司名称': 'org_name_cn',
                '英文名称': 'org_name_en',
                '注册地': 'reg_location',
                '注册地址': 'reg_address',
                '办公地址': 'office_address_cn',
                '联系电话': 'telephone',
                '传真': 'fax',
                'E-MAIL': 'email',
                '公司网址': 'org_website',
                '公司介绍': 'org_cn_introduction',
                '董事长': 'chairman',
                '公司秘书': 'secretary',
                '公司成立日期': 'established_date',
                '员工人数': 'staff_num',
                '所属行业': 'industry',
            }
            
            for chinese_key, english_key in needed_fields.items():
                if chinese_key in profile_dict:
                    print(f"  ✅ {chinese_key} ({english_key}): {profile_dict[chinese_key]}")
                else:
                    print(f"  ❌ {chinese_key} ({english_key}): 缺失")
                    
        except Exception as e:
            print(f"❌ 错误: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_stock_hk_company_profile_em()
