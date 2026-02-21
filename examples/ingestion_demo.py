# -*- coding: utf-8 -*-
"""
Ingestion 层使用示例
演示如何使用新的爬虫架构
"""

import sys
import os

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.ingestion import CninfoAShareCrawler, CrawlTask
from src.common.constants import Market, DocType


def demo_single_task():
    """演示单任务爬取"""
    print("=" * 60)
    print("示例 1：单任务爬取")
    print("=" * 60)

    # 创建爬虫实例
    crawler = CninfoAShareCrawler(
        enable_minio=True,      # 启用 MinIO 上传
        enable_postgres=True,   # 启用 PostgreSQL 记录
        workers=1               # 单任务模式
    )

    # 创建爬取任务
    task = CrawlTask(
        stock_code="000001",
        company_name="平安银行",
        market=Market.HS,
        doc_type=DocType.QUARTERLY_REPORT,
        year=2023,
        quarter=3,
        metadata={"source": "demo"}
    )

    # 执行爬取
    print(f"\n正在爬取: {task.company_name} ({task.stock_code}) {task.year} Q{task.quarter}")
    result = crawler.crawl(task)

    # 打印结果
    print("\n" + "=" * 60)
    print("爬取结果")
    print("=" * 60)

    if result.success:
        print(f"✅ 状态: 成功")
        print(f"📄 本地文件: {result.local_file_path}")
        print(f"☁️  MinIO路径: {result.minio_object_name}")
        print(f"🗄️  数据库ID: {result.document_id}")
        print(f"📊 文件大小: {result.file_size:,} bytes ({result.file_size / 1024 / 1024:.2f} MB)")
        print(f"🔒 文件哈希: {result.file_hash[:16]}...")
    else:
        print(f"❌ 状态: 失败")
        print(f"⚠️  错误信息: {result.error_message}")

    # 验证结果
    is_valid, error_msg = crawler.validate_result(result)
    print(f"\n{'✅' if is_valid else '❌'} 验证结果: {'通过' if is_valid else error_msg}")


def demo_batch_tasks():
    """演示批量爬取"""
    print("\n\n" + "=" * 60)
    print("示例 2：批量爬取（多进程）")
    print("=" * 60)

    # 创建爬虫实例（启用多进程）
    crawler = CninfoAShareCrawler(
        enable_minio=True,
        enable_postgres=True,
        workers=4  # 4个并行进程
    )

    # 创建批量任务
    tasks = [
        CrawlTask(
            stock_code="000001",
            company_name="平安银行",
            market=Market.HS,
            doc_type=DocType.QUARTERLY_REPORT,
            year=2023,
            quarter=3
        ),
        CrawlTask(
            stock_code="000002",
            company_name="万科A",
            market=Market.HS,
            doc_type=DocType.QUARTERLY_REPORT,
            year=2023,
            quarter=3
        ),
        CrawlTask(
            stock_code="600519",
            company_name="贵州茅台",
            market=Market.HS,
            doc_type=DocType.QUARTERLY_REPORT,
            year=2023,
            quarter=3
        ),
    ]

    print(f"\n准备爬取 {len(tasks)} 个任务，使用 {crawler.workers} 个并行进程")

    # 执行批量爬取
    results = crawler.crawl_batch(tasks)

    # 统计结果
    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count

    print("\n" + "=" * 60)
    print("批量爬取结果")
    print("=" * 60)
    print(f"✅ 成功: {success_count}/{len(tasks)}")
    print(f"❌ 失败: {fail_count}/{len(tasks)}")

    # 显示详细结果
    print("\n详细结果:")
    for i, result in enumerate(results, 1):
        status = "✅" if result.success else "❌"
        task = result.task
        print(f"\n{i}. {status} {task.company_name} ({task.stock_code}) {task.year} Q{task.quarter}")
        if result.success:
            print(f"   文件: {result.local_file_path}")
            print(f"   MinIO: {result.minio_object_name}")
            print(f"   数据库ID: {result.document_id}")
        else:
            print(f"   错误: {result.error_message}")


def demo_storage_integration():
    """演示 storage 层集成"""
    print("\n\n" + "=" * 60)
    print("示例 3：Storage 层集成检查")
    print("=" * 60)

    from src.storage.object_store.minio_client import MinIOClient
    from src.storage.metadata.postgres_client import get_postgres_client
    from src.storage.metadata import crud

    # 检查 MinIO
    print("\n1️⃣ 检查 MinIO 连接")
    try:
        minio_client = MinIOClient()
        print(f"   ✅ MinIO 连接成功: {minio_client.endpoint}")

        # 列出最近的文件
        files = minio_client.list_files(prefix="bronze/hs_stock/", max_results=5)
        print(f"   📂 最近的文件 (前5个):")
        for file in files[:5]:
            print(f"      - {file['name']} ({file['size']:,} bytes)")
    except Exception as e:
        print(f"   ❌ MinIO 连接失败: {e}")

    # 检查 PostgreSQL
    print("\n2️⃣ 检查 PostgreSQL 连接")
    try:
        pg_client = get_postgres_client()
        if pg_client.test_connection():
            print(f"   ✅ PostgreSQL 连接成功")

            # 获取表统计
            info = pg_client.get_table_info()
            print(f"   📊 数据库统计:")
            for table, count in info.items():
                if count > 0:
                    print(f"      - {table}: {count:,} 条记录")

            # 查询最新的文档
            with pg_client.get_session() as session:
                recent_docs = crud.get_documents_by_status(session, "crawled", limit=5)
                print(f"\n   📄 最新爬取的文档 (前5个):")
                for doc in recent_docs[:5]:
                    print(f"      - {doc.stock_code} {doc.company_name} {doc.year} Q{doc.quarter or 4}")
    except Exception as e:
        print(f"   ❌ PostgreSQL 连接失败: {e}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Ingestion 层使用示例')
    parser.add_argument('--mode', choices=['single', 'batch', 'storage', 'all'], default='all',
                        help='运行模式: single=单任务, batch=批量任务, storage=存储检查, all=所有示例')

    args = parser.parse_args()

    if args.mode in ['single', 'all']:
        demo_single_task()

    if args.mode in ['batch', 'all']:
        demo_batch_tasks()

    if args.mode in ['storage', 'all']:
        demo_storage_integration()

    print("\n\n" + "=" * 60)
    print("示例运行完成！")
    print("=" * 60)
    print("\n提示:")
    print("- 确保已启动 MinIO 和 PostgreSQL 服务")
    print("- 设置环境变量（参考 docs/STORAGE_LAYER_GUIDE.md）")
    print("- 查看日志了解详细执行过程")
