#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导出 listed_companies 表为 CSV 文件
"""

import csv
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud


def export_listed_companies_to_csv(output_path: str = "listed_companies.csv"):
    """
    导出 listed_companies 表为 CSV 文件
    
    Args:
        output_path: 输出 CSV 文件路径（默认：listed_companies.csv）
    """
    print(f"开始导出 listed_companies 表...")
    
    try:
        pg_client = get_postgres_client()
        
        with pg_client.get_session() as session:
            # 获取所有上市公司数据
            companies = crud.get_all_listed_companies(session, limit=None)
            
            if not companies:
                print("⚠️ 表中没有数据")
                return
            
            # 写入 CSV 文件
            with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                
                # 写入表头
                writer.writerow(['code', 'name', 'created_at', 'updated_at'])
                
                # 写入数据
                for company in companies:
                    writer.writerow([
                        company.code,
                        company.name,
                        company.created_at.isoformat() if company.created_at else '',
                        company.updated_at.isoformat() if company.updated_at else ''
                    ])
            
            print(f"✅ 导出成功！")
            print(f"   文件路径: {output_path}")
            print(f"   记录数量: {len(companies)}")
            print(f"   字段: code, name, created_at, updated_at")
            
    except Exception as e:
        print(f"❌ 导出失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="导出 listed_companies 表为 CSV")
    parser.add_argument(
        "-o", "--output",
        default="listed_companies.csv",
        help="输出 CSV 文件路径（默认: listed_companies.csv）"
    )
    
    args = parser.parse_args()
    export_listed_companies_to_csv(args.output)
