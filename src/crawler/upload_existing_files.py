#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
上传已有文件到MinIO
将本地已爬取的文件上传到MinIO
"""

import os
import sys
import glob
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def upload_existing_files(reports_dir="./reports", dry_run=False):
    """
    上传已有的PDF文件到MinIO
    
    Args:
        reports_dir: 报告目录
        dry_run: 如果为True，只显示将要上传的文件，不实际上传
    """
    from src.crawler.config import CrawlerConfig
    from src.crawler.minio_storage import create_minio_storage_from_config
    from src.crawler.base_crawler import Market, DocType, CrawlTask
    
    # 检查配置
    config = CrawlerConfig.from_env()
    
    if not config.use_minio:
        print("❌ MinIO未启用")
        print("\n请先设置环境变量:")
        print("  export USE_MINIO=true")
        print("  export MINIO_ENDPOINT=http://localhost:9000")
        print("  export MINIO_ACCESS_KEY=admin")
        print("  export MINIO_SECRET_KEY=admin123456")
        print("  export MINIO_BUCKET=finnet-datalake")
        return False
    
    # 创建MinIO存储实例
    minio_storage = create_minio_storage_from_config(config)
    if minio_storage is None:
        print("❌ 无法创建MinIO存储实例")
        return False
    
    print("=" * 60)
    print("上传已有文件到MinIO")
    print("=" * 60)
    print(f"报告目录: {reports_dir}")
    print(f"MinIO桶: {config.minio_bucket}")
    print(f"模式: {'预览模式（不实际上传）' if dry_run else '实际上传'}")
    print()
    
    # 查找所有PDF文件
    pdf_files = []
    for pattern in ["SZ/**/*.pdf", "SH/**/*.pdf", "BJ/**/*.pdf"]:
        pdf_files.extend(glob.glob(os.path.join(reports_dir, pattern), recursive=True))
    
    if not pdf_files:
        print("❌ 未找到PDF文件")
        return False
    
    print(f"找到 {len(pdf_files)} 个PDF文件\n")
    
    # 解析文件路径，生成MinIO对象名称
    upload_tasks = []
    
    for pdf_path in pdf_files:
        # 解析路径: reports/SZ/000001/2023/000001_2023_Q1_29-04-2023.pdf
        parts = pdf_path.replace(reports_dir, "").strip("/").split("/")
        
        if len(parts) < 4:
            print(f"⚠️  跳过无法解析的文件: {pdf_path}")
            continue
        
        exchange = parts[0]  # SZ, SH, BJ
        stock_code = parts[1]
        year = parts[2]
        filename = parts[3]
        
        # 解析文件名: 000001_2023_Q1_29-04-2023.pdf
        name_parts = filename.replace(".pdf", "").split("_")
        if len(name_parts) < 3:
            print(f"⚠️  跳过文件名格式异常的文件: {filename}")
            continue
        
        file_stock_code = name_parts[0]
        file_year = name_parts[1]
        quarter_str = name_parts[2]  # Q1, Q2, Q3, Q4
        
        # 验证一致性
        if stock_code != file_stock_code or year != file_year:
            print(f"⚠️  路径与文件名不一致: {pdf_path}")
            continue
        
        # 确定市场类型
        market_map = {
            "SZ": Market.A_SHARE,
            "SH": Market.A_SHARE,
            "BJ": Market.A_SHARE,
        }
        market = market_map.get(exchange, Market.A_SHARE)
        
        # 确定文档类型
        quarter_num = int(quarter_str[1]) if quarter_str.startswith("Q") else 4
        if quarter_num == 4:
            doc_type = DocType.ANNUAL_REPORT
        elif quarter_num == 2:
            doc_type = DocType.INTERIM_REPORT
        else:
            doc_type = DocType.QUARTERLY_REPORT
        
        # 生成MinIO对象名称
        # 格式: bronze/zh_stock/quarterly_reports/{year}/{quarter}/{stock_code}/{filename}
        object_name = f"bronze/{market.value}/{doc_type.value}/{year}/{quarter_str}/{stock_code}/{filename}"
        
        upload_tasks.append({
            "local_path": pdf_path,
            "object_name": object_name,
            "stock_code": stock_code,
            "year": year,
            "quarter": quarter_str,
        })
    
    print(f"准备上传 {len(upload_tasks)} 个文件\n")
    
    # 显示前10个文件
    print("前10个文件预览:")
    for i, task in enumerate(upload_tasks[:10], 1):
        print(f"  {i}. {task['stock_code']} {task['year']} {task['quarter']}")
        print(f"     本地: {task['local_path']}")
        print(f"     MinIO: {task['object_name']}")
    
    if len(upload_tasks) > 10:
        print(f"  ... 还有 {len(upload_tasks) - 10} 个文件")
    
    if dry_run:
        print("\n✅ 预览完成（未实际上传）")
        print("要实际上传，运行: python src/crawler/upload_existing_files.py --upload")
        return True
    
    # 实际上传
    print("\n" + "=" * 60)
    print("开始上传...")
    print("=" * 60)
    
    success_count = 0
    fail_count = 0
    
    for i, task in enumerate(upload_tasks, 1):
        local_path = task['local_path']
        object_name = task['object_name']
        
        # 检查文件是否已存在
        if minio_storage.file_exists(object_name):
            print(f"[{i}/{len(upload_tasks)}] ⏭️  已存在，跳过: {object_name}")
            success_count += 1
            continue
        
        print(f"[{i}/{len(upload_tasks)}] 上传: {task['stock_code']} {task['year']} {task['quarter']}")
        
        success = minio_storage.upload_file(
            local_path,
            object_name,
            content_type='application/pdf'
        )
        
        if success:
            success_count += 1
        else:
            fail_count += 1
    
    print("\n" + "=" * 60)
    print("上传完成")
    print("=" * 60)
    print(f"✅ 成功: {success_count}")
    print(f"❌ 失败: {fail_count}")
    print(f"📊 总计: {len(upload_tasks)}")
    
    if success_count > 0:
        print(f"\n✅ 已成功上传 {success_count} 个文件到MinIO")
        print("现在可以在MinIO UI中查看文件了！")
        print("访问: http://localhost:9001")
    
    return fail_count == 0


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="上传已有文件到MinIO")
    parser.add_argument("--reports-dir", default="./reports", help="报告目录（默认: ./reports）")
    parser.add_argument("--upload", action="store_true", help="实际上传（默认只预览）")
    parser.add_argument("--dry-run", action="store_true", help="预览模式（不实际上传）")
    
    args = parser.parse_args()
    
    dry_run = not args.upload and not args.dry_run  # 默认是预览模式
    
    if args.upload:
        dry_run = False
    
    success = upload_existing_files(args.reports_dir, dry_run=dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
