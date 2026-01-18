#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 UUID 功能
验证所有使用 UUID 主键的功能是否正常工作
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.common.logger import get_logger

logger = get_logger(__name__)


def test_uuid_functionality():
    """测试 UUID 功能"""
    print("=" * 60)
    print("UUID 功能测试")
    print("=" * 60)
    
    pg_client = get_postgres_client()
    
    try:
        # 测试 1: 创建文档记录（应该自动生成 UUID）
        print("\n1️⃣ 测试创建文档记录...")
        with pg_client.get_session() as session:
            doc = crud.create_document(
                session=session,
                stock_code="000001",
                company_name="测试公司",
                market="a_share",
                doc_type="test",
                year=2024,
                quarter=1,
                minio_object_path="test/uuid_test/document.pdf"
            )
            print(f"   ✅ 文档创建成功")
            print(f"      - ID 类型: {type(doc.id)}")
            print(f"      - ID 值: {doc.id}")
            print(f"      - ID 字符串: {str(doc.id)}")
            
            # 验证 ID 是 UUID 类型
            import uuid
            assert isinstance(doc.id, uuid.UUID), f"ID 应该是 UUID 类型，但得到 {type(doc.id)}"
            print(f"   ✅ ID 类型验证通过")
            
            doc_id = doc.id
        
        # 测试 2: 使用 UUID 对象查询文档
        print("\n2️⃣ 测试使用 UUID 对象查询文档...")
        with pg_client.get_session() as session:
            doc = crud.get_document_by_id(session, doc_id)
            assert doc is not None, "应该能找到文档"
            assert doc.id == doc_id, "ID 应该匹配"
            print(f"   ✅ 使用 UUID 对象查询成功")
        
        # 测试 3: 使用字符串 UUID 查询文档
        print("\n3️⃣ 测试使用字符串 UUID 查询文档...")
        with pg_client.get_session() as session:
            doc = crud.get_document_by_id(session, str(doc_id))
            assert doc is not None, "应该能找到文档"
            assert doc.id == doc_id, "ID 应该匹配"
            print(f"   ✅ 使用字符串 UUID 查询成功")
        
        # 测试 4: 创建解析任务（使用 UUID 外键）
        print("\n4️⃣ 测试创建解析任务（UUID 外键）...")
        with pg_client.get_session() as session:
            parse_task = crud.create_parse_task(
                session=session,
                document_id=doc_id,  # 使用 UUID 对象
                parser_type="mineru",
                parser_version="1.0.0"
            )
            print(f"   ✅ 解析任务创建成功")
            print(f"      - 任务 ID: {parse_task.id}")
            print(f"      - 文档 ID: {parse_task.document_id}")
            assert isinstance(parse_task.id, uuid.UUID), "任务 ID 应该是 UUID"
            assert parse_task.document_id == doc_id, "文档 ID 应该匹配"
            print(f"   ✅ UUID 外键验证通过")
            
            parse_task_id = parse_task.id
        
        # 测试 5: 使用字符串 UUID 创建解析任务
        print("\n5️⃣ 测试使用字符串 UUID 创建解析任务...")
        with pg_client.get_session() as session:
            parse_task2 = crud.create_parse_task(
                session=session,
                document_id=str(doc_id),  # 使用字符串 UUID
                parser_type="mineru",
                parser_version="1.0.0"
            )
            assert parse_task2.document_id == doc_id, "文档 ID 应该匹配"
            print(f"   ✅ 使用字符串 UUID 创建成功")
        
        # 测试 6: 创建解析文档记录（多个 UUID 外键）
        print("\n6️⃣ 测试创建解析文档记录（多个 UUID 外键）...")
        with pg_client.get_session() as session:
            parsed_doc = crud.create_parsed_document(
                session=session,
                document_id=doc_id,
                parse_task_id=parse_task_id,
                content_json_path="test/parsed/content.json",
                content_json_hash="test_hash_123",
                source_document_hash="test_hash_123",
                parser_type="mineru"
            )
            print(f"   ✅ 解析文档记录创建成功")
            print(f"      - 解析文档 ID: {parsed_doc.id}")
            print(f"      - 文档 ID: {parsed_doc.document_id}")
            print(f"      - 解析任务 ID: {parsed_doc.parse_task_id}")
            assert isinstance(parsed_doc.id, uuid.UUID), "解析文档 ID 应该是 UUID"
            assert parsed_doc.document_id == doc_id, "文档 ID 应该匹配"
            assert parsed_doc.parse_task_id == parse_task_id, "解析任务 ID 应该匹配"
            print(f"   ✅ 多个 UUID 外键验证通过")
        
        # 测试 7: 查询关联记录
        print("\n7️⃣ 测试查询关联记录...")
        with pg_client.get_session() as session:
            parsed_docs = crud.get_parsed_documents_by_document_id(session, doc_id)
            assert len(parsed_docs) > 0, "应该能找到解析文档"
            print(f"   ✅ 查询关联记录成功，找到 {len(parsed_docs)} 条记录")
        
        # 测试 8: 更新文档状态（使用 UUID）
        print("\n8️⃣ 测试更新文档状态（使用 UUID）...")
        with pg_client.get_session() as session:
            success = crud.update_document_status(
                session=session,
                document_id=doc_id,
                status="test_status"
            )
            assert success, "更新应该成功"
            print(f"   ✅ 更新文档状态成功")
        
        # 清理测试数据
        print("\n9️⃣ 清理测试数据...")
        with pg_client.get_session() as session:
            # 删除解析文档
            parsed_docs = crud.get_parsed_documents_by_document_id(session, doc_id)
            for pd in parsed_docs:
                session.delete(pd)
            
            # 删除解析任务
            tasks = session.query(crud.ParseTask).filter(
                crud.ParseTask.document_id == doc_id
            ).all()
            for task in tasks:
                session.delete(task)
            
            # 删除文档
            doc = crud.get_document_by_id(session, doc_id)
            if doc:
                session.delete(doc)
            
            session.commit()
            print(f"   ✅ 测试数据清理完成")
        
        print("\n" + "=" * 60)
        print("✅ 所有 UUID 功能测试通过！")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        pg_client.close()


if __name__ == '__main__':
    success = test_uuid_functionality()
    sys.exit(0 if success else 1)
