#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 stock_individual_basic_info_xq 接口
检查是否能获取公司全称等信息
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_stock_individual_basic_info_xq():
    """测试 stock_individual_basic_info_xq 接口"""
    print("=" * 60)
    print("测试 stock_individual_basic_info_xq 接口")
    print("=" * 60)
    print()
    
    try:
        import akshare as ak
        print("✅ akshare 导入成功")
    except Exception as e:
        print(f"❌ akshare 导入失败: {e}")
        return False
    
    # 测试几个股票代码（需要带市场前缀：SH=上海，SZ=深圳）
    test_codes = [
        ('SZ000001', '000001', '平安银行'),  # 深圳
        ('SZ000002', '000002', '万科'),      # 深圳
        ('SZ000006', '000006', '深振业'),    # 深圳
        ('SH600036', '600036', '招商银行'),  # 上海
        ('SH601318', '601318', '中国平安'),  # 上海
        ('SH601127', '601127', '示例代码'),  # 用户提供的示例
    ]
    
    success_count = 0
    error_count = 0
    
    for symbol_with_prefix, code, name in test_codes:
        print(f"\n{'='*60}")
        print(f"测试股票代码: {symbol_with_prefix} ({code} - {name})")
        print(f"{'='*60}")
        
        try:
            # 使用带市场前缀的格式（如 SH601127, SZ000001）
            print(f"正在调用 ak.stock_individual_basic_info_xq(symbol='{symbol_with_prefix}')...")
            info_df = ak.stock_individual_basic_info_xq(symbol=symbol_with_prefix)
            
            if info_df is None or info_df.empty:
                print(f"  ❌ 返回数据为空")
                error_count += 1
                continue
            
            print(f"  ✅ 获取成功")
            print(f"    数据形状: {info_df.shape}")
            print(f"    列名: {info_df.columns.tolist()}")
            print()
            
            # 显示所有数据
            print("  返回的所有字段:")
            print("  " + "-" * 56)
            for idx, row in info_df.iterrows():
                # 尝试获取字段名和值
                if len(info_df.columns) >= 2:
                    # 假设是两列：字段名和值
                    field_name = str(row.iloc[0]) if len(row) > 0 else f"列{idx}"
                    field_value = str(row.iloc[1]) if len(row) > 1 else ""
                    
                    # 截断过长的值
                    if len(field_value) > 100:
                        field_value = field_value[:100] + "..."
                    
                    print(f"    {field_name}: {field_value}")
                else:
                    print(f"    行{idx}: {row.to_dict()}")
            
            print()
            
            # 尝试查找关键字段
            print("  查找关键字段:")
            print("  " + "-" * 56)
            
            # 转换为字典（如果可能）
            try:
                if len(info_df.columns) >= 2:
                    # 假设第一列是字段名，第二列是值
                    info_dict = {}
                    for idx, row in info_df.iterrows():
                        key = str(row.iloc[0]).strip()
                        value = str(row.iloc[1]).strip() if len(row) > 1 else ""
                        info_dict[key] = value
                    
                    # 查找可能的全称字段
                    possible_keys = [
                        '公司名称', '公司全称', '公司简称', '股票简称',
                        '英文名称', '曾用简称', '曾用名',
                        '公司', '名称', '全称', '简称'
                    ]
                    
                    found_keys = []
                    for key in possible_keys:
                        for dict_key, dict_value in info_dict.items():
                            if key in dict_key:
                                found_keys.append((dict_key, dict_value))
                                break
                    
                    if found_keys:
                        print("    找到相关字段:")
                        for k, v in found_keys:
                            print(f"      {k}: {v}")
                    else:
                        print("    ⚠️  未找到明显的公司名称字段")
                        print("    所有字段名:")
                        for k in info_dict.keys():
                            print(f"      - {k}")
                else:
                    print(f"    ⚠️  数据格式不符合预期（列数: {len(info_df.columns)}）")
                    print(f"    列名: {info_df.columns.tolist()}")
            except Exception as e:
                print(f"    ⚠️  解析数据时出错: {e}")
            
            success_count += 1
            
        except Exception as e:
            error_msg = str(e)
            print(f"  ❌ 调用失败: {error_msg[:200]}")
            
            # 判断错误类型
            if 'proxy' in error_msg.lower() or 'connection' in error_msg.lower():
                print(f"    错误类型: 网络连接/代理问题")
            elif 'timeout' in error_msg.lower():
                print(f"    错误类型: 请求超时")
            elif 'not found' in error_msg.lower() or '404' in error_msg.lower():
                print(f"    错误类型: 接口不存在或参数错误")
            else:
                print(f"    错误类型: 其他错误")
            
            import traceback
            print(f"\n    详细错误:")
            traceback.print_exc()
            
            error_count += 1
    
    print()
    print("=" * 60)
    print(f"测试结果: 成功 {success_count}/{len(test_codes)}, 失败 {error_count}/{len(test_codes)}")
    print("=" * 60)
    
    if success_count > 0:
        print("\n✅ 接口可用，可以获取数据")
        print("   建议：检查返回的字段结构，确认是否包含公司全称")
    else:
        print("\n❌ 接口调用失败")
        print("   建议：检查接口名称是否正确，或尝试其他接口")
    
    return success_count > 0


if __name__ == "__main__":
    success = test_stock_individual_basic_info_xq()
    sys.exit(0 if success else 1)
