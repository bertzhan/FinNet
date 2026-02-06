# -*- coding: utf-8 -*-
"""
港股报告标题解析器
从披露易公告标题中提取年份、季度、报告期等信息
"""

import re
from datetime import datetime
from typing import Optional, Tuple


class HKEXTitleParser:
    """
    港股报告标题解析器
    
    支持解析：
    - 年份（包括中文数字年份、跨年格式等）
    - 季度（Q1/Q2/Q3/Q4）
    - 报告期末日期
    - 报告类型
    """
    
    # 中文数字映射
    CHINESE_NUMERIC_MAP = {
        '零': '0', '〇': '0', '一': '1', '二': '2', '三': '3',
        '四': '4', '五': '5', '六': '6', '七': '7', '八': '8', '九': '9'
    }
    
    # 中文月份映射
    CHINESE_MONTH_MAP = {
        '一月': 1, '二月': 2, '三月': 3, '四月': 4, '五月': 5, '六月': 6,
        '七月': 7, '八月': 8, '九月': 9, '十月': 10, '十一月': 11, '十二月': 12,
    }
    
    # 报告类型排除关键词
    EXCLUDE_KEYWORDS = [
        '通知', '通告', '公告', '通知信', '通知函', '通知書',
        '信函', '函件', '函', '信件', '信',
        '申請', '申请', '申請書', '申请书',
        '表格', '表', '表格文件',
        '補充', '补充', '更正', '修正', '修訂', '修订',
        '說明', '说明', '說明書', '说明书',
        '回覆', '回复', '答覆', '答复',
        '通知股東', '通知股东', '股東通知', '股东通知',
        '登記', '登记', '註冊', '注册',
        '發佈通知', '发布通知', '刊發', '刊发',
        '澄清',
    ]
    
    # 报告类型关键词
    REPORT_KEYWORDS = [
        '年报', '年報', '年度报告', '年度報告', 'annual',
        'annual report', 'annual results',
        '年度業績', '年度业绩',
        '中期', '中報', '中期报告', '中期報告', 'interim', 'half-year',
        'interim report', 'interim results',
        '中期業績', '中期业绩', '半年度', '半年度报告', '半年度報告',
        '季度', '季報', '季度报告', '季度報告', 'quarter', 'q1', 'q2', 'q3', 'q4',
        'quarterly report', 'quarterly results',
        '季度業績', '季度业绩',
        '第一季', '第二季', '第三季', '第四季',
        '业绩', '業績', 'results', 'financial',
        '財務', '财务', '财务报表', '財務報表', 'financial statement', 'financial report',
        '業績公告', '业绩公告', '財務摘要', '财务摘要',
    ]
    
    def _chinese_numeric_to_arabic(self, chinese_str: str) -> str:
        """将中文数字字符串转换为阿拉伯数字字符串"""
        result = ''
        for char in chinese_str:
            result += self.CHINESE_NUMERIC_MAP.get(char, char)
        return result
    
    def _determine_fiscal_year(self, year_end: int, month_end: int, is_annual_report: bool) -> int:
        """
        根据截止日期判断财年
        
        例如：截至2022年3月31日止的年报，实际是2021财年
        """
        # 年报：
        # - 截至12月底（10-12月）：当年
        # - 截至3月底（1-3月）：前一年
        # - 截至6月底（4-6月）：当年或前一年，需要更多上下文
        # - 截至9月底（7-9月）：当年
        
        if is_annual_report:
            if month_end in [10, 11, 12]:
                return year_end
            elif month_end in [1, 2, 3]:
                return year_end - 1
            elif month_end in [4, 5, 6]:
                # 6月底可能是中期报告的截止日期
                return year_end - 1
            else:
                return year_end
        else:
            # 中期/季度报告：直接使用截止年份
            return year_end
    
    def identify_quarter(self, title: str) -> Optional[str]:
        """
        识别季度型公告的季度号
        
        Args:
            title: 公告标题
            
        Returns:
            'Q1', 'Q2', 'Q3', 'Q4' 或 None
        """
        title = re.sub(r'<[^>]+>', '', title)
        title_lower = title.lower()
        
        # Q1 关键词识别
        q1_keywords = [
            '第一季度', '第一季', '首季度', '首季', '一季度', '一季',
            '1季', 'q1', '1q', 'Q1', '1Q',
            'first quarter', '1st quarter', 'First Quarter', '1st Quarter'
        ]
        if any(keyword in title_lower for keyword in q1_keywords):
            return 'Q1'
        
        # Q2 关键词识别
        q2_keywords = [
            '第二季度', '第二季', '二季度', '二季',
            '2季', 'q2', '2q', 'Q2', '2Q',
            'second quarter', '2nd quarter', 'Second Quarter', '2nd Quarter',
            '中期', '中報', '半年', '半年度', 'interim', 'half-year', 'half year',
            '六個月', '六个月'
        ]
        if any(keyword in title_lower for keyword in q2_keywords):
            return 'Q2'
        
        # Q3 关键词识别
        q3_keywords = [
            '第三季度', '第三季', '三季度', '三季',
            '3季', 'q3', '3q', 'Q3', '3Q',
            'third quarter', '3rd quarter', 'Third Quarter', '3rd Quarter',
            '九个月', '九個月', 'nine-month', 'nine month', 'Nine-Month', 'Nine Month'
        ]
        if any(keyword in title_lower for keyword in q3_keywords):
            return 'Q3'
        
        # Q4 关键词识别
        q4_keywords = [
            '第四季度', '第四季', '四季度', '四季',
            '4季', 'q4', '4q', 'Q4', '4Q',
            'fourth quarter', '4th quarter', 'Fourth Quarter', '4th Quarter',
            '年报', '年報', '年度', 'annual', '十二個月', '十二个月', 'twelve'
        ]
        if any(keyword in title_lower for keyword in q4_keywords):
            return 'Q4'
        
        # 基于日期的季度推断
        截至格式 = re.search(r'截至.*?(\d{4})年(\d{1,2})月', title)
        if 截至格式:
            month = int(截至格式.group(2))
            if month in [1, 2, 3]:
                return 'Q1'
            elif month in [4, 5, 6]:
                return 'Q2'
            elif month in [7, 8, 9]:
                return 'Q3'
            elif month in [10, 11, 12]:
                return 'Q4'
        
        return None
    
    def extract_year_from_title(self, title: str, timestamp_ms: int) -> str:
        """
        从标题中提取年份（考虑财年截止日期）
        
        Args:
            title: 公告标题
            timestamp_ms: 发布时间戳（毫秒）
            
        Returns:
            年份字符串
        """
        title = re.sub(r'<[^>]+>', '', title)
        
        try:
            dt = datetime.fromtimestamp(timestamp_ms / 1000)
        except (OSError, ValueError, OverflowError):
            dt = datetime.utcnow()
        release_year_str = str(dt.year)
        
        # 方案1：截至XX年XX月格式
        截至格式 = re.search(r'截至.*?(\d{4})年(\d{1,2})月', title)
        if 截至格式:
            year_end = int(截至格式.group(1))
            month_end = int(截至格式.group(2))
            is_annual_report = any(kw in title for kw in ['年报', '年報', '年度', 'annual'])
            fiscal_year = self._determine_fiscal_year(year_end, month_end, is_annual_report)
            return str(fiscal_year)
        
        # 方案2：中文年份格式
        中文年份格式 = re.search(r'截至.*?二[零〇]([零〇一二三四五六七八九]{2})年', title)
        if 中文年份格式:
            中文年份 = 中文年份格式.group(1)
            阿拉伯年份 = self._chinese_numeric_to_arabic(中文年份)
            year_end = 2000 + int(阿拉伯年份)
            
            month_end = None
            for 月份, 数字 in self.CHINESE_MONTH_MAP.items():
                if 月份 in title:
                    month_end = 数字
                    break
            
            if month_end is not None:
                is_annual_report = any(kw in title for kw in ['年报', '年報', '年度', 'annual'])
                fiscal_year = self._determine_fiscal_year(year_end, month_end, is_annual_report)
                return str(fiscal_year)
            
            return str(year_end)
        
        # 跨年格式：2022-2023 或 2022/2023
        跨年格式 = re.search(r'(\d{4})[-/](\d{4})', title)
        if 跨年格式:
            return 跨年格式.group(1)
        
        # 省略年份的跨年格式：2023/24
        省略年份格式 = re.search(r'(\d{4})[-/](\d{2})(?!\d)', title)
        if 省略年份格式:
            return 省略年份格式.group(1)
        
        # 标准年份格式
        年度格式 = re.search(r'(\d{4})年', title)
        if 年度格式:
            return 年度格式.group(1)
        
        # 查找中文年份：二零二三
        中文年格式 = re.search(r'二[零〇]([零〇一二三四五六七八九]{2})', title)
        if 中文年格式:
            中文数字 = 中文年格式.group(1)
            阿拉伯数字 = self._chinese_numeric_to_arabic(中文数字)
            return '20' + 阿拉伯数字
        
        # 任意四位数字年份
        任意年份 = re.search(r'20(\d{2})', title)
        if 任意年份:
            return '20' + 任意年份.group(1)
        
        # 兜底：使用发布时间
        if dt.month <= 4:
            return str(dt.year - 1)
        return release_year_str
    
    def should_exclude_announcement(self, title: str) -> bool:
        """
        检查公告是否应该被剔除（通知、信函、申請、表格等非报表文件）
        
        Args:
            title: 公告标题
            
        Returns:
            True: 应该剔除，False: 应该保留
        """
        clean_title = re.sub(r'<[^>]+>', '', title).strip()
        title_lower = clean_title.lower()
        
        # 补充公告关键词
        supplement_keywords = ['補充公告', '补充公告', '補充公布', '补充公布', 'supplement']
        for keyword in supplement_keywords:
            if keyword in title_lower:
                if title_lower.startswith(keyword) or '補充公告' in title_lower or '补充公告' in title_lower:
                    return True
        
        # 澄清公告关键词
        clarification_keywords = ['澄清公告', '澄清公布', '澄清公佈', 'clarification']
        for keyword in clarification_keywords:
            if keyword in title_lower:
                return True
        
        # 通知信函关键词
        notice_letter_keywords = [
            '通知信函', '通知信', '通知函',
            '登記持有人通知信函', '登记持有人通知信函',
            '登記股東通知信函', '登记股东通知信函',
        ]
        for keyword in notice_letter_keywords:
            if keyword in title_lower:
                return True
        
        # 更正公告关键词
        correction_keywords = ['更正公告', '更正公布', '更正公佈', 'correction']
        for keyword in correction_keywords:
            if keyword in title_lower:
                return True
        
        # 检查是否包含报告类型关键词
        has_report_keyword = any(keyword in title_lower for keyword in self.REPORT_KEYWORDS)
        
        if has_report_keyword:
            return False
        
        # 检查是否包含剔除关键词
        has_exclude_keyword = any(keyword in title_lower for keyword in self.EXCLUDE_KEYWORDS)
        
        if has_exclude_keyword:
            return True
        
        return False
    
    def extract_report_period(self, title: str, timestamp_ms: int) -> Optional[str]:
        """
        从标题中提取报告期末日期
        
        Args:
            title: 公告标题
            timestamp_ms: 发布时间戳（毫秒）
            
        Returns:
            报告期末日期 (格式: YYYY-MM-DD)，如果无法提取则返回 None
        """
        title = re.sub(r'<[^>]+>', '', title)
        
        # 截至XX年XX月XX日止
        截至格式 = re.search(r'截至.*?(\d{4})年(\d{1,2})月(?:(\d{1,2})日)?', title)
        if 截至格式:
            year = 截至格式.group(1)
            month = 截至格式.group(2).zfill(2)
            day = 截至格式.group(3)
            if day:
                day = day.zfill(2)
                return f"{year}-{month}-{day}"
            else:
                month_int = int(month)
                if month_int in [1, 3, 5, 7, 8, 10, 12]:
                    return f"{year}-{month}-31"
                elif month_int in [4, 6, 9, 11]:
                    return f"{year}-{month}-30"
                elif month_int == 2:
                    return f"{year}-{month}-28"
                return f"{year}-{month}"
        
        return None
    
    def get_doc_type_from_quarter(self, quarter: Optional[str]) -> str:
        """
        根据季度获取文档类型
        
        Args:
            quarter: 季度标识 ('Q1', 'Q2', 'Q3', 'Q4' 或 None)
            
        Returns:
            文档类型名称
        """
        if not quarter:
            return 'unknown'
        
        if quarter == 'Q4':
            return 'annual_report'
        elif quarter == 'Q2':
            return 'interim_report'
        elif quarter in ['Q1', 'Q3']:
            return 'quarterly_report'
        else:
            return 'unknown'
