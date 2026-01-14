#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 MinIO 中的文件
用于验证爬取的文件是否已上传到 MinIO
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.object_store.minio_client import MinIOClient
from collections import defaultdict

def main():
    print("=" * 60)
    print("检查 MinIO 中的文件")
    print("=" * 60)
    print()
    
    try:
        client = MinIOClient()
        
        # 统计各路径的文件数量
        stats = defaultdict(int)
        total_size = 0
        files = []
        
        # 列出所有 bronze 层的文件
        print("正在列出文件...")
        file_list = client.list_files(prefix="bronze/", recursive=True)
        
        for file_info in file_list:
            obj_name = file_info['name']
            obj_size = file_info['size']
            
            path_parts = obj_name.split('/')
            if len(path_parts) >= 2:
                category = f"{path_parts[0]}/{path_parts[1]}"  # bronze/a_share
                stats[category] += 1
            total_size += obj_size
            files.append((obj_name, obj_size))
        
        print(f"✅ 找到 {len(files)} 个文件，总大小: {total_size / 1024 / 1024:.2f} MB")
        print()
        
        # 按类别统计
        if stats:
            print("📊 文件分布:")
            for category, count in sorted(stats.items()):
                print(f"  {category}: {count} 个文件")
            print()
        
        # 显示最近的文件（最多20个）
        if files:
            print("📄 文件列表（最多显示20个）:")
            for obj_name, size in files[:20]:
                print(f"  {obj_name} ({size / 1024:.2f} KB)")
            
            if len(files) > 20:
                print(f"  ... 还有 {len(files) - 20} 个文件")
        else:
            print("⚠️  未找到任何文件")
            print()
            print("可能的原因:")
            print("1. 文件还未上传")
            print("2. 路径前缀不匹配")
            print("3. MinIO 配置不正确")
            print()
            print("建议:")
            print("1. 检查 Dagster UI 中的运行日志")
            print("2. 查看是否有 'MinIO 上传成功' 的日志")
            print("3. 确认 enable_minio 配置为 true")
            print("4. 访问 MinIO Console: http://localhost:9001")
        
        print()
        print("=" * 60)
        print("检查完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
