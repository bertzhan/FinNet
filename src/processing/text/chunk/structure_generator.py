#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档结构生成器
从 Markdown 提取标题并构建目录结构树
"""

import json
import logging
import re
from typing import List, Dict, Any
from pathlib import Path

from src.processing.text.title_level_detector import TitleLevelDetector
from src.processing.text.structure_utils import structure_tree_to_text

logger = logging.getLogger(__name__)


class StructureGenerator:
    """文档结构生成器 - 第一步：生成 structure.json"""

    def __init__(self, document_path: str, chunk_mode: str = "chinese"):
        self.document_path = document_path
        self.chunk_mode = chunk_mode
        self.detector = TitleLevelDetector(chunk_mode=chunk_mode)
        self.headings: List[Dict[str, Any]] = []
        self.structure: List[Dict[str, Any]] = []
        self.valid_headings: List[Dict[str, Any]] = []

    def extract_headings(self) -> List[Dict[str, Any]]:
        """从 document.md 中提取所有标题，排除表格内的行"""
        self.headings = []
        table_depth = 0
        with open(self.document_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line_num, line in enumerate(lines, 1):
            raw_line = line
            line = line.strip()
            if not line:
                continue
            table_depth += raw_line.count('<table>') - raw_line.count('</table>')
            if table_depth > 0 or '</table>' in raw_line:
                continue
            match = re.match(r'^(#+)\s+(.+)$', line)
            if match:
                self.headings.append({
                    'markdown_level': len(match.group(1)),
                    'title': match.group(2).strip(),
                    'line_number': line_num,
                    'is_markdown': True
                })
                continue
            base_level, pattern_name = self.detector.detect_by_format(line)
            if base_level > 0:
                self.headings.append({
                    'markdown_level': None,
                    'title': line,
                    'line_number': line_num,
                    'is_markdown': False,
                    'detected_level': base_level,
                    'pattern_name': pattern_name
                })

        logger.info("已提取 %d 个标题", len(self.headings))
        return self.headings

    def detect_structure(self) -> List[Dict[str, Any]]:
        """使用规则检测器识别目录结构"""
        headings_with_levels = self.detector.detect_all_headings(self.headings)
        self.valid_headings = []
        deleted_headings = []
        for h in headings_with_levels:
            if h['level'] > 0:
                h['heading_index'] = len(self.valid_headings)
                self.valid_headings.append(h)
            else:
                deleted_headings.append(h)

        logger.info("识别出 %d 个有效标题（共%d个）", len(self.valid_headings), len(headings_with_levels))
        if deleted_headings:
            logger.debug("被删除的标题（共%d个）", len(deleted_headings))

        self.structure = self._build_structure_tree(self.valid_headings)
        self._prepend_preface_node_if_needed()
        logger.info("已构建目录结构，包含 %d 个顶级节点", len(self.structure))
        return self.structure

    def _prepend_preface_node_if_needed(self) -> None:
        """
        若首个标题之前存在非空内容，插入虚拟「前言」节点（L1）。
        若在首次出现 L1（第X节）之前存在 L2/L3 等子级标题（如 一、二、），
        将这些标题挂到前言下作为子节点。
        """
        if not self.valid_headings:
            return
        first_heading_line = self.valid_headings[0]['line_number']
        idx_first_l1 = next(
            (i for i, h in enumerate(self.valid_headings) if h['level'] == 1),
            None
        )
        if idx_first_l1 is None:
            return
        with open(self.document_path, 'r', encoding='utf-8') as f:
            content_lines = f.readlines()
        preface_content = ''.join(content_lines[0:first_heading_line - 1]).strip()
        preface_children: List[Dict[str, Any]] = []
        for root in list(self.structure):
            hi = root.get('heading_index')
            if hi is not None and hi < idx_first_l1:
                preface_children.append(root)
                self.structure.remove(root)
        preface_title = 'Part 0' if self.chunk_mode == 'english' else '前言'
        preface_node: Dict[str, Any] = {
            'title': preface_title,
            'level': 1,
            'heading_index': -1,
            'line_number': 1,
            'children': preface_children,
            'is_preface': True,
        }
        if preface_content or preface_children:
            self.structure.insert(0, preface_node)
            logger.debug(
                "已插入虚拟前言节点，覆盖第 1-%d 行，含 %d 个子标题",
                first_heading_line - 1,
                len(preface_children),
            )

    def _build_structure_tree(self, headings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """构建目录结构树"""
        if not headings:
            return []
        tree = []
        stack = []
        for i, heading in enumerate(headings):
            level = heading['level']
            node = {
                'title': heading['title'],
                'level': level,
                'heading_index': i,
                'line_number': heading['line_number'],
                'children': []
            }
            while stack and stack[-1][1] >= level:
                stack.pop()
            if stack:
                stack[-1][0]['children'].append(node)
            else:
                tree.append(node)
            stack.append((node, level))
        return tree

    def save_structure(self, output_path: str, also_txt: bool = True) -> None:
        """保存识别的目录结构（JSON，可选同时保存 .txt）"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.structure, f, ensure_ascii=False, indent=2)
        logger.info("已保存目录结构到: %s", output_path)
        if also_txt:
            text_path = str(Path(output_path).with_suffix('.txt'))
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(structure_tree_to_text(self.structure))
            logger.info("已保存文本格式目录树到: %s", text_path)

    def run(self, output_structure: str = None) -> List[Dict[str, Any]]:
        """执行完整的结构生成流程"""
        logger.info("开始生成文档结构")
        self.extract_headings()
        self.detect_structure()
        if output_structure:
            self.save_structure(output_structure, also_txt=True)
        logger.info("结构生成完成")
        return self.structure
