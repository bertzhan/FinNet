#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dagster 爬虫集成测试脚本
用于快速测试 Dagster Jobs 是否正常工作
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dagster import execute_job, RunConfig
from src.processing.compute.dagster.jobs import (
    crawl_a_share_reports_job,
    crawl_a_share_ipo_job,
)


def test_reports_job():
    """测试定期报告爬取Job"""
    print("=" * 60)
    print("测试: crawl_a_share_reports_job")
    print("=" * 60)
    
    # 配置：只爬取少量公司进行测试
    config = RunConfig(
        ops={
            "crawl_a_share_reports_op": {
                "config": {
                    "company_list_path": str(project_root / "src" / "crawler" / "zh" / "company_list.csv"),
                    "output_root": str(project_root / "downloads" / "test"),
                    "workers": 2,  # 测试时使用少量worker
                    "doc_type": "quarterly_report",
                    "year": 2023,
                    "quarter": 3,
                    "enable_minio": True,
                    "enable_postgres": True,
                }
            }
        }
    )
    
    try:
        result = execute_job(crawl_a_share_reports_job, run_config=config)
        print(f"\n✅ Job 执行完成")
        print(f"   成功: {result.success}")
        if result.success:
            print(f"   运行ID: {result.run_id}")
        else:
            print(f"   错误: {result.failure}")
        return result.success
    except Exception as e:
        print(f"\n❌ Job 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ipo_job():
    """测试IPO爬取Job"""
    print("\n" + "=" * 60)
    print("测试: crawl_a_share_ipo_job")
    print("=" * 60)
    
    config = RunConfig(
        ops={
            "crawl_a_share_ipo_op": {
                "config": {
                    "company_list_path": str(project_root / "src" / "crawler" / "zh" / "company_list.csv"),
                    "output_root": str(project_root / "downloads" / "test_ipo"),
                    "workers": 2,
                    "enable_minio": True,
                    "enable_postgres": True,
                }
            }
        }
    )
    
    try:
        result = execute_job(crawl_a_share_ipo_job, run_config=config)
        print(f"\n✅ Job 执行完成")
        print(f"   成功: {result.success}")
        if result.success:
            print(f"   运行ID: {result.run_id}")
        else:
            print(f"   错误: {result.failure}")
        return result.success
    except Exception as e:
        print(f"\n❌ Job 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("Dagster 爬虫集成测试")
    print(f"项目根目录: {project_root}")
    print()
    
    # 检查环境变量
    print("检查环境变量...")
    minio_enabled = os.getenv("MINIO_ENDPOINT") is not None
    postgres_enabled = os.getenv("POSTGRES_HOST") is not None
    
    print(f"  MinIO: {'✅ 已配置' if minio_enabled else '⚠️  未配置'}")
    print(f"  PostgreSQL: {'✅ 已配置' if postgres_enabled else '⚠️  未配置'}")
    print()
    
    # 运行测试
    print("开始测试...")
    print()
    
    # 测试报告爬取（注释掉，避免实际爬取）
    # success1 = test_reports_job()
    
    # 测试IPO爬取（注释掉，避免实际爬取）
    # success2 = test_ipo_job()
    
    print("\n" + "=" * 60)
    print("提示：")
    print("1. 取消注释上面的测试函数来实际运行爬取")
    print("2. 或使用 Dagster UI 来手动触发任务")
    print("3. 启动 UI: bash scripts/start_dagster.sh")
    print("=" * 60)
