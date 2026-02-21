#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试 get_hs_companies_op 中 listed_date、established_date 的插入问题

用法:
    python scripts/debug_hs_date_fields.py
    python scripts/debug_hs_date_fields.py --code 600519 000001
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def _df_to_info_dict(info_df) -> dict:
    """与 company_list_jobs 中相同的转换逻辑"""
    import math
    from datetime import datetime, date
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
        elif isinstance(value, (datetime, date)) or (hasattr(value, 'date') and callable(getattr(value, 'date', None))):
            value = value
        else:
            value_str = str(value).strip()
            value = None if value_str in ('', 'None', 'nan', 'NaN') else value_str
        info_dict[item] = value
    return info_dict


def debug_date_fields(code: str) -> bool:
    """调试单个股票的日期字段"""
    import akshare as ak

    if code.startswith('6'):
        symbol = f"SH{code}"
    elif code.startswith(('0', '3')):
        symbol = f"SZ{code}"
    elif code.startswith('9'):
        symbol = f"BJ{code}"
    else:
        print(f"  无法确定市场: {code}")
        return False

    try:
        info_df = ak.stock_individual_basic_info_xq(symbol=symbol)
        if info_df is None or info_df.empty:
            print(f"  {code}: 返回数据为空")
            return False

        info_dict = _df_to_info_dict(info_df)

        # 检查日期相关 key
        date_keys = ['成立日期', '上市日期', 'established_date', 'listed_date']
        print(f"  {code} ({symbol}):")
        for k in date_keys:
            v = info_dict.get(k)
            if v is not None:
                print(f"    {k}: {repr(v)} (type={type(v).__name__})")
            else:
                print(f"    {k}: 无")
        return True
    except Exception as e:
        print(f"  {code}: 错误 {e}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="调试 HS 公司 listed_date、established_date 字段")
    parser.add_argument("--code", "-c", nargs="+", default=["600519", "000001"],
                        help="股票代码（默认: 600519 000001）")
    args = parser.parse_args()

    print("=" * 60)
    print("调试 stock_individual_basic_info_xq 日期字段")
    print("=" * 60)
    for code in args.code:
        debug_date_fields(code)
    print("=" * 60)


if __name__ == "__main__":
    main()
