#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 akshare 获取公司全称功能
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_akshare_full_name():
    """测试获取单个公司的全称"""
    try:
        import akshare as ak
    except Exception as e:
        print(f"❌ 导入 akshare 失败: {e}")
        return False
    
    # 测试几个股票代码
    test_codes = [
        ('000001', '平安银行'),
        ('000002', '万科'),
        ('000006', '深振业'),
    ]
    
    print("=" * 60)
    print("测试 akshare stock_individual_info_em 接口")
    print("=" * 60)
    print()
    
    success_count = 0
    error_count = 0
    
    for code, name in test_codes:
        print(f"测试股票代码: {code} ({name})")
        print("-" * 60)
        
        try:
            # 获取公司详细信息
            info_df = ak.stock_individual_info_em(symbol=code)
            
            if info_df is None or info_df.empty:
                print(f"  ❌ 返回数据为空")
                error_count += 1
                continue
            
            print(f"  ✅ 获取成功，共 {len(info_df)} 条信息")
            
            # 转换为字典便于查找
            info_dict = dict(zip(info_df['item'], info_df['value']))
            
            # 查找关键字段
            full_name = info_dict.get('公司名称', None)
            english_name = info_dict.get('英文名称', None)
            former_names = info_dict.get('曾用简称', None)
            stock_name = info_dict.get('股票简称', None)
            
            print(f"  股票简称: {stock_name}")
            print(f"  公司名称（全称）: {full_name}")
            print(f"  英文名称: {english_name}")
            print(f"  曾用简称: {former_names}")
            
            if full_name:
                success_count += 1
                print(f"  ✅ 成功获取全称: {full_name}")
            else:
                print(f"  ⚠️  未找到公司全称字段")
                error_count += 1
            
        except Exception as e:
            error_msg = str(e)
            print(f"  ❌ 获取失败: {error_msg[:200]}")
            
            # 判断错误类型
            if 'proxy' in error_msg.lower() or 'connection' in error_msg.lower():
                print(f"    错误类型: 网络连接/代理问题")
            elif 'timeout' in error_msg.lower():
                print(f"    错误类型: 请求超时")
            else:
                print(f"    错误类型: 其他错误")
            
            error_count += 1
        
        print()
    
    print("=" * 60)
    print(f"测试结果: 成功 {success_count}/{len(test_codes)}, 失败 {error_count}/{len(test_codes)}")
    print("=" * 60)
    
    return success_count > 0


if __name__ == "__main__":
    success = test_akshare_full_name()
    sys.exit(0 if success else 1)
