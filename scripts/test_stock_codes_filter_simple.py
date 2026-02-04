#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简化的股票代码过滤功能测试
直接测试数据库查询逻辑，不依赖 dagster

使用方法：
    python scripts/test_stock_codes_filter_simple.py
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata import get_postgres_client, crud
from src.storage.metadata.models import ListedCompany


def test_stock_codes_query():
    """测试按股票代码查询功能"""

    print("=" * 80)
    print("测试股票代码查询功能")
    print("=" * 80)

    pg_client = get_postgres_client()

    # 测试 1: 查询指定的股票代码
    print("\n测试 1: 查询指定的股票代码")
    print("-" * 80)
    stock_codes = ["000001", "000002", "600000"]
    try:
        with pg_client.get_session() as session:
            listed_companies = session.query(ListedCompany).filter(
                ListedCompany.code.in_(stock_codes)
            ).all()

            print(f"✅ 查询成功，找到 {len(listed_companies)} 家公司")
            for company in listed_companies:
                print(f"   - {company.code}: {company.name}")
    except Exception as e:
        print(f"❌ 查询失败: {e}")

    # 测试 2: 查询不存在的股票代码
    print("\n测试 2: 查询不存在的股票代码")
    print("-" * 80)
    stock_codes = ["999999", "888888"]
    try:
        with pg_client.get_session() as session:
            listed_companies = session.query(ListedCompany).filter(
                ListedCompany.code.in_(stock_codes)
            ).all()

            if len(listed_companies) == 0:
                print(f"✅ 正确：未找到不存在的股票代码（返回空列表）")
            else:
                print(f"⚠️  意外：找到了 {len(listed_companies)} 家公司")
    except Exception as e:
        print(f"❌ 查询失败: {e}")

    # 测试 3: 查询混合存在和不存在的代码
    print("\n测试 3: 查询混合存在和不存在的股票代码")
    print("-" * 80)
    stock_codes = ["000001", "999999", "000002", "888888", "600000"]
    try:
        with pg_client.get_session() as session:
            listed_companies = session.query(ListedCompany).filter(
                ListedCompany.code.in_(stock_codes)
            ).all()

            print(f"✅ 查询成功，找到 {len(listed_companies)} 家公司（过滤掉不存在的代码）")
            for company in listed_companies:
                print(f"   - {company.code}: {company.name}")
    except Exception as e:
        print(f"❌ 查询失败: {e}")

    # 测试 4: 空列表查询
    print("\n测试 4: 空股票代码列表查询")
    print("-" * 80)
    stock_codes = []
    try:
        with pg_client.get_session() as session:
            listed_companies = session.query(ListedCompany).filter(
                ListedCompany.code.in_(stock_codes)
            ).all()

            if len(listed_companies) == 0:
                print(f"✅ 正确：空列表返回空结果")
            else:
                print(f"⚠️  意外：返回了 {len(listed_companies)} 家公司")
    except Exception as e:
        print(f"❌ 查询失败: {e}")

    # 测试 5: 对比使用 stock_codes 和 limit 的查询
    print("\n测试 5: 对比 stock_codes 查询 vs limit 查询")
    print("-" * 80)
    stock_codes = ["000001", "000002"]
    limit = 10
    try:
        with pg_client.get_session() as session:
            # 使用 stock_codes
            companies_by_codes = session.query(ListedCompany).filter(
                ListedCompany.code.in_(stock_codes)
            ).all()

            # 使用 limit
            companies_by_limit = session.query(ListedCompany).limit(limit).all()

            print(f"✅ stock_codes 查询: {len(companies_by_codes)} 家公司")
            for company in companies_by_codes:
                print(f"   - {company.code}: {company.name}")

            print(f"✅ limit 查询: {len(companies_by_limit)} 家公司（前3家）")
            for company in companies_by_limit[:3]:
                print(f"   - {company.code}: {company.name}")
            if len(companies_by_limit) > 3:
                print(f"   ... 还有 {len(companies_by_limit) - 3} 家公司")
    except Exception as e:
        print(f"❌ 查询失败: {e}")

    # 测试 6: 大量股票代码
    print("\n测试 6: 查询大量股票代码")
    print("-" * 80)
    stock_codes = [f"{i:06d}" for i in range(1, 51)]  # 000001 到 000050
    try:
        with pg_client.get_session() as session:
            listed_companies = session.query(ListedCompany).filter(
                ListedCompany.code.in_(stock_codes)
            ).all()

            print(f"✅ 查询成功，从 {len(stock_codes)} 个代码中找到 {len(listed_companies)} 家公司")
            if len(listed_companies) > 0:
                print(f"   前3家:")
                for company in listed_companies[:3]:
                    print(f"   - {company.code}: {company.name}")
                if len(listed_companies) > 3:
                    print(f"   ... 还有 {len(listed_companies) - 3} 家公司")
    except Exception as e:
        print(f"❌ 查询失败: {e}")

    print("\n" + "=" * 80)
    print("所有测试完成")
    print("=" * 80)


if __name__ == "__main__":
    test_stock_codes_query()
