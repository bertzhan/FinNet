# -*- coding: utf-8 -*-
"""
测试 akshare 港股公司详细信息接口
查看实际返回的字段结构
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(project_root))

def test_stock_hk_company_profile_em():
    """测试 stock_hk_company_profile_em 接口"""
    try:
        import akshare as ak
        import pandas as pd
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("请运行: pip install akshare pandas")
        return False
    
    # 测试几个港股代码
    test_codes = ['00001', '00700', '00939']  # 長和、騰訊、建設銀行
    
    print("=" * 80)
    print("测试 akshare.stock_hk_company_profile_em 接口")
    print("=" * 80)
    
    for code in test_codes:
        print(f"\n{'='*80}")
        print(f"测试代码: {code}")
        print(f"{'='*80}")
        
        try:
            profile = ak.stock_hk_company_profile_em(symbol=code)
            
            if profile is None:
                print(f"  ❌ 返回 None")
                continue
            
            if profile.empty:
                print(f"  ❌ 返回空 DataFrame")
                continue
            
            print(f"\n  ✅ 返回数据类型: {type(profile)}")
            print(f"  ✅ 数据形状: {profile.shape}")
            print(f"  ✅ 列名 ({len(profile.columns)} 列):")
            
            for i, col in enumerate(profile.columns, 1):
                print(f"      {i}. {col}")
            
            print(f"\n  📊 数据内容:")
            print(profile.to_string())
            
            # 如果是 key-value 格式，显示映射关系
            if len(profile.columns) >= 2:
                print(f"\n  🔑 Key-Value 映射:")
                for idx, row in profile.iterrows():
                    key = str(row.iloc[0]).strip()
                    value = row.iloc[1] if len(row) > 1 else None
                    if pd.notna(value) and value != '':
                        print(f"      {key}: {value}")
            
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            import traceback
            traceback.print_exc()
    
    return True


def test_stock_hk_security_profile_em():
    """测试 stock_hk_security_profile_em 接口（原代码使用的）"""
    try:
        import akshare as ak
        import pandas as pd
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False
    
    test_codes = ['00001', '00700']
    
    print("\n" + "=" * 80)
    print("测试 akshare.stock_hk_security_profile_em 接口（原代码使用的）")
    print("=" * 80)
    
    for code in test_codes:
        print(f"\n{'='*80}")
        print(f"测试代码: {code}")
        print(f"{'='*80}")
        
        try:
            profile = ak.stock_hk_security_profile_em(symbol=code)
            
            if profile is None:
                print(f"  ❌ 返回 None")
                continue
            
            if profile.empty:
                print(f"  ❌ 返回空 DataFrame")
                continue
            
            print(f"\n  ✅ 返回数据类型: {type(profile)}")
            print(f"  ✅ 数据形状: {profile.shape}")
            print(f"  ✅ 列名 ({len(profile.columns)} 列):")
            
            for i, col in enumerate(profile.columns, 1):
                print(f"      {i}. {col}")
            
            print(f"\n  📊 数据内容:")
            print(profile.to_string())
            
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            import traceback
            traceback.print_exc()
    
    return True


if __name__ == '__main__':
    print("开始测试...")
    
    # 测试两个接口
    test_stock_hk_company_profile_em()
    test_stock_hk_security_profile_em()
    
    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)
    print("\n请根据实际返回的字段调整 akshare_helper.py 中的字段映射")
