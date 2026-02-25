#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
结构树工具函数
供 StructureGenerator 和 TextChunker 共用
"""

from typing import List, Dict, Any


def structure_tree_to_text(structure: List[Dict[str, Any]]) -> str:
    """
    将目录结构树转换为文本格式

    Args:
        structure: 文档结构（树形结构），每个节点含 title, level, children

    Returns:
        文本格式的目录结构树，每行一个标题，带 [L{n}] 层级标记
    """
    lines = []

    def _visit(node: Dict[str, Any], indent: int = 0) -> None:
        prefix = '  ' * indent
        level_marker = f"[L{node['level']}] " if node.get('level') else ""
        lines.append(f"{prefix}{level_marker}{node['title']}")
        for child in node.get('children', []):
            _visit(child, indent + 1)

    for root_node in structure:
        _visit(root_node)

    return '\n'.join(lines)
