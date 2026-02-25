#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简易分块模式
序号不识别，全部为一级标题
"""

from typing import List, Optional, Tuple

from .base import ChunkMode


class SimpleChunkMode(ChunkMode):
    """简易模式：序号不识别，全部为一级标题"""

    def is_flat_mode(self) -> bool:
        """全部为 L1，不根据序号区分层级"""
        return True

    def get_patterns(self) -> List[Tuple[str, int, str]]:
        # 不识别序号，无 pattern 时由 handle_no_pattern_match 返回 L1
        return []

    def handle_no_pattern_match(
        self,
        heading: str,
        separator_count: int,
        section_count: int,
        has_keyword: bool,
        title_keywords: List[str],
    ) -> Tuple[int, str]:
        return (1, "简易模式-一级(无序号)")

    def handle_rule_not_applied(
        self, base_level: int, prev_level: int
    ) -> Optional[Tuple[int, str]]:
        level = min(base_level, prev_level + 1)
        return (level, f"simple模式：按格式保留层级{level}")
