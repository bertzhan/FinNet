#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查询光伏设备公司"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata import get_postgres_client
from sqlalchemy import text

def query_pv_companies():
    pg_client = get_postgres_client()

    with pg_client.get_session() as session:
        # 查询光伏设备公司
        result = session.execute(text("""
            SELECT
                code,
                name,
                affiliate_industry->>'ind_name' as industry,
                affiliate_industry->>'ind_code' as industry_code
            FROM listed_companies
            WHERE affiliate_industry->>'ind_name' LIKE '%光伏设备%'
            ORDER BY code
            LIMIT 3
        """)).fetchall()

        print("=" * 80)
        print("光伏设备行业前三家公司（按股票代码排序）")
        print("=" * 80)
        print()

        for i, (code, name, industry, ind_code) in enumerate(result, 1):
            print(f"{i}. {code} - {name}")
            print(f"   行业: {industry} ({ind_code})")
            print()

if __name__ == "__main__":
    query_pv_companies()
