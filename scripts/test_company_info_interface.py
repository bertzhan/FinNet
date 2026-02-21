#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 stock_individual_basic_info_xq 接口（雪球）

用法:
    python scripts/test_company_info_interface.py
    python scripts/test_company_info_interface.py --code 000001
    python scripts/test_company_info_interface.py --code 600519 000001 000002
"""

import sys
import math
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def _df_to_info_dict(info_df) -> dict:
    """将 akshare 返回的 DataFrame（item/value 列）转为字典"""
    info_dict = {}
    for idx, row in info_df.iterrows():
        item = str(row['item']).strip()
        value = row['value']
        if value is None:
            value = None
        elif isinstance(value, float):
            value = None if math.isnan(value) else value
        elif isinstance(value, (int, bool)):
            value = value
        elif isinstance(value, dict):
            value = value
        else:
            value_str = str(value).strip()
            value = None if value_str in ('', 'None', 'nan', 'NaN') else value_str
        info_dict[item] = value
    return info_dict


def test_stock_individual_basic_info_xq(code: str) -> tuple[bool, dict | None, str]:
    """
    测试 stock_individual_basic_info_xq（雪球）接口

    Returns:
        (是否成功, info_dict 或 None, 错误信息或空字符串)
    """
    import akshare as ak

    # 确定市场前缀
    if code.startswith('6'):
        symbol_with_prefix = f"SH{code}"
    elif code.startswith(('0', '3')):
        symbol_with_prefix = f"SZ{code}"
    elif code.startswith('9'):
        symbol_with_prefix = f"BJ{code}"
    else:
        return False, None, "无法确定市场前缀"

    try:
        info_df = ak.stock_individual_basic_info_xq(symbol=symbol_with_prefix)
        if info_df is None or info_df.empty:
            return False, None, "返回数据为空"
        info_dict = _df_to_info_dict(info_df)
        return True, info_dict, ""
    except KeyError as e:
        return False, None, f"KeyError: {e}（雪球接口可能已变更）"
    except Exception as e:
        return False, None, f"{type(e).__name__}: {e}"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="测试 stock_individual_basic_info_xq（雪球）接口")
    parser.add_argument("--code", "-c", nargs="+", default=["000001", "600519"],
                        help="股票代码，可多个（默认: 000001 600519）")
    args = parser.parse_args()

    print("=" * 70)
    print("stock_individual_basic_info_xq（雪球）接口测试")
    print("=" * 70)
    print()

    success_count = 0
    for code in args.code:
        print(f"【{code}】")
        print("-" * 50)
        try:
            ok, info, err = test_stock_individual_basic_info_xq(code)
            if ok and info:
                success_count += 1
                print("  ✅ 成功")
                for key in ['org_name_cn', 'org_short_name_cn', 'org_name_en', 'classi_name',
                            'listed_date', 'chairman', 'legal_representative']:
                    if key in info and info[key] is not None:
                        print(f"     {key}: {info[key]}")
            else:
                print(f"  ❌ 失败: {err}")
        except Exception as e:
            print(f"  ❌ 异常: {e}")
        print()

    print("=" * 70)
    print(f"结果: {success_count}/{len(args.code)} 成功")
    print("=" * 70)
    return 0 if success_count == len(args.code) else 1


if __name__ == "__main__":
    sys.exit(main())
