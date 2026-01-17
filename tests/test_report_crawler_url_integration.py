# -*- coding: utf-8 -*-
"""
集成测试：验证 report_crawler 完整流程中 URL 的保存
测试从下载到数据库保存的完整流程
"""

import sys
import os
import tempfile
import json
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.ingestion.a_share.crawlers.report_crawler import ReportCrawler
from src.ingestion.base.base_crawler import CrawlTask
from src.common.constants import Market, DocType
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.storage.metadata.models import Document


def test_report_crawler_url_save_integration():
    """集成测试：模拟完整的爬取流程，验证URL保存"""
    print("=" * 60)
    print("集成测试: report_crawler URL 保存完整流程")
    print("=" * 60)
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix='test_report_integration_')
    
    try:
        # 1. 创建测试PDF文件和metadata文件（模拟processor的输出）
        test_pdf_path = os.path.join(temp_dir, "bronze", "a_share", "quarterly_reports", "2024", "Q1", "TEST999", "TEST999_2024_Q1.pdf")
        os.makedirs(os.path.dirname(test_pdf_path), exist_ok=True)
        
        # 创建最小PDF文件
        with open(test_pdf_path, 'wb') as f:
            f.write(b'%PDF-1.4\n')
        
        # 创建metadata文件（模拟report_processor的输出）
        metadata_file = test_pdf_path.replace('.pdf', '.meta.json')
        test_url = "https://www.cninfo.com.cn/new/disclosure/detail?plate=&orgId=9900001234&stockCode=TEST999&announcementId=999888777"
        metadata_info = {
            'source_url': test_url
        }
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata_info, f, ensure_ascii=False)
        
        print(f"✅ 创建测试文件:")
        print(f"   PDF: {test_pdf_path}")
        print(f"   Metadata: {metadata_file}")
        print(f"   URL: {test_url}")
        
        # 2. 创建爬虫实例（启用PostgreSQL，禁用MinIO以避免实际上传）
        crawler = ReportCrawler(
            enable_minio=False,  # 禁用MinIO，避免实际上传
            enable_postgres=True  # 启用PostgreSQL，测试数据库保存
        )
        
        # 3. 创建任务
        task = CrawlTask(
            stock_code="TEST999",
            company_name="测试集成公司",
            market=Market.A_SHARE,
            doc_type=DocType.QUARTERLY_REPORT,
            year=2024,
            quarter=1
        )
        
        print(f"\n✅ 创建爬虫任务:")
        print(f"   stock_code: {task.stock_code}")
        print(f"   year: {task.year}, quarter: {task.quarter}")
        
        # 4. 调用 _process_downloaded_file（模拟完整流程）
        print(f"\n开始处理文件...")
        result = crawler._process_downloaded_file(
            file_path=test_pdf_path,
            task=task,
            extract_year_from_filename=False
        )
        
        print(f"✅ 文件处理完成")
        print(f"   成功: {result.success}")
        print(f"   文档ID: {result.document_id}")
        print(f"   task.metadata中的source_url: {task.metadata.get('source_url', 'N/A')}")
        
        # 5. 验证数据库中的URL
        if result.document_id:
            pg_client = get_postgres_client()
            with pg_client.get_session() as session:
                doc = crud.get_document_by_id(session, result.document_id)
                if doc:
                    print(f"\n✅ 从数据库查询文档:")
                    print(f"   document_id: {doc.id}")
                    print(f"   stock_code: {doc.stock_code}")
                    print(f"   source_url: {doc.source_url}")
                    
                    # 验证URL是否正确保存
                    if doc.source_url == test_url:
                        print(f"✅ URL验证通过！")
                        
                        # 清理测试数据
                        session.delete(doc)
                        session.commit()
                        print(f"✅ 测试数据已清理")
                        return True
                    else:
                        print(f"❌ URL不匹配:")
                        print(f"   期望: {test_url}")
                        print(f"   实际: {doc.source_url}")
                        
                        # 清理测试数据
                        session.delete(doc)
                        session.commit()
                        return False
                else:
                    print(f"❌ 未找到文档记录: id={result.document_id}")
                    return False
        else:
            print(f"❌ 未创建文档记录")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理临时文件
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except:
            pass


def test_query_documents_by_url():
    """测试：查询包含特定URL的文档"""
    print("\n" + "=" * 60)
    print("测试: 查询包含特定URL的文档")
    print("=" * 60)
    
    pg_client = get_postgres_client()
    
    with pg_client.get_session() as session:
        # 创建测试文档
        test_url = "https://www.cninfo.com.cn/new/disclosure/detail?plate=&orgId=9900001234&stockCode=QUERY_TEST&announcementId=111222333"
        
        doc = crud.create_document(
            session=session,
            stock_code="QUERY_TEST",
            company_name="查询测试公司",
            market=Market.A_SHARE.value,
            doc_type=DocType.QUARTERLY_REPORT.value,
            year=2024,
            quarter=2,
            minio_object_path="bronze/a_share/quarterly_reports/2024/Q2/QUERY_TEST/test.pdf",
            file_size=2048000,
            file_hash="test_hash_query",
            source_url=test_url
        )
        session.commit()
        
        doc_id = doc.id
        print(f"✅ 创建测试文档: id={doc_id}, source_url={doc.source_url}")
        
        # 通过URL查询文档
        docs = session.query(Document).filter(Document.source_url == test_url).all()
        
        if len(docs) > 0:
            print(f"✅ 通过URL查询成功: 找到 {len(docs)} 条记录")
            for d in docs:
                print(f"   - document_id={d.id}, stock_code={d.stock_code}, source_url={d.source_url}")
            
            # 清理测试数据
            session.delete(doc)
            session.commit()
            print(f"✅ 测试数据已清理")
            return True
        else:
            print(f"❌ 通过URL查询失败: 未找到记录")
            
            # 清理测试数据
            session.delete(doc)
            session.commit()
            return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("开始集成测试 report_crawler URL 保存功能")
    print("=" * 60)
    
    try:
        test1_result = test_report_crawler_url_save_integration()
        test2_result = test_query_documents_by_url()
        
        print("\n" + "=" * 60)
        if test1_result and test2_result:
            print("✅ 所有集成测试通过！")
            print("\n总结:")
            print("  ✅ report_crawler 能正确读取 metadata 文件中的 URL")
            print("  ✅ URL 能正确保存到数据库的 source_url 字段")
            print("  ✅ 可以通过 URL 查询文档")
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
