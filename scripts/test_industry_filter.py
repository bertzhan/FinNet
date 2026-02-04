#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试行业过滤功能
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.storage.metadata import get_postgres_client, crud
from src.storage.metadata.models import ListedCompany, Document
from sqlalchemy import text

def test_industry_filter():
    """测试行业过滤"""
    pg_client = get_postgres_client()

    with pg_client.get_session() as session:
        print("=" * 60)
        print("测试行业过滤功能")
        print("=" * 60)

        # 测试不同的行业关键词
        test_keywords = ["光伏", "光伏设备", "银行", "证券", "文化传媒"]

        for keyword in test_keywords:
            print(f"\n关键词: '{keyword}'")
            print("-" * 40)

            # 使用 crud 函数查询
            companies = crud.get_all_listed_companies(
                session=session,
                industry=keyword,
                limit=10
            )

            print(f"找到 {len(companies)} 家公司:")
            for company in companies[:5]:  # 显示前5个
                ind_name = company.affiliate_industry.get('ind_name') if company.affiliate_industry else 'N/A'
                print(f"  - {company.code}: {company.name} (行业: {ind_name})")

            # 查询这些公司的文档数量
            if companies:
                company_codes = [c.code for c in companies]
                doc_count = session.query(Document).filter(
                    Document.stock_code.in_(company_codes)
                ).count()
                print(f"  这些公司共有 {doc_count} 个文档")

        # 特别测试：查找 Document 表中有文档的公司的行业分布
        print("\n" + "=" * 60)
        print("Document 表中公司的行业分布")
        print("=" * 60)

        # 获取所有有文档的公司代码
        docs = session.query(Document.stock_code).distinct().all()
        stock_codes_in_docs = [d[0] for d in docs]

        print(f"\nDocument 表中共有 {len(stock_codes_in_docs)} 家公司")

        # 查询这些公司的行业分布
        companies_with_docs = session.query(ListedCompany).filter(
            ListedCompany.code.in_(stock_codes_in_docs)
        ).all()

        industry_counts = {}
        for company in companies_with_docs:
            if company.affiliate_industry:
                ind_name = company.affiliate_industry.get('ind_name', 'Unknown')
                industry_counts[ind_name] = industry_counts.get(ind_name, 0) + 1

        print(f"\n行业分布:")
        for ind_name, count in sorted(industry_counts.items(), key=lambda x: x[1], reverse=True)[:20]:
            print(f"  {ind_name}: {count} 家公司")

if __name__ == '__main__':
    test_industry_filter()
