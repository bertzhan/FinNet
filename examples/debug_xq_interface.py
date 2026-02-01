#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试 stock_individual_basic_info_xq 接口，查看实际返回内容
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import akshare as ak
import requests
import json


def debug_xq_interface(code: str = "000488"):
    """调试接口，查看实际返回内容"""
    print("=" * 60)
    print(f"调试 stock_individual_basic_info_xq 接口")
    print("=" * 60)
    print()
    
    # 确定市场前缀
    if code.startswith('6'):
        symbol_with_prefix = f"SH{code}"
    elif code.startswith(('0', '3')):
        symbol_with_prefix = f"SZ{code}"
    else:
        print(f"❌ 无法确定股票代码 {code} 的市场")
        return False
    
    print(f"股票代码: {code}")
    print(f"完整代码: {symbol_with_prefix}")
    print()
    
    try:
        # 查看 akshare 源码，了解接口如何调用
        import inspect
        source_file = inspect.getfile(ak.stock_individual_basic_info_xq)
        print(f"接口源码文件: {source_file}")
        print()
        
        # 尝试直接查看接口实现
        try:
            source = inspect.getsource(ak.stock_individual_basic_info_xq)
            # 查找 URL
            import re
            url_match = re.search(r'url\s*=\s*["\']([^"\']+)["\']', source)
            if url_match:
                print(f"接口 URL: {url_match.group(1)}")
            print()
        except:
            pass
        
        # 尝试调用接口并捕获原始响应
        print("尝试调用接口...")
        try:
            info_df = ak.stock_individual_basic_info_xq(symbol=symbol_with_prefix)
            print(f"✅ 调用成功")
            print(f"   返回类型: {type(info_df)}")
            if info_df is not None:
                print(f"   数据形状: {info_df.shape}")
                print(f"   列名: {info_df.columns.tolist()}")
        except KeyError as e:
            print(f"❌ KeyError: {e}")
            print("   说明：接口返回的 JSON 中没有预期的字段")
            print()
            print("   可能的原因：")
            print("   1. 接口需要登录/认证")
            print("   2. 接口返回格式已变更")
            print("   3. akshare 版本问题，需要更新")
            print()
            print("   建议：")
            print("   1. 更新 akshare: pip install --upgrade akshare")
            print("   2. 检查 akshare 文档确认接口是否仍可用")
            print("   3. 或继续使用 stock_individual_info_em 接口")
        except Exception as e:
            print(f"❌ 其他错误: {e}")
            import traceback
            traceback.print_exc()
        
    except Exception as e:
        print(f"❌ 调试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="调试 stock_individual_basic_info_xq 接口")
    parser.add_argument("--code", type=str, default="000488", help="股票代码（默认：000488）")
    args = parser.parse_args()
    
    success = debug_xq_interface(args.code)
    sys.exit(0 if success else 1)
