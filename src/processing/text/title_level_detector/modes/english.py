#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
英文分块模式
PART X、ITEM X、数字. 格式，大小写不敏感（Part I、Item 1 等均可识别）
"""

from typing import List, Optional, Tuple

from .base import ChunkMode


class EnglishChunkMode(ChunkMode):
    """英文模式：PART X（L1）、ITEM X（L2），其余 # 标题均为 L3"""

    def get_patterns(self) -> List[Tuple[str, int, str]]:
        return [
            (r"(?i)^PART\s+(?:I{1,3}|IV|V|VI+|IX|X+|\d+)\b", 1, "一级标题(PART X)"),
            (r"(?i)^ITEM\s+\d+", 2, "二级标题(ITEM X)"),
        ]

    def should_reject_heading(self, heading: str, pattern_name: str) -> bool:
        return "(continued)" in heading

    def handle_no_pattern_match(
        self,
        heading: str,
        separator_count: int,
        section_count: int,
        has_keyword: bool,
        title_keywords: List[str],
    ) -> Tuple[int, str]:
        # 未匹配 PART/ITEM 的 # 标题均识别为 L3（L2 下的三级标题）
        return (3, "三级标题")

    def handle_rule_not_applied(
        self, base_level: int, prev_level: int
    ) -> Optional[Tuple[int, str]]:
        level = min(base_level, prev_level + 1)
        return (level, f"english模式：按格式保留层级{level}")

    def get_min_level_for_format(self, format_type: str) -> Optional[int]:
        # 仅识别 L1/L2，不强制任何格式为 L3
        return None
