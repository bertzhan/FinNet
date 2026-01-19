#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于规则的标题级别识别算法
根据标题格式和上下文关系自动识别标题层级（1-5级）
"""

import re
from typing import List, Dict, Any, Optional, Tuple


class TitleLevelDetector:
    """标题级别检测器"""
    
    # 常量定义
    MAX_TITLE_LENGTH = 200  # 标题最大长度
    MAX_LEVEL = 7  # 最大层级
    MIN_LEVEL = 1  # 最小层级
    MAX_SEPARATOR_COUNT = 3  # 最大分隔符数量
    
    def __init__(self):
        """初始化检测器"""
        # 定义标题格式模式（按优先级排序）
        self.patterns = [
            # 一级标题：第X节、第X章
            (r'^第[一二三四五六七八九十\d]+[节章]', 1, '一级标题（第X节/章）'),
            
            # 二级标题：一、二、三、...、十一、十二、...
            (r'^[一二三四五六七八九十百]+、', 2, '二级标题（中文数字）'),
            
            # 三级标题：多种格式
            (r'^（[一二三四五六七八九十百]+）', 3, '三级标题（中文括号）'),
            (r'^\([一二三四五六七八九十百]+\)', 3, '三级标题（英文括号中文数字）'),  # 添加英文括号支持
            (r'^\d+[、.]', 3, '三级标题（数字编号）'),
            (r'^\d+[．.]', 3, '三级标题（数字全角句号）'),  # 添加全角句号支持
            
            # 四级标题：（1）、（2）、1）、2）
            (r'^（\d+）', 4, '四级标题（中文括号数字）'),
            (r'^\(\d+\)', 4, '四级标题（英文括号数字）'),  # 修复：之前写成了d+，应该是\d+
            (r'^\d+）', 4, '四级标题（右括号数字）'),  # 添加右括号格式支持
            
            # 五级标题：LaTeX格式的圆圈数字
            (r'\\textcircled\{\d+\}', 5, '五级标题（LaTeX圆圈）'),
        ]
        
        # 特殊关键词（可能是标题但不是标准格式）
        self.title_keywords = ['目录', '释义', '概述', '总结', '附录', '备查文件']
        
        # 封面标题关键词（应忽略）
        self.cover_keywords = ['新晨科技', 'BRILLIANCETECH', '年度报告', '股份有限公司']
    
    def detect_by_format(self, heading: str) -> Tuple[int, str]:
        """
        根据格式模式判断标题层级
        
        Args:
            heading: 标题文本
            
        Returns:
            (level, pattern_name): 层级（0表示不是标题）和匹配的模式名称
        """
        heading = heading.strip()
        
        # 如果内容为空，不是标题
        if not heading:
            return (0, '空内容')
        
        # 如果内容过长（超过200字符），不太可能是标题
        if len(heading) > self.MAX_TITLE_LENGTH:
            return (0, '内容过长')
        
        # 先检查格式模式，如果匹配了格式模式，即使分隔符较多也认为是标题
        # 这样可以避免误删有效的标题（如长标题）
        for pattern, level, pattern_name in self.patterns:
            if re.search(pattern, heading):
                # 匹配了格式模式，直接返回，不检查分隔符
                return (level, pattern_name)
        
        # 如果没有匹配格式模式，再检查分隔符（可能是正文）
        sentence_separators = ['。', '；', ';', '.', '，', ',']
        separator_count = sum(heading.count(sep) for sep in sentence_separators)
        if separator_count > self.MAX_SEPARATOR_COUNT:
            return (0, '包含过多分隔符')
        
        # 排除目录内容（包含多个"第X节"的通常是目录）
        section_count = len(re.findall(r'第[一二三四五六七八九十\d]+节', heading))
        if section_count > 1:
            return (0, '目录内容')
        
        # 检查是否包含标题关键词
        if any(keyword in heading for keyword in self.title_keywords):
            # 排除目录中的内容
            if '目录' in heading and len(heading) > 50:
                return (0, '目录内容')
            # 如果包含"第X节"，可能是章节标题
            if section_count == 1:
                return (1, '章节标题（关键词）')
            # 其他关键词标题，默认作为四级标题
            return (4, '关键词标题')
        
        return (0, '未匹配')
    
    def is_cover_title(self, heading: str) -> bool:
        """
        判断是否为封面标题（应忽略）
        
        Args:
            heading: 标题文本
            
        Returns:
            是否为封面标题
        """
        heading = heading.strip()
        
        # 检查是否只包含封面关键词
        for keyword in self.cover_keywords:
            if heading == keyword or heading.startswith(keyword):
                # 如果标题很短且只包含封面关键词，可能是封面标题
                if len(heading) < 30:
                    return True
        
        # 检查是否包含"年年度报告"等封面特征
        if '年年度报告' in heading and len(heading) < 30:
            return True
        
        # 检查是否只包含公司名称（没有其他内容）
        if heading in ['公司']:
            return True
        
        return False
    
    def _chinese_to_arabic(self, chinese_str: str) -> int:
        """
        将中文数字转换为阿拉伯数字（统一方法）
        
        Args:
            chinese_str: 中文数字字符串（如"一"、"十一"、"二十"、"一百"等）
            
        Returns:
            对应的阿拉伯数字，如果无法转换则返回0
        """
        chinese_to_num = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, 
                        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
        
        # 单个字符：一、二、...、十
        if len(chinese_str) == 1:
            return chinese_to_num.get(chinese_str, 0)
        
        # 两个字符：十一、十二、...、十九、二十、三十、...
        if len(chinese_str) == 2:
            first = chinese_str[0]
            second = chinese_str[1]
            
            # 十一、十二、...、十九
            if first == '十':
                return 10 + chinese_to_num.get(second, 0)
            # 二十、三十、...、九十
            elif second == '十':
                return chinese_to_num.get(first, 0) * 10
            # 二十一、二十二、...、九十九
            elif first in chinese_to_num and second in chinese_to_num:
                return chinese_to_num[first] * 10 + chinese_to_num[second]
        
        # 三个字符：一百、二百、...、九百
        if len(chinese_str) == 3:
            first = chinese_str[0]
            second = chinese_str[1]
            third = chinese_str[2]
            
            # 一百、二百、...、九百
            if first in chinese_to_num and second == '百':
                return chinese_to_num[first] * 100
        
        return 0
    
    def _extract_chinese_format(self, heading: str) -> Optional[Tuple[str, int]]:
        """
        提取中文数字格式（一、二、三等）
        
        Args:
            heading: 标题文本
            
        Returns:
            (format_type, number) 或 None
            format_type: 'chinese' 或 'chinese_space'
        """
        # 先检查带空格的情况
        match = re.match(r'^([一二三四五六七八九十百]+)、\s+', heading)
        if match:
            chinese_num = match.group(1)
            num = self._chinese_to_arabic(chinese_num)
            if num > 0:
                return ('chinese_space', num)  # 带空格的格式
        
        # 再检查不带空格的情况
        match = re.match(r'^([一二三四五六七八九十百]+)、', heading)
        if match:
            chinese_num = match.group(1)
            num = self._chinese_to_arabic(chinese_num)
            if num > 0:
                return ('chinese', num)  # 不带空格的格式
        
        return None
    
    def _extract_latex_format(self, heading: str) -> Optional[Tuple[str, int]]:
        """
        提取LaTeX圆圈数字格式（$\textcircled{1}$ 等）
        
        Args:
            heading: 标题文本
            
        Returns:
            (format_type, number) 或 None
            format_type: 'latex_circled'
        """
        # LaTeX圆圈数字：$\textcircled{1}$ 或 \textcircled{1}
        # 在Python原始字符串中，\\表示单个反斜杠字符
        # 需要先检查LaTeX格式，避免被其他格式误匹配
        match = re.match(r'^\$?\\textcircled\{(\d+)\}\$?', heading)
        if match:
            num = int(match.group(1))
            return ('latex_circled', num)
        
        return None
    
    def _extract_arabic_format(self, heading: str) -> Optional[Tuple[str, int]]:
        """
        提取阿拉伯数字格式（1、1．1.等）
        
        Args:
            heading: 标题文本
            
        Returns:
            (format_type, number) 或 None
            format_type: 'arabic', 'arabic_period', 'arabic_dot'
        """
        # 阿拉伯数字：1、2、3、（使用中文顿号）
        match = re.match(r'^(\d+)[、]', heading)
        if match:
            return ('arabic', int(match.group(1)))  # 使用顿号的格式
        
        # 阿拉伯数字：1．2．3．（使用全角句号）
        match = re.match(r'^(\d+)[．]', heading)
        if match:
            return ('arabic_period', int(match.group(1)))  # 使用全角句号的格式
        
        # 阿拉伯数字：1.2.3.（使用英文句号）
        match = re.match(r'^(\d+)[.]', heading)
        if match:
            return ('arabic_dot', int(match.group(1)))  # 使用英文句号的格式
        
        return None
    
    def _extract_bracket_chinese_format(self, heading: str) -> Optional[Tuple[str, int]]:
        """
        提取括号中文数字格式（（一）、（二）等）
        
        Args:
            heading: 标题文本
            
        Returns:
            (format_type, number) 或 None
            format_type: 'bracket_chinese'
        """
        # 中文括号：（一）、（二）、（十一）、（十二）等
        match = re.match(r'^[（(]([一二三四五六七八九十百]+)[）)]', heading)
        if match:
            chinese_num = match.group(1)
            num = self._chinese_to_arabic(chinese_num)
            if num > 0:
                return ('bracket_chinese', num)
        
        return None
    
    def _extract_bracket_arabic_format(self, heading: str) -> Optional[Tuple[str, int]]:
        """
        提取括号阿拉伯数字格式（（1）、1）等）
        
        Args:
            heading: 标题文本
            
        Returns:
            (format_type, number) 或 None
            format_type: 'bracket_arabic' 或 'right_bracket_arabic'
        """
        # 数字括号：（1）、（2）或 1）、2）
        # 先检查带左括号的情况
        match = re.match(r'^[（(](\d+)[）)]', heading)
        if match:
            return ('bracket_arabic', int(match.group(1)))  # 带左括号的格式
        
        # 再检查只有右括号的情况
        match = re.match(r'^(\d+)[）)]', heading)
        if match:
            return ('right_bracket_arabic', int(match.group(1)))  # 只有右括号的格式
        
        return None
    
    def _extract_number_format(self, heading: str) -> Optional[Tuple[str, int]]:
        """
        提取标题中的数字格式和数字值（主函数）
        
        Args:
            heading: 标题文本
            
        Returns:
            (format_type, number) 或 None
            format_type: 'chinese'（中文数字）、'arabic'（阿拉伯数字）、'bracket_chinese'（括号中文）、'bracket_arabic'（括号数字）等
            注意：格式类型会包含空格信息，如'chinese'（无空格）和'chinese_space'（有空格）
        """
        heading = heading.strip()
        
        # 按优先级顺序检查各种格式
        # 1. 中文数字格式（优先级最高，因为可能与其他格式冲突）
        result = self._extract_chinese_format(heading)
        if result:
            return result
        
        # 2. LaTeX格式（需要优先检查，避免被其他格式误匹配）
        result = self._extract_latex_format(heading)
        if result:
            return result
        
        # 3. 阿拉伯数字格式
        result = self._extract_arabic_format(heading)
        if result:
            return result
        
        # 4. 括号中文数字格式
        result = self._extract_bracket_chinese_format(heading)
        if result:
            return result
        
        # 5. 括号阿拉伯数字格式
        result = self._extract_bracket_arabic_format(heading)
        if result:
            return result
        
        return None
    
    def _apply_special_rule_section(self, heading: str, base_level: int, 
                                    prev_heading: Optional[Dict], 
                                    current_format: Optional[Tuple[str, int]],
                                    prev_format: Optional[Tuple[str, int]]) -> Optional[Tuple[int, str]]:
        """
        特殊规则1：处理"第X节"格式
        
        Args:
            heading: 当前标题文本
            base_level: 基础层级
            prev_heading: 前一个标题信息
            current_format: 当前标题格式
            prev_format: 前一个标题格式
            
        Returns:
            (adjusted_level, reason) 或 None（如果规则未应用）
        """
        if current_format is None and base_level == 1:
            # 检查当前标题是否是"第X节"格式
            if re.match(r'^第[一二三四五六七八九十\d]+[节章]', heading):
                prev_level = prev_heading.get('level', 0) if prev_heading else 0
                prev_title = prev_heading.get('title', '') if prev_heading else ''
                
                # 如果前一个标题也是"第X节"格式，保持同级L1
                if prev_format is None and prev_level == 1 and re.match(r'^第[一二三四五六七八九十\d]+[节章]', prev_title):
                    return (prev_level, '特殊规则：前一个标题是"第X节"格式，当前标题也是"第X节"格式，保持同级L1')
                # 如果前一个标题不是"第X节"格式，但当前标题是"第X节"格式，应该保持L1（顶级标题）
                elif not re.match(r'^第[一二三四五六七八九十\d]+[节章]', prev_title):
                    return (1, '特殊规则：当前标题是"第X节"格式（顶级标题），保持L1')
        
        return None
    
    def _apply_special_rule_after_section(self, current_format: Optional[Tuple[str, int]],
                                         prev_format: Optional[Tuple[str, int]],
                                         prev_level: int) -> Optional[Tuple[int, str]]:
        """
        特殊规则2：如果前一个标题格式为None（如"第X节"），且当前标题从1开始时，识别为子标题
        
        Args:
            current_format: 当前标题格式
            prev_format: 前一个标题格式
            prev_level: 前一个标题层级
            
        Returns:
            (adjusted_level, reason) 或 None（如果规则未应用）
        """
        if current_format and prev_format is None:
            current_format_type, current_num = current_format
            # 如果当前标题从1开始，且前一个标题是L1（通常是"第X节"），识别为子标题
            if current_num == 1 and prev_level == 1:
                adjusted_level = prev_level + 1
                return (adjusted_level, f'特殊规则：前一个标题格式为None（第X节），当前标题从1开始，识别为子标题{adjusted_level}')
        
        return None

    def _apply_rule_1_same_format_consecutive(self, current_format: Optional[Tuple[str, int]],
                                              prev_format: Optional[Tuple[str, int]],
                                              prev_level: int) -> Optional[Tuple[int, str]]:
        """
        规则1：格式相同且数字连续 → 保持同级（最高优先级）
        
        Args:
            current_format: 当前标题格式
            prev_format: 前一个标题格式
            prev_level: 前一个标题层级
            
        Returns:
            (adjusted_level, reason) 或 None（如果规则未应用）
        """
        if current_format and prev_format:
            current_format_type, current_num = current_format
            prev_format_type, prev_num = prev_format
            
            # 格式相同且数字连续（如：（二）->（三））
            if current_format_type == prev_format_type and current_num == prev_num + 1:
                reason = f'规则1：格式相同且数字连续({prev_num}->{current_num})，保持与前一个标题同级{prev_level}'
                return (prev_level, reason)
        
        return None

        
    def _apply_rule_2_start_from_one(self, current_format: Optional[Tuple[str, int]],
                                     prev_format: Optional[Tuple[str, int]],
                                     prev_level: int) -> Optional[Tuple[int, str]]:
        """
        规则2：无论格式是否变化，只要从1开始，就是次级标题
        
        Args:
            current_format: 当前标题格式
            prev_format: 前一个标题格式
            prev_level: 前一个标题层级
            
        Returns:
            (adjusted_level, reason) 或 None（如果规则未应用）
        """
        if current_format:
            current_format_type, current_num = current_format
            if current_num == 1:
                # 特殊处理：如果当前标题是"一、"开头，且前一个标题也是L3级别的"一、"标题（格式相同且数字连续），应该识别为L3
                if current_format_type == 'chinese' and prev_format:
                    prev_format_type, prev_num = prev_format
                    if prev_format_type == 'chinese' and prev_num == 1 and prev_level == 3:
                        # 前一个标题是L3级别的"一、"，当前标题也是"一、"，应该保持同级
                        return (3, '规则2特殊：前一个标题是L3级别的"一、"，当前标题也是"一、"，保持同级L3')
                
                # 应用规则2：从1开始，识别为次级标题
                prev_format_type = prev_format[0] if prev_format else 'None'
                adjusted_level = min(prev_level + 1, self.MAX_LEVEL)
                if adjusted_level < prev_level + 1:
                    reason = f'规则2：从1开始（格式{current_format_type}），调整为次级标题{adjusted_level}（限制在L7以内）'
                else:
                    reason = f'规则2：从1开始（格式{current_format_type}），调整为次级标题{adjusted_level}'
                return (adjusted_level, reason)
        
        return None
    
    
    def _apply_rule_3_parent_format_match(self, current_format: Optional[Tuple[str, int]],
                                         prev_parent_heading: Optional[Dict]) -> Optional[Tuple[int, str]]:
        """
        规则3：格式与上个标题不同，但与上个标题的父标题的格式相同且连续 -> 保持与父标题同级
        
        Args:
            current_format: 当前标题格式
            prev_parent_heading: 前一个标题的父标题信息
            
        Returns:
            (adjusted_level, reason) 或 None（如果规则未应用）
        """
        if current_format and prev_parent_heading:
            current_format_type, current_num = current_format
            prev_parent_title = prev_parent_heading.get('title', '')
            prev_parent_format = self._extract_number_format(prev_parent_title) if prev_parent_title else None
            
            if prev_parent_format:
                prev_parent_format_type, prev_parent_num = prev_parent_format
                # 当前格式与父标题格式相同，且数字连续
                if current_format_type == prev_parent_format_type and current_num == prev_parent_num + 1:
                    prev_parent_level = prev_parent_heading.get('level', 0)
                    if prev_parent_level > 0:
                        reason = f'规则3：格式与上个标题不同，但与父标题格式相同且连续({prev_parent_num}->{current_num})，保持与父标题同级{prev_parent_level}'
                        return (prev_parent_level, reason)
        
        return None
    
    def _apply_rule_4_parent_chain_match(self, current_format: Optional[Tuple[str, int]],
                                        prev_parent_chain: Optional[List[Dict]]) -> Optional[Tuple[int, str]]:
        """
        规则4：格式与上个标题不同，但与父标题链格式相同且连续
        
        Args:
            current_format: 当前标题格式
            prev_parent_chain: 前一个标题的父标题链
            
        Returns:
            (adjusted_level, reason) 或 None（如果规则未应用）
        """
        if current_format and prev_parent_chain:
            current_format_type, current_num = current_format
            for parent in prev_parent_chain:
                parent_title = parent.get('title', '')
                parent_format = self._extract_number_format(parent_title) if parent_title else None
                if parent_format:
                    parent_format_type, parent_num = parent_format
                    # 当前格式与父标题格式相同，且数字连续
                    if current_format_type == parent_format_type and current_num == parent_num + 1:
                        parent_level = parent.get('level', 0)
                        if parent_level > 0:
                            reason = f'规则4：格式与上个标题不同，但与父标题链格式相同且连续({parent_num}->{current_num})，保持与父标题同级{parent_level}'
                            return (parent_level, reason)
        
        return None
    
    def _apply_rule_4_extended_sibling_match(self, current_format: Optional[Tuple[str, int]],
                                            prev_parent_chain: Optional[List[Dict]],
                                            result_list: Optional[List[Dict]]) -> Optional[Tuple[int, str]]:
        """
        规则4扩展：检查前一个标题的所有祖先标题的兄弟标题
        
        Args:
            current_format: 当前标题格式
            prev_parent_chain: 前一个标题的父标题链
            result_list: 已处理的标题列表
            
        Returns:
            (adjusted_level, reason) 或 None（如果规则未应用）
        """
        if current_format and prev_parent_chain and result_list:
            current_format_type, current_num = current_format
            # 对于父标题链中的每个父标题，检查是否有同级标题格式匹配
            for parent in prev_parent_chain:
                parent_level = parent.get('level', 0)
                if parent_level > 0:
                    # 在result_list中查找与parent同级的标题
                    for candidate in result_list:
                        candidate_level = candidate.get('level', 0)
                        if candidate_level == parent_level:
                            candidate_title = candidate.get('title', candidate.get('content', ''))
                            candidate_format = self._extract_number_format(candidate_title) if candidate_title else None
                            if candidate_format:
                                candidate_format_type, candidate_num = candidate_format
                                # 当前格式与候选标题格式相同，且数字连续
                                if current_format_type == candidate_format_type and current_num == candidate_num + 1:
                                    reason = f'规则4：格式与上个标题不同，但与父标题链同级标题格式相同且连续({candidate_num}->{current_num})，保持与父标题同级{parent_level}'
                                    return (parent_level, reason)
        
        return None
    
    def _apply_rule_4_extended2_sibling_search(self, current_format: Optional[Tuple[str, int]],
                                               base_level: int,
                                               prev_heading: Optional[Dict],
                                               result_list: Optional[List[Dict]]) -> Optional[Tuple[int, str]]:
        """
        规则4扩展2：在result_list中搜索格式相同且数字连续的标题
        
        Args:
            current_format: 当前标题格式
            base_level: 基础层级
            prev_heading: 前一个标题信息
            result_list: 已处理的标题列表
            
        Returns:
            (adjusted_level, reason) 或 None（如果规则未应用）
        """
        if current_format and result_list:
            current_format_type, current_num = current_format
            
            # 如果当前标题是"一、"开头，优先查找L3级别的"一、"标题
            if current_format_type == 'chinese' and current_num == 1:
                # 查找L3级别的"一、"标题
                for candidate in reversed(result_list):
                    candidate_level = candidate.get('level', 0)
                    if candidate_level == 3:  # 只检查L3级别
                        candidate_title = candidate.get('title', candidate.get('content', ''))
                        candidate_format = self._extract_number_format(candidate_title) if candidate_title else None
                        if candidate_format and candidate_format[0] == 'chinese' and candidate_format[1] == 1:
                            # 找到L3级别的"一、"标题，当前标题应该也是L3
                            return (3, '规则4扩展：与L3级别的"一、"标题同级，识别为L3')
            
            # 如果还没应用规则，继续查找格式相同且数字连续的标题
            # 优先检查同级标题（相同层级），如果找不到，再检查同一父节点下的标题
            
            # 先尝试查找同级标题（相同层级且相同父节点）
            # 注意：如果前一个标题的层级与当前标题的基础层级不同，可能需要查找更早的同级标题
            current_parent_id = prev_heading.get('parent_id') if prev_heading else None
            prev_level = prev_heading.get('level', 0) if prev_heading else 0
            
            # 如果前一个标题的层级与当前标题的基础层级不同，放宽parent_id限制，查找所有同级标题
            # 这样可以跳过被删除的标题，找到更早的同级标题
            need_find_sibling = (prev_level != base_level)
            
            for candidate in reversed(result_list):  # 从后往前查找，优先匹配最近的
                candidate_level = candidate.get('level', 0)
                if candidate_level > 0 and candidate_level <= self.MAX_LEVEL:  # 只检查有效层级
                    # 首先检查层级是否匹配：候选标题的层级应该与当前标题的基础层级相同
                    if candidate_level != base_level:
                        continue
                    
                    # 检查候选标题是否与当前标题在同一个父节点下
                    candidate_parent_id = candidate.get('parent_id')
                    if not need_find_sibling:
                        # 如果前一个标题的层级与当前标题的基础层级相同，严格检查parent_id
                        if current_parent_id is not None:
                            if candidate_parent_id != current_parent_id:
                                # 不在同一个父节点下，跳过
                                continue
                        else:
                            # current_parent_id为None时，只匹配parent_id也为None的标题
                            if candidate_parent_id is not None:
                                continue
                    # 如果need_find_sibling为True，不检查parent_id，允许跨父节点匹配
                    
                    candidate_title = candidate.get('title', candidate.get('content', ''))
                    candidate_format = self._extract_number_format(candidate_title) if candidate_title else None
                    if candidate_format:
                        candidate_format_type, candidate_num = candidate_format
                        # 当前格式与候选标题格式相同，且数字连续
                        if current_format_type == candidate_format_type and current_num == candidate_num + 1:
                            reason = f'规则4扩展：格式与已处理标题格式相同且连续({candidate_num}->{current_num})，保持同级{candidate_level}'
                            return (candidate_level, reason)
            
            # 如果没找到同级标题，再检查同一父节点下的标题
            # 注意：只有在格式不同且不满足规则1-4的情况下才会进入这里
            # 这里应该更严格地检查：只匹配真正同级的标题（相同层级且相同父节点）
            current_parent_id = prev_heading.get('parent_id') if prev_heading else None
            
            for candidate in reversed(result_list):  # 从后往前查找，优先匹配最近的
                candidate_level = candidate.get('level', 0)
                if candidate_level > 0 and candidate_level <= self.MAX_LEVEL:  # 只检查有效层级
                    # 检查候选标题是否与当前标题在同一个父节点下
                    candidate_parent_id = candidate.get('parent_id')
                    
                    # 严格匹配：必须parent_id相同
                    if current_parent_id is not None:
                        if candidate_parent_id != current_parent_id:
                            # 不在同一个父节点下，跳过
                            continue
                    else:
                        # current_parent_id为None时，只匹配parent_id也为None的标题
                        if candidate_parent_id is not None:
                            continue
                    
                    # 额外检查：候选标题的层级应该与基础层级相同，或者与前一个标题的层级相同
                    # 这样可以避免跨层级误匹配
                    if candidate_level != base_level and candidate_level != prev_heading.get('level', 0) if prev_heading else 0:
                        continue
                    
                    candidate_title = candidate.get('title', candidate.get('content', ''))
                    candidate_format = self._extract_number_format(candidate_title) if candidate_title else None
                    if candidate_format:
                        candidate_format_type, candidate_num = candidate_format
                        # 当前格式与候选标题格式相同，且数字连续
                        if current_format_type == candidate_format_type and current_num == candidate_num + 1:
                            reason = f'规则4扩展：格式与已处理标题格式相同且连续({candidate_num}->{current_num})，保持同级{candidate_level}'
                            return (candidate_level, reason)
        
        return None
    
    def detect_by_context(self, heading: str, prev_heading: Optional[Dict] = None, 
                         next_heading: Optional[Dict] = None,
                         prev_parent_heading: Optional[Dict] = None,
                         prev_parent_chain: Optional[List[Dict]] = None,
                         result_list: Optional[List[Dict]] = None) -> Tuple[int, str]:
        """
        根据上下文调整标题层级
        
        Args:
            heading: 当前标题文本
            prev_heading: 前一个标题信息（包含level和title字段）
            next_heading: 下一个标题信息（包含level字段）
            
        Returns:
            (level, reason): 调整后的层级和调整原因
        """
        # 首先根据格式识别基础层级
        base_level, pattern_name = self.detect_by_format(heading)
        
        if base_level == 0:
            return (0, pattern_name)
        
        adjusted_level = base_level
        reasons = [pattern_name]
        rule_applied = False  # 标记是否有规则应用
        
        # 根据前一个标题调整
        if prev_heading and prev_heading.get('level', 0) > 0:
            prev_level = prev_heading['level']
            prev_title = prev_heading.get('title', '')
            
            # 提取数字格式
            current_format = self._extract_number_format(heading)
            prev_format = self._extract_number_format(prev_title) if prev_title else None
            
            # 按优先级顺序应用规则：
            # 1. 特殊规则1和2
            # 2. 规则2（从1开始）
            # 3. 规则3和4（父标题匹配）
            # 4. 规则1（格式相同且数字连续）- 最高优先级，最后应用以覆盖之前的规则
            
            # 特殊规则1：处理"第X节"格式
            result = self._apply_special_rule_section(heading, base_level, prev_heading, current_format, prev_format)
            if result:
                adjusted_level, reason = result
                reasons.append(reason)
                rule_applied = True
            
            # 特殊规则2：前一个标题格式为None，当前标题从1开始
            if not rule_applied:
                result = self._apply_special_rule_after_section(current_format, prev_format, prev_level)
                if result:
                    adjusted_level, reason = result
                    reasons.append(reason)
                    rule_applied = True
            
            # 规则2：从1开始 → 次级标题
            if not rule_applied:
                result = self._apply_rule_2_start_from_one(current_format, prev_format, prev_level)
                if result:
                    adjusted_level, reason = result
                    reasons.append(reason)
                    rule_applied = True
            
            # 尝试规则3和规则4（检查父标题格式匹配）
            # 注意：即使格式相同，也应该检查父标题，因为可能数字不连续但应该与父标题同级
            if not rule_applied and current_format and prev_format:
                current_format_type, current_num = current_format
                prev_format_type, prev_num = prev_format
                
                # 规则3：格式与父标题格式相同且连续（无论当前格式与前一个格式是否相同）
                result = self._apply_rule_3_parent_format_match(current_format, prev_parent_heading)
                if result:
                    adjusted_level, reason = result
                    reasons.append(reason)
                    rule_applied = True
                
                # 规则4：格式与父标题链格式相同且连续
                if not rule_applied:
                    result = self._apply_rule_4_parent_chain_match(current_format, prev_parent_chain)
                    if result:
                        adjusted_level, reason = result
                        reasons.append(reason)
                        rule_applied = True
                
                # # 规则4扩展：检查父标题链同级标题
                if not rule_applied:
                    result = self._apply_rule_4_extended_sibling_match(current_format, prev_parent_chain, result_list)
                    if result:
                        adjusted_level, reason = result
                        reasons.append(reason)
                        rule_applied = True
                
                # 规则4扩展2：在result_list中搜索（只在格式不同时检查，避免与规则1冲突）
                if not rule_applied and current_format_type != prev_format_type:
                    result = self._apply_rule_4_extended2_sibling_search(current_format, base_level, prev_heading, result_list)
                    if result:
                        adjusted_level, reason = result
                        reasons.append(reason)
                        rule_applied = True
            
            # 规则1：格式相同且数字连续 → 保持同级（最高优先级，覆盖之前的规则）
            if current_format and prev_format:
                result = self._apply_rule_1_same_format_consecutive(current_format, prev_format, prev_level)
                if result:
                    adjusted_level, reason = result
                    reasons.append(reason)
                    rule_applied = True
            
            # 如果没有任何规则应用，返回0表示应删除该标题
            if not rule_applied:
                # 不满足任何规则，应删除该标题
                return (0, '无规则应用，删除该标题')
            # 如果前一个标题层级更高（数字更小），当前标题应该比前一个标题层级低
            # 但如果规则已应用，跳过此调整
            elif prev_level < adjusted_level:
                # 确保层级递增（数字越小层级越高）
                # 当前标题应该比前一个标题层级低至少1级
                if adjusted_level > prev_level + 1:
                    adjusted_level = prev_level + 1
                    reasons.append(f'前一个标题层级{prev_level}，调整为{adjusted_level}')
                elif adjusted_level == prev_level + 1:
                    reasons.append(f'前一个标题层级{prev_level}，保持{adjusted_level}')
            
            # 如果前一个标题层级相同或更低，当前标题不应该比前一个标题层级高太多
            # 但如果规则已应用，跳过此调整
            elif rule_applied and prev_level >= adjusted_level:
                # 规则已应用，不进行额外调整
                pass
            elif not rule_applied and prev_level >= adjusted_level:
                # 如果层级跳跃太大，可能需要调整
                if adjusted_level < prev_level - 2:
                    adjusted_level = prev_level - 1
                    reasons.append(f'前一个标题层级{prev_level}，调整为{adjusted_level}')
                # 特殊情况：如果前一个标题层级较高（>=4），当前标题层级比前一个高，且格式从中文括号变为阿拉伯数字
                # 说明当前标题的层级识别过高，应该大幅降低
                elif prev_level >= 4 and adjusted_level > prev_level:
                    current_format = self._extract_number_format(heading)
                    prev_format = self._extract_number_format(prev_title) if prev_title else None
                    if current_format and prev_format:
                        current_format_type, current_num = current_format
                        prev_format_type, prev_num = prev_format
                        # 格式从中文括号变为阿拉伯数字，且数字相同
                        if prev_format_type == 'bracket_chinese' and current_format_type == 'arabic' and prev_num == current_num:
                            # 降低2级
                            adjusted_level = max(prev_level - 2, 1)
                            reasons.append(f'格式对应但层级异常，降低2级到{adjusted_level}')
        
        # 根据下一个标题调整
        # 但如果规则已应用，跳过此调整（规则优先级最高）
        if not rule_applied and next_heading and next_heading.get('level', 0) > 0:
            next_level = next_heading['level']
            
            # 如果下一个标题层级更低（数字更大），当前标题应该比下一个标题层级高
            if next_level > adjusted_level:
                # 确保层级合理
                if adjusted_level < next_level - 2:
                    # 如果层级差距太大，可能需要调整
                    # 但通常不应该根据下一个标题降低当前标题的层级
                    pass
            # 如果下一个标题层级更高（数字更小），当前标题不应该比下一个标题层级低太多
            elif next_level < adjusted_level:
                if adjusted_level > next_level + 2:
                    adjusted_level = next_level + 1
                    reasons.append(f'下一个标题层级{next_level}，调整为{adjusted_level}')
        
        # 限制最终层级在1-7范围内
        adjusted_level = max(self.MIN_LEVEL, min(adjusted_level, self.MAX_LEVEL))
        
        reason_str = ' | '.join(reasons)
        return (adjusted_level, reason_str)
    
    def detect_title_level(self, heading: str, context: Optional[Dict] = None) -> Tuple[int, str]:
        """
        根据标题内容和上下文判断层级（主入口函数）
        
        Args:
            heading: 标题文本
            context: 上下文信息，包含prev_heading、next_heading和in_main_business_section
            
        Returns:
            (level, reason): 层级（0表示不是标题）和识别原因
        """
        # 检查是否为封面标题
        if self.is_cover_title(heading):
            return (0, '封面标题（忽略）')
        
        # 如果有上下文，使用上下文调整
        if context:
            prev_heading = context.get('prev_heading')
            next_heading = context.get('next_heading')
            prev_parent_heading = context.get('prev_parent_heading')
            prev_parent_chain = context.get('prev_parent_chain')
            result_list = context.get('result_list')
            return self.detect_by_context(heading, prev_heading, next_heading, prev_parent_heading, prev_parent_chain, result_list)
        else:
            # 没有上下文，仅根据格式判断
            return self.detect_by_format(heading)
    
    def detect_all_headings(self, headings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量检测所有标题的层级
        
        Args:
            headings: 标题列表，每个标题包含title字段
            
        Returns:
            添加了level和detection_reason字段的标题列表
        """
        result = []
        
        for i, heading_info in enumerate(headings):
            heading = heading_info.get('title', heading_info.get('content', ''))
            
            # 构建上下文
            # 前一个标题需要包含title字段以便提取数字格式
            prev_heading = None
            prev_parent_heading = None
            prev_parent_chain = []
            prev_level = 0
            if result:
                # 找到最近的有效标题（level > 0）
                prev_item = None
                for j in range(len(result) - 1, -1, -1):
                    candidate = result[j]
                    candidate_level = candidate.get('level', 0)
                    if candidate_level > 0:
                        prev_item = candidate
                        break
                
                if prev_item:
                    prev_level = prev_item.get('level', 0)
                    prev_heading = {
                        'title': prev_item.get('title', prev_item.get('content', '')),
                        'level': prev_level,
                        'parent_id': prev_item.get('parent_id')  # 传递parent_id用于规则4扩展
                    }
                else:
                    prev_heading = None
                    prev_level = 0
                
                # 查找前一个标题的父标题链（用于规则3和规则4）
                if prev_level > 1:
                    # 向前查找，构建父标题链
                    current_level = prev_level
                    seen_levels = set()  # 记录已经添加的层级，避免重复
                    for j in range(len(result) - 2, -1, -1):
                        candidate_level = result[j].get('level', 0)
                        # 找到直接父标题（层级低1级）
                        if candidate_level == prev_level - 1 and prev_parent_heading is None:
                            prev_parent_heading = {
                                'title': result[j].get('title', result[j].get('content', '')),
                                'level': candidate_level
                            }
                        # 构建完整的父标题链（所有层级更低的父标题）
                        # 对于每个层级，只添加第一个遇到的标题（即该层级的父标题）
                        if candidate_level < current_level and candidate_level not in seen_levels:
                            prev_parent_chain.append({
                                'title': result[j].get('title', result[j].get('content', '')),
                                'level': candidate_level
                            })
                            seen_levels.add(candidate_level)
                            current_level = candidate_level
                        # 如果已经找到所有层级的父标题，可以提前退出
                        if candidate_level == 1:
                            break
            
            # 下一个标题（暂时不处理，因为需要先检测当前标题）
            next_heading = None
            if i + 1 < len(headings):
                next_item = headings[i + 1]
                next_title = next_item.get('title', next_item.get('content', ''))
                # 先检测下一个标题的层级（用于上下文调整）
                next_level, _ = self.detect_by_format(next_title)
                if next_level > 0:
                    next_heading = {'level': next_level}
            
            context = {
                'prev_heading': prev_heading,
                'next_heading': next_heading,
                'prev_parent_heading': prev_parent_heading,
                'prev_parent_chain': prev_parent_chain,
                'result_list': result  # 传递result列表用于规则4扩展
            }
            
            # 检测层级
            level, reason = self.detect_title_level(heading, context)
            
            # 创建结果项
            result_item = heading_info.copy()
            result_item['level'] = level
            result_item['detection_reason'] = reason
            
            # 设置parent_id：找到最近的层级更低的标题作为父节点
            if result:
                # 从后往前查找最近的层级更低的标题
                parent_id = None
                for j in range(len(result) - 1, -1, -1):
                    candidate = result[j]
                    candidate_level = candidate.get('level', 0)
                    if candidate_level > 0 and candidate_level < level:
                        # 找到父节点，使用heading_index作为parent_id
                        parent_id = candidate.get('heading_index', j)
                        break
                result_item['parent_id'] = parent_id
            else:
                result_item['parent_id'] = None
            
            result.append(result_item)
        
        return result
