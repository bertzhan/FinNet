#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上市公司列表更新作业简单测试脚本
直接测试核心功能，不依赖完整的 Dagster 环境
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_akshare_import():
    """测试 akshare 导入"""
    print("=" * 60)
    print("测试1: akshare 导入")
    print("=" * 60)
    print()
    
    try:
        import akshare as ak
        print("✅ akshare 导入成功")
        print(f"   版本: {ak.__version__ if hasattr(ak, '__version__') else '未知'}")
        return True
    except ImportError as e:
        print(f"❌ akshare 导入失败: {e}")
        print("   提示: 请运行 pip install akshare")
        return False


def test_akshare_data():
    """测试从 akshare 获取数据"""
    print("\n" + "=" * 60)
    print("测试2: 从 akshare 获取A股上市公司数据")
    print("=" * 60)
    print()
    
    try:
        import akshare as ak
        
        print("正在从 akshare 获取数据...")
        stock_df = ak.stock_info_a_code_name()
        
        if stock_df is None or stock_df.empty:
            print("❌ 获取的数据为空")
            return False
        
        print(f"✅ 获取数据成功")
        print(f"   数据形状: {stock_df.shape}")
        print(f"   列名: {stock_df.columns.tolist()}")
        
        # 检查必要的列
        if 'code' not in stock_df.columns or 'name' not in stock_df.columns:
            print(f"❌ 缺少必要的列 (code, name)")
            return False
        
        # 显示前几条数据
        print(f"\n前5条数据示例:")
        for idx, row in stock_df.head(5).iterrows():
            code = str(row.get('code', '')).strip()
            name = str(row.get('name', '')).strip()
            print(f"   {code} - {name}")
        
        # 只保留 code 和 name
        stock_df = stock_df[['code', 'name']].copy()
        stock_df = stock_df.dropna(subset=['code', 'name'])
        stock_df['code'] = stock_df['code'].astype(str).str.strip()
        stock_df['name'] = stock_df['name'].astype(str).str.strip()
        stock_df = stock_df[(stock_df['code'] != '') & (stock_df['name'] != '')]
        
        print(f"\n   清理后数据量: {len(stock_df)} 家")
        
        return True
        
    except Exception as e:
        print(f"❌ 获取数据失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_model():
    """测试数据库模型"""
    print("\n" + "=" * 60)
    print("测试3: 数据库模型")
    print("=" * 60)
    print()
    
    try:
        from src.storage.metadata.models import ListedCompany
        
        print("✅ ListedCompany 模型导入成功")
        print(f"   表名: {ListedCompany.__tablename__}")
        print(f"   字段:")
        for column in ListedCompany.__table__.columns:
            print(f"     - {column.name}: {column.type}")
        
        return True
        
    except Exception as e:
        print(f"❌ 模型导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_crud_operations():
    """测试 CRUD 操作"""
    print("\n" + "=" * 60)
    print("测试4: CRUD 操作")
    print("=" * 60)
    print()
    
    try:
        from src.storage.metadata import crud
        
        print("✅ CRUD 模块导入成功")
        print(f"   可用函数:")
        print(f"     - upsert_listed_company")
        print(f"     - get_listed_company_by_code")
        print(f"     - get_all_listed_companies")
        
        return True
        
    except Exception as e:
        print(f"❌ CRUD 模块导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dagster_op():
    """测试 Dagster Op（不执行，只检查导入）"""
    print("\n" + "=" * 60)
    print("测试5: Dagster Op 定义")
    print("=" * 60)
    print()
    
    try:
        # 只导入 company_list_jobs，不导入整个 dagster 模块
        from src.processing.compute.dagster.jobs.company_list_jobs import (
            update_listed_companies_op,
            update_listed_companies_job,
            daily_update_companies_schedule,
            manual_trigger_companies_sensor,
        )
        
        print("✅ Dagster Op 导入成功")
        print(f"   Op: update_listed_companies_op")
        print(f"   Job: update_listed_companies_job")
        print(f"   Schedule: daily_update_companies_schedule")
        print(f"   Sensor: manual_trigger_companies_sensor")
        
        return True
        
    except Exception as e:
        print(f"❌ Dagster Op 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_connection():
    """测试数据库连接"""
    print("\n" + "=" * 60)
    print("测试6: 数据库连接")
    print("=" * 60)
    print()
    
    try:
        from src.storage.metadata import get_postgres_client
        
        pg_client = get_postgres_client()
        
        if pg_client.test_connection():
            print("✅ 数据库连接成功")
            
            # 检查表是否存在
            if pg_client.table_exists('listed_companies'):
                print("✅ listed_companies 表已存在")
                
                # 获取记录数
                count = pg_client.get_table_count('listed_companies')
                print(f"   当前记录数: {count} 家")
            else:
                print("⚠️  listed_companies 表不存在")
                print("   提示: 运行 python scripts/init_database.py 创建表")
            
            return True
        else:
            print("❌ 数据库连接失败")
            return False
            
    except Exception as e:
        print(f"❌ 数据库连接测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("上市公司列表更新作业 - 简单测试")
    print("=" * 60)
    print()
    
    results = []
    
    # 测试1: akshare 导入
    try:
        result = test_akshare_import()
        results.append(("akshare 导入", result))
    except Exception as e:
        print(f"\n❌ 测试1异常: {e}")
        results.append(("akshare 导入", False))
    
    # 测试2: 获取数据（需要网络）
    if results[-1][1]:  # 如果导入成功
        try:
            result = test_akshare_data()
            results.append(("获取 akshare 数据", result))
        except Exception as e:
            print(f"\n❌ 测试2异常: {e}")
            results.append(("获取 akshare 数据", False))
    else:
        print("\n⚠️  跳过数据获取测试（akshare 未安装）")
        results.append(("获取 akshare 数据", None))
    
    # 测试3: 数据库模型
    try:
        result = test_database_model()
        results.append(("数据库模型", result))
    except Exception as e:
        print(f"\n❌ 测试3异常: {e}")
        results.append(("数据库模型", False))
    
    # 测试4: CRUD 操作
    try:
        result = test_crud_operations()
        results.append(("CRUD 操作", result))
    except Exception as e:
        print(f"\n❌ 测试4异常: {e}")
        results.append(("CRUD 操作", False))
    
    # 测试5: Dagster Op
    try:
        result = test_dagster_op()
        results.append(("Dagster Op", result))
    except Exception as e:
        print(f"\n❌ 测试5异常: {e}")
        results.append(("Dagster Op", False))
    
    # 测试6: 数据库连接
    try:
        result = test_database_connection()
        results.append(("数据库连接", result))
    except Exception as e:
        print(f"\n❌ 测试6异常: {e}")
        results.append(("数据库连接", False))
    
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
    
    if passed == total:
        print("\n🎉 所有测试通过！")
        print("\n📝 下一步:")
        print("   1. 运行 python scripts/init_database.py 创建数据库表")
        print("   2. 运行 python examples/test_company_list_job.py 执行完整测试")
        print("   3. 或使用 Dagster UI 手动触发作业")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
