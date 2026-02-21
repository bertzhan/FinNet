#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速检查 us_listed_companies 表中是否有 AAPL
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.storage.metadata.postgres_client import get_postgres_client


def main():
    pg = get_postgres_client()
    with pg.get_session() as session:
        # 1. 总记录数
        r = session.execute(text("SELECT COUNT(*) FROM us_listed_companies"))
        total = r.scalar()
        print(f"表总记录数: {total}")

        # 2. 查询 AAPL（大写，与存储一致）
        r = session.execute(
            text("SELECT code, name, org_id FROM us_listed_companies WHERE code = :code"),
            {"code": "AAPL"}
        )
        row = r.fetchone()
        if row:
            print(f"✅ AAPL 存在: code={row[0]}, name={row[1]}, org_id={row[2]}")
        else:
            print("❌ 未找到 code='AAPL'")

        # 3. 若用小写 appl 查询（PostgreSQL 默认区分大小写）
        r = session.execute(
            text("SELECT code, name FROM us_listed_companies WHERE code = :code"),
            {"code": "appl"}
        )
        row = r.fetchone()
        if row:
            print(f"   code='appl' 小写查询: {row}")
        else:
            print("   code='appl' 小写查询: 无结果（正常，因存储为大写 AAPL）")

        # 4. 不区分大小写查询
        r = session.execute(
            text("SELECT code, name FROM us_listed_companies WHERE UPPER(code) = 'AAPL'")
        )
        row = r.fetchone()
        if row:
            print(f"   UPPER(code)='AAPL' 查询: {row}")

        # 5. 前 5 条记录
        r = session.execute(
            text("SELECT code, name FROM us_listed_companies ORDER BY code LIMIT 5")
        )
        print("\n前 5 条记录:")
        for row in r:
            print(f"  {row[0]}: {row[1]}")


if __name__ == "__main__":
    main()
