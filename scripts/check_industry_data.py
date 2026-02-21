#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查 ListedCompany 表中的行业数据格式
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.storage.metadata import get_postgres_client
from src.storage.metadata.models import ListedCompany, Document
from sqlalchemy import String
import json

def check_industry_data():
    """检查行业数据格式"""
    pg_client = get_postgres_client()

    with pg_client.get_session() as session:
        # 1. 先从 Document 表中找到有"光伏设备"的公司 stock_code
        print("=" * 60)
        print("1. 查找 Document 表中的公司")
        print("=" * 60)

        documents = session.query(Document).limit(20).all()
        stock_codes = set(doc.stock_code for doc in documents)
        print(f"\n找到 {len(documents)} 个文档，涉及 {len(stock_codes)} 家公司")
        print(f"公司代码: {sorted(stock_codes)[:10]}")

        # 2. 查看这些公司在 ListedCompany 表中的 industry 字段
        print("\n" + "=" * 60)
        print("2. 查看 ListedCompany 表中的行业信息")
        print("=" * 60)

        for stock_code in sorted(stock_codes)[:5]:  # 只查看前5个
            company = session.query(ListedCompany).filter(
                ListedCompany.code == stock_code
            ).first()

            if company:
                print(f"\n公司代码: {stock_code}")
                print(f"公司名称: {company.name}")
                print(f"industry_code: {company.industry_code}")
                print(f"industry: {company.industry}")
            else:
                print(f"\n⚠️ 公司代码 {stock_code} 在 ListedCompany 表中不存在")

        # 3. 测试不同的查询方式
        print("\n" + "=" * 60)
        print("3. 测试查询方式")
        print("=" * 60)

        test_keywords = ["光伏", "光伏设备", "银行", "证券"]

        for keyword in test_keywords:
            print(f"\n关键词: '{keyword}'")

            # 方式1: LIKE 查询（当前使用的方式）
            try:
                companies_like = session.query(ListedCompany).filter(
                    ListedCompany.industry.like(f'%{keyword}%')
                ).limit(5).all()
                print(f"  LIKE 查询: 找到 {len(companies_like)} 家公司")
                if companies_like:
                    for c in companies_like[:3]:
                        print(f"    - {c.code}: {c.name}")
            except Exception as e:
                print(f"  LIKE 查询失败: {e}")

            # 方式2: LIKE 查询
            try:
                from sqlalchemy import text
                companies_json = session.query(ListedCompany).filter(
                    text(f"industry LIKE '%{keyword}%'")
                ).limit(5).all()
                print(f"  JSON text 查询: 找到 {len(companies_json)} 家公司")
                if companies_json:
                    for c in companies_json[:3]:
                        print(f"    - {c.code}: {c.name}")
            except Exception as e:
                print(f"  JSON text 查询失败: {e}")

        # 4. 查找所有有 industry 的公司样本
        print("\n" + "=" * 60)
        print("4. 查看所有公司的行业数据样本")
        print("=" * 60)

        companies_with_industry = session.query(ListedCompany).filter(
            ListedCompany.industry.isnot(None)
        ).limit(10).all()

        print(f"\n找到 {len(companies_with_industry)} 家有行业信息的公司（样本）:")
        for company in companies_with_industry:
            print(f"\n{company.code} - {company.name}")
            print(f"  industry_code: {company.industry_code}")
            print(f"  industry: {company.industry}")

if __name__ == '__main__':
    check_industry_data()
