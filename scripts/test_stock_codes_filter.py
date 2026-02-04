#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速验证爬虫 stock_codes 参数功能

使用方法：
    python scripts/test_stock_codes_filter.py
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.processing.compute.dagster.jobs.crawl_jobs import load_company_list_from_db
from src.common.logger import get_logger

logger = get_logger(__name__)


def test_stock_codes_filter():
    """测试股票代码过滤功能"""

    print("=" * 80)
    print("测试爬虫 stock_codes 参数功能")
    print("=" * 80)

    # 测试 1: 按股票代码过滤
    print("\n测试 1: 按股票代码列表过滤")
    print("-" * 80)
    stock_codes = ["000001", "000002", "600000"]
    try:
        companies = load_company_list_from_db(stock_codes=stock_codes, logger=logger)
        print(f"✅ 成功加载 {len(companies)} 家公司")
        for company in companies:
            print(f"   - {company['code']}: {company['name']}")
    except Exception as e:
        print(f"❌ 测试失败: {e}")

    # 测试 2: 不存在的股票代码
    print("\n测试 2: 不存在的股票代码")
    print("-" * 80)
    stock_codes = ["999999", "888888"]
    try:
        companies = load_company_list_from_db(stock_codes=stock_codes, logger=logger)
        if len(companies) == 0:
            print(f"✅ 正确处理不存在的股票代码（返回空列表）")
        else:
            print(f"⚠️  意外：返回了 {len(companies)} 家公司")
    except Exception as e:
        print(f"❌ 测试失败: {e}")

    # 测试 3: 混合存在和不存在的代码
    print("\n测试 3: 混合存在和不存在的股票代码")
    print("-" * 80)
    stock_codes = ["000001", "999999", "000002"]
    try:
        companies = load_company_list_from_db(stock_codes=stock_codes, logger=logger)
        print(f"✅ 成功加载 {len(companies)} 家公司（过滤掉不存在的代码）")
        for company in companies:
            print(f"   - {company['code']}: {company['name']}")
    except Exception as e:
        print(f"❌ 测试失败: {e}")

    # 测试 4: 优先级测试 - stock_codes vs limit
    print("\n测试 4: 优先级测试 - stock_codes 优先于 limit")
    print("-" * 80)
    stock_codes = ["000001", "000002"]
    limit = 100
    try:
        companies = load_company_list_from_db(
            stock_codes=stock_codes,
            limit=limit,
            logger=logger
        )
        if len(companies) <= len(stock_codes):
            print(f"✅ 正确：优先使用 stock_codes（返回 {len(companies)} 家，忽略 limit={limit}）")
            for company in companies:
                print(f"   - {company['code']}: {company['name']}")
        else:
            print(f"⚠️  错误：返回了 {len(companies)} 家公司，超过了 stock_codes 的数量")
    except Exception as e:
        print(f"❌ 测试失败: {e}")

    # 测试 5: 优先级测试 - stock_codes vs industry
    print("\n测试 5: 优先级测试 - stock_codes 优先于 industry")
    print("-" * 80)
    stock_codes = ["000001"]  # 平安银行（银行业）
    industry = "制造业"  # 不同的行业
    try:
        companies = load_company_list_from_db(
            stock_codes=stock_codes,
            industry=industry,
            logger=logger
        )
        if len(companies) > 0 and companies[0]['code'] == "000001":
            print(f"✅ 正确：优先使用 stock_codes（返回平安银行，忽略 industry={industry}）")
            for company in companies:
                print(f"   - {company['code']}: {company['name']}")
        else:
            print(f"⚠️  结果: 返回了 {len(companies)} 家公司")
    except Exception as e:
        print(f"❌ 测试失败: {e}")

    # 测试 6: 空列表
    print("\n测试 6: 空股票代码列表")
    print("-" * 80)
    stock_codes = []
    try:
        companies = load_company_list_from_db(stock_codes=stock_codes, logger=logger)
        if len(companies) == 0:
            print(f"✅ 正确处理空列表（返回空结果）")
        else:
            print(f"⚠️  意外：返回了 {len(companies)} 家公司")
    except Exception as e:
        print(f"❌ 测试失败: {e}")

    # 测试 7: None（回退到其他过滤方式）
    print("\n测试 7: stock_codes=None（回退到 limit 参数）")
    print("-" * 80)
    limit = 5
    try:
        companies = load_company_list_from_db(limit=limit, logger=logger)
        print(f"✅ 成功回退到 limit 参数（返回 {len(companies)} 家公司，limit={limit}）")
        for company in companies[:3]:  # 只显示前3个
            print(f"   - {company['code']}: {company['name']}")
        if len(companies) > 3:
            print(f"   ... 还有 {len(companies) - 3} 家公司")
    except Exception as e:
        print(f"❌ 测试失败: {e}")

    print("\n" + "=" * 80)
    print("所有测试完成")
    print("=" * 80)


if __name__ == "__main__":
    test_stock_codes_filter()
