# -*- coding: utf-8 -*-
"""
测试 akshare.stock_hk_security_profile_em 接口
打印接口返回的所有字段信息
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import akshare as ak
    import pandas as pd
except ImportError as e:
    print(f"导入失败: {e}")
    print("请确保已安装 akshare: pip install akshare")
    sys.exit(1)


def test_stock_hk_security_profile_em(stock_code: str = "00001"):
    """
    测试 stock_hk_security_profile_em 接口
    
    Args:
        stock_code: 股票代码（5位数字，如：00001）
    """
    print(f"=" * 80)
    print(f"测试股票代码: {stock_code}")
    print(f"=" * 80)
    
    try:
        # 调用接口
        print(f"\n正在调用 ak.stock_hk_security_profile_em(symbol='{stock_code}')...")
        profile_df = ak.stock_hk_security_profile_em(symbol=stock_code)
        
        if profile_df is None:
            print("❌ 接口返回 None")
            return
        
        if profile_df.empty:
            print("❌ 接口返回空 DataFrame")
            return
        
        print(f"\n✅ 接口调用成功")
        print(f"DataFrame 形状: {profile_df.shape}")
        print(f"列数: {len(profile_df.columns)}")
        print(f"行数: {len(profile_df)}")
        
        # 打印列名
        print(f"\n{'=' * 80}")
        print("DataFrame 列名:")
        print(f"{'=' * 80}")
        for i, col in enumerate(profile_df.columns, 1):
            print(f"{i:2d}. {col}")
        
        # 打印数据类型
        print(f"\n{'=' * 80}")
        print("数据类型:")
        print(f"{'=' * 80}")
        print(profile_df.dtypes)
        
        # 打印完整数据
        print(f"\n{'=' * 80}")
        print("完整数据内容:")
        print(f"{'=' * 80}")
        print(profile_df.to_string())
        
        # 如果 DataFrame 是 key-value 格式（第一列是字段名，第二列是值）
        if len(profile_df.columns) >= 2:
            print(f"\n{'=' * 80}")
            print("Key-Value 格式解析:")
            print(f"{'=' * 80}")
            profile_dict = {}
            for idx, row in profile_df.iterrows():
                key = str(row.iloc[0]).strip() if len(row) > 0 else None
                value = row.iloc[1] if len(row) > 1 else None
                
                # 处理空值
                if pd.isna(value) or value == '' or str(value).strip() == '':
                    value = None
                
                if key:
                    profile_dict[key] = value
                    print(f"{key:20s} = {value}")
            
            print(f"\n{'=' * 80}")
            print(f"解析后的字典（共 {len(profile_dict)} 个字段）:")
            print(f"{'=' * 80}")
            for key, value in profile_dict.items():
                print(f"  {key}: {value}")
        
        # 打印 DataFrame 的 info
        print(f"\n{'=' * 80}")
        print("DataFrame.info():")
        print(f"{'=' * 80}")
        profile_df.info()
        
    except Exception as e:
        print(f"\n❌ 调用失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 测试几个不同的股票代码
    test_codes = ["00001", "00700", "09988"]  # 长和、腾讯、阿里
    
    for code in test_codes:
        test_stock_hk_security_profile_em(code)
        print("\n\n")
