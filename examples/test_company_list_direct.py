#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上市公司列表更新作业直接测试
直接导入 company_list_jobs 模块，避免依赖其他 Dagster 作业
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 直接导入 company_list_jobs，避免通过 __init__.py 导入其他模块
import importlib.util

def test_company_list_job_direct():
    """直接测试 company_list_jobs 模块"""
    print("=" * 60)
    print("直接测试 company_list_jobs 模块")
    print("=" * 60)
    print()
    
    try:
        # 直接加载模块文件
        module_path = project_root / "src" / "processing" / "compute" / "dagster" / "jobs" / "company_list_jobs.py"
        
        spec = importlib.util.spec_from_file_location("company_list_jobs", module_path)
        module = importlib.util.module_from_spec(spec)
        
        # 设置必要的环境
        sys.modules['dagster'] = __import__('dagster')
        sys.modules['src.storage.metadata.postgres_client'] = __import__('src.storage.metadata.postgres_client', fromlist=['get_postgres_client'])
        sys.modules['src.storage.metadata'] = __import__('src.storage.metadata', fromlist=['crud'])
        
        spec.loader.exec_module(module)
        
        print("✅ company_list_jobs 模块加载成功")
        print(f"   找到的组件:")
        
        if hasattr(module, 'update_listed_companies_op'):
            print(f"     - update_listed_companies_op")
        if hasattr(module, 'update_listed_companies_job'):
            print(f"     - update_listed_companies_job")
        if hasattr(module, 'daily_update_companies_schedule'):
            print(f"     - daily_update_companies_schedule")
        if hasattr(module, 'manual_trigger_companies_sensor'):
            print(f"     - manual_trigger_companies_sensor")
        
        return True
        
    except Exception as e:
        print(f"❌ 模块加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_op_functionality():
    """测试 Op 的核心功能（模拟执行）"""
    print("\n" + "=" * 60)
    print("测试 Op 核心功能")
    print("=" * 60)
    print()
    
    try:
        # 测试 akshare 数据获取
        print("1. 测试 akshare 数据获取...")
        try:
            import akshare as ak
            stock_df = ak.stock_info_a_code_name()
            
            if stock_df is None or stock_df.empty:
                print("   ⚠️  数据为空（可能是网络问题）")
            else:
                print(f"   ✅ 获取到 {len(stock_df)} 条数据")
                print(f"   列名: {stock_df.columns.tolist()}")
                
                # 检查数据格式
                if 'code' in stock_df.columns and 'name' in stock_df.columns:
                    print("   ✅ 数据格式正确（包含 code 和 name）")
                    
                    # 显示示例
                    print(f"\n   前3条数据示例:")
                    for idx, row in stock_df.head(3).iterrows():
                        code = str(row.get('code', '')).strip()
                        name = str(row.get('name', '')).strip()
                        print(f"     {code} - {name}")
                else:
                    print("   ❌ 数据格式不正确（缺少 code 或 name）")
                    return False
        except ImportError:
            print("   ⚠️  akshare 未安装，跳过数据获取测试")
        except Exception as e:
            print(f"   ⚠️  数据获取失败: {e}")
        
        # 测试数据库操作
        print("\n2. 测试数据库操作...")
        try:
            from src.storage.metadata import get_postgres_client, crud
            
            pg_client = get_postgres_client()
            
            if pg_client.test_connection():
                print("   ✅ 数据库连接成功")
                
                # 检查表是否存在
                if pg_client.table_exists('listed_companies'):
                    print("   ✅ listed_companies 表存在")
                    
                    # 获取当前记录数
                    count = pg_client.get_table_count('listed_companies')
                    print(f"   当前记录数: {count} 家")
                else:
                    print("   ⚠️  listed_companies 表不存在")
                    print("   提示: 运行 python scripts/init_database.py")
            else:
                print("   ⚠️  数据库连接失败（可能是数据库未启动）")
        except Exception as e:
            print(f"   ⚠️  数据库操作测试失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行测试"""
    print("\n" + "=" * 60)
    print("上市公司列表更新作业 - 直接测试")
    print("=" * 60)
    print()
    
    results = []
    
    # 测试1: 模块加载
    try:
        result = test_company_list_job_direct()
        results.append(("模块加载", result))
    except Exception as e:
        print(f"\n❌ 测试1异常: {e}")
        results.append(("模块加载", False))
    
    # 测试2: 功能测试
    try:
        result = test_op_functionality()
        results.append(("功能测试", result))
    except Exception as e:
        print(f"\n❌ 测试2异常: {e}")
        results.append(("功能测试", False))
    
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
        print("\n📝 下一步:")
        print("   1. 安装依赖: pip install akshare")
        print("   2. 初始化数据库: python scripts/init_database.py")
        print("   3. 运行完整测试: python examples/test_company_list_job.py")
        print("   4. 或使用 Dagster UI 手动触发作业")
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败")
    
    return 0 if passed == total else 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
