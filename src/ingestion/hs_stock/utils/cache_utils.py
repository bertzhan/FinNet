# -*- coding: utf-8 -*-
"""
缓存工具函数
"""

import os
import csv
from typing import Dict, List

from ..config import CODE_CHANGE_CACHE_FILE, NAME_CHANGE_CSV, CSV_ENCODING
from .file_utils import load_json, save_json


def load_code_change_cache() -> Dict[str, List[str]]:
    """
    加载股票代码变更缓存
    格式: {orgId: [old_code, new_code, ...]}
    """
    return load_json(CODE_CHANGE_CACHE_FILE, {})


def save_code_change_cache(cache: Dict[str, List[str]]):
    """
    保存股票代码变更缓存
    
    Args:
        cache: 代码变更缓存字典
    """
    save_json(CODE_CHANGE_CACHE_FILE, cache)


def append_name_change(csv_path: str, code: str, name_input: str, name_api: str):
    """
    追加名称变更记录到CSV文件
    
    Args:
        csv_path: CSV文件路径
        code: 股票代码
        name_input: 输入的名称
        name_api: API返回的名称
    """
    exists = os.path.exists(csv_path)
    with open(csv_path, "a" if exists else "w", encoding=CSV_ENCODING, newline="", errors="replace") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["code", "name_input", "name_from_api"])
        w.writerow([code, name_input, name_api])
