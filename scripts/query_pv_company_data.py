#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查询光伏设备公司的文档和分块数据"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata import get_postgres_client
from sqlalchemy import text

def query_pv_company_data():
    pg_client = get_postgres_client()

    with pg_client.get_session() as session:
        # 查询光伏设备公司及其数据统计
        result = session.execute(text("""
            WITH pv_companies AS (
                SELECT code, name
                FROM hs_listed_companies
                WHERE industry LIKE '%光伏设备%'
                ORDER BY code
                LIMIT 3
            )
            SELECT
                c.code,
                c.name,
                COUNT(DISTINCT d.id) as document_count,
                COUNT(dc.id) as chunk_count,
                COUNT(dc.id) FILTER (WHERE dc.vectorized_at IS NOT NULL) as vectorized_chunk_count
            FROM pv_companies c
            LEFT JOIN documents d ON d.stock_code = c.code
            LEFT JOIN document_chunks dc ON dc.document_id = d.id
            GROUP BY c.code, c.name
            ORDER BY c.code
        """)).fetchall()

        print("=" * 80)
        print("光伏设备公司数据统计")
        print("=" * 80)
        print()

        for code, name, doc_count, chunk_count, vectorized_count in result:
            print(f"📊 {code} - {name}")
            print(f"   文档数: {doc_count}")
            print(f"   分块数: {chunk_count}")
            print(f"   已向量化: {vectorized_count} / {chunk_count}")
            if chunk_count > 0:
                print(f"   向量化率: {vectorized_count / chunk_count * 100:.1f}%")
            print()

if __name__ == "__main__":
    query_pv_company_data()
