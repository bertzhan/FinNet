#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 100 家港股公司的年度和季度解析是否正确

用法：
    python scripts/test_hk_fiscal_period.py              # 测试前 100 家
    python scripts/test_hk_fiscal_period.py 100 100       # 测试第 101-200 家（offset=100）
    python scripts/test_hk_fiscal_period.py 100 0 random  # 随机抽样 100 家（覆盖不同代码段）

从披露易拉取真实公告，验证 HKEXTitleParser 的 extract_year_from_title 和 identify_quarter 解析结果。
港股季度报告非强制披露，多数公司无季度报告；可用 random 模式随机抽样提高覆盖。
"""
import sys
import time
import random
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def fetch_and_test(limit: int = 100, offset: int = 0, random_sample: bool = False, announcements_per_type: int = 2):
    """从披露易获取真实公告，测试年度/季度解析"""
    from src.storage.metadata.postgres_client import get_postgres_client
    from src.storage.metadata import crud
    from src.ingestion.hk_stock.api.hkex_client import HKEXClient

    pg = get_postgres_client()
    hkex = HKEXClient()

    # 获取港股公司（有 org_id 的），在 session 内提取属性避免 DetachedInstanceError
    with pg.get_session() as session:
        if random_sample:
            # 随机抽样：取 2000 家再随机选 limit 家，覆盖不同代码段
            all_rows = crud.get_all_hk_listed_companies(
                session, limit=2000, with_org_id_only=True
            )
            all_companies = [{"code": r.code, "name": r.name, "org_id": r.org_id} for r in all_rows]
            companies = random.sample(all_companies, min(limit, len(all_companies)))
        else:
            rows = crud.get_all_hk_listed_companies(
                session, limit=limit, offset=offset, with_org_id_only=True
            )
            companies = [{"code": r.code, "name": r.name, "org_id": r.org_id} for r in rows]

    if not companies:
        print("❌ 未找到港股公司，请先运行 get_hk_companies_op 更新公司列表")
        return []

    report_types = ['年报', '中期报告', '季度报告']
    # 日期范围：近 3 年
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now().replace(year=datetime.now().year - 3)).strftime('%Y-%m-%d')

    all_results = []
    total_companies = len(companies)
    failed_companies = []

    for idx, company in enumerate(companies, 1):
        code = company["code"]
        name = company["name"]
        org_id = company["org_id"]

        print(f"[{idx}/{total_companies}] {code} {name}...", end=" ", flush=True)

        for report_type in report_types:
            try:
                announcements, error = hkex.query_reports(
                    stock_code=code,
                    org_id=org_id,
                    report_type=report_type,
                    start_date=start_date,
                    end_date=end_date,
                )
                if error:
                    print(f"\n  ⚠️ {report_type}: {error}")
                    continue

                # 过滤真实报告（排除补充公告等）
                filtered = hkex.filter_real_report(announcements)

                for ann in filtered[:announcements_per_type]:
                    title = ann.get("announcementTitle", "")
                    year = ann.get("hkexFiscalYear", "")
                    quarter = ann.get("hkexQuarter", "")
                    all_results.append({
                        "code": code,
                        "name": name,
                        "report_type": report_type,
                        "title": title[:80] + "..." if len(title) > 80 else title,
                        "parsed_year": year,
                        "parsed_quarter": quarter,
                    })
            except Exception as e:
                failed_companies.append((code, str(e)))
                print(f"\n  ❌ {report_type}: {e}")
                continue

        print("✓")
        time.sleep(0.3)  # 限流，避免请求过快

    return all_results, failed_companies


def main():
    limit = 100
    offset = 0
    random_sample = False
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            pass
    if len(sys.argv) > 2:
        try:
            offset = int(sys.argv[2])
        except ValueError:
            if sys.argv[2].lower() == "random":
                random_sample = True
    if len(sys.argv) > 3 and sys.argv[3].lower() == "random":
        random_sample = True

    desc = f"随机抽样 {limit} 家" if random_sample else f"{limit} 家 (offset={offset})"
    print("=" * 100)
    print(f"港股年度/季度解析测试 - 测试 {desc}")
    print("=" * 100)

    results, failed = fetch_and_test(
        limit=limit, offset=offset, random_sample=random_sample, announcements_per_type=2
    )

    # 按公司分组输出
    by_code = {}
    for r in results:
        by_code.setdefault(r["code"], []).append(r)

    for code in sorted(by_code.keys()):
        rows = by_code[code]
        name = rows[0]["name"] if rows else ""
        print(f"\n{code} {name}")
        print("-" * 95)
        for r in rows:
            q_str = r["parsed_quarter"] or "-"
            print(f"  {r['report_type']:8} {r['parsed_year']} {q_str:3} | {r['title']}")

    # 统计
    print("\n" + "=" * 100)
    print("统计")
    print("=" * 100)
    print(f"  测试公司数: {limit} (offset={offset}, random={random_sample})")
    print(f"  成功解析公告数: {len(results)}")
    print(f"  失败公司数: {len(failed)}")
    if failed:
        print(f"  失败明细: {failed[:5]}{'...' if len(failed) > 5 else ''}")

    # 简单校验：年份应为 4 位数字
    invalid_year = [r for r in results if r["parsed_year"] and (len(r["parsed_year"]) != 4 or not r["parsed_year"].isdigit())]
    if invalid_year:
        print(f"\n  ⚠️ 年份格式异常 ({len(invalid_year)} 条):")
        for r in invalid_year[:5]:
            print(f"    {r['code']} {r['report_type']}: year={r['parsed_year']!r}")

    # 季度校验：应为 Q1/Q2/Q3/Q4
    invalid_quarter = [r for r in results if r["parsed_quarter"] and r["parsed_quarter"] not in ("Q1", "Q2", "Q3", "Q4")]
    if invalid_quarter:
        print(f"\n  ⚠️ 季度格式异常 ({len(invalid_quarter)} 条):")
        for r in invalid_quarter[:5]:
            print(f"    {r['code']} {r['report_type']}: quarter={r['parsed_quarter']!r}")

    print("\n请人工核对上述解析结果是否符合预期（尤其关注非 12 月年结的公司）")
    print("=" * 100)


if __name__ == "__main__":
    main()
