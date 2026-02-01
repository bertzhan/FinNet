#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试方案A：检查 stock_info_a_code_name() 返回的 name 字段是否已经是全称
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_stock_info_a_code_name():
    """测试 stock_info_a_code_name 返回的数据结构"""
    print("=" * 60)
    print("测试方案A：检查 stock_info_a_code_name() 返回的数据")
    print("=" * 60)
    print()
    
    try:
        import akshare as ak
        print("✅ akshare 导入成功")
    except Exception as e:
        print(f"❌ akshare 导入失败: {e}")
        return False
    
    try:
        print("正在调用 ak.stock_info_a_code_name()...")
        stock_df = ak.stock_info_a_code_name()
        
        if stock_df is None or stock_df.empty:
            print("❌ 返回数据为空")
            return False
        
        print(f"✅ 获取数据成功")
        print(f"   数据形状: {stock_df.shape}")
        print(f"   列名: {stock_df.columns.tolist()}")
        print()
        
        # 检查必要的列
        if 'code' not in stock_df.columns or 'name' not in stock_df.columns:
            print(f"❌ 缺少必要的列 (code, name)")
            print(f"   实际列名: {stock_df.columns.tolist()}")
            return False
        
        # 显示前20条数据，分析 name 字段的内容
        print("=" * 60)
        print("前20条数据示例（分析 name 字段是否为全称）:")
        print("=" * 60)
        print()
        
        sample_companies = [
            ('000001', '平安银行'),
            ('000002', '万科'),
            ('000006', '深振业'),
            ('600036', '招商银行'),
            ('601318', '中国平安'),
        ]
        
        # 查找这些公司
        found_companies = []
        for code, expected_name in sample_companies:
            matching = stock_df[stock_df['code'] == code]
            if not matching.empty:
                name = matching.iloc[0]['name']
                found_companies.append((code, expected_name, name))
        
        print("已知公司的 name 字段内容:")
        print("-" * 60)
        for code, expected_short, actual_name in found_companies:
            is_full = False
            indicators = []
            
            # 判断是否可能是全称的指标
            if '股份' in actual_name or '有限' in actual_name:
                is_full = True
                indicators.append("包含'股份'或'有限'")
            
            if len(actual_name) > len(expected_short) + 5:
                is_full = True
                indicators.append(f"长度较长({len(actual_name)}字符)")
            
            if '公司' in actual_name and actual_name.endswith('公司'):
                is_full = True
                indicators.append("以'公司'结尾")
            
            status = "✅ 可能是全称" if is_full else "⚠️  可能是简称"
            print(f"股票代码: {code}")
            print(f"  预期简称: {expected_short}")
            print(f"  实际 name: {actual_name}")
            print(f"  状态: {status}")
            if indicators:
                print(f"  判断依据: {', '.join(indicators)}")
            print()
        
        # 统计所有数据的 name 字段特征
        print("=" * 60)
        print("数据统计分析:")
        print("=" * 60)
        print()
        
        # 统计包含"股份"或"有限"的公司数量
        contains_company_type = stock_df['name'].str.contains('股份|有限', na=False).sum()
        total = len(stock_df)
        percentage = (contains_company_type / total * 100) if total > 0 else 0
        
        print(f"总公司数: {total}")
        print(f"name 字段包含'股份'或'有限'的公司数: {contains_company_type} ({percentage:.1f}%)")
        print()
        
        # 统计 name 字段长度分布
        name_lengths = stock_df['name'].str.len()
        print(f"name 字段长度统计:")
        print(f"  最短: {name_lengths.min()} 字符")
        print(f"  最长: {name_lengths.max()} 字符")
        print(f"  平均: {name_lengths.mean():.1f} 字符")
        print(f"  中位数: {name_lengths.median():.1f} 字符")
        print()
        
        # 显示一些长名称的示例（可能是全称）
        print("=" * 60)
        print("长名称示例（可能是全称）:")
        print("=" * 60)
        print()
        
        long_names = stock_df[name_lengths >= 10].head(10)
        for idx, row in long_names.iterrows():
            print(f"  {row['code']} - {row['name']} ({len(row['name'])}字符)")
        
        print()
        
        # 显示一些短名称的示例（可能是简称）
        print("=" * 60)
        print("短名称示例（可能是简称）:")
        print("=" * 60)
        print()
        
        short_names = stock_df[name_lengths <= 6].head(10)
        for idx, row in short_names.iterrows():
            print(f"  {row['code']} - {row['name']} ({len(row['name'])}字符)")
        
        print()
        print("=" * 60)
        print("结论:")
        print("=" * 60)
        
        if percentage > 50:
            print("✅ name 字段很可能是全称（超过50%包含'股份'或'有限'）")
            print("   建议：可以直接使用 name 字段作为全称，无需调用 stock_individual_info_em")
        elif percentage > 20:
            print("⚠️  name 字段部分是全称（20-50%包含'股份'或'有限'）")
            print("   建议：可以先用 name 字段，对缺失的再调用 stock_individual_info_em")
        else:
            print("❌ name 字段主要是简称（少于20%包含'股份'或'有限'）")
            print("   建议：需要调用 stock_individual_info_em 获取全称")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_stock_info_a_code_name()
    sys.exit(0 if success else 1)
