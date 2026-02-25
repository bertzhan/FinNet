#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中文分块模式
第X节、一、、（一）、1.1 等格式
"""

import re
from typing import List, Optional, Tuple

from .base import ChunkMode


def _is_toc_section_entry(heading: str) -> bool:
    """判断是否为目录项（第X节后带 .. 或页号），而非正文一级标题"""
    if not heading or not heading.strip().startswith("第"):
        return False
    s = heading.strip()
    if not re.search(r"^第[一二三四五六七八九十\d]+[节章]", s):
        return False
    # 目录项特征：结尾带页号、. 、.. 等
    if re.search(r"\s\d+\s*$", s):  # "第一节 XXX 2"
        return True
    if re.search(r"\.\s*\d*\s*$", s):  # "第二节 XXX." 或 "第三节 XXX. 11"
        return True
    if ".." in s and re.search(r"\.\.\s*\d", s):  # "第四节 XXX. .. 31"
        return True
    return False


class ChineseChunkMode(ChunkMode):
    """中文模式：第X节、一、、（一）、1.1 等多级格式"""

    def should_reject_heading(self, heading: str, pattern_name: str) -> bool:
        """拒绝目录项（第X节后带 .. 或页号），这些不是正文一级标题"""
        if pattern_name == "一级标题（第X节/章）" and _is_toc_section_entry(heading):
            return True
        return False

    def get_patterns(self) -> List[Tuple[str, int, str]]:
        return [
            (r"^第[一二三四五六七八九十\d]+[节章]", 1, "一级标题（第X节/章）"),
            (r"^[一二三四五六七八九十百]+、", 2, "二级标题（中文数字）"),
            (r"^（[一二三四五六七八九十百]+）", 3, "三级标题（中文括号）"),
            (r"^\([一二三四五六七八九十百]+\)", 3, "三级标题（英文括号中文数字）"),
            (r"^\d+[、.]", 3, "三级标题（数字编号）"),
            (r"^\d+[．.]", 3, "三级标题（数字全角句号）"),
            (r"^（\d+）", 4, "四级标题（中文括号数字）"),
            (r"^\(\d+\)", 4, "四级标题（英文括号数字）"),
            (r"^\d+）", 4, "四级标题（右括号数字）"),
            (r"^\d+\.\d+", 4, "四级标题（多级数字序号，如1.1）"),
            (r"^[（(][a-z][）)]", 5, "五级标题（括号英文小写序号）"),
            (r"^[（(][A-Z][）)]", 5, "五级标题（括号英文大写序号）"),
            (r"^[（(][ivxlcdmIVXLCDM]+[）)]", 5, "五级标题（括号罗马序号）"),
            (r"^[a-z][、.)]", 5, "五级标题（英文小写序号）"),
            (r"^[A-Z][、.)]", 5, "五级标题（英文大写序号）"),
            (r"^[ivxlcdmIVXLCDM]+[、.)]", 5, "五级标题（罗马序号）"),
            (r"\\textcircled\{\d+\}", 6, "六级标题（LaTeX圆圈）"),
        ]

    def handle_pattern_match_special(
        self,
        heading: str,
        pattern_name: str,
        dot_separated_format: Optional[Tuple[str, int]],
    ) -> Optional[Tuple[int, str]]:
        if pattern_name != "四级标题（多级数字序号，如1.1）":
            return None
        if not dot_separated_format:
            return None
        format_type, last_num = dot_separated_format
        if not format_type.startswith("dot_separated_"):
            return None
        num_parts = int(format_type.split("_")[-1])
        if num_parts == 2:
            adjusted_level = 4
        elif num_parts == 3:
            adjusted_level = 4
        elif num_parts == 4:
            adjusted_level = 5
        elif num_parts == 5:
            adjusted_level = 6
        elif num_parts >= 6:
            adjusted_level = 7
        else:
            adjusted_level = 4
        return (adjusted_level, f"多级数字序号（{format_type}）")

    def handle_no_pattern_match(
        self,
        heading: str,
        separator_count: int,
        section_count: int,
        has_keyword: bool,
        title_keywords: List[str],
    ) -> Tuple[int, str]:
        if section_count > 1:
            return (0, "目录内容")
        if has_keyword:
            if "目录" in heading and len(heading) > 50:
                return (0, "目录内容")
            if section_count == 1:
                return (1, "章节标题（关键词）")
            return (4, "关键词标题")
        return (0, "未匹配")

    def handle_rule_not_applied(
        self, base_level: int, prev_level: int
    ) -> Optional[Tuple[int, str]]:
        return None  # 中文模式：删除

    def should_reject_subheading_under_section(
        self, level: int, parent_title: str
    ) -> bool:
        """第一节下不识别次级标题"""
        if level < 2:
            return False
        title = (parent_title or "").strip()
        return title.startswith("第一节")
