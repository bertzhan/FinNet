#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接测试 get_hs_companies_job
模拟执行作业的核心逻辑，不依赖完整的 Dagster 环境
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_akshare_data_fetch():
    """测试从 akshare 获取数据"""
    print("=" * 60)
    print("测试1: 从 akshare 获取A股上市公司数据")
    print("=" * 60)
    print()
    
    try:
        import akshare as ak
        
        print("正在从 akshare 获取数据...")
        stock_df = ak.stock_info_a_code_name()
        
        if stock_df is None or stock_df.empty:
            print("❌ 获取的数据为空")
            return False, None
        
        print(f"✅ 获取数据成功")
        print(f"   数据形状: {stock_df.shape}")
        print(f"   列名: {stock_df.columns.tolist()}")
        
        # 检查必要的列
        if 'code' not in stock_df.columns or 'name' not in stock_df.columns:
            print(f"❌ 缺少必要的列 (code, name)")
            return False, None
        
        # 只保留 code 和 name 字段
        stock_df = stock_df[['code', 'name']].copy()
        
        # 清理数据
        stock_df = stock_df.dropna(subset=['code', 'name'])
        stock_df['code'] = stock_df['code'].astype(str).str.strip()
        stock_df['name'] = stock_df['name'].astype(str).str.strip()
        stock_df = stock_df[(stock_df['code'] != '') & (stock_df['name'] != '')]
        
        total_count = len(stock_df)
        print(f"\n   清理后数据量: {total_count} 家")
        
        # 显示前5条数据
        print(f"\n   前5条数据示例:")
        for idx, row in stock_df.head(5).iterrows():
            code = str(row['code']).strip()
            name = str(row['name']).strip()
            print(f"     {code} - {name}")
        
        return True, stock_df
        
    except ImportError:
        print("❌ akshare 未安装")
        print("   提示: 请运行 pip install akshare")
        return False, None
    except Exception as e:
        print(f"❌ 获取数据失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_database_upsert(stock_df):
    """测试数据库更新操作"""
    print("\n" + "=" * 60)
    print("测试2: 数据库更新操作")
    print("=" * 60)
    print()
    
    if stock_df is None or stock_df.empty:
        print("⚠️  跳过数据库测试（没有数据）")
        return False
    
    try:
        from src.storage.metadata import get_postgres_client, crud
        
        pg_client = get_postgres_client()
        
        # 测试连接
        if not pg_client.test_connection():
            print("❌ 数据库连接失败")
            print("   提示: 请确保 PostgreSQL 服务正在运行")
            return False
        
        print("✅ 数据库连接成功")
        
        # 检查表是否存在
        if not pg_client.table_exists('hs_listed_companies'):
            print("❌ hs_listed_companies 表不存在")
            print("   提示: 请先运行 python scripts/migrate_listed_companies_table.py")
            return False
        
        print("✅ hs_listed_companies 表存在")
        
        # 获取更新前的记录数
        before_count = pg_client.get_table_count('hs_listed_companies')
        print(f"   更新前记录数: {before_count} 家")
        
        # 执行更新操作（只更新前10条作为测试）
        print(f"\n   开始更新数据库（测试前10条）...")
        test_df = stock_df.head(10)
        
        inserted_count = 0
        updated_count = 0
        
        with pg_client.get_session() as session:
            # 获取现有公司的 code 集合
            existing_codes = {
                company.code
                for company in crud.get_all_listed_companies(session)
            }
            
            # 遍历并更新
            for _, row in test_df.iterrows():
                code = str(row['code']).strip()
                name = str(row['name']).strip()
                
                if not code or not name:
                    continue
                
                is_new = code not in existing_codes
                
                # 使用 upsert 函数
                company = crud.upsert_listed_company(session, code, name)
                
                if is_new:
                    inserted_count += 1
                else:
                    updated_count += 1
            
            session.commit()
        
        # 获取更新后的记录数
        after_count = pg_client.get_table_count('hs_listed_companies')
        
        print(f"   ✅ 更新完成")
        print(f"   新增: {inserted_count} 家")
        print(f"   更新: {updated_count} 家")
        print(f"   更新后记录数: {after_count} 家")
        
        # 验证数据
        print(f"\n   验证更新后的数据:")
        with pg_client.get_session() as session:
            for _, row in test_df.head(3).iterrows():
                code = str(row['code']).strip()
                company = crud.get_listed_company_by_code(session, code)
                if company:
                    print(f"     ✅ {company.code} - {company.name}")
                else:
                    print(f"     ❌ {code} - 未找到")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据库操作失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_job_simulation():
    """模拟完整作业执行"""
    print("\n" + "=" * 60)
    print("测试3: 模拟完整作业执行")
    print("=" * 60)
    print()
    
    try:
        # 步骤1: 获取数据
        success, stock_df = test_akshare_data_fetch()
        if not success:
            print("⚠️  跳过完整作业测试（数据获取失败）")
            return False
        
        # 步骤2: 更新数据库
        db_success = test_database_upsert(stock_df)
        if not db_success:
            print("⚠️  数据库更新失败")
            return False
        
        print("\n✅ 完整作业模拟成功")
        print(f"   处理了 {len(stock_df)} 家公司的数据")
        
        return True
        
    except Exception as e:
        print(f"❌ 作业模拟失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dagster_job_execution():
    """测试实际的 Dagster 作业执行（直接调用 op）"""
    print("\n" + "=" * 60)
    print("测试4: Dagster 作业执行")
    print("=" * 60)
    print()
    
    try:
        from dagster import build_op_context
        from src.processing.compute.dagster.jobs.company_list_jobs import get_hs_companies_op
        
        print("配置作业参数...")
        config = {
            "clear_before_update": False,  # 使用 upsert 策略
        }
        
        print("创建 Op Context...")
        context = build_op_context(op_config=config)
        
        print("开始执行 Op...")
        result = get_hs_companies_op(context)
        
        if result.get('success'):
            print("✅ 作业执行成功")
            
            print(f"\n📊 作业输出:")
            print(f"   总计: {result.get('total', 0)} 家")
            print(f"   新增: {result.get('inserted', 0)} 家")
            print(f"   更新: {result.get('updated', 0)} 家")
            print(f"   更新时间: {result.get('updated_at', 'N/A')}")
            
            return True
        else:
            print("❌ 作业执行失败")
            error = result.get('error', '未知错误')
            print(f"   错误: {error}")
            return False
            
    except ImportError as e:
        print(f"⚠️  无法导入模块: {e}")
        print("   提示: 可能需要安装缺失的依赖")
        import traceback
        traceback.print_exc()
        return None  # 跳过不算失败
    except Exception as e:
        print(f"❌ 作业执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("get_hs_companies_job 完整测试")
    print("=" * 60)
    print()
    
    results = []
    
    # 测试1: 获取数据
    try:
        success, stock_df = test_akshare_data_fetch()
        results.append(("获取 akshare 数据", success))
    except Exception as e:
        print(f"\n❌ 测试1异常: {e}")
        results.append(("获取 akshare 数据", False))
        stock_df = None
    
    # 测试2: 数据库更新（如果有数据）
    if stock_df is not None:
        try:
            success = test_database_upsert(stock_df)
            results.append(("数据库更新操作", success))
        except Exception as e:
            print(f"\n❌ 测试2异常: {e}")
            results.append(("数据库更新操作", False))
    else:
        print("\n⚠️  跳过数据库更新测试（没有数据）")
        results.append(("数据库更新操作", None))
    
    # 测试3: 完整作业模拟
    try:
        success = test_full_job_simulation()
        results.append(("完整作业模拟", success))
    except Exception as e:
        print(f"\n❌ 测试3异常: {e}")
        results.append(("完整作业模拟", False))
    
    # 测试4: Dagster 作业执行
    try:
        success = test_dagster_job_execution()
        results.append(("Dagster 作业执行", success))
    except Exception as e:
        print(f"\n❌ 测试4异常: {e}")
        results.append(("Dagster 作业执行", False))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print()
    
    for test_name, success in results:
        if success is None:
            status = "⏭️  跳过"
        elif success:
            status = "✅ 通过"
        else:
            status = "❌ 失败"
        print(f"  {test_name}: {status}")
    
    total = len([r for r in results if r[1] is not None])
    passed = sum(1 for _, success in results if success is True)
    
    print()
    print(f"总计: {passed}/{total} 通过")
    
    if passed == total and total > 0:
        print("\n🎉 所有测试通过！")
        return 0
    elif passed > 0:
        print(f"\n⚠️  部分测试通过 ({passed}/{total})")
        return 1
    else:
        print(f"\n❌ 所有测试失败")
        print("\n📝 提示:")
        print("   1. 安装 akshare: pip install akshare")
        print("   2. 确保数据库服务运行")
        print("   3. 运行迁移脚本: python scripts/migrate_listed_companies_table.py")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
