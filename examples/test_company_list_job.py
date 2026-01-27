#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上市公司列表更新作业测试脚本
用于测试 update_listed_companies_job 是否正常工作
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dagster import build_op_context
from src.processing.compute.dagster.jobs.company_list_jobs import update_listed_companies_op
from src.storage.metadata import get_postgres_client, crud


def test_company_list_job():
    """测试上市公司列表更新Job"""
    print("=" * 60)
    print("测试: update_listed_companies_job")
    print("=" * 60)
    print()
    
    # 配置：使用默认的 upsert 策略
    config = {
        "clear_before_update": False,  # 使用 upsert 策略
    }
    
    print("配置:")
    print(f"  clear_before_update: {config['clear_before_update']}")
    print()
    
    try:
        print("创建 Op Context...")
        context = build_op_context(op_config=config)
        
        print("开始执行 Op...")
        result = update_listed_companies_op(context)
        
        print(f"\n✅ Job 执行完成")
        success = result.get('success', False)
        print(f"   成功: {success}")
        
        if success:
            print(f"\n📊 更新结果:")
            print(f"   总计: {result.get('total', 0)} 家")
            print(f"   新增: {result.get('inserted', 0)} 家")
            print(f"   更新: {result.get('updated', 0)} 家")
            print(f"   更新时间: {result.get('updated_at', 'N/A')}")
        else:
            error = result.get('error', '未知错误')
            print(f"   错误: {error}")
        
        return success
        
    except Exception as e:
        print(f"\n❌ Job 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_records():
    """测试数据库记录"""
    print("\n" + "=" * 60)
    print("验证数据库记录")
    print("=" * 60)
    print()
    
    try:
        pg_client = get_postgres_client()
        
        with pg_client.get_session() as session:
            # 获取所有公司
            companies = crud.get_all_listed_companies(session, limit=10)
            
            total_count = len(crud.get_all_listed_companies(session))
            
            print(f"📊 数据库统计:")
            print(f"   总记录数: {total_count} 家")
            print()
            
            if companies:
                print(f"前 10 家公司示例:")
                for i, company in enumerate(companies, 1):
                    print(f"   {i}. {company.code} - {company.name}")
                    print(f"      创建时间: {company.created_at}")
                    print(f"      更新时间: {company.updated_at}")
            else:
                print("   ⚠️  数据库中没有记录")
                print("   提示: 先运行更新作业")
            
            return True
            
    except Exception as e:
        print(f"\n❌ 数据库查询失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_query_by_code():
    """测试根据代码查询"""
    print("\n" + "=" * 60)
    print("测试根据代码查询")
    print("=" * 60)
    print()
    
    try:
        pg_client = get_postgres_client()
        
        with pg_client.get_session() as session:
            # 先获取一个公司代码
            companies = crud.get_all_listed_companies(session, limit=1)
            
            if companies:
                test_code = companies[0].code
                print(f"测试代码: {test_code}")
                
                # 查询
                company = crud.get_listed_company_by_code(session, test_code)
                
                if company:
                    print(f"✅ 查询成功:")
                    print(f"   代码: {company.code}")
                    print(f"   名称: {company.name}")
                    print(f"   创建时间: {company.created_at}")
                    print(f"   更新时间: {company.updated_at}")
                    return True
                else:
                    print(f"❌ 未找到代码为 {test_code} 的公司")
                    return False
            else:
                print("⚠️  数据库中没有记录，跳过测试")
                return True  # 跳过不算失败
                
    except Exception as e:
        print(f"\n❌ 查询测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("上市公司列表更新作业测试")
    print("=" * 60)
    print()
    
    results = []
    
    # 测试1: 执行更新作业
    try:
        job_success = test_company_list_job()
        results.append(("执行更新作业", job_success))
    except Exception as e:
        print(f"\n❌ 测试1异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("执行更新作业", False))
    
    # 测试2: 验证数据库记录
    try:
        db_success = test_database_records()
        results.append(("验证数据库记录", db_success))
    except Exception as e:
        print(f"\n❌ 测试2异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("验证数据库记录", False))
    
    # 测试3: 测试查询功能
    try:
        query_success = test_query_by_code()
        results.append(("测试查询功能", query_success))
    except Exception as e:
        print(f"\n❌ 测试3异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("测试查询功能", False))
    
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


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
