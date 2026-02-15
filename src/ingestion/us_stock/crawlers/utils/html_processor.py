# -*- coding: utf-8 -*-
"""
HTML处理工具（编码保持和图片路径重写）
适配自 SEC-Filings-ETL/utils/html_processor.py

核心原则：
1. 保留原始编码声明（ASCII、UTF-8等）
2. 使用html.parser避免字符标准化
3. 仅修改<img src>属性，其他内容保持不变
4. 优雅处理编码边界情况
"""
import re
from typing import Dict
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urlparse

from src.common.logger import get_logger

logger = get_logger(__name__)


def detect_encoding(content_bytes: bytes) -> str:
    """
    从HTML/XML内容中检测声明的编码

    Args:
        content_bytes: HTML内容的原始字节

    Returns:
        检测到的编码字符串（如：'ascii', 'utf-8'）
    """
    # 在前500字节中搜索编码声明
    header = content_bytes[:500]

    # 匹配模式如 encoding='ASCII' 或 encoding="UTF-8"
    match = re.search(rb"encoding=['\"]([^'\"]+)['\"]", header, re.IGNORECASE)

    if match:
        declared = match.group(1).decode('ascii').lower()

        # 标准化编码名称
        if 'ascii' in declared:
            return 'ascii'
        elif 'utf' in declared:
            return 'utf-8'
        elif 'iso-8859' in declared or 'latin' in declared:
            return 'latin-1'
        else:
            return declared

    # 如果未找到声明，默认使用UTF-8
    return 'utf-8'


def process_html_preserve_encoding(
    content_bytes: bytes,
    img_replacements: Dict[str, str]
) -> bytes:
    """
    处理HTML内容，同时保留原始编码

    此函数：
    1. 检测原始编码声明
    2. 使用html.parser避免字符标准化（防止乱码）
    3. 根据替换映射替换图片src属性
    4. 使用原始编码输出，以保持字节级准确性

    Args:
        content_bytes: 原始HTML内容（字节）
        img_replacements: 旧图片URL到新本地路径的映射字典
                         例如：{"https://sec.gov/img.gif": "./local_img-001.gif"}

    Returns:
        处理后的HTML内容（字节），保留原始编码

    Example:
        >>> html = b'<?xml version="1.0" encoding="ASCII"?><html><img src="http://sec.gov/a.gif"/></html>'
        >>> replacements = {"http://sec.gov/a.gif": "./local.gif"}
        >>> result = process_html_preserve_encoding(html, replacements)
        >>> b"./local.gif" in result
        True
        >>> b"encoding='ASCII'" in result  # 编码已保留
        True
    """
    # 检测原始编码
    original_encoding = detect_encoding(content_bytes)

    logger.debug(
        f"处理HTML，编码: {original_encoding}，替换数: {len(img_replacements)}",
        extra={
            "original_encoding": original_encoding,
            "replacements_count": len(img_replacements)
        }
    )

    # 使用检测到的编码解码
    try:
        content_str = content_bytes.decode(original_encoding)
    except (UnicodeDecodeError, LookupError) as e:
        # 回退到UTF-8并处理错误
        logger.warning(
            f"编码解码失败: {original_encoding}，回退到UTF-8",
            extra={
                "declared_encoding": original_encoding,
                "error": str(e)
            }
        )
        content_str = content_bytes.decode('utf-8', errors='replace')
        original_encoding = 'utf-8'

    # 使用html.parser解析（不使用lxml），避免字符标准化
    # html.parser保留ASCII字符原样，不会转换为UTF-8
    soup = BeautifulSoup(content_str, 'html.parser')

    # 跟踪是否有修改
    modified = False
    modifications_count = 0

    # 查找所有img标签并替换src属性
    img_tags = soup.find_all('img')

    for img in img_tags:
        src = img.get('src')

        if not src:
            continue

        # 检查此src是否应该被替换
        if src in img_replacements:
            new_src = img_replacements[src]
            img['src'] = new_src
            modified = True
            modifications_count += 1

            logger.debug(
                f"图片src已替换: {src[:100]} -> {new_src}",
                extra={
                    "old_src": src[:100],  # 截断以便记录
                    "new_src": new_src
                }
            )

    if modified:
        logger.info(
            f"HTML已处理，替换图片数: {modifications_count}",
            extra={
                "images_replaced": modifications_count,
                "encoding": original_encoding
            }
        )

    # 转换回字符串
    result_str = str(soup)

    # 确定输出编码：若原始编码无法表示解析后的 Unicode 字符（如 BeautifulSoup 将 &#8217; 转为 '），
    # 则升级为 UTF-8，避免 errors='replace' 将字符变成 ?
    output_encoding = original_encoding
    try:
        result_str.encode(original_encoding)
    except UnicodeEncodeError:
        # 内容超出原始编码范围（如 ASCII 声明但含弯引号、em-dash 等），改用 UTF-8
        output_encoding = 'utf-8'
        result_str = _update_encoding_declaration(result_str, 'utf-8')
        logger.info(
            f"内容含原始编码无法表示的字符，升级为 UTF-8 输出（避免出现 ?）",
            extra={
                "original_encoding": original_encoding,
                "output_encoding": output_encoding
            }
        )

    try:
        result_bytes = result_str.encode(output_encoding)
    except (UnicodeEncodeError, LookupError) as e:
        logger.warning(
            f"编码失败 {output_encoding}，回退到 UTF-8",
            extra={"error": str(e)}
        )
        result_str = _update_encoding_declaration(result_str, 'utf-8')
        result_bytes = result_str.encode('utf-8')

    return result_bytes


