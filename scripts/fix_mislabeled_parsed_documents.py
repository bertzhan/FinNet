#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查并修复被错误标记为 parsed 的文档

查找状态为 'parsed' 但没有 ParsedDocument 记录的文档，
并将它们的状态改回 'crawled'
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.common.constants import DocumentStatus


def check_and_fix_mislabeled_documents(dry_run=True):
    """
    检查并修复被错误标记的文档
    
    Args:
        dry_run: 如果为 True，只检查不修改；如果为 False，实际修改状态
    """
    print("=" * 80)
    print("检查被错误标记为 parsed 的文档")
    print("=" * 80)
    print(f"模式: {'[DRY RUN] 只检查，不修改' if dry_run else '[实际修改] 将修复错误标记的文档'}")
    print()
    
    pg_client = get_postgres_client()
    
    with pg_client.get_session() as session:
        # 1. 查找所有状态为 'parsed' 的文档
        print("1. 查找所有状态为 'parsed' 的文档...")
        parsed_docs = crud.get_documents_by_status(
            session=session,
            status=DocumentStatus.PARSED.value,
            limit=10000  # 获取所有
        )
        print(f"   找到 {len(parsed_docs)} 个状态为 'parsed' 的文档\n")
        
        if not parsed_docs:
            print("✅ 没有找到状态为 'parsed' 的文档")
            return
        
        # 2. 检查每个文档是否有 ParsedDocument 记录
        print("2. 检查每个文档是否有 ParsedDocument 记录...")
        mislabeled_docs = []
        
        for i, doc in enumerate(parsed_docs, 1):
            # 检查是否有 ParsedDocument 记录
            parsed_doc = crud.get_latest_parsed_document(session, doc.id)
            
            if not parsed_doc:
                # 没有 ParsedDocument 记录，说明被错误标记
                mislabeled_docs.append(doc)
                if len(mislabeled_docs) <= 10:  # 只打印前10个
                    print(f"   ❌ 文档 {doc.id}: {doc.stock_code} {doc.year} Q{doc.quarter} - 没有 ParsedDocument 记录")
            
            if i % 100 == 0:
                print(f"   已检查 {i}/{len(parsed_docs)} 个文档...")
        
        print(f"\n   检查完成！找到 {len(mislabeled_docs)} 个被错误标记的文档\n")
        
        if not mislabeled_docs:
            print("✅ 所有状态为 'parsed' 的文档都有对应的 ParsedDocument 记录")
            return
        
        # 3. 显示详细信息
        print("3. 被错误标记的文档详情（前20个）:")
        print("-" * 80)
        for i, doc in enumerate(mislabeled_docs[:20], 1):
            print(f"{i}. document_id: {doc.id}")
            print(f"   stock_code: {doc.stock_code}")
            print(f"   company_name: {doc.company_name}")
            print(f"   market: {doc.market}")
            print(f"   doc_type: {doc.doc_type}")
            print(f"   year: {doc.year}, quarter: {doc.quarter}")
            print(f"   parsed_at: {doc.parsed_at}")
            print(f"   minio_object_path: {doc.minio_object_path}")
            print()
        
        if len(mislabeled_docs) > 20:
            print(f"   ... 还有 {len(mislabeled_docs) - 20} 个文档未显示\n")
        
        # 4. 修复（如果不是 dry_run）
        if dry_run:
            print("=" * 80)
            print("⚠️  DRY RUN 模式：未进行实际修改")
            print("=" * 80)
            print(f"如果要实际修复，请运行:")
            print(f"  python {Path(__file__).name} --fix")
        else:
            print("4. 开始修复...")
            fixed_count = 0
            failed_count = 0
            
            for doc in mislabeled_docs:
                try:
                    # 将状态改回 'crawled'
                    success = crud.update_document_status(
                        session=session,
                        document_id=doc.id,
                        status=DocumentStatus.CRAWLED.value
                    )
                    if success:
                        fixed_count += 1
                        if fixed_count <= 10:
                            print(f"   ✅ 已修复: document_id={doc.id}, {doc.stock_code}")
                    else:
                        failed_count += 1
                        print(f"   ❌ 修复失败: document_id={doc.id}")
                except Exception as e:
                    failed_count += 1
                    print(f"   ❌ 修复异常: document_id={doc.id}, error={e}")
            
            session.commit()
            
            print()
            print("=" * 80)
            print("修复完成！")
            print("=" * 80)
            print(f"成功修复: {fixed_count} 个文档")
            print(f"修复失败: {failed_count} 个文档")
            print(f"总计: {len(mislabeled_docs)} 个文档")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="检查并修复被错误标记为 parsed 的文档")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="实际修复（默认只检查不修改）"
    )
    
    args = parser.parse_args()
    
    try:
        check_and_fix_mislabeled_documents(dry_run=not args.fix)
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
