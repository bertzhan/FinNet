#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 Milvus 存储空间使用情况
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.object_store.minio_client import MinIOClient
from src.common.config import milvus_config


def get_directory_size(path: str) -> int:
    """获取目录大小（字节）"""
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total += os.path.getsize(filepath)
    except Exception as e:
        print(f"  计算目录大小失败: {e}")
    return total


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def check_milvus_storage():
    """检查 Milvus 存储空间"""
    print("=" * 80)
    print("检查 Milvus 存储空间使用情况")
    print("=" * 80)
    print()
    
    # 检查 Docker 卷
    print("1. 检查 Docker 卷存储...")
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "volume", "inspect", "finnet_minio_milvus_data", "--format", "{{.Mountpoint}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            mount_point = result.stdout.strip()
            if mount_point:
                print(f"  MinIO Milvus 数据卷挂载点: {mount_point}")
                size = get_directory_size(mount_point)
                print(f"  存储使用: {format_size(size)}")
            else:
                print("  ⚠️  未找到挂载点")
        else:
            print("  ⚠️  无法获取卷信息（可能需要 Docker 权限）")
    except Exception as e:
        print(f"  ⚠️  检查 Docker 卷失败: {e}")
    
    print()
    
    # 检查 Milvus 数据卷
    print("2. 检查 Milvus 数据卷...")
    try:
        result = subprocess.run(
            ["docker", "volume", "inspect", "finnet_milvus_data", "--format", "{{.Mountpoint}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            mount_point = result.stdout.strip()
            if mount_point:
                print(f"  Milvus 数据卷挂载点: {mount_point}")
                size = get_directory_size(mount_point)
                print(f"  存储使用: {format_size(size)}")
            else:
                print("  ⚠️  未找到挂载点")
        else:
            print("  ⚠️  无法获取卷信息（可能需要 Docker 权限）")
    except Exception as e:
        print(f"  ⚠️  检查 Docker 卷失败: {e}")
    
    print()
    
    # 检查磁盘空间
    print("3. 检查磁盘空间...")
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        print(f"  总空间: {format_size(total)}")
        print(f"  已使用: {format_size(used)} ({used/total*100:.1f}%)")
        print(f"  可用空间: {format_size(free)} ({free/total*100:.1f}%)")
        
        if free < 1024 * 1024 * 1024:  # 小于 1GB
            print("  ⚠️  警告：可用空间不足 1GB，可能导致 Milvus 无法正常工作")
    except Exception as e:
        print(f"  ⚠️  检查磁盘空间失败: {e}")
    
    print()
    print("=" * 80)
    print("清理建议:")
    print("=" * 80)
    print("1. 清理 Milvus 旧数据:")
    print("   - 删除不需要的 Collection")
    print("   - 清理 Milvus 日志文件")
    print()
    print("2. 清理 MinIO Milvus 存储:")
    print("   - 删除不需要的对象")
    print("   - 清理过期数据")
    print()
    print("3. 扩展存储空间:")
    print("   - 增加磁盘容量")
    print("   - 或迁移到更大的存储卷")
    print()
    print("4. 调整 Milvus 配置:")
    print("   - 降低最小可用空间阈值（如果支持）")
    print("   - 启用数据压缩")


if __name__ == "__main__":
    check_milvus_storage()
