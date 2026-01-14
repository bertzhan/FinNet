#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查看 Dagster 运行结果文件（pickle 格式）
"""

import sys
import pickle
import json
from pathlib import Path


def view_result_file(file_path: str):
    """查看 Dagster 结果文件"""
    file_path = Path(file_path)
    
    if not file_path.exists():
        print(f"❌ 文件不存在: {file_path}")
        return
    
    try:
        # 读取 pickle 文件
        with open(file_path, 'rb') as f:
            data = pickle.load(f)
        
        print("=" * 80)
        print(f"文件: {file_path.name}")
        print("=" * 80)
        print()
        
        # 如果是字典，格式化输出
        if isinstance(data, dict):
            # 使用 JSON 格式输出，确保中文正确显示
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            # 其他类型直接打印
            print(data)
        
        print()
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ 读取失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 view_dagster_result.py <result_file_path>")
        print()
        print("示例:")
        print("  python3 view_dagster_result.py .tmp_dagster_home_xxx/storage/xxx/crawl_a_share_reports_op/result")
        sys.exit(1)
    
    view_result_file(sys.argv[1])
