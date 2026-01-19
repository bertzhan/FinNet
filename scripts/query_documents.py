#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询 documents 表
快速查询文档表的所有记录
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import Document

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False
    print("⚠️  提示: 安装 tabulate 可以获得更好的表格显示效果: pip install tabulate")


def query_all_documents(limit: int = 100):
    """查询所有文档"""
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            # 查询所有文档
            documents = session.query(Document).limit(limit).all()
            
            if not documents:
                print("📭 没有找到文档记录")
                return
            
            print(f"📊 找到 {len(documents)} 条文档记录（最多显示 {limit} 条）\n")
            
            # 准备表格数据
            table_data = []
            for doc in documents:
                table_data.append([
                    str(doc.id)[:8] + "...",  # UUID 截断显示
                    doc.stock_code,
                    doc.company_name[:20] + "..." if len(doc.company_name) > 20 else doc.company_name,
                    doc.market,
                    doc.doc_type,
                    doc.year,
                    doc.quarter or "N/A",
                    doc.status,
                    doc.file_size or "N/A",
                    doc.created_at.strftime("%Y-%m-%d %H:%M") if doc.created_at else "N/A",
                ])
            
            headers = [
                "ID",
                "股票代码",
                "公司名称",
                "市场",
                "文档类型",
                "年份",
                "季度",
                "状态",
                "文件大小",
                "创建时间"
            ]
            
            if HAS_TABULATE:
                print(tabulate(table_data, headers=headers, tablefmt="grid"))
            else:
                # 简单格式输出
                print(" | ".join(headers))
                print("-" * 120)
                for row in table_data:
                    print(" | ".join(str(cell) for cell in row))
            
            # 统计信息
            print("\n📈 统计信息:")
            status_counts = {}
            for doc in documents:
                status_counts[doc.status] = status_counts.get(doc.status, 0) + 1
            
            for status, count in sorted(status_counts.items()):
                print(f"  - {status}: {count}")
            
    except Exception as e:
        print(f"❌ 查询失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def query_documents_sql(sql: str):
    """执行自定义 SQL 查询"""
    pg_client = get_postgres_client()
    
    try:
        with pg_client.get_session() as session:
            from sqlalchemy import text
            result = session.execute(text(sql))
            
            # 获取列名
            columns = result.keys()
            
            # 获取所有行
            rows = result.fetchall()
            
            if not rows:
                print("📭 查询结果为空")
                return
            
            print(f"📊 查询结果: {len(rows)} 行\n")
            
            # 显示结果
            table_data = [list(row) for row in rows]
            if HAS_TABULATE:
                print(tabulate(table_data, headers=columns, tablefmt="grid"))
            else:
                # 简单格式输出
                print(" | ".join(columns))
                print("-" * 120)
                for row in table_data:
                    print(" | ".join(str(cell) for cell in row))
            
    except Exception as e:
        print(f"❌ SQL 执行失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="查询 documents 表")
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="限制返回的记录数（默认: 100）"
    )
    parser.add_argument(
        "--sql",
        type=str,
        help="执行自定义 SQL 查询（例如: 'SELECT * FROM documents LIMIT 10'）"
    )
    
    args = parser.parse_args()
    
    if args.sql:
        print(f"🔍 执行 SQL: {args.sql}\n")
        query_documents_sql(args.sql)
    else:
        query_all_documents(limit=args.limit)
