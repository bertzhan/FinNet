# -*- coding: utf-8 -*-
"""
通用工具函数
提供日期处理、文件操作、字符串处理等常用功能
"""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import re

from .constants import QUARTER_MAP


def get_current_quarter() -> tuple[int, int]:
    """
    获取当前年份和季度

    Returns:
        (年份, 季度)

    Example:
        >>> get_current_quarter()
        (2025, 1)
    """
    now = datetime.now()
    year = now.year
    month = now.month

    if month <= 3:
        quarter = 1
    elif month <= 6:
        quarter = 2
    elif month <= 9:
        quarter = 3
    else:
        quarter = 4

    return year, quarter


def get_previous_quarter(year: int, quarter: int) -> tuple[int, int]:
    """
    获取上一季度

    Args:
        year: 年份
        quarter: 季度

    Returns:
        (年份, 季度)

    Example:
        >>> get_previous_quarter(2025, 1)
        (2024, 4)
    """
    if quarter == 1:
        return year - 1, 4
    else:
        return year, quarter - 1


def quarter_to_string(quarter: int) -> str:
    """
    季度数字转字符串

    Args:
        quarter: 季度 (1-4)

    Returns:
        季度字符串 (Q1-Q4)

    Example:
        >>> quarter_to_string(1)
        'Q1'
    """
    return QUARTER_MAP.get(quarter, f"Q{quarter}")


def string_to_quarter(quarter_str: str) -> int:
    """
    季度字符串转数字

    Args:
        quarter_str: 季度字符串 (Q1-Q4 或 1-4)

    Returns:
        季度数字 (1-4)

    Example:
        >>> string_to_quarter("Q1")
        1
        >>> string_to_quarter("3")
        3
    """
    quarter_str = quarter_str.upper().strip()

    if quarter_str.startswith('Q'):
        quarter_str = quarter_str[1:]

    try:
        quarter = int(quarter_str)
        if 1 <= quarter <= 4:
            return quarter
    except ValueError:
        pass

    raise ValueError(f"Invalid quarter string: {quarter_str}")


