# -*- coding: utf-8 -*-
"""
测试解析前10页并验证图片上传功能
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
            # 重置状态为 CRAWLED，以便重新解析
            doc.status = DocumentStatus.CRAWLED.value
            session.commit()
            print(f"已重置文档状态为 CRAWLED，可以重新解析")
            return doc.id
        
        # 如果不存在，创建一个测试文档记录
        parts = minio_path.split('/')
        stock_code = parts[3] if len(parts) > 3 else "TEST"
        
        doc = Document(
            stock_code=stock_code,
            company_name=f"测试公司_{stock_code}",
            market=Market.A_SHARE.value,
            doc_type=DocType.IPO_PROSPECTUS.value if "ipo" in minio_path.lower() else DocType.QUARTERLY_REPORT.value,
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


def test_parse_first_10_pages():
    """测试解析前10页并验证图片上传"""
    print("=" * 60)
    print("测试：解析前10页（页面 0-9）并验证图片上传")
    print("=" * 60)
    print()
    
    # 1. 查找 MinIO 中不同的 PDF 文件
    print("步骤1: 查找 MinIO 中的 PDF 文件")
    print("-" * 60)
    minio_client = MinIOClient()
    objects = list(minio_client.client.list_objects(
        minio_client.bucket,
        prefix="bronze/a_share/",
        recursive=True
    ))
    
    pdf_objects = [o for o in objects if o.object_name.endswith('.pdf')]
    if not pdf_objects:
        print("❌ MinIO 中没有找到 PDF 文件")
        return False
    
    # 找一个不同的文件（不是 300542）
    pdf_object = None
    for obj in pdf_objects:
        if "300542" not in obj.object_name:
            pdf_object = obj
            break
    
    # 如果都包含 300542，就用第一个
    if not pdf_object:
        pdf_object = pdf_objects[0]
    
    print(f"✅ 找到 PDF 文件: {pdf_object.object_name}")
    print(f"   大小: {pdf_object.size / 1024 / 1024:.2f} MB")
    print()
    
    # 2. 查找或创建文档记录
    print("步骤2: 查找或创建文档记录")
    print("-" * 60)
    document_id = find_or_create_document(pdf_object.object_name)
    print()
    
    # 3. 解析文档（只解析前10页）
    print("步骤3: 解析文档（只解析前10页：0-9）")
    print("-" * 60)
    print(f"   document_id: {document_id}")
    print(f"   MinIO 路径: {pdf_object.object_name}")
    print(f"   页面范围: 0-9 (前10页)")
    print(f"   这可能需要一些时间，请耐心等待...")
    print()
    
    parser = get_mineru_parser()
    
    try:
        result = parser.parse_document(
            document_id=document_id,
            save_to_silver=True,
            start_page_id=0,
            end_page_id=9  # 只解析前10页（0-9）
        )
        
        if result.get("success"):
            print(f"\n✅ 解析成功！")
            print(f"   解析任务ID: {result.get('parse_task_id')}")
            print(f"   Silver 层路径: {result.get('output_path')}")
            print(f"   文本长度: {result.get('extracted_text_length', 0)} 字符")
            print(f"   表格数量: {result.get('extracted_tables_count', 0)}")
            print(f"   图片数量: {result.get('extracted_images_count', 0)}")
            
            # 4. 验证所有文件是否上传
            print(f"\n步骤4: 验证所有文件上传")
            print("-" * 60)
            silver_path = result.get('output_path')
            if silver_path:
                # 下载 JSON 文件查看所有文件路径
                json_data = minio_client.download_file(silver_path)
                if json_data:
                    import json
                    parsed_data = json.loads(json_data.decode('utf-8'))
                    image_paths = parsed_data.get('image_paths', [])
                    uploaded_files = parsed_data.get('uploaded_files', {})
                    uploaded_files_count = parsed_data.get('uploaded_files_count', 0)
                    
                    print(f"   JSON 中的图片路径数量: {len(image_paths)}")
                    print(f"   实际上传文件总数: {uploaded_files_count}")
                    print(f"\n   按文件类型统计:")
                    for file_type, paths in uploaded_files.items():
                        print(f"     - {file_type}: {len(paths)} 个文件")
                        # 验证前3个文件是否存在
                        for i, file_path in enumerate(paths[:3]):
                            try:
                                file_stat = minio_client.client.stat_object(
                                    minio_client.bucket, file_path
                                )
                                print(f"       {i+1}. {file_path.split('/')[-1]}")
                                print(f"          ✅ 文件存在 ({file_stat.size} bytes)")
                            except Exception as e:
                                print(f"       {i+1}. {file_path.split('/')[-1]}")
                                print(f"          ❌ 文件不存在: {e}")
                    
                    if image_paths:
                        print(f"\n   图片文件路径:")
                        for i, img_path in enumerate(image_paths[:5]):
                            print(f"     {i+1}. {img_path.split('/')[-1]}")
                    else:
                        print(f"   ⚠️  未找到图片路径（可能该文档前10页没有图片）")
            
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


if __name__ == '__main__':
    try:
        success = test_parse_first_10_pages()
        
        print("\n" + "=" * 60)
        if success:
            print("✅ 测试通过！前10页解析和图片上传功能正常")
        else:
            print("❌ 测试失败，请检查错误信息")
        print("=" * 60)
        
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
