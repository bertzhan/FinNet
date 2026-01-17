# -*- coding: utf-8 -*-
"""
测试文档publish_date保存功能
验证爬虫时publish_date是否正确保存到数据库的Document表中
"""

import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.common.constants import Market, DocType


def test_create_document_with_publish_date():
    """测试1: 直接传入publish_date参数"""
    print("=" * 60)
    print("测试1: 直接传入publish_date参数")
    print("=" * 60)
    
    pg_client = get_postgres_client()
    test_date = datetime(2024, 1, 15, 10, 30, 0)
    
    with pg_client.get_session() as session:
        # 创建测试文档记录
        doc = crud.create_document(
            session=session,
            stock_code="TEST_DATE001",
            company_name="测试日期公司",
            market=Market.A_SHARE.value,
            doc_type=DocType.QUARTERLY_REPORT.value,
            year=2024,
            quarter=1,
            minio_object_path="bronze/a_share/quarterly_reports/2024/Q1/TEST_DATE001/test.pdf",
            file_size=1024000,
            file_hash="test_hash_date1",
            publish_date=test_date
        )
        session.commit()
        
        print(f"✅ 创建文档记录成功: id={doc.id}")
        print(f"   publish_date: {doc.publish_date}")
        print(f"   期望日期: {test_date}")
        
        # 验证日期是否正确保存
        assert doc.publish_date == test_date, f"日期不匹配: 期望={test_date}, 实际={doc.publish_date}"
        print(f"✅ 日期验证通过")
        
        # 清理测试数据
        session.delete(doc)
        session.commit()
        print(f"✅ 测试数据已清理")


def test_create_document_with_iso_date_in_metadata():
    """测试2: 从metadata中的ISO格式日期字符串提取"""
    print("\n" + "=" * 60)
    print("测试2: 从metadata中的ISO格式日期字符串提取")
    print("=" * 60)
    
    pg_client = get_postgres_client()
    test_date_str = "2024-02-20T14:30:00"
    expected_date = datetime.fromisoformat(test_date_str)
    
    with pg_client.get_session() as session:
        # 创建测试文档记录，日期在metadata中（ISO格式字符串）
        metadata = {
            'publication_date_iso': test_date_str,
            'other_field': 'test_value'
        }
        
        doc = crud.create_document(
            session=session,
            stock_code="TEST_DATE002",
            company_name="测试日期公司2",
            market=Market.A_SHARE.value,
            doc_type=DocType.ANNUAL_REPORT.value,
            year=2023,
            quarter=4,
            minio_object_path="bronze/a_share/annual_reports/2023/TEST_DATE002/test.pdf",
            file_size=2048000,
            file_hash="test_hash_date2",
            metadata=metadata
        )
        session.commit()
        
        print(f"✅ 创建文档记录成功: id={doc.id}")
        print(f"   publish_date: {doc.publish_date}")
        print(f"   metadata中的日期: {test_date_str}")
        print(f"   期望日期: {expected_date}")
        
        # 验证日期是否正确从metadata中提取
        if doc.publish_date and abs((doc.publish_date - expected_date).total_seconds()) < 1:
            print(f"✅ 日期从metadata中提取成功")
            
            # 清理测试数据
            session.delete(doc)
            session.commit()
            print(f"✅ 测试数据已清理")
            return True
        else:
            print(f"❌ 日期提取失败")
            print(f"   期望: {expected_date}")
            print(f"   实际: {doc.publish_date}")
            
            # 清理测试数据
            session.delete(doc)
            session.commit()
            return False


def test_create_document_with_pub_date_iso_in_metadata():
    """测试3: 从metadata中的pub_date_iso字段提取"""
    print("\n" + "=" * 60)
    print("测试3: 从metadata中的pub_date_iso字段提取")
    print("=" * 60)
    
    pg_client = get_postgres_client()
    test_date_str = "2024-03-10T09:15:00"
    expected_date = datetime.fromisoformat(test_date_str)
    
    with pg_client.get_session() as session:
        # 创建测试文档记录，日期在metadata的pub_date_iso字段中
        metadata = {
            'pub_date_iso': test_date_str,  # 使用pub_date_iso而不是publication_date_iso
            'publication_date': '10032024'  # DDMMYYYY格式
        }
        
        doc = crud.create_document(
            session=session,
            stock_code="TEST_DATE003",
            company_name="测试日期公司3",
            market=Market.A_SHARE.value,
            doc_type=DocType.IPO_PROSPECTUS.value,
            year=2024,
            quarter=None,
            minio_object_path="bronze/a_share/ipo_prospectus/TEST_DATE003/test.pdf",
            file_size=3072000,
            file_hash="test_hash_date3",
            metadata=metadata
        )
        session.commit()
        
        print(f"✅ 创建文档记录成功: id={doc.id}")
        print(f"   publish_date: {doc.publish_date}")
        print(f"   metadata中的pub_date_iso: {test_date_str}")
        print(f"   期望日期: {expected_date}")
        
        # 验证日期是否正确从metadata的pub_date_iso中提取
        if doc.publish_date and abs((doc.publish_date - expected_date).total_seconds()) < 1:
            print(f"✅ 日期从metadata的pub_date_iso字段中提取成功")
            
            # 清理测试数据
            session.delete(doc)
            session.commit()
            print(f"✅ 测试数据已清理")
            return True
        else:
            print(f"❌ 日期提取失败")
            print(f"   期望: {expected_date}")
            print(f"   实际: {doc.publish_date}")
            
            # 清理测试数据
            session.delete(doc)
            session.commit()
            return False


