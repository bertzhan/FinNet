#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查并修复 MinIO 配置
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.common.config import minio_config
from src.storage.object_store.minio_client import MinIOClient


def check_minio_config():
    """检查 MinIO 配置"""
    print("=" * 60)
    print("MinIO 配置检查")
    print("=" * 60)
    
    print(f"\n当前配置:")
    print(f"  Endpoint: {minio_config.MINIO_ENDPOINT}")
    print(f"  Access Key: {minio_config.MINIO_ACCESS_KEY}")
    print(f"  Secret Key: {'*' * len(minio_config.MINIO_SECRET_KEY)}")
    print(f"  Bucket: {minio_config.MINIO_BUCKET}")
    print(f"  Secure: {minio_config.MINIO_SECURE}")
    
    # 检查环境变量
    print(f"\n环境变量:")
    env_vars = {
        'MINIO_ENDPOINT': os.getenv('MINIO_ENDPOINT'),
        'MINIO_ACCESS_KEY': os.getenv('MINIO_ACCESS_KEY'),
        'MINIO_SECRET_KEY': os.getenv('MINIO_SECRET_KEY'),
        'MINIO_BUCKET': os.getenv('MINIO_BUCKET'),
        'MINIO_ROOT_USER': os.getenv('MINIO_ROOT_USER'),
        'MINIO_ROOT_PASSWORD': os.getenv('MINIO_ROOT_PASSWORD'),
    }
    
    for key, value in env_vars.items():
        if value:
            if 'SECRET' in key or 'PASSWORD' in key:
                display_value = '*' * len(value)
            else:
                display_value = value
            print(f"  {key}: {display_value}")
        else:
            print(f"  {key}: (未设置)")
    
    # 尝试连接
    print(f"\n连接测试:")
    try:
        client = MinIOClient()
        print(f"  ✅ MinIO 客户端创建成功")
        
        # 尝试列出文件
        try:
            files = client.list_files(max_results=1)
            print(f"  ✅ MinIO 连接成功")
            print(f"  ✅ 桶 '{client.bucket}' 可访问")
            return True
        except Exception as e:
            print(f"  ❌ MinIO 连接失败: {e}")
            print(f"\n建议:")
            print(f"  1. 检查 MinIO 服务是否运行: docker-compose ps minio")
            print(f"  2. 检查环境变量配置:")
            print(f"     MINIO_ENDPOINT={minio_config.MINIO_ENDPOINT}")
            print(f"     MINIO_ACCESS_KEY={minio_config.MINIO_ACCESS_KEY}")
            print(f"     MINIO_SECRET_KEY=***")
            print(f"  3. 根据 docker-compose.yml，MinIO 使用:")
            print(f"     MINIO_ROOT_USER: admin")
            print(f"     MINIO_ROOT_PASSWORD: admin123456")
            print(f"     所以访问密钥应该是:")
            print(f"     MINIO_ACCESS_KEY=admin")
            print(f"     MINIO_SECRET_KEY=admin123456")
            return False
            
    except Exception as e:
        print(f"  ❌ MinIO 客户端创建失败: {e}")
        return False


def show_fix_instructions():
    """显示修复说明"""
    print("\n" + "=" * 60)
    print("修复说明")
    print("=" * 60)
    
    print("\n方法 1: 更新 .env 文件")
    print("-" * 60)
    print("在项目根目录的 .env 文件中添加或更新以下配置:")
    print("")
    print("MINIO_ENDPOINT=localhost:9000")
    print("MINIO_ACCESS_KEY=admin")
    print("MINIO_SECRET_KEY=admin123456")
    print("MINIO_BUCKET=company-datalake")
    print("MINIO_SECURE=false")
    
    print("\n方法 2: 设置环境变量")
    print("-" * 60)
    print("export MINIO_ENDPOINT=localhost:9000")
    print("export MINIO_ACCESS_KEY=admin")
    print("export MINIO_SECRET_KEY=admin123456")
    print("export MINIO_BUCKET=company-datalake")
    print("export MINIO_SECURE=false")
    
    print("\n方法 3: 检查 docker-compose.yml")
    print("-" * 60)
    print("确保 MinIO 服务使用以下凭据:")
    print("  MINIO_ROOT_USER: admin")
    print("  MINIO_ROOT_PASSWORD: admin123456")
    print("")
    print("然后确保应用使用相同的凭据:")
    print("  MINIO_ACCESS_KEY = MINIO_ROOT_USER = admin")
    print("  MINIO_SECRET_KEY = MINIO_ROOT_PASSWORD = admin123456")


def main():
    """主函数"""
    success = check_minio_config()
    
    if not success:
        show_fix_instructions()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ MinIO 配置正确，连接成功！")
    else:
        print("⚠️ MinIO 配置需要修复")
    print("=" * 60)


if __name__ == '__main__':
    main()
