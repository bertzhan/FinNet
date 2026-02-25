#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分块模式抽象基类
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional


class ChunkMode(ABC):
    """分块模式抽象基类"""

    @abstractmethod
    def get_patterns(self) -> List[Tuple[str, int, str]]:
        """返回 (regex, level, name) 列表"""
        pass

    def get_re_flags(self) -> int:
        """返回正则匹配标志，0 表示无额外标志"""
        return 0

    def is_flat_mode(self) -> bool:
        """是否全部为一级标题（不根据序号区分层级），默认 False"""
        return False

    def should_reject_heading(self, heading: str, pattern_name: str) -> bool:
        """模式特定：是否拒绝该标题（如 english 的 continued）"""
        return False

    def handle_pattern_match_special(
        self,
        heading: str,
        pattern_name: str,
        dot_separated_format: Optional[Tuple[str, int]],
    ) -> Optional[Tuple[int, str]]:
        """模式特定：pattern 匹配后的特殊处理（如 chinese 的 1.1）"""
        return None

    def handle_no_pattern_match(
        self,
        heading: str,
        separator_count: int,
        section_count: int,
        has_keyword: bool,
        title_keywords: List[str],
    ) -> Tuple[int, str]:
        """无 pattern 匹配时的回退逻辑"""
        return (0, "未匹配")

    def handle_rule_not_applied(
        self, base_level: int, prev_level: int
    ) -> Optional[Tuple[int, str]]:
        """无规则应用时的处理：None=删除，否则 (level, reason)"""
        return None

    def get_min_level_for_format(self, format_type: str) -> Optional[int]:
        """某格式的最低层级约束，None 表示无约束"""
        return None

    def should_reject_subheading_under_section(
        self, level: int, parent_title: str
    ) -> bool:
        """模式特定：某 section 下的次级标题是否不识别（如 chinese 的第一节下不识别 L2+）"""
        return False