def test_create_document_without_date():
    """测试4: 创建没有日期的文档（应该允许）"""
    print("\n" + "=" * 60)
    print("测试4: 创建没有日期的文档（应该允许）")
    print("=" * 60)
    
    pg_client = get_postgres_client()
    
    with pg_client.get_session() as session:
        # 创建测试文档记录，不提供日期
        doc = crud.create_document(
            session=session,
            stock_code="TEST_DATE004",
            company_name="测试日期公司4",
            market=Market.A_SHARE.value,
            doc_type=DocType.QUARTERLY_REPORT.value,
            year=2024,
            quarter=2,
            minio_object_path="bronze/a_share/quarterly_reports/2024/Q2/TEST_DATE004/test.pdf",
            file_size=4096000,
            file_hash="test_hash_date4"
        )
        session.commit()
        
        print(f"✅ 创建文档记录成功: id={doc.id}")
        print(f"   publish_date: {doc.publish_date}")
        
        # 验证日期为None（允许为空）
        assert doc.publish_date is None, f"日期应该为None，但实际为{doc.publish_date}"
        print(f"✅ 无日期文档创建成功（publish_date为None）")
        
        # 清理测试数据
        session.delete(doc)
        session.commit()
        print(f"✅ 测试数据已清理")


def test_query_documents_by_publish_date():
    """测试5: 查询特定发布日期范围的文档"""
    print("\n" + "=" * 60)
    print("测试5: 查询特定发布日期范围的文档")
    print("=" * 60)
    
    pg_client = get_postgres_client()
    test_date = datetime(2024, 4, 1, 12, 0, 0)
    
    with pg_client.get_session() as session:
        # 创建测试文档
        doc = crud.create_document(
            session=session,
            stock_code="TEST_DATE005",
            company_name="查询测试公司",
            market=Market.A_SHARE.value,
            doc_type=DocType.QUARTERLY_REPORT.value,
            year=2024,
            quarter=1,
            minio_object_path="bronze/a_share/quarterly_reports/2024/Q1/TEST_DATE005/test.pdf",
            file_size=5120000,
            file_hash="test_hash_date5",
            publish_date=test_date
        )
        session.commit()
        
        doc_id = doc.id
        print(f"✅ 创建测试文档: id={doc_id}, publish_date={doc.publish_date}")
        
        # 通过日期查询文档
        from src.storage.metadata.models import Document
        from sqlalchemy import and_
        
        start_date = datetime(2024, 4, 1)
        end_date = datetime(2024, 4, 2)
        docs = session.query(Document).filter(
            and_(
                Document.publish_date >= start_date,
                Document.publish_date < end_date
            )
        ).all()
        
        if len(docs) > 0:
            print(f"✅ 通过日期范围查询成功: 找到 {len(docs)} 条记录")
            for d in docs:
                print(f"   - document_id={d.id}, stock_code={d.stock_code}, publish_date={d.publish_date}")
            
            # 清理测试数据
            session.delete(doc)
            session.commit()
            print(f"✅ 测试数据已清理")
            return True
        else:
            print(f"❌ 通过日期范围查询失败: 未找到记录")
            
            # 清理测试数据
            session.delete(doc)
            session.commit()
            return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("开始测试文档publish_date保存功能")
    print("=" * 60)
    
    try:
        test_create_document_with_publish_date()
        test2_result = test_create_document_with_iso_date_in_metadata()
        test3_result = test_create_document_with_pub_date_iso_in_metadata()
        test_create_document_without_date()
        test5_result = test_query_documents_by_publish_date()
        
        print("\n" + "=" * 60)
        if test2_result and test3_result and test5_result:
            print("✅ 所有测试通过！")
        else:
            print("❌ 部分测试失败")
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
