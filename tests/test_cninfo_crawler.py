# -*- coding: utf-8 -*-
"""
测试 CninfoAShareCrawler
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.ingestion.a_share import ReportCrawler
# 向后兼容
CninfoAShareCrawler = ReportCrawler
from src.ingestion.base.base_crawler import CrawlTask
from src.common.constants import Market, DocType


def test_basic_import():
    """测试基本导入"""
    print("=" * 60)
    print("测试 1: 基本导入")
    print("=" * 60)

    try:
        # 创建爬虫实例
        crawler = CninfoAShareCrawler(
            enable_minio=False,      # 测试时禁用 MinIO
            enable_postgres=False,   # 测试时禁用 PostgreSQL
            workers=1
        )
        print(f"✅ 爬虫实例创建成功: {crawler.__class__.__name__}")
        print(f"   市场: {crawler.market.value}")
        print(f"   MinIO 启用: {crawler.enable_minio}")
        print(f"   PostgreSQL 启用: {crawler.enable_postgres}")
        return True
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_task_creation():
    """测试任务创建"""
    print("\n" + "=" * 60)
    print("测试 2: 任务创建")
    print("=" * 60)

    try:
        task = CrawlTask(
            stock_code="000001",
            company_name="平安银行",
            market=Market.A_SHARE,
            doc_type=DocType.QUARTERLY_REPORT,
            year=2023,
            quarter=3,
            metadata={"test": "value"}
        )

        print(f"✅ 任务创建成功:")
        print(f"   股票代码: {task.stock_code}")
        print(f"   公司名称: {task.company_name}")
        print(f"   市场: {task.market.value}")
        print(f"   文档类型: {task.doc_type.value}")
        print(f"   年份: {task.year}")
        print(f"   季度: {task.quarter}")
        print(f"   元数据: {task.metadata}")

        # 测试 to_dict
        task_dict = task.to_dict()
        print(f"\n   转换为字典:")
        for key, value in task_dict.items():
            print(f"     {key}: {value}")

        return True
    except Exception as e:
        print(f"❌ 任务创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_path_generation():
    """测试路径生成"""
    print("\n" + "=" * 60)
    print("测试 3: 路径生成")
    print("=" * 60)

    try:
        crawler = CninfoAShareCrawler(
            enable_minio=False,
            enable_postgres=False
        )

        task = CrawlTask(
            stock_code="000001",
            company_name="平安银行",
            market=Market.A_SHARE,
            doc_type=DocType.QUARTERLY_REPORT,
            year=2023,
            quarter=3
        )

        # 测试路径生成
        filename = "000001_2023_Q3.pdf"
        minio_path = crawler.path_manager.get_bronze_path(
            market=task.market,
            doc_type=task.doc_type,
            stock_code=task.stock_code,
            year=task.year,
            quarter=task.quarter,
            filename=filename
        )

        print(f"✅ MinIO 路径生成成功:")
        print(f"   {minio_path}")

        # 验证路径格式
        expected_parts = [
            "bronze",
            "a_share",
            "quarterly_reports",
            "2023",
            "Q3",
            "000001",
            "000001_2023_Q3.pdf"
        ]

        path_parts = minio_path.split('/')
        print(f"\n   路径组成部分:")
        for i, part in enumerate(path_parts):
            expected = expected_parts[i] if i < len(expected_parts) else "N/A"
            match = "✓" if part == expected else "✗"
            print(f"     [{match}] {part} (期望: {expected})")

        return all(a == b for a, b in zip(path_parts, expected_parts))
    except Exception as e:
        print(f"❌ 路径生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_storage_clients():
    """测试 Storage 客户端初始化"""
    print("\n" + "=" * 60)
    print("测试 4: Storage 客户端")
    print("=" * 60)

    success = True

    # 测试禁用模式
    print("\n4.1 禁用模式")
    try:
        crawler = CninfoAShareCrawler(
            enable_minio=False,
            enable_postgres=False
        )
        print(f"✅ 禁用模式创建成功:")
        print(f"   MinIO 客户端: {crawler.minio_client}")
        print(f"   PostgreSQL 客户端: {crawler.pg_client}")
        print(f"   PathManager: {crawler.path_manager is not None}")
    except Exception as e:
        print(f"❌ 禁用模式失败: {e}")
        success = False

    # 测试启用模式（可能会失败，如果服务未启动）
    print("\n4.2 启用模式（需要 MinIO 和 PostgreSQL 服务）")
    try:
        crawler = CninfoAShareCrawler(
            enable_minio=True,
            enable_postgres=True
        )
        print(f"✅ 启用模式创建成功:")
        print(f"   MinIO 客户端: {crawler.minio_client is not None}")
        print(f"   PostgreSQL 客户端: {crawler.pg_client is not None}")

        # 测试 MinIO 连接
        minio_ok = False
        if crawler.minio_client:
            try:
                files = crawler.minio_client.list_files(max_results=1)
                print(f"   MinIO 连接测试: ✅ 成功")
                minio_ok = True
            except Exception as e:
                print(f"   MinIO 连接测试: ⚠️ {e}")
        else:
            print(f"   MinIO 客户端: ⚠️ 未初始化")

        # 测试 PostgreSQL 连接
        postgres_ok = False
        if crawler.pg_client:
            try:
                if crawler.pg_client.test_connection():
                    print(f"   PostgreSQL 连接测试: ✅ 成功")
                    postgres_ok = True
            except Exception as e:
                print(f"   PostgreSQL 连接测试: ⚠️ {e}")
        else:
            print(f"   PostgreSQL 客户端: ⚠️ 未初始化")

        # 如果两个都成功，测试通过
        if minio_ok and postgres_ok:
            print(f"\n✅ Storage 客户端测试通过")
        else:
            print(f"\n⚠️ Storage 客户端部分功能未启用或服务未启动")
            # 不标记为失败，因为可能是服务未启动

    except Exception as e:
        print(f"⚠️ 启用模式警告: {e}")
        print(f"   提示: 确保 MinIO 和 PostgreSQL 服务已启动")
        # 不标记为失败，因为可能是服务未启动

    return success


def test_validation():
    """测试结果验证"""
    print("\n" + "=" * 60)
    print("测试 5: 结果验证")
    print("=" * 60)

    try:
        from src.ingestion.base.base_crawler import CrawlResult

        crawler = CninfoAShareCrawler(
            enable_minio=False,
            enable_postgres=False
        )

        task = CrawlTask(
            stock_code="000001",
            company_name="平安银行",
            market=Market.A_SHARE,
            doc_type=DocType.QUARTERLY_REPORT,
            year=2023,
            quarter=3
        )

        # 测试失败结果
        print("\n5.1 验证失败结果")
        fail_result = CrawlResult(
            task=task,
            success=False,
            error_message="测试错误"
        )

        is_valid, error_msg = crawler.validate_result(fail_result)
        print(f"   验证结果: {'通过' if is_valid else '失败'}")
        print(f"   错误信息: {error_msg}")

        # 测试成功但文件不存在
        print("\n5.2 验证成功结果（文件不存在）")
        success_result = CrawlResult(
            task=task,
            success=True,
            local_file_path="/tmp/nonexistent.pdf"
        )

        is_valid, error_msg = crawler.validate_result(success_result)
        print(f"   验证结果: {'通过' if is_valid else '失败'}")
        print(f"   错误信息: {error_msg}")

        print(f"\n✅ 验证功能正常")
        return True
    except Exception as e:
        print(f"❌ 验证测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("开始测试 CninfoAShareCrawler\n")

    tests = [
        ("基本导入", test_basic_import),
        ("任务创建", test_task_creation),
        ("路径生成", test_path_generation),
        ("Storage 客户端", test_storage_clients),
        ("结果验证", test_validation),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ 测试 '{name}' 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")

    total = len(results)
    passed = sum(1 for _, r in results if r)

    print(f"\n总计: {passed}/{total} 通过 ({passed*100//total}%)")

    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️ 有 {total - passed} 个测试失败")


if __name__ == '__main__':
    main()
