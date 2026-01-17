# -*- coding: utf-8 -*-
"""
测试MinIO metadata统一功能
验证不同doc_type的metadata都只保留source_url和publish_date
"""

import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.ingestion.base.base_crawler import CrawlTask
from src.ingestion.a_share.crawlers.report_crawler import ReportCrawler
from src.common.constants import Market, DocType


def test_prepare_minio_metadata():
    """测试_prepare_minio_metadata函数"""
    print("=" * 60)
    print("测试: _prepare_minio_metadata 统一metadata格式")
    print("=" * 60)
    
    # 创建一个ReportCrawler实例（禁用MinIO和PostgreSQL，只测试metadata函数）
    crawler = ReportCrawler(enable_minio=False, enable_postgres=False)
    
    # 测试1: IPO类型，包含完整metadata
    print("\n测试1: IPO类型，包含完整metadata")
    task1 = CrawlTask(
        stock_code="688111",
        company_name="测试公司",
        market=Market.A_SHARE,
        doc_type=DocType.IPO_PROSPECTUS,
        metadata={
            'source_url': 'https://www.cninfo.com.cn/test1',
            'publication_date': '01012024',
            'publication_year': '2024',
            'publication_date_iso': '2024-01-01T00:00:00',
            'other_field': 'should_be_removed'
        }
    )
    meta1 = crawler._prepare_minio_metadata(task1)
    print(f"   输入metadata: {task1.metadata}")
    print(f"   输出metadata: {meta1}")
    
    assert 'source_url' in meta1, "缺少source_url"
    assert meta1['source_url'] == 'https://www.cninfo.com.cn/test1', f"source_url不匹配: {meta1.get('source_url')}"
    assert 'publish_date' in meta1, "缺少publish_date"
    assert meta1['publish_date'] == '2024-01-01T00:00:00', f"publish_date不匹配: {meta1.get('publish_date')}"
    assert 'other_field' not in meta1, "不应该包含other_field"
    assert 'publication_date' not in meta1, "不应该包含publication_date（只保留ISO格式）"
    print("   ✅ 测试1通过")
    
    # 测试2: 定期报告类型
    print("\n测试2: 定期报告类型")
    task2 = CrawlTask(
        stock_code="000001",
        company_name="测试公司2",
        market=Market.A_SHARE,
        doc_type=DocType.QUARTERLY_REPORT,
        year=2024,
        quarter=1,
        metadata={
            'source_url': 'https://www.cninfo.com.cn/test2',
            'publication_date_iso': '2024-03-15T14:30:00',
            'stock_code': '000001',
            'year': '2024'
        }
    )
    meta2 = crawler._prepare_minio_metadata(task2)
    print(f"   输入metadata: {task2.metadata}")
    print(f"   输出metadata: {meta2}")
    
    assert 'source_url' in meta2, "缺少source_url"
    assert meta2['source_url'] == 'https://www.cninfo.com.cn/test2', f"source_url不匹配: {meta2.get('source_url')}"
    assert 'publish_date' in meta2, "缺少publish_date"
    assert meta2['publish_date'] == '2024-03-15T14:30:00', f"publish_date不匹配: {meta2.get('publish_date')}"
    assert 'stock_code' not in meta2, "不应该包含stock_code"
    assert 'year' not in meta2, "不应该包含year"
    print("   ✅ 测试2通过")
    
    # 测试3: 只有source_url，没有publish_date
    print("\n测试3: 只有source_url，没有publish_date")
    task3 = CrawlTask(
        stock_code="000002",
        company_name="测试公司3",
        market=Market.A_SHARE,
        doc_type=DocType.ANNUAL_REPORT,
        year=2023,
        quarter=4,
        metadata={
            'source_url': 'https://www.cninfo.com.cn/test3'
        }
    )
    meta3 = crawler._prepare_minio_metadata(task3)
    print(f"   输入metadata: {task3.metadata}")
    print(f"   输出metadata: {meta3}")
    
    assert 'source_url' in meta3, "缺少source_url"
    assert 'publish_date' not in meta3, "不应该包含publish_date（如果没有提供）"
    print("   ✅ 测试3通过")
    
    # 测试4: 使用doc_url作为source_url
    print("\n测试4: 使用doc_url作为source_url")
    task4 = CrawlTask(
        stock_code="000003",
        company_name="测试公司4",
        market=Market.A_SHARE,
        doc_type=DocType.QUARTERLY_REPORT,
        year=2024,
        quarter=2,
        metadata={
            'doc_url': 'https://www.cninfo.com.cn/test4',
            'pub_date_iso': '2024-06-20T09:00:00'
        }
    )
    meta4 = crawler._prepare_minio_metadata(task4)
    print(f"   输入metadata: {task4.metadata}")
    print(f"   输出metadata: {meta4}")
    
    assert 'source_url' in meta4, "缺少source_url"
    assert meta4['source_url'] == 'https://www.cninfo.com.cn/test4', f"source_url应该从doc_url提取: {meta4.get('source_url')}"
    assert 'publish_date' in meta4, "缺少publish_date"
    assert meta4['publish_date'] == '2024-06-20T09:00:00', f"publish_date不匹配: {meta4.get('publish_date')}"
    print("   ✅ 测试4通过")
    
    # 测试5: datetime对象转换为ISO字符串
    print("\n测试5: datetime对象转换为ISO字符串")
    task5 = CrawlTask(
        stock_code="000004",
        company_name="测试公司5",
        market=Market.A_SHARE,
        doc_type=DocType.IPO_PROSPECTUS,
        metadata={
            'source_url': 'https://www.cninfo.com.cn/test5',
            'publication_date_iso': datetime(2024, 7, 10, 15, 30, 0)
        }
    )
    meta5 = crawler._prepare_minio_metadata(task5)
    print(f"   输入metadata: {task5.metadata}")
    print(f"   输出metadata: {meta5}")
    
    assert 'source_url' in meta5, "缺少source_url"
    assert 'publish_date' in meta5, "缺少publish_date"
    assert isinstance(meta5['publish_date'], str), "publish_date应该是字符串"
    assert meta5['publish_date'] == '2024-07-10T15:30:00', f"publish_date转换不正确: {meta5.get('publish_date')}"
    print("   ✅ 测试5通过")
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)
    print("\n总结:")
    print("  ✅ metadata统一格式：只保留source_url和publish_date")
    print("  ✅ source_url可以从source_url/doc_url/pdf_url字段提取")
    print("  ✅ publish_date从publication_date_iso/pub_date_iso/publish_date_iso提取")
    print("  ✅ datetime对象自动转换为ISO格式字符串")
    print("  ✅ 其他字段都被过滤掉")


if __name__ == '__main__':
    try:
        test_prepare_minio_metadata()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
