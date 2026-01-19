#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于规则的文档结构识别和分块方案
使用TitleLevelDetector完全基于规则识别标题层级
"""

import json
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from title_level_detector import TitleLevelDetector


class StructureGenerator:
    """文档结构生成器 - 第一步：生成 structure.json"""
    
    def __init__(self, document_path: str):
        """
        初始化结构生成器
        
        Args:
            document_path: document.md 文件路径
        """
        self.document_path = document_path
        self.detector = TitleLevelDetector()
        self.headings = []  # 存储提取的标题
        self.structure = []  # 存储识别的目录结构
        self.valid_headings = []  # 存储有效标题（level > 0）
    
    def extract_headings(self) -> List[Dict[str, Any]]:
        """
        从document.md中提取所有标题
        
        Returns:
            标题列表，每个标题包含：level, title, line_number
        """
        self.headings = []
        
        with open(self.document_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            # 匹配Markdown标题（# 开头）
            match = re.match(r'^(#+)\s+(.+)$', line)
            if match:
                markdown_level = len(match.group(1))  # #的数量表示Markdown层级
                title = match.group(2).strip()
                self.headings.append({
                    'markdown_level': markdown_level,
                    'title': title,
                    'line_number': line_num
                })
        
        print(f"✓ 已提取 {len(self.headings)} 个标题")
        return self.headings
    
    def detect_structure(self) -> List[Dict[str, Any]]:
        """
        使用规则检测器识别目录结构
        
        Returns:
            目录结构（树形结构）
        """
        # 使用检测器识别所有标题的层级
        headings_with_levels = self.detector.detect_all_headings(self.headings)
        
        # 过滤掉非标题（level=0）和封面标题
        self.valid_headings = []
        deleted_headings = []
        for h in headings_with_levels:
            if h['level'] > 0:
                # 确保heading_index正确设置
                h['heading_index'] = len(self.valid_headings)
                self.valid_headings.append(h)
            else:
                # 记录被删除的标题
                deleted_headings.append(h)
        
        print(f"✓ 识别出 {len(self.valid_headings)} 个有效标题（共{len(headings_with_levels)}个）")
        
        # 打印被删除的标题
        if deleted_headings:
            print(f"\n被删除的标题（共{len(deleted_headings)}个）:")
            print("-" * 80)
            for h in deleted_headings:
                title = h.get('title', h.get('content', ''))
                line_num = h.get('line_number', 'N/A')
                reason = h.get('detection_reason', 'N/A')
                
                # 查找前后标题作为上下文
                prev_title = None
                next_title = None
                for i, heading in enumerate(headings_with_levels):
                    if heading == h:
                        if i > 0:
                            prev_item = headings_with_levels[i-1]
                            if prev_item.get('level', 0) > 0:
                                prev_title = prev_item.get('title', prev_item.get('content', ''))
                        if i + 1 < len(headings_with_levels):
                            next_item = headings_with_levels[i+1]
                            if next_item.get('level', 0) > 0:
                                next_title = next_item.get('title', next_item.get('content', ''))
                        break
                
                print(f"行号: {line_num}")
                print(f"标题: {title}")
                print(f"原因: {reason}")
                if prev_title:
                    print(f"前一个标题: {prev_title}")
                if next_title:
                    print(f"下一个标题: {next_title}")
                print()
        
        # 构建目录结构树
        self.structure = self._build_structure_tree(self.valid_headings)
        
        print(f"✓ 已构建目录结构，包含 {len(self.structure)} 个顶级节点")
        return self.structure
    
    def _build_structure_tree(self, headings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        构建目录结构树
        
        Args:
            headings: 带层级的标题列表
            
        Returns:
            树形结构列表
        """
        if not headings:
            return []
        
        # 构建索引映射
        heading_map = {i: h for i, h in enumerate(headings)}
        
        # 构建树结构
        tree = []
        stack = []  # 用于跟踪当前路径 [(node, level), ...]
        
        for i, heading in enumerate(headings):
            level = heading['level']
            node = {
                'title': heading['title'],
                'level': level,
                'heading_index': i,
                'line_number': heading['line_number'],
                'children': []
            }
            
            # 找到父节点：在栈中找到层级小于当前层级的最后一个节点
            while stack and stack[-1][1] >= level:
                stack.pop()
            
            if stack:
                # 添加到父节点的children
                parent_node = stack[-1][0]
                parent_node['children'].append(node)
            else:
                # 顶级节点
                tree.append(node)
            
            # 将当前节点加入栈
            stack.append((node, level))
        
        return tree
    
    def save_structure(self, output_path: str):
        """保存识别的目录结构"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.structure, f, ensure_ascii=False, indent=2)
        print(f"✓ 已保存目录结构到: {output_path}")
    
    def generate_structure_tree(self, output_path: str):
        """
        生成目录结构树文件
        
        Args:
            output_path: 输出文件路径
        """
        # 保存为JSON格式
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.structure, f, ensure_ascii=False, indent=2)
        print(f"✓ 已保存目录结构树到: {output_path}")
        
        # 同时生成文本格式
        text_output_path = str(Path(output_path).with_suffix('.txt'))
        with open(text_output_path, 'w', encoding='utf-8') as f:
            def print_tree_node(node, indent=0):
                """递归打印树节点"""
                prefix = '  ' * indent
                level_marker = f"[L{node['level']}] " if node.get('level') else ""
                f.write(f"{prefix}{level_marker}{node['title']}\n")
                
                for child in node.get('children', []):
                    print_tree_node(child, indent + 1)
            
            for root_node in self.structure:
                print_tree_node(root_node)
        
        print(f"✓ 已保存文本格式目录树到: {text_output_path}")
    
    def run(self, output_structure: str = None):
        """
        执行完整的结构生成流程
        
        Args:
            output_structure: 目录结构输出路径
        """
        print("开始生成文档结构...")
        print("-" * 60)
        
        # 1. 提取标题
        self.extract_headings()
        
        # 2. 使用规则检测器识别目录结构
        self.detect_structure()
        
        # 3. 保存识别的目录结构
        if output_structure:
            self.save_structure(output_structure)
            self.generate_structure_tree(output_structure)
        
        print(f"\n✓ 结构生成完成！")
        return self.structure


class ChunkGenerator:
    """文档分块生成器 - 第二步：根据 structure.json 生成 chunk.json"""
    
    def __init__(self, document_path: str, structure_path: str):
        """
        初始化分块生成器
        
        Args:
            document_path: document.md 文件路径
            structure_path: structure.json 文件路径
        """
        self.document_path = document_path
        self.structure_path = structure_path
        self.structure = []  # 存储加载的目录结构
        self.chunks = []  # 存储分块结果
        self.valid_headings = []  # 存储有效标题（level > 0）
    
    def load_structure(self) -> List[Dict[str, Any]]:
        """
        从 structure.json 加载目录结构
        
        Returns:
            目录结构（树形结构）
        """
        with open(self.structure_path, 'r', encoding='utf-8') as f:
            self.structure = json.load(f)
        
        print(f"✓ 已加载目录结构，包含 {len(self.structure)} 个顶级节点")
        return self.structure
    
    def build_valid_headings_from_structure(self) -> List[Dict[str, Any]]:
        """
        从结构树中构建有效标题列表
        
        Returns:
            有效标题列表
        """
        self.valid_headings = []
        
        def traverse_node(node: Dict):
            """递归遍历节点，收集标题信息"""
            heading_index = node.get('heading_index')
            if heading_index is not None:
                # 确保索引正确
                if heading_index == len(self.valid_headings):
                    self.valid_headings.append({
                        'title': node['title'],
                        'level': node['level'],
                        'line_number': node['line_number'],
                        'heading_index': heading_index
                    })
            
            for child in node.get('children', []):
                traverse_node(child)
        
        for root_node in self.structure:
            traverse_node(root_node)
        
        print(f"✓ 已构建 {len(self.valid_headings)} 个有效标题")
        return self.valid_headings
    
    def build_heading_index_to_level_map(self) -> Dict[int, int]:
        """
        构建标题索引到层级的映射
        
        Returns:
            {heading_index: level} 的字典
        """
        index_to_level = {}
        
        def traverse_node(node: Dict):
            """递归遍历节点，构建映射"""
            heading_index = node.get('heading_index')
            if heading_index is not None:
                index_to_level[heading_index] = node.get('level', 1)
            
            for child in node.get('children', []):
                traverse_node(child)
        
        for root_node in self.structure:
            traverse_node(root_node)
        
        return index_to_level
    
    def chunk_by_structure(self) -> List[Dict[str, Any]]:
        """
        根据加载的目录结构对document.md进行分块
        
        Returns:
            分块结果列表
        """
        # 读取文档内容
        with open(self.document_path, 'r', encoding='utf-8') as f:
            content_lines = f.readlines()
        
        # 使用从结构构建的valid_headings
        valid_headings = self.valid_headings
        
        # 构建标题索引到层级的映射
        index_to_level = self.build_heading_index_to_level_map()
        
        # 递归处理结构树
        def process_node(node: Dict, parent_id: Optional[int] = None) -> List[Dict]:
            """递归处理节点"""
            chunks = []
            heading_index = node.get('heading_index')
            
            if heading_index is None or heading_index >= len(valid_headings):
                return chunks
            
            heading_info = valid_headings[heading_index]
            start_line = heading_info['line_number']
            current_level = node.get('level', 1)
            
            # 找到下一个同级或更高级标题的行号
            # 策略：如果有子节点，父标题块只包含到第一个子标题之前的内容
            end_line = len(content_lines) + 1  # 默认到文档末尾
            
            # 收集当前节点的直接子节点的heading_index
            direct_child_indices = []
            for child in node.get('children', []):
                child_idx = child.get('heading_index')
                if child_idx is not None:
                    direct_child_indices.append(child_idx)
            
            # 如果有子节点，父标题块只包含到第一个子标题之前
            if direct_child_indices:
                first_child_idx = min(direct_child_indices)
                if first_child_idx < len(valid_headings):
                    end_line = valid_headings[first_child_idx]['line_number']
            else:
                # 没有子节点，查找下一个同级或更高级标题
                for i in range(heading_index + 1, len(valid_headings)):
                    if i in index_to_level:
                        next_level = index_to_level[i]
                        if next_level <= current_level:
                            end_line = valid_headings[i]['line_number']
                            break
            
            # 提取内容（从标题行到下一个标题行之前）
            content_lines_slice = content_lines[start_line - 1:end_line - 1]
            content = ''.join(content_lines_slice).strip()
            
            # 检查是否包含表格
            is_table = '<table>' in content
            
            # 如果内容只包含表格，将表格单独提取
            if is_table and not content.strip().startswith('#'):
                table_match = re.search(r'<table>.*?</table>', content, re.DOTALL)
                if table_match:
                    table_html = table_match.group(0)
                    if len(table_html) > len(content) * 0.8:
                        content = table_html
            
            # 创建块
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
            
            # 处理子节点
            for child in node.get('children', []):
                child_chunks = process_node(child, parent_id=chunk_id)
                chunks.extend(child_chunks)
            
            return chunks
        
        # 处理所有顶级节点
        all_chunks = []
        for root_node in self.structure:
            chunks = process_node(root_node)
            all_chunks.extend(chunks)
        
        print(f"✓ 已完成分块，共生成 {len(self.chunks)} 个块")
        return self.chunks
    
    def save_chunks(self, output_json: str, output_md: str = None):
        """
        保存分块结果
        
        Args:
            output_json: JSON输出路径
            output_md: Markdown输出路径（可选）
        """
        # 保存JSON格式
        output_data = []
        for chunk in self.chunks:
            output_data.append({
                'chunk_id': chunk['chunk_id'],
                'title': chunk['title'],
                'title_level': chunk['title_level'],
                'parent_id': chunk.get('parent_id'),
                'heading_index': chunk.get('heading_index'),
                'content': chunk['content'],
                'start_line': chunk['start_line'],
                'end_line': chunk['end_line'],
                'content_length': len(chunk['content']),
                'is_table': chunk.get('is_table', False)
            })
        
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"✓ 已保存 JSON 格式分块结果到: {output_json}")
        
        # 保存Markdown格式
        if output_md:
            with open(output_md, 'w', encoding='utf-8') as f:
                for chunk in self.chunks:
                    title_prefix = '#' * (chunk['title_level'] + 1)
                    parent_info = f" (父节点: 块{chunk['parent_id']})" if chunk.get('parent_id') else ""
                    f.write(f"{title_prefix} 块 {chunk['chunk_id']}: {chunk['title']}{parent_info}\n\n")
                    f.write(f"{chunk['content']}\n\n")
                    f.write(f"---\n\n")
            print(f"✓ 已保存 Markdown 格式分块结果到: {output_md}")
    
    def run(self, output_json: str = None, output_md: str = None):
        """
        执行完整的分块流程
        
        Args:
            output_json: JSON输出路径
            output_md: Markdown输出路径
        """
        print("开始基于结构进行文档分块...")
        print("-" * 60)
        
        # 1. 加载目录结构
        self.load_structure()
        
        # 2. 从结构构建有效标题列表
        self.build_valid_headings_from_structure()
        
        # 3. 根据结构分块
        self.chunk_by_structure()
        
        # 4. 保存分块结果
        if output_json:
            self.save_chunks(output_json, output_md)
        
        print(f"\n✓ 分块完成！共生成 {len(self.chunks)} 个块")
        return self.chunks


def main():
    """主函数"""
    # 文件路径
    base_dir = Path(__file__).parent
    document_path = base_dir / 'document.md'
    structure_path = base_dir / 'structure.json'
    
    # 第一步：生成 structure.json
    print("=" * 60)
    print("第一步：生成文档结构")
    print("=" * 60)
    structure_generator = StructureGenerator(document_path=str(document_path))
    structure_generator.run(output_structure=str(structure_path))
    
    # 第二步：根据 structure.json 生成 chunk.json
    print("\n" + "=" * 60)
    print("第二步：根据结构生成分块")
    print("=" * 60)
    chunk_generator = ChunkGenerator(
        document_path=str(document_path),
        structure_path=str(structure_path)
    )
    chunks = chunk_generator.run(
        output_json=str(base_dir / 'chunks.json'),
        output_md=str(base_dir / 'chunks.md')
    )
    
    print(f"\n✓ 全部完成！共生成 {len(chunks)} 个块")


if __name__ == '__main__':
    main()
