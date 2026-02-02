# -*- coding: utf-8 -*-
"""
检查万科A数据
查看万科A(000002) 2024年的数据情况
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import Document


def check_wanke_data():
    """检查万科A数据"""
    print("=" * 80)
    print("检查万科A(000002) 2024年的数据")
    print("=" * 80)
    
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 查询万科A 2024年的所有文档
            print("\n1. 查询万科A(000002) 2024年的所有文档:")
            print("-" * 80)
            all_docs = session.query(Document).filter(
                Document.stock_code == "000002",
                Document.year == 2024
            ).all()
            
            if not all_docs:
                print("❌ 没有找到万科A 2024年的任何文档")
                
                # 检查是否有其他年份的数据
                print("\n2. 查询万科A(000002) 所有年份的文档:")
                print("-" * 80)
                all_years_docs = session.query(Document).filter(
                    Document.stock_code == "000002"
                ).order_by(Document.year.desc(), Document.quarter).limit(20).all()
                
                if not all_years_docs:
                    print("❌ 没有找到万科A的任何文档")
                else:
                    print(f"✅ 找到 {len(all_years_docs)} 个文档（显示最近20个）:\n")
                    for doc in all_years_docs:
                        quarter_str = f"Q{doc.quarter}" if doc.quarter else "年报"
                        print(f"  - {doc.year}年 {doc.doc_type}: {quarter_str}, ID: {doc.id}")
                
                return
            
            print(f"✅ 找到 {len(all_docs)} 个文档:\n")
            for doc in all_docs:
                quarter_str = f"Q{doc.quarter}" if doc.quarter else "年报"
                print(f"  - {doc.doc_type}: {quarter_str}, ID: {doc.id}, quarter字段: {doc.quarter}")
            
            # 查询第二季度季报
            print("\n2. 查询万科A(000002) 2024年第二季度季报:")
            print("-" * 80)
            q2_docs = session.query(Document).filter(
                Document.stock_code == "000002",
                Document.year == 2024,
                Document.quarter == 2
            ).all()
            
            if not q2_docs:
                print("❌ 没有找到第二季度的文档")
            else:
                print(f"✅ 找到 {len(q2_docs)} 个第二季度文档:\n")
                for doc in q2_docs:
                    print(f"  - doc_type: {doc.doc_type}, ID: {doc.id}, quarter: {doc.quarter}")
            
            # 查询所有季度报告
            print("\n3. 查询万科A(000002) 2024年所有季度报告:")
            print("-" * 80)
            quarterly_docs = session.query(Document).filter(
                Document.stock_code == "000002",
                Document.year == 2024,
                Document.doc_type == "quarterly_reports"
            ).all()
            
            if not quarterly_docs:
                print("❌ 没有找到季度报告")
            else:
                print(f"✅ 找到 {len(quarterly_docs)} 个季度报告:\n")
                for doc in quarterly_docs:
                    print(f"  - Q{doc.quarter}: ID: {doc.id}")
            
            # 统计所有doc_type
            print("\n4. 万科A 2024年所有文档的doc_type统计:")
            print("-" * 80)
            doc_types = {}
            for doc in all_docs:
                doc_type = doc.doc_type
                quarter = doc.quarter if doc.quarter else "NULL"
                key = f"{doc_type} (quarter={quarter})"
                doc_types[key] = doc_types.get(key, 0) + 1
            
            for key, count in sorted(doc_types.items()):
                print(f"  - {key}: {count} 个")
            
            # 检查是否有interim_reports（半年报，通常quarter=2）
            print("\n5. 检查是否有interim_reports（半年报）:")
            print("-" * 80)
            interim_docs = session.query(Document).filter(
                Document.stock_code == "000002",
                Document.year == 2024,
                Document.doc_type == "interim_reports"
            ).all()
            
            if not interim_docs:
                print("❌ 没有找到半年报")
            else:
                print(f"✅ 找到 {len(interim_docs)} 个半年报:\n")
                for doc in interim_docs:
                    print(f"  - quarter: {doc.quarter}, ID: {doc.id}")
            
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    check_wanke_data()
