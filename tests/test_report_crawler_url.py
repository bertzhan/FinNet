# -*- coding: utf-8 -*-
"""
测试 report_crawler 的 URL 保存功能
验证定期报告爬虫是否正确保存URL到数据库
"""

import sys
import os
import tempfile
import json
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.ingestion.a_share.crawlers.base_cninfo_crawler import CninfoBaseCrawler
from src.ingestion.base.base_crawler import CrawlTask
from src.common.constants import Market, DocType
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud


def test_process_downloaded_file_with_metadata():
    """测试 _process_downloaded_file 方法读取 metadata 文件中的 URL"""
    print("=" * 60)
    print("测试: _process_downloaded_file 读取 metadata 文件中的 URL")
    print("=" * 60)
    
    # 创建临时目录和文件
    temp_dir = tempfile.mkdtemp(prefix='test_report_url_')
    test_pdf_path = os.path.join(temp_dir, "000001_2024_Q1.pdf")
    
    # 创建测试PDF文件（空文件即可）
    with open(test_pdf_path, 'wb') as f:
        f.write(b'%PDF-1.4\n')  # 最小PDF文件头
    
    # 创建 metadata 文件
    metadata_file = test_pdf_path.replace('.pdf', '.meta.json')
    test_url = "https://www.cninfo.com.cn/new/disclosure/detail?plate=&orgId=9900001234&stockCode=000001&announcementId=123456789"
    metadata_info = {
        'source_url': test_url
    }
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata_info, f, ensure_ascii=False)
    
    print(f"✅ 创建测试文件:")
    print(f"   PDF文件: {test_pdf_path}")
    print(f"   Metadata文件: {metadata_file}")
    print(f"   URL: {test_url}")
    
    # 使用 ReportCrawler（禁用MinIO和PostgreSQL，只测试metadata读取）
    from src.ingestion.a_share.crawlers.report_crawler import ReportCrawler
    crawler = ReportCrawler(
        enable_minio=False,
        enable_postgres=False
    )
    
    # 创建任务
    task = CrawlTask(
        stock_code="000001",
        company_name="测试公司",
        market=Market.A_SHARE,
        doc_type=DocType.QUARTERLY_REPORT,
        year=2024,
        quarter=1
    )
    
    print(f"\n✅ 创建任务:")
    print(f"   stock_code: {task.stock_code}")
    print(f"   year: {task.year}, quarter: {task.quarter}")
    print(f"   初始metadata: {task.metadata}")
    
    # 调用 _process_downloaded_file（会读取metadata文件）
    # 注意：由于禁用了PostgreSQL，这里会跳过数据库操作
    try:
        result = crawler._process_downloaded_file(
            file_path=test_pdf_path,
            task=task,
            extract_year_from_filename=False
        )
        
        print(f"\n✅ _process_downloaded_file 执行成功")
        print(f"   任务metadata中的source_url: {task.metadata.get('source_url', 'N/A')}")
        
        # 验证URL是否正确添加到task.metadata
        if task.metadata.get('source_url') == test_url:
            print(f"✅ URL已正确添加到task.metadata")
            return True
        else:
            print(f"❌ URL未正确添加到task.metadata")
            print(f"   期望: {test_url}")
            print(f"   实际: {task.metadata.get('source_url', 'N/A')}")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理临时文件
        try:
            os.remove(test_pdf_path)
            os.remove(metadata_file)
            os.rmdir(temp_dir)
        except:
            pass


def test_create_document_with_metadata_url():
    """测试通过metadata创建文档记录时URL是否正确保存"""
    print("\n" + "=" * 60)
    print("测试: 通过metadata创建文档记录时URL是否正确保存")
    print("=" * 60)
    
    pg_client = get_postgres_client()
    test_url = "https://www.cninfo.com.cn/new/disclosure/detail?plate=&orgId=9900001234&stockCode=000002&announcementId=987654321"
    
    with pg_client.get_session() as session:
        # 创建测试文档记录，URL在metadata中（模拟report_crawler的行为）
        metadata = {
            'source_url': test_url,
            'other_field': 'test_value'
        }
        
        doc = crud.create_document(
            session=session,
            stock_code="TEST_REPORT",
            company_name="测试报告公司",
            market=Market.A_SHARE.value,
            doc_type=DocType.QUARTERLY_REPORT.value,
            year=2024,
            quarter=1,
            minio_object_path="bronze/a_share/quarterly_reports/2024/Q1/TEST_REPORT/test.pdf",
            file_size=1024000,
            file_hash="test_hash_report",
            metadata=metadata
        )
        session.commit()
        
        print(f"✅ 创建文档记录成功: id={doc.id}")
        print(f"   source_url: {doc.source_url}")
        print(f"   metadata中的source_url: {metadata.get('source_url')}")
        
        # 验证URL是否正确从metadata中提取
        if doc.source_url == test_url:
            print(f"✅ URL从metadata中提取并保存成功")
            
            # 清理测试数据
            session.delete(doc)
            session.commit()
            print(f"✅ 测试数据已清理")
            return True
        else:
            print(f"❌ URL提取失败")
            print(f"   期望: {test_url}")
            print(f"   实际: {doc.source_url}")
            
            # 清理测试数据
            session.delete(doc)
            session.commit()
            return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("开始测试 report_crawler 的 URL 保存功能")
    print("=" * 60)
    
    try:
        test1_result = test_process_downloaded_file_with_metadata()
        test2_result = test_create_document_with_metadata_url()
        
        print("\n" + "=" * 60)
        if test1_result and test2_result:
            print("✅ 所有测试通过！")
        else:
            print("❌ 部分测试失败")
        print("=" * 60)
        
        return test1_result and test2_result
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ 测试失败: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
