# -*- coding: utf-8 -*-
"""
测试只解析前3页的解析作业
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.processing.ai.pdf_parser import get_mineru_parser
from src.storage.object_store.minio_client import MinIOClient
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.storage.metadata.models import Document
from src.common.constants import DocumentStatus, Market, DocType


def find_or_create_document(minio_path: str):
    """查找或创建文档记录"""
    pg_client = get_postgres_client()
    
    with pg_client.get_session() as session:
        # 先查找是否已存在
        doc = crud.get_document_by_path(session, minio_path)
        if doc:
            print(f"找到已有文档记录: document_id={doc.id}")
            return doc.id
        
        # 如果不存在，创建一个测试文档记录
        parts = minio_path.split('/')
        stock_code = parts[3] if len(parts) > 3 else "300542"
        
        doc = Document(
            stock_code=stock_code,
            company_name=f"测试公司_{stock_code}",
            market=Market.A_SHARE.value,
            doc_type=DocType.IPO_PROSPECTUS.value,
            year=2023,
            quarter=None,
            minio_object_name=minio_path,
            file_size=0,
            file_hash="",
            status=DocumentStatus.CRAWLED.value,
        )
        session.add(doc)
        session.flush()
        document_id = doc.id
        session.commit()
        
        print(f"创建测试文档记录: document_id={document_id}")
        return document_id


def test_parse_first_3_pages():
    """测试只解析前3页"""
    print("=" * 60)
    print("测试：只解析前3页（页面 0, 1, 2）")
    print("=" * 60)
    print()
    
    # 1. 查找 MinIO 中实际存在的 PDF
    print("步骤1: 查找 MinIO 中的 PDF 文件")
    print("-" * 60)
    minio_client = MinIOClient()
    objects = list(minio_client.client.list_objects(
        minio_client.bucket,
        prefix="bronze/a_share/ipo_prospectus/",
        recursive=True
    ))
    
    pdf_objects = [o for o in objects if o.object_name.endswith('.pdf')]
    if not pdf_objects:
        print("❌ MinIO 中没有找到 PDF 文件")
        return False
    
    pdf_object = pdf_objects[0]
    print(f"✅ 找到 PDF 文件: {pdf_object.object_name}")
    print(f"   大小: {pdf_object.size / 1024 / 1024:.2f} MB")
    print()
    
    # 2. 查找或创建文档记录
    print("步骤2: 查找或创建文档记录")
    print("-" * 60)
    document_id = find_or_create_document(pdf_object.object_name)
    print()
    
    # 3. 解析文档（只解析前3页）
    print("步骤3: 解析文档（只解析前3页：0, 1, 2）")
    print("-" * 60)
    print(f"   document_id: {document_id}")
    print(f"   MinIO 路径: {pdf_object.object_name}")
    print(f"   页面范围: 0-2 (前3页)")
    print(f"   这可能需要一些时间，请耐心等待...")
    print()
    
    parser = get_mineru_parser()
    
    try:
        result = parser.parse_document(
            document_id=document_id,
            save_to_silver=True,
            start_page_id=0,
            end_page_id=2  # 只解析前3页（0, 1, 2）
        )
        
        if result.get("success"):
            print(f"\n✅ 解析成功！")
            print(f"   解析任务ID: {result.get('parse_task_id')}")
            print(f"   Silver 层路径: {result.get('output_path')}")
            print(f"   文本长度: {result.get('extracted_text_length', 0)} 字符")
            print(f"   表格数量: {result.get('extracted_tables_count', 0)}")
            print(f"   图片数量: {result.get('extracted_images_count', 0)}")
            return True
        else:
            error_msg = result.get('error_message', '未知错误')
            print(f"\n❌ 解析失败: {error_msg}")
            return False
            
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print(f"解析结果:")
    print(f"  成功: {parse_result.get('success')}")
    print(f"  解析成功: {parse_result.get('parsed_count', 0)}")
    print(f"  解析失败: {parse_result.get('failed_count', 0)}")
    
    if parse_result.get('parsed_count', 0) > 0:
        print(f"\n✅ 解析成功！")
        failed_docs = parse_result.get('failed_documents', [])
        if failed_docs:
            print(f"   失败文档: {failed_docs}")
        return True
    else:
        failed_docs = parse_result.get('failed_documents', [])
        if failed_docs:
            print(f"\n❌ 解析失败:")
            for failed in failed_docs:
                print(f"   - document_id={failed['document_id']}, error={failed['error']}")
        return False


if __name__ == '__main__':
    try:
        success = test_parse_first_3_pages()
        
        print("\n" + "=" * 60)
        if success:
            print("✅ 测试通过！前3页解析功能正常")
        else:
            print("❌ 测试失败，请检查错误信息")
        print("=" * 60)
        
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
