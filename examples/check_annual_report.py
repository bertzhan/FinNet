# -*- coding: utf-8 -*-
"""
检查年报数据
查看平安银行2024年年报在数据库中的情况
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import Document
from sqlalchemy import and_


def check_annual_reports():
    """检查年报数据"""
    print("=" * 80)
    print("检查平安银行2024年年报数据")
    print("=" * 80)
    
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 查询平安银行2024年的所有文档
            print("\n1. 查询平安银行(000001) 2024年的所有文档:")
            print("-" * 80)
            all_docs = session.query(Document).filter(
                Document.stock_code == "000001",
                Document.year == 2024
            ).all()
            
            if not all_docs:
                print("❌ 没有找到平安银行2024年的任何文档")
                return
            
            print(f"✅ 找到 {len(all_docs)} 个文档:\n")
            for doc in all_docs:
                quarter_str = f"Q{doc.quarter}" if doc.quarter else "年报"
                print(f"  - {doc.doc_type}: {quarter_str}, ID: {doc.id}, quarter字段: {doc.quarter}")
            
            # 查询年报类型的文档
            print("\n2. 查询平安银行(000001) 2024年年报类型(annual_reports)的文档:")
            print("-" * 80)
            annual_docs = session.query(Document).filter(
                Document.stock_code == "000001",
                Document.year == 2024,
                Document.doc_type == "annual_reports"
            ).all()
            
            if not annual_docs:
                print("❌ 没有找到年报类型的文档")
            else:
                print(f"✅ 找到 {len(annual_docs)} 个年报文档:\n")
                for doc in annual_docs:
                    print(f"  - ID: {doc.id}")
                    print(f"    quarter字段: {doc.quarter} (类型: {type(doc.quarter)})")
                    print(f"    quarter是否为None: {doc.quarter is None}")
                    print(f"    doc_type: {doc.doc_type}")
                    print(f"    year: {doc.year}")
                    print()
            
            # 查询quarter为NULL的文档
            print("\n3. 查询平安银行(000001) 2024年quarter为NULL的文档:")
            print("-" * 80)
            null_quarter_docs = session.query(Document).filter(
                Document.stock_code == "000001",
                Document.year == 2024,
                Document.quarter.is_(None)
            ).all()
            
            if not null_quarter_docs:
                print("❌ 没有找到quarter为NULL的文档")
            else:
                print(f"✅ 找到 {len(null_quarter_docs)} 个quarter为NULL的文档:\n")
                for doc in null_quarter_docs:
                    print(f"  - doc_type: {doc.doc_type}, ID: {doc.id}")
            
            # 测试查询逻辑
            print("\n4. 测试查询逻辑:")
            print("-" * 80)
            
            # 测试1: quarter=None, doc_type=annual_reports
            query1 = session.query(Document.id).filter(
                Document.stock_code == "000001",
                Document.year == 2024,
                Document.doc_type == "annual_reports",
                Document.quarter.is_(None)
            )
            result1 = query1.first()
            print(f"  查询条件: quarter=None, doc_type=annual_reports")
            print(f"  结果: {'找到' if result1 else '未找到'}")
            if result1:
                print(f"  document_id: {result1[0]}")
            
            # 测试2: 查看所有doc_type
            print("\n5. 平安银行2024年所有文档的doc_type统计:")
            print("-" * 80)
            doc_types = {}
            for doc in all_docs:
                doc_type = doc.doc_type
                quarter = doc.quarter if doc.quarter else "NULL"
                key = f"{doc_type} (quarter={quarter})"
                doc_types[key] = doc_types.get(key, 0) + 1
            
            for key, count in sorted(doc_types.items()):
                print(f"  - {key}: {count} 个")
            
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    check_annual_reports()
