#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 search_listed_company 函数
验证新增字段匹配和规范化功能
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata import get_postgres_client, crud
from src.storage.metadata.crud import _normalize_company_name


def test_normalize_function():
    """测试规范化函数"""
    print("\n" + "=" * 60)
    print("测试1: 规范化函数 (_normalize_company_name)")
    print("=" * 60)
    print()
    
    test_cases = [
        ("平安银行股份有限公司", "平安银行"),
        ("万科企业股份有限公司", "万科企业"),
        ("中国平安保险(集团)股份有限公司", "中国平安保险(集团)"),  # 注意：括号内的集团不会被删除
        ("深振业集团", "深振业"),
        ("平安银行", "平安银行"),
        ("万  科Ａ", "万科"),
        ("ST深振业", "深振业"),
        ("*ST平安", "平安"),
        ("平安银行A", "平安银行"),
    ]
    
    passed = 0
    failed = 0
    
    for input_name, expected in test_cases:
        result = _normalize_company_name(input_name)
        if result == expected:
            print(f"✅ {input_name:30} -> {result:20} (期望: {expected})")
            passed += 1
        else:
            print(f"❌ {input_name:30} -> {result:20} (期望: {expected})")
            failed += 1
    
    print()
    print(f"结果: {passed} 通过, {failed} 失败")
    return failed == 0


def test_search_by_name():
    """测试公司名称搜索函数"""
    print("\n" + "=" * 60)
    print("测试2: 公司名称搜索 (search_listed_company)")
    print("=" * 60)
    print()
    
    pg_client = get_postgres_client()
    
    # 测试用例：包含各种匹配场景
    test_cases = [
        # (查询名称, 描述, 是否应该找到)
        ("平安银行", "精确匹配简称", True),
        ("平安银行股份有限公司", "精确匹配全称（带后缀）", True),
        ("平安", "简称包含查询词", True),
        ("深圳振业", "查询词包含简称", True),
    ]
    
    passed = 0
    failed = 0
    skipped = 0
    
    with pg_client.get_session() as session:
        # 先检查数据库中是否有数据
        count = session.query(crud.ListedCompany).count()
        if count == 0:
            print("⚠️  数据库中暂无数据，跳过搜索测试")
            print("   请先运行 get_hs_companies_job 填充数据")
            return True
        
        print(f"数据库中有 {count} 家公司")
        print()
        
        for query_name, description, should_find in test_cases:
            try:
                companies = crud.search_listed_company(session, query_name)
                
                if companies:
                    if should_find:
                        if len(companies) == 1:
                            print(f"✅ [{description}] '{query_name}' -> {companies[0].code} ({companies[0].name})")
                        else:
                            print(f"✅ [{description}] '{query_name}' -> 找到 {len(companies)} 个候选")
                        passed += 1
                    else:
                        print(f"⚠️  [{description}] '{query_name}' -> 找到 {len(companies)} 个 (意外找到)")
                        failed += 1
                else:
                    if should_find:
                        print(f"❌ [{description}] '{query_name}' -> 未找到 (应该找到)")
                        failed += 1
                    else:
                        print(f"✅ [{description}] '{query_name}' -> 未找到 (正确)")
                        passed += 1
                        
            except Exception as e:
                print(f"❌ [{description}] '{query_name}' -> 错误: {e}")
                failed += 1
    
    print()
    print(f"结果: {passed} 通过, {failed} 失败, {skipped} 跳过")
    return failed == 0


def test_field_matching():
    """测试不同字段的匹配"""
    print("\n" + "=" * 60)
    print("测试3: 字段匹配测试")
    print("=" * 60)
    print()
    
    pg_client = get_postgres_client()
    
    with pg_client.get_session() as session:
        # 获取一些有完整信息的公司进行测试
        companies = session.query(crud.ListedCompany).filter(
            crud.ListedCompany.org_name_cn.isnot(None)
        ).limit(5).all()
        
        if not companies:
            print("⚠️  没有找到包含完整信息的公司，跳过字段匹配测试")
            return True
        
        print(f"测试 {len(companies)} 家公司")
        print()
        
        passed = 0
        failed = 0
        
        for company in companies:
            # 测试不同的字段
            test_fields = [
                ("name", company.name),
                ("org_name_cn", company.org_name_cn),
                ("org_short_name_cn", company.org_short_name_cn),
                ("org_name_en", company.org_name_en),
                ("org_short_name_en", company.org_short_name_en),
            ]
            
            for field_name, field_value in test_fields:
                if not field_value:
                    continue
                
                # 测试精确匹配
                results = crud.search_listed_company(session, field_value)
                if results and any(r.code == company.code for r in results):
                    print(f"✅ [{company.code}] 字段 '{field_name}' = '{field_value[:30]}' -> 匹配成功")
                    passed += 1
                else:
                    print(f"❌ [{company.code}] 字段 '{field_name}' = '{field_value[:30]}' -> 匹配失败")
                    failed += 1
        
        print()
        print(f"结果: {passed} 通过, {failed} 失败")
        return failed == 0


def main():
    """运行所有测试"""
    print("=" * 60)
    print("search_listed_company 函数测试")
    print("=" * 60)
    
    results = []
    
    # 测试1: 规范化函数
    try:
        result1 = test_normalize_function()
        results.append(("规范化函数测试", result1))
    except Exception as e:
        print(f"\n❌ 测试1异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("规范化函数测试", False))
    
    # 测试2: 搜索函数
    try:
        result2 = test_search_by_name()
        results.append(("公司名称搜索测试", result2))
    except Exception as e:
        print(f"\n❌ 测试2异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("公司名称搜索测试", False))
    
    # 测试3: 字段匹配
    try:
        result3 = test_field_matching()
        results.append(("字段匹配测试", result3))
    except Exception as e:
        print(f"\n❌ 测试3异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("字段匹配测试", False))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print()
    
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {test_name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, success in results if success)
    
    print()
    print(f"总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
