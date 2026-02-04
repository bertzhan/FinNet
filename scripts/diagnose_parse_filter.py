#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
诊断 parse_pdf_job 的行业过滤问题
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.storage.metadata import get_postgres_client, crud
from src.storage.metadata.models import ListedCompany, Document
from src.common.constants import DocumentStatus
from sqlalchemy import text

def diagnose_filter():
    """诊断过滤步骤"""
    pg_client = get_postgres_client()

    industry_filter = "光伏设备"
    force_reparse = True
    limit = 100

    with pg_client.get_session() as session:
        print("=" * 80)
        print("诊断 parse_pdf_job 行业过滤问题")
        print("=" * 80)
        print(f"配置: industry_filter='{industry_filter}', force_reparse={force_reparse}, limit={limit}")

        # 步骤 1: 查询文档（根据 force_reparse）
        print("\n" + "=" * 80)
        print("步骤 1: 查询文档（根据状态）")
        print("=" * 80)

        if force_reparse:
            print("强制重新解析模式：查询 'crawled' 和 'parsed' 状态的文档")
            documents_crawled = crud.get_documents_by_status(
                session=session,
                status=DocumentStatus.CRAWLED.value,
                limit=limit,
                offset=0
            )
            documents_parsed = crud.get_documents_by_status(
                session=session,
                status=DocumentStatus.PARSED.value,
                limit=limit,
                offset=0
            )
            documents = documents_crawled + documents_parsed

            # 去重
            seen_ids = set()
            unique_documents = []
            for doc in documents:
                if doc.id not in seen_ids:
                    seen_ids.add(doc.id)
                    unique_documents.append(doc)
            documents = unique_documents[:limit]

            print(f"  crawled 状态: {len(documents_crawled)} 个文档")
            print(f"  parsed 状态: {len(documents_parsed)} 个文档")
            print(f"  合并去重后: {len(documents)} 个文档")
        else:
            documents = crud.get_documents_by_status(
                session=session,
                status=DocumentStatus.CRAWLED.value,
                limit=limit,
                offset=0
            )
            print(f"  crawled 状态: {len(documents)} 个文档")

        # 显示文档的公司分布
        stock_codes_in_docs = set(doc.stock_code for doc in documents)
        print(f"\n  涉及公司: {len(stock_codes_in_docs)} 家")
        print(f"  公司代码样本: {sorted(stock_codes_in_docs)[:10]}")

        # 步骤 2: 应用行业过滤
        print("\n" + "=" * 80)
        print("步骤 2: 应用行业过滤")
        print("=" * 80)

        if industry_filter:
            print(f"  行业过滤关键词: '{industry_filter}'")

            # 查询符合行业的公司列表
            companies = session.query(ListedCompany).filter(
                text("affiliate_industry->>'ind_name' LIKE :industry")
            ).params(industry=f'%{industry_filter}%').all()

            company_codes = {c.code for c in companies}
            print(f"\n  找到符合行业的公司: {len(company_codes)} 家")

            if companies:
                print(f"  公司列表:")
                for company in companies[:10]:
                    ind_name = company.affiliate_industry.get('ind_name') if company.affiliate_industry else 'N/A'
                    print(f"    - {company.code}: {company.name} (行业: {ind_name})")

                # 检查这些公司是否在 documents 中
                print(f"\n  检查公司是否在 Document 表中:")
                for code in sorted(company_codes)[:10]:
                    doc_count = sum(1 for d in documents if d.stock_code == code)
                    total_doc_count = session.query(Document).filter(
                        Document.stock_code == code
                    ).count()
                    print(f"    {code}: 当前查询中有 {doc_count} 个文档, 总共 {total_doc_count} 个文档")

            # 过滤文档
            documents_before = len(documents)
            documents = [d for d in documents if d.stock_code in company_codes]
            documents_after = len(documents)

            print(f"\n  过滤前文档数: {documents_before}")
            print(f"  过滤后文档数: {documents_after}")
            print(f"  被过滤掉: {documents_before - documents_after}")

        # 步骤 3: 检查这些文档的状态分布
        print("\n" + "=" * 80)
        print("步骤 3: 过滤后的文档状态分布")
        print("=" * 80)

        status_counts = {}
        for doc in documents:
            status = doc.status
            status_counts[status] = status_counts.get(status, 0) + 1

        print(f"  总文档数: {len(documents)}")
        for status, count in status_counts.items():
            print(f"    {status}: {count}")

        # 步骤 4: 检查 PDF 文档
        print("\n" + "=" * 80)
        print("步骤 4: 检查 PDF 文档")
        print("=" * 80)

        pdf_documents = [
            d for d in documents
            if d.minio_object_path and d.minio_object_path.endswith('.pdf')
        ]

        print(f"  过滤前文档数: {len(documents)}")
        print(f"  PDF 文档数: {len(pdf_documents)}")
        print(f"  非 PDF 文档: {len(documents) - len(pdf_documents)}")

        if pdf_documents:
            print(f"\n  PDF 文档样本:")
            for doc in pdf_documents[:5]:
                print(f"    - {doc.stock_code}: {doc.company_name} ({doc.status})")
                print(f"      路径: {doc.minio_object_path}")

        # 步骤 4.5: 检查 MinIO 文件是否存在
        print("\n" + "=" * 80)
        print("步骤 4.5: 检查 MinIO 文件是否存在")
        print("=" * 80)

        from src.storage.object_store.minio_client import MinIOClient
        minio_client = MinIOClient()

        existing_count = 0
        missing_count = 0

        for doc in pdf_documents:
            exists = minio_client.file_exists(doc.minio_object_path)
            if exists:
                existing_count += 1
            else:
                missing_count += 1
                print(f"  ❌ 文件不存在: {doc.stock_code} - {doc.minio_object_path}")

        print(f"\n  MinIO 文件检查结果:")
        print(f"    存在: {existing_count} 个")
        print(f"    缺失: {missing_count} 个")

        if missing_count > 0:
            print(f"\n  ⚠️ 警告: {missing_count} 个文档在 MinIO 中不存在，将被过滤掉！")

        # 步骤 5: 查看所有光伏设备公司的文档及其状态
        print("\n" + "=" * 80)
        print("步骤 5: 查看光伏设备公司的所有文档及状态")
        print("=" * 80)

        # 查询光伏设备公司
        pv_companies = session.query(ListedCompany).filter(
            text("affiliate_industry->>'ind_name' LIKE :industry")
        ).params(industry=f'%{industry_filter}%').all()

        if pv_companies:
            pv_codes = [c.code for c in pv_companies]
            print(f"  光伏设备公司: {len(pv_codes)} 家")

            for company in pv_companies[:5]:
                print(f"\n  公司: {company.code} - {company.name}")

                # 查询该公司的所有文档
                docs = session.query(Document).filter(
                    Document.stock_code == company.code
                ).all()

                print(f"    总文档数: {len(docs)}")

                if docs:
                    # 按状态分组
                    status_dist = {}
                    for doc in docs:
                        status_dist[doc.status] = status_dist.get(doc.status, 0) + 1

                    for status, count in status_dist.items():
                        print(f"      {status}: {count}")

                    # 显示几个文档样本
                    print(f"    文档样本:")
                    for doc in docs[:3]:
                        print(f"      - ID: {doc.id}")
                        print(f"        状态: {doc.status}")
                        print(f"        路径: {doc.minio_object_path}")
                        print(f"        类型: {doc.doc_type}")

if __name__ == '__main__':
    diagnose_filter()
