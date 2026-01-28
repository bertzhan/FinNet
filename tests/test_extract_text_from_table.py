#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 extract_text_from_table 函数
使用实际数据测试表格文本提取功能
"""

import sys
import json
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.common.utils import extract_text_from_table


def test_extract_text_from_table():
    """使用实际数据测试 extract_text_from_table 函数"""
    
    print("=" * 80)
    print("测试 extract_text_from_table 函数")
    print("=" * 80)
    print()
    
    # 测试用例1：释义表格（包含文本，少量数字）
    test_case_1 = {
        "name": "释义表格",
        "html": """<table><tr><td>释义项</td><td>指</td><td>释义内容</td></tr><tr><td>和仁科技</td><td>指</td><td>浙江和仁科技股份有限公司</td></tr><tr><td>天津和仁</td><td>指</td><td>和仁（天津）科技有限公司</td></tr><tr><td>西安和仁</td><td>指</td><td>西安和仁汇达信息科技有限公司</td></tr></table>"""
    }
    
    # 测试用例2：公司基本信息表格（包含地址、邮编等数字）
    test_case_2 = {
        "name": "公司基本信息表格",
        "html": """<table><tr><td>股票简称</td><td>和仁科技</td><td>股票代码</td><td>300550</td></tr><tr><td>公司的中文名称</td><td colspan="3">浙江和仁科技股份有限公司</td></tr><tr><td>注册地址</td><td colspan="3">浙江省杭州市滨江区西兴街道新联路625号</td></tr><tr><td>注册地址的邮政编码</td><td colspan="3">310051</td></tr><tr><td>公司注册地址历史变更情况</td><td colspan="3">2012年1月公司注册地址由杭州市滨江区滨安路1197号3号楼226室变更为杭州市东信大道66号E座302室，2017年9月公司注册地址由杭州市东信大道66号E座302室变更为浙江省杭州市滨江区西兴街道新联路625号</td></tr></table>"""
    }
    
    # 测试用例3：联系人和联系方式表格（包含电话、传真等数字）
    test_case_3 = {
        "name": "联系人和联系方式表格",
        "html": """<table><tr><td></td><td>董事会秘书</td><td>证券事务代表</td></tr><tr><td>姓名</td><td>章逸</td><td>屈鑫</td></tr><tr><td>联系地址</td><td>浙江省杭州市滨江区西兴街道新联路625号</td><td>浙江省杭州市滨江区西兴街道新联路625号</td></tr><tr><td>电话</td><td>0571-81397006</td><td>0571-81397006</td></tr><tr><td>传真</td><td>0571-81397100</td><td>0571-81397100</td></tr><tr><td>电子信箱</td><td>contact@herenit.com</td><td>contact@herenit.com</td></tr></table>"""
    }
    
    # 测试用例4：财务数据表格（包含大量数字和百分比）
    test_case_4 = {
        "name": "财务数据表格",
        "html": """<table><tr><td></td><td>营业收入</td><td>营业成本</td><td>毛利率</td><td>营业收入比上年同期增减</td><td>营业成本比上年同期增减</td><td>毛利率比上年同期增减</td></tr><tr><td colspan="7">分客户所处行业</td></tr><tr><td>医疗信息化</td><td>426,576,751.08</td><td>261,792,634.44</td><td>38.63%</td><td>23.55%</td><td>-6.92%</td><td>20.09%</td></tr><tr><td>其他</td><td>12,675,505.13</td><td>6,508,723.21</td><td>48.65%</td><td>-15.92%</td><td>20.13%</td><td>-15.41%</td></tr><tr><td colspan="7">分产品</td></tr><tr><td>场景化应用系统</td><td>172,519,813.80</td><td>120,609,365.01</td><td>30.09%</td><td>134.16%</td><td>82.47%</td><td>19.80%</td></tr><tr><td>医疗信息系统</td><td>213,271,035.78</td><td>122,136,321.68</td><td>42.73%</td><td>-12.89%</td><td>-39.60%</td><td>25.32%</td></tr></table>"""
    }
    
    # 测试用例5：账龄表格（包含大量数字）
    test_case_5 = {
        "name": "账龄表格",
        "html": """<table><tr><td>账龄</td><td>期末账面余额</td><td>期初账面余额</td></tr><tr><td>1年以内（含1年）</td><td>115,849,187.76</td><td>52,949,268.44</td></tr><tr><td>1至2年</td><td>53,088,965.14</td><td>76,506,986.53</td></tr><tr><td>2至3年</td><td>47,626,619.44</td><td>65,845,933.28</td></tr><tr><td>3年以上</td><td>146,394,515.91</td><td>116,443,129.09</td></tr><tr><td>合计</td><td>362,959,288.25</td><td>311,745,317.34</td></tr></table>"""
    }
    
    # 测试用例6：合同资产表格（包含大量数字）
    test_case_6 = {
        "name": "合同资产表格",
        "html": """<table><tr><td rowspan="2">项目</td><td colspan="3">期末余额</td><td colspan="3">期初余额</td></tr><tr><td>账面余额</td><td>坏账准备</td><td>账面价值</td><td>账面余额</td><td>坏账准备</td><td>账面价值</td></tr><tr><td>应收合同对价</td><td>316,746,169.99</td><td>40,586,925.33</td><td>276,159,244.66</td><td>337,198,001.24</td><td>35,284,138.44</td><td>301,913,862.80</td></tr><tr><td>合计</td><td>316,746,169.99</td><td>40,586,925.33</td><td>276,159,244.66</td><td>337,198,001.24</td><td>35,284,138.44</td><td>301,913,862.80</td></tr></table>"""
    }
    
    test_cases = [
        test_case_1,
        test_case_2,
        test_case_3,
        test_case_4,
        test_case_5,
        test_case_6
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'=' * 80}")
        print(f"测试用例 {i}: {test_case['name']}")
        print(f"{'=' * 80}")
        
        html = test_case['html']
        print(f"\n原始HTML长度: {len(html)} 字符")
        print(f"\n原始HTML（前200字符）:")
        print(html[:200] + ("..." if len(html) > 200 else ""))
        
        # 测试1：移除数字
        print(f"\n{'─' * 80}")
        print("测试1: 提取文本（移除数字）")
        print(f"{'─' * 80}")
        result_without_numbers = extract_text_from_table(html, remove_numbers=True)
        print(f"提取的文本长度: {len(result_without_numbers)} 字符")
        print(f"\n提取的文本:")
        print(result_without_numbers)
        
        # 测试2：保留数字
        print(f"\n{'─' * 80}")
        print("测试2: 提取文本（保留数字）")
        print(f"{'─' * 80}")
        result_with_numbers = extract_text_from_table(html, remove_numbers=False)
        print(f"提取的文本长度: {len(result_with_numbers)} 字符")
        print(f"\n提取的文本:")
        print(result_with_numbers)
        
        # 对比
        print(f"\n{'─' * 80}")
        print("对比:")
        print(f"  移除数字后长度: {len(result_without_numbers)} 字符")
        print(f"  保留数字后长度: {len(result_with_numbers)} 字符")
        print(f"  减少: {len(result_with_numbers) - len(result_without_numbers)} 字符")
    
    print(f"\n{'=' * 80}")
    print("测试完成！")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    test_extract_text_from_table()