def calculate_file_hash(file_path: Union[str, Path], algorithm: str = "md5") -> str:
    """
    计算文件哈希值

    Args:
        file_path: 文件路径
        algorithm: 哈希算法 (md5, sha256)

    Returns:
        文件哈希值

    Example:
        >>> calculate_file_hash("test.pdf")
        'a1b2c3d4e5f6...'
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    hash_func = hashlib.new(algorithm)

    with open(file_path, 'rb') as f:
        # 分块读取，避免大文件内存溢出
        for chunk in iter(lambda: f.read(8192), b''):
            hash_func.update(chunk)

    return hash_func.hexdigest()


def safe_filename(filename: str) -> str:
    """
    清理文件名，移除非法字符

    Args:
        filename: 原始文件名

    Returns:
        安全的文件名

    Example:
        >>> safe_filename("平安银行<2023>年报.pdf")
        '平安银行_2023_年报.pdf'
    """
    # 替换非法字符为下划线
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)

    # 移除多余的下划线
    filename = re.sub(r'_+', '_', filename)

    # 移除首尾下划线
    filename = filename.strip('_')

    return filename


def ensure_dir(path: Union[str, Path]) -> Path:
    """
    确保目录存在，不存在则创建

    Args:
        path: 目录路径

    Returns:
        Path 对象

    Example:
        >>> ensure_dir("/data/bronze/a_share")
        PosixPath('/data/bronze/a_share')
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_json(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    加载 JSON 文件

    Args:
        file_path: JSON 文件路径

    Returns:
        JSON 数据字典

    Example:
        >>> load_json("config.json")
        {'key': 'value'}
    """
    file_path = Path(file_path)

    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data: Dict[str, Any], file_path: Union[str, Path], indent: int = 2) -> None:
    """
    保存数据为 JSON 文件

    Args:
        data: 要保存的数据
        file_path: 保存路径
        indent: 缩进空格数

    Example:
        >>> save_json({'key': 'value'}, "output.json")
    """
    file_path = Path(file_path)
    ensure_dir(file_path.parent)

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小

    Args:
        size_bytes: 字节数

    Returns:
        格式化后的大小字符串

    Example:
        >>> format_file_size(1024)
        '1.00 KB'
        >>> format_file_size(1048576)
        '1.00 MB'
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def extract_text_from_table(table_html: str, remove_numbers: bool = True) -> str:
    """
    从表格HTML中提取文本内容
    
    移除HTML标签，保留表格中的文本内容，用于向量化。
    可选择性地移除数字内容。
    
    Args:
        table_html: 包含表格HTML的文本
        remove_numbers: 是否移除数字（默认True，移除纯数字和带单位的数字）
        
    Returns:
        提取的纯文本内容（已移除数字）
        
    Example:
        >>> html = "<table><tr><td>收入</td><td>1000万元</td><td>2024年</td></tr></table>"
        >>> extract_text_from_table(html)
        "收入"
        >>> extract_text_from_table(html, remove_numbers=False)
        "收入 1000万元 2024年"
    """
    if not table_html:
        return ""
    
    # 移除HTML标签，保留文本内容
    # 使用正则表达式移除所有HTML标签
    text = re.sub(r'<[^>]+>', ' ', table_html)
    
    # 如果启用数字移除，剔除数字内容
    if remove_numbers:
        # 移除带单位的数字（如：1000万元、50%、2024年、1.5倍等）
        # 匹配数字+常见单位/符号，包括：
        # - 货币单位：元、万元、亿元、美元等
        # - 百分比：%（需要和数字一起移除）
        # - 时间单位：年、月、日、季度、期等（但保留地址中的门牌号，如"625号"）
        # - 其他单位：倍、次、个、项等
        # 先移除带单位的数字，避免重复匹配
        # 注意：不匹配地址中的门牌号（如"625号"），因为门牌号对语义搜索有意义
        text = re.sub(r'\d+[.,]?\d*\s*[万千亿]?[元美元]?%?[年月日季度期倍次个项]', '', text)
        
        # 移除百分比（如：38.63%、-6.92%等）
        text = re.sub(r'[+-]?\d+\.?\d*%', '', text)
        
        # 移除大额数字（通常用于财务数据，如：426,576,751.08）
        # 匹配包含千分位分隔符的数字（通常是财务数据）
        text = re.sub(r'\d{1,3}(?:,\d{3})+(?:\.\d+)?', '', text)
        
        # 移除纯数字（连续的数字，可能包含小数点）
        # 例如：1000, 1.5, 1000.00, -100, +50
        # 但保留短数字（可能是门牌号、年份等有意义的信息）
        # 只移除较长的数字（通常是无意义的财务数据）
        text = re.sub(r'[+-]?\d{4,}(?:\.\d+)?', '', text)  # 移除4位及以上的数字
        text = re.sub(r'[+-]?\d+\.\d{2,}', '', text)  # 移除带小数点的数字（通常是金额）
        
        # 清理残留的逗号、连字符、百分比符号等
        text = re.sub(r'\s*[,，]\s*', ' ', text)  # 移除逗号
        text = re.sub(r'\s*-\s*-', '', text)  # 移除双连字符
        text = re.sub(r'\s*%\s*', ' ', text)  # 移除单独的百分比符号
    
    # 清理多余空白：多个空格/换行符合并为一个空格
    text = re.sub(r'\s+', ' ', text)
    
    # 移除首尾空白
    text = text.strip()
    
    return text


def clean_text(text: str) -> str:
    """
    清洗文本，但保留单个换行符
    
    清理规则：
    - 将多个连续空格合并为单个空格（行内）
    - 将多个连续换行符（3个以上）合并为2个
    - 保留单个换行符
    - 移除首尾空白

    Args:
        text: 原始文本

    Returns:
        清洗后的文本

    Example:
        >>> clean_text("  这是  一段   文本\\n\\n\\n另一段")
        '这是 一段 文本\\n另一段'
    """
    if not text:
        return text
    
    # 先处理换行符：将2个以上连续换行符合并为1个
    text = re.sub(r'\n{2,}', '\n', text)
    
    # 按行处理，清理每行内的多余空格
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # 清理行内多余空格（多个连续空格合并为单个空格）
        cleaned_line = re.sub(r' +', ' ', line)
        # 移除行首尾空白
        cleaned_line = cleaned_line.strip()
        cleaned_lines.append(cleaned_line)
    
    # 重新组合，保留换行符
    result = '\n'.join(cleaned_lines)
    
    # 移除首尾空白
    result = result.strip()
    
    return result


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    截断文本

    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 截断后缀

    Returns:
        截断后的文本

    Example:
        >>> truncate_text("这是一段很长的文本", max_length=5)
        '这是一段很...'
    """
    if len(text) <= max_length:
        return text

    return text[:max_length] + suffix


def is_valid_stock_code(code: str, market: str = "a_share") -> bool:
    """
    验证股票代码格式

    Args:
        code: 股票代码
        market: 市场类型 (a_share, hk_stock, us_stock)

    Returns:
        是否有效

    Example:
        >>> is_valid_stock_code("000001", "a_share")
        True
        >>> is_valid_stock_code("AAPL", "us_stock")
        True
    """
    if market == "a_share":
        # A股：6位数字
        return bool(re.match(r'^\d{6}$', code))
    elif market == "hk_stock":
        # 港股：5位数字
        return bool(re.match(r'^\d{5}$', code))
    elif market == "us_stock":
        # 美股：1-5个字母
        return bool(re.match(r'^[A-Z]{1,5}$', code.upper()))
    else:
        return False


def retry_on_exception(
    func,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    带重试的函数装饰器

    Args:
        func: 要包装的函数
        max_retries: 最大重试次数
        delay: 初始延迟（秒）
        backoff: 延迟倍增因子
        exceptions: 需要捕获的异常类型

    Example:
        @retry_on_exception(max_retries=3)
        def my_function():
            pass
    """
    import time
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        current_delay = delay
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                if attempt == max_retries:
                    raise
                time.sleep(current_delay)
                current_delay *= backoff
        return None

    return wrapper
