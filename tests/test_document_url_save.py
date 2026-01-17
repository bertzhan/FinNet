# -*- coding: utf-8 -*-
"""
测试文档URL保存功能
验证爬虫时URL是否正确保存到数据库的Document表中
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.common.constants import Market, DocType


def test_create_document_with_url():
    """测试1: 直接传入source_url参数"""
    print("=" * 60)
    print("测试1: 直接传入source_url参数")
    print("=" * 60)
    
    pg_client = get_postgres_client()
    test_url = "https://www.cninfo.com.cn/new/disclosure/detail?plate=&orgId=9900001234&stockCode=000001&announcementId=123456789"
    
    with pg_client.get_session() as session:
        # 创建测试文档记录
        doc = crud.create_document(
            session=session,
            stock_code="TEST001",
            company_name="测试公司",
            market=Market.A_SHARE.value,
            doc_type=DocType.QUARTERLY_REPORT.value,
            year=2024,
            quarter=1,
            minio_object_path="bronze/a_share/quarterly_reports/2024/Q1/TEST001/test.pdf",
            file_size=1024000,
            file_hash="test_hash_12345",
            source_url=test_url
        )
        session.commit()
        
        print(f"✅ 创建文档记录成功: id={doc.id}")
        print(f"   source_url: {doc.source_url}")
        
        # 验证URL是否正确保存
        assert doc.source_url == test_url, f"URL不匹配: 期望={test_url}, 实际={doc.source_url}"
        print(f"✅ URL验证通过")
        
        # 清理测试数据
        session.delete(doc)
        session.commit()
        print(f"✅ 测试数据已清理")


def test_create_document_with_url_in_metadata():
    """测试2: 从metadata中提取URL"""
    print("\n" + "=" * 60)
    print("测试2: 从metadata中提取URL")
    print("=" * 60)
    
    pg_client = get_postgres_client()
    test_url = "https://www.cninfo.com.cn/new/disclosure/detail?plate=&orgId=9900001234&stockCode=000002&announcementId=987654321"
    
    with pg_client.get_session() as session:
        # 创建测试文档记录，URL在metadata中
        metadata = {
            'source_url': test_url,
            'publication_date': '20240101',
            'other_field': 'test_value'
        }
        
        doc = crud.create_document(
            session=session,
            stock_code="TEST002",
            company_name="测试公司2",
            market=Market.A_SHARE.value,
            doc_type=DocType.ANNUAL_REPORT.value,
            year=2023,
            quarter=4,
            minio_object_path="bronze/a_share/annual_reports/2023/TEST002/test.pdf",
            file_size=2048000,
            file_hash="test_hash_67890",
            metadata=metadata
        )
        session.commit()
        
        print(f"✅ 创建文档记录成功: id={doc.id}")
        print(f"   source_url: {doc.source_url}")
        print(f"   metadata中的source_url: {metadata.get('source_url')}")
        
        # 验证URL是否正确从metadata中提取
        assert doc.source_url == test_url, f"URL不匹配: 期望={test_url}, 实际={doc.source_url}"
        print(f"✅ URL从metadata中提取成功")
        
        # 清理测试数据
        session.delete(doc)
        session.commit()
        print(f"✅ 测试数据已清理")


def test_create_document_with_doc_url_in_metadata():
    """测试3: 从metadata中的doc_url字段提取URL"""
    print("\n" + "=" * 60)
    print("测试3: 从metadata中的doc_url字段提取URL")
    print("=" * 60)
    
    pg_client = get_postgres_client()
    test_url = "https://www.cninfo.com.cn/new/disclosure/detail?plate=&orgId=9900001234&stockCode=000003&announcementId=111222333"
    
    with pg_client.get_session() as session:
        # 创建测试文档记录，URL在metadata的doc_url字段中
        metadata = {
            'doc_url': test_url,  # 使用doc_url而不是source_url
            'publication_date': '20240201'
        }
        
        doc = crud.create_document(
            session=session,
            stock_code="TEST003",
            company_name="测试公司3",
            market=Market.A_SHARE.value,
            doc_type=DocType.IPO_PROSPECTUS.value,
            year=2024,
            quarter=None,
            minio_object_path="bronze/a_share/ipo_prospectus/TEST003/test.pdf",
            file_size=3072000,
            file_hash="test_hash_abcde",
            metadata=metadata
        )
        session.commit()
        
        print(f"✅ 创建文档记录成功: id={doc.id}")
        print(f"   source_url: {doc.source_url}")
        print(f"   metadata中的doc_url: {metadata.get('doc_url')}")
        
        # 验证URL是否正确从metadata的doc_url中提取
        assert doc.source_url == test_url, f"URL不匹配: 期望={test_url}, 实际={doc.source_url}"
        print(f"✅ URL从metadata的doc_url字段中提取成功")
        
        # 清理测试数据
        session.delete(doc)
        session.commit()
        print(f"✅ 测试数据已清理")


def test_query_document_by_url():
    """测试4: 查询包含URL的文档"""
    print("\n" + "=" * 60)
    print("测试4: 查询包含URL的文档")
    print("=" * 60)
    
    pg_client = get_postgres_client()
    test_url = "https://www.cninfo.com.cn/new/disclosure/detail?plate=&orgId=9900001234&stockCode=000004&announcementId=444555666"
    
    with pg_client.get_session() as session:
        # 创建测试文档记录
        doc = crud.create_document(
            session=session,
            stock_code="TEST004",
            company_name="测试公司4",
            market=Market.A_SHARE.value,
            doc_type=DocType.QUARTERLY_REPORT.value,
            year=2024,
            quarter=2,
            minio_object_path="bronze/a_share/quarterly_reports/2024/Q2/TEST004/test.pdf",
            file_size=4096000,
            file_hash="test_hash_fghij",
            source_url=test_url
        )
        session.commit()
        
        doc_id = doc.id
        print(f"✅ 创建文档记录成功: id={doc_id}, source_url={doc.source_url}")
        
        # 重新查询文档
        from src.storage.metadata.models import Document
        queried_doc = session.query(Document).filter(Document.id == doc_id).first()
        
        assert queried_doc is not None, "查询文档失败"
        assert queried_doc.source_url == test_url, f"查询的URL不匹配: 期望={test_url}, 实际={queried_doc.source_url}"
        print(f"✅ 查询文档成功，URL正确: {queried_doc.source_url}")
        
        # 测试通过URL查询文档
        docs_by_url = session.query(Document).filter(Document.source_url == test_url).all()
        assert len(docs_by_url) > 0, "通过URL查询文档失败"
        assert docs_by_url[0].id == doc_id, "查询到的文档ID不匹配"
        print(f"✅ 通过URL查询文档成功: 找到{len(docs_by_url)}条记录")
        
        # 清理测试数据
        session.delete(doc)
        session.commit()
        print(f"✅ 测试数据已清理")


def test_document_without_url():
    """测试5: 创建没有URL的文档（应该允许）"""
    print("\n" + "=" * 60)
    print("测试5: 创建没有URL的文档（应该允许）")
    print("=" * 60)
    
    pg_client = get_postgres_client()
    
    with pg_client.get_session() as session:
        # 创建测试文档记录，不提供URL
        doc = crud.create_document(
            session=session,
            stock_code="TEST005",
            company_name="测试公司5",
            market=Market.A_SHARE.value,
            doc_type=DocType.QUARTERLY_REPORT.value,
            year=2024,
            quarter=3,
            minio_object_path="bronze/a_share/quarterly_reports/2024/Q3/TEST005/test.pdf",
            file_size=5120000,
            file_hash="test_hash_klmno"
        )
        session.commit()
        
        print(f"✅ 创建文档记录成功: id={doc.id}")
        print(f"   source_url: {doc.source_url}")
        
        # 验证URL为None（允许）
        assert doc.source_url is None, f"URL应该为None，但实际为{doc.source_url}"
        print(f"✅ 无URL文档创建成功（source_url为None）")
        
        # 清理测试数据
        session.delete(doc)
        session.commit()
        print(f"✅ 测试数据已清理")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("开始测试文档URL保存功能")
    print("=" * 60)
    
    try:
        test_create_document_with_url()
        test_create_document_with_url_in_metadata()
        test_create_document_with_doc_url_in_metadata()
        test_query_document_by_url()
        test_document_without_url()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ 测试失败: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
