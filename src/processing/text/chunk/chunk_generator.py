#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档分块生成器
根据 structure.json 对文档进行分块
"""

import json
import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

from src.common.utils import clean_text

logger = logging.getLogger(__name__)


class ChunkGenerator:
    """文档分块生成器 - 第二步：根据 structure.json 生成 chunk.json"""

    def __init__(self, document_path: str, structure_path: str, chunk_mode: str = "chinese"):
        self.document_path = document_path
        self.structure_path = structure_path
        self.chunk_mode = chunk_mode
        self.structure: List[Dict[str, Any]] = []
        self.chunks: List[Dict[str, Any]] = []
        self.valid_headings: List[Dict[str, Any]] = []

    def load_structure(self) -> List[Dict[str, Any]]:
        """从 structure.json 加载目录结构（支持纯树数组或包装格式 {structure: [...]}）"""
        with open(self.structure_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.structure = data.get('structure', data) if isinstance(data, dict) and 'structure' in data else (data if isinstance(data, list) else [])
        logger.info("已加载目录结构，包含 %d 个顶级节点", len(self.structure))
        return self.structure

    def build_valid_headings_from_structure(self) -> List[Dict[str, Any]]:
        """从结构树中构建有效标题列表"""
        self.valid_headings = []

        def traverse(node: Dict):
            idx = node.get('heading_index')
            if idx is not None and idx == len(self.valid_headings):
                self.valid_headings.append({
                    'title': node['title'],
                    'level': node['level'],
                    'line_number': node['line_number'],
                    'heading_index': idx
                })
            for child in node.get('children', []):
                traverse(child)

        for root in self.structure:
            traverse(root)
        logger.info("已构建 %d 个有效标题", len(self.valid_headings))
        return self.valid_headings

    def build_heading_index_to_level_map(self) -> Dict[int, int]:
        """构建标题索引到层级的映射"""
        index_to_level = {}

        def traverse(node: Dict):
            idx = node.get('heading_index')
            if idx is not None:
                index_to_level[idx] = node.get('level', 1)
            for child in node.get('children', []):
                traverse(child)

        for root in self.structure:
            traverse(root)
        return index_to_level

    def _split_long_chunk(
        self,
        content: str,
        title: str,
        title_level: int,
        start_line: int,
        end_line: int,
        parent_id: Optional[int],
        heading_index: int,
        is_table: bool,
        max_length: int = 500
    ) -> List[Dict[str, Any]]:
        """将长 chunk 按换行符分割成多个子块，保护表格完整性"""
        sub_chunks = []
        lines = content.split('\n')
        if not lines:
            return sub_chunks
        current_chunk_lines = []
        chunk_index = 1
        in_table = False
        table_depth = 0

        for line in lines:
            open_tags = line.count('<table>')
            close_tags = line.count('</table>')
            if open_tags > 0:
                table_depth += open_tags
                in_table = True
            if close_tags > 0:
                table_depth -= close_tags
                if table_depth <= 0:
                    table_depth = 0
                    in_table = False

            temp = current_chunk_lines + [line]
            new_length = len('\n'.join(temp))
            should_split = new_length > max_length and current_chunk_lines and not in_table

            if should_split:
                chunk_content = '\n'.join(current_chunk_lines)
                chunk_id = len(self.chunks) + len(sub_chunks) + 1
                sub_chunks.append({
                    'chunk_id': chunk_id,
                    'title': f"{title} (Part {chunk_index})",
                    'title_level': title_level,
                    'content': chunk_content,
                    'start_line': start_line,
                    'end_line': end_line,
                    'parent_id': parent_id,
                    'heading_index': heading_index,
                    'is_table': is_table
                })
                current_chunk_lines = [line]
                chunk_index += 1
            else:
                current_chunk_lines.append(line)

        if current_chunk_lines:
            chunk_id = len(self.chunks) + len(sub_chunks) + 1
            sub_title = title if not sub_chunks else f"{title} (Part {chunk_index})"
            sub_chunks.append({
                'chunk_id': chunk_id,
                'title': sub_title,
                'title_level': title_level,
                'content': '\n'.join(current_chunk_lines),
                'start_line': start_line,
                'end_line': end_line,
                'parent_id': parent_id,
                'heading_index': heading_index,
                'is_table': is_table
            })
        return sub_chunks

    def chunk_by_structure(self) -> List[Dict[str, Any]]:
        """根据加载的目录结构对 document.md 进行分块"""
        with open(self.document_path, 'r', encoding='utf-8') as f:
            content_lines = f.readlines()
        valid_headings = self.valid_headings
        index_to_level = self.build_heading_index_to_level_map()
        MAX_CHUNK_LENGTH = 500

        # 插入虚拟前言节点（L1）：首个标题之前的内容
        first_heading_line = (
            valid_headings[0]['line_number'] if valid_headings else len(content_lines) + 1
        )
        if first_heading_line > 1:
            preface_content = ''.join(content_lines[0:first_heading_line - 1]).strip()
            if preface_content:
                is_table = '<table>' in preface_content
                if is_table and not preface_content.strip().startswith('#'):
                    table_matches = list(re.finditer(r'<table>.*?</table>', preface_content, re.DOTALL))
                    if table_matches:
                        total_table_len = sum(len(m.group(0)) for m in table_matches)
                        if total_table_len > len(preface_content) * 0.8:
                            preface_content = '\n'.join(m.group(0) for m in table_matches).strip()
                        else:
                            parts = []
                            last_end = 0
                            for m in table_matches:
                                before = preface_content[last_end:m.start()].strip()
                                if before:
                                    parts.append(clean_text(before))
                                parts.append(m.group(0))
                                last_end = m.end()
                            after = preface_content[last_end:].strip()
                            if after:
                                parts.append(clean_text(after))
                            preface_content = '\n'.join(parts)
                    else:
                        preface_content = clean_text(preface_content)
                elif not preface_content.strip().startswith('#'):
                    preface_content = clean_text(preface_content)
                preface_title = 'Part 0' if self.chunk_mode == 'english' else '前言'
                if len(preface_content) <= MAX_CHUNK_LENGTH:
                    chunk_id = len(self.chunks) + 1
                    pref_chunk = {
                        'chunk_id': chunk_id,
                        'title': preface_title,
                        'title_level': 1,
                        'content': preface_content,
                        'start_line': 1,
                        'end_line': first_heading_line - 1,
                        'parent_id': None,
                        'heading_index': -1,  # 虚拟节点
                        'is_table': is_table
                    }
                    self.chunks.append(pref_chunk)
                else:
                    sub_chunks = self._split_long_chunk(
                        preface_content, preface_title, 1, 1, first_heading_line - 1,
                        None, -1, is_table, MAX_CHUNK_LENGTH
                    )
                    for sc in sub_chunks:
                        self.chunks.append(sc)
                logger.debug("已添加虚拟前言节点，覆盖第 1-%d 行", first_heading_line - 1)

        def process_node(node: Dict, parent_id: Optional[int] = None) -> List[Dict]:
            chunks = []
            heading_index = node.get('heading_index')
            if heading_index is None:
                return chunks
            # 虚拟前言节点（heading_index=-1）：不为其建 chunk，但需处理其子节点
            if heading_index < 0:
                preface_children = node.get('children', [])
                if preface_children and not self.chunks:
                    # structure 有前言子节点但未创建前言 chunk（first_heading_line=1 时无 preface_content）
                    # 创建占位 chunk 以保证 chunks 与 structure 一致
                    preface_title = 'Part 0' if self.chunk_mode == 'english' else '前言'
                    chunk_id = len(self.chunks) + 1
                    self.chunks.append({
                        'chunk_id': chunk_id,
                        'title': preface_title,
                        'title_level': 1,
                        'content': '',
                        'start_line': 1,
                        'end_line': 0,
                        'parent_id': None,
                        'heading_index': -1,
                        'is_table': False,
                    })
                preface_chunk_id = self.chunks[0]['chunk_id'] if self.chunks else None
                for child in preface_children:
                    chunks.extend(process_node(child, parent_id=preface_chunk_id))
                return chunks
            if heading_index >= len(valid_headings):
                return chunks
            heading_info = valid_headings[heading_index]
            start_line = heading_info['line_number']
            current_level = node.get('level', 1)
            end_line = len(content_lines) + 1
            direct_child_indices = [c.get('heading_index') for c in node.get('children', []) if c.get('heading_index') is not None]
            if direct_child_indices:
                first_child_idx = min(direct_child_indices)
                if first_child_idx < len(valid_headings):
                    end_line = valid_headings[first_child_idx]['line_number']
            else:
                for i in range(heading_index + 1, len(valid_headings)):
                    if i in index_to_level and index_to_level[i] <= current_level:
                        end_line = valid_headings[i]['line_number']
                        break

            content = ''.join(content_lines[start_line - 1:end_line - 1]).strip()
            is_table = '<table>' in content

            if is_table and not content.strip().startswith('#'):
                table_matches = list(re.finditer(r'<table>.*?</table>', content, re.DOTALL))
                if table_matches:
                    total_table_len = sum(len(m.group(0)) for m in table_matches)
                    if total_table_len > len(content) * 0.8:
                        content = '\n'.join(m.group(0) for m in table_matches).strip()
                    else:
                        parts = []
                        last_end = 0
                        for m in table_matches:
                            before = content[last_end:m.start()].strip()
                            if before:
                                parts.append(clean_text(before))
                            parts.append(m.group(0))
                            last_end = m.end()
                        after = content[last_end:].strip()
                        if after:
                            parts.append(clean_text(after))
                        content = '\n'.join(parts)
                else:
                    content = clean_text(content)
            else:
                content = clean_text(content)

            if len(content) <= MAX_CHUNK_LENGTH:
                chunk_id = len(self.chunks) + 1
                chunk = {
                    'chunk_id': chunk_id,
                    'title': node['title'],
                    'title_level': current_level,
                    'content': content,
                    'start_line': start_line,
                    'end_line': end_line - 1,
                    'parent_id': parent_id,
                    'heading_index': heading_index,
                    'is_table': is_table
                }
                chunks.append(chunk)
                self.chunks.append(chunk)
                for child in node.get('children', []):
                    chunks.extend(process_node(child, parent_id=chunk_id))
            else:
                sub_chunks = self._split_long_chunk(
                    content, node['title'], current_level, start_line, end_line - 1,
                    parent_id, heading_index, is_table, MAX_CHUNK_LENGTH
                )
                first_sub_id = None
                for sc in sub_chunks:
                    chunks.append(sc)
                    self.chunks.append(sc)
                    if first_sub_id is None:
                        first_sub_id = sc['chunk_id']
                for child in node.get('children', []):
                    chunks.extend(process_node(child, parent_id=first_sub_id))
            return chunks

        for root in self.structure:
            process_node(root)
        logger.info("已完成分块，共生成 %d 个块", len(self.chunks))
        return self.chunks

    def save_chunks(self, output_json: str, output_md: str = None) -> None:
        """保存分块结果"""
        output_data = [{
            'chunk_id': c['chunk_id'],
            'title': c['title'],
            'title_level': c['title_level'],
            'parent_id': c.get('parent_id'),
            'heading_index': c.get('heading_index'),
            'content': c['content'],
            'start_line': c['start_line'],
            'end_line': c['end_line'],
            'content_length': len(c['content']),
            'is_table': c.get('is_table', False)
        } for c in self.chunks]
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        logger.info("已保存 JSON 格式分块结果到: %s", output_json)
        if output_md:
            with open(output_md, 'w', encoding='utf-8') as f:
                for c in self.chunks:
                    prefix = '#' * (c['title_level'] + 1)
                    parent_info = f" (父节点: 块{c['parent_id']})" if c.get('parent_id') else ""
                    f.write(f"{prefix} 块 {c['chunk_id']}: {c['title']}{parent_info}\n\n{c['content']}\n\n---\n\n")
            logger.info("已保存 Markdown 格式分块结果到: %s", output_md)

    def run(self, output_json: str = None, output_md: str = None) -> List[Dict[str, Any]]:
        """执行完整的分块流程"""
        logger.info("开始基于结构进行文档分块")
        self.load_structure()
        self.build_valid_headings_from_structure()
        self.chunk_by_structure()
        if output_json:
            self.save_chunks(output_json, output_md)
        logger.info("分块完成，共生成 %d 个块", len(self.chunks))
        return self.chunks