def _update_encoding_declaration(html_str: str, new_encoding: str) -> str:
    """
    更新 HTML/XML 中的 encoding 声明为指定编码

    Args:
        html_str: HTML 字符串
        new_encoding: 新编码（如 'utf-8'）

    Returns:
        更新声明后的 HTML 字符串
    """
    return re.sub(
        r"(encoding\s*=\s*)(['\"])([^'\"]+)(['\"])",
        rf"\1\2{new_encoding}\4",
        html_str,
        count=1,
        flags=re.IGNORECASE
    )


def build_image_replacement_mapping(
    html_url: str,
    image_artifacts: list
) -> Dict[str, str]:
    """
    构建从图片引用到本地相对路径的映射

    此函数处理多种图片引用格式：
    1. 完整SEC URL: https://www.sec.gov/Archives/edgar/data/.../image.gif
    2. 相对SEC路径: /Archives/edgar/data/.../image.gif
    3. 仅文件名引用: aapl-20250927_g1.jpg

    Args:
        html_url: HTML文档的URL（用于解析相对URL）
        image_artifacts: Artifact对象列表，具有url、filename和local_path属性

    Returns:
        图片引用（URL或文件名）到本地相对路径的映射字典

    Example:
        >>> artifacts = [
        ...     MockArtifact(
        ...         url="https://sec.gov/data/123/img1.gif",
        ...         filename="img1.gif",
        ...         local_path="NASDAQ/AAPL/2025/AAPL_2025_FY_31-10-2025_image-001.gif"
        ...     )
        ... ]
        >>> mapping = build_image_replacement_mapping("https://sec.gov/filing.html", artifacts)
        >>> mapping["https://sec.gov/data/123/img1.gif"]
        './AAPL_2025_FY_31-10-2025_image-001.gif'
        >>> mapping["img1.gif"]  # 也按文件名映射
        './AAPL_2025_FY_31-10-2025_image-001.gif'
    """
    mapping = {}

    for artifact in image_artifacts:
        remote_url = artifact.url
        original_filename = artifact.filename if hasattr(artifact, 'filename') else Path(remote_url).name
        local_path = artifact.local_path

        # 将绝对本地路径转换为相对路径（仅文件名）
        local_filename = Path(local_path).name
        relative_path = f"./{local_filename}"

        # 映射1: 完整URL → 本地路径
        mapping[remote_url] = relative_path

        # 映射2: 仅文件名 → 本地路径
        # 处理HTML中有相对引用的情况，如 "aapl-20250927_g1.jpg"
        mapping[original_filename] = relative_path

        # 映射3: URL路径（无域名）→ 本地路径
        # 处理如 "/Archives/edgar/data/.../image.gif" 的情况
        parsed = urlparse(remote_url)
        if parsed.path:
            mapping[parsed.path] = relative_path

    logger.debug(
        f"构建图片映射，映射数: {len(mapping)}",
        extra={
            "mapping_size": len(mapping),
            "artifacts_count": len(image_artifacts)
        }
    )

    return mapping


def validate_encoding_preserved(
    original_bytes: bytes,
    processed_bytes: bytes
) -> bool:
    """
    验证HTML处理期间编码是否已保留

    检查：
    1. 声明的编码在两个版本中匹配
    2. ASCII文件中未引入UTF-8多字节字符
    3. 文件大小增加很小（仅由于路径更改）

    Args:
        original_bytes: 原始HTML内容
        processed_bytes: 处理后的HTML内容

    Returns:
        如果编码正确保留则返回True，否则返回False
    """
    # 提取编码声明
    original_encoding = detect_encoding(original_bytes)
    processed_encoding = detect_encoding(processed_bytes)

    if original_encoding != processed_encoding:
        logger.error(
            f"编码不匹配: 原始={original_encoding}, 处理后={processed_encoding}",
            extra={
                "original": original_encoding,
                "processed": processed_encoding
            }
        )
        return False

    # 如果原始声明ASCII，检查UTF-8多字节序列
    if original_encoding == 'ascii':
        # 常见的UTF-8多字节模式
        utf8_patterns = [
            b'\xe2\x80\x99',  # 右单引号 '
            b'\xe2\x80\x98',  # 左单引号 '
            b'\xe2\x80\x9c',  # 左双引号 "
            b'\xe2\x80\x9d',  # 右双引号 "
            b'\xe2\x80\x94',  # em-dash —
            b'\xe2\x80\x93',  # en-dash –
        ]

        for pattern in utf8_patterns:
            if pattern in processed_bytes:
                logger.error(
                    f"ASCII文件中发现UTF-8字符: {pattern.hex()}",
                    extra={
                        "pattern": pattern.hex(),
                        "encoding": original_encoding
                    }
                )
                return False

    # 检查文件大小增加是否合理（< 10% 或 < 10KB）
    size_diff = len(processed_bytes) - len(original_bytes)
    size_increase_pct = (size_diff / len(original_bytes)) * 100 if len(original_bytes) > 0 else 0

    if size_increase_pct > 10 and size_diff > 10000:
        logger.warning(
            f"文件大小增加过多: {size_diff} 字节 ({size_increase_pct:.2f}%)",
            extra={
                "size_diff": size_diff,
                "size_increase_pct": f"{size_increase_pct:.2f}%"
            }
        )
        # 不失败，仅警告 - 可能是合法的路径更改

    logger.info(
        f"编码验证通过: {original_encoding}",
        extra={
            "encoding": original_encoding,
            "size_diff": size_diff
        }
    )

    return True
