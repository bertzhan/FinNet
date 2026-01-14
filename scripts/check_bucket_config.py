#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 MinIO bucket 配置
诊断为什么仍然使用 company-datalake 而不是 finnet-datalake
"""

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common.config import minio_config

def main():
    print("=" * 60)
    print("MinIO Bucket 配置检查")
    print("=" * 60)
    
    # 检查环境变量
    env_bucket = os.getenv("MINIO_BUCKET")
    print(f"\n1. 环境变量 MINIO_BUCKET:")
    if env_bucket:
        print(f"   ✅ 已设置: {env_bucket}")
        if env_bucket == "company-datalake":
            print(f"   ⚠️  警告: 环境变量设置为旧值 'company-datalake'")
            print(f"   💡 建议: 更新为 'finnet-datalake' 或删除环境变量使用默认值")
    else:
        print(f"   ℹ️  未设置（将使用代码中的默认值）")
    
    # 检查配置文件中的值
    print(f"\n2. 代码中的默认值:")
    print(f"   src/common/config.py: 'finnet-datalake'")
    
    # 检查实际加载的配置值
    print(f"\n3. 实际加载的配置值:")
    print(f"   minio_config.MINIO_BUCKET: '{minio_config.MINIO_BUCKET}'")
    
    if minio_config.MINIO_BUCKET == "company-datalake":
        print(f"   ❌ 问题: 配置值仍然是 'company-datalake'")
        print(f"\n   可能的原因:")
        print(f"   1. 环境变量 MINIO_BUCKET=company-datalake 覆盖了默认值")
        print(f"   2. .env 文件中设置了 MINIO_BUCKET=company-datalake")
        print(f"\n   解决方法:")
        print(f"   1. 检查并更新环境变量:")
        print(f"      export MINIO_BUCKET=finnet-datalake")
        print(f"   2. 检查并更新 .env 文件:")
        print(f"      MINIO_BUCKET=finnet-datalake")
        print(f"   3. 或者删除环境变量/.env 中的设置，使用代码默认值")
    elif minio_config.MINIO_BUCKET == "finnet-datalake":
        print(f"   ✅ 正确: 配置值已经是 'finnet-datalake'")
    else:
        print(f"   ⚠️  未知值: '{minio_config.MINIO_BUCKET}'")
    
    # 检查 .env 文件
    env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    print(f"\n4. .env 文件检查:")
    if os.path.exists(env_file):
        print(f"   ✅ .env 文件存在: {env_file}")
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith("MINIO_BUCKET"):
                    print(f"   📝 找到配置: {line}")
                    if "company-datalake" in line:
                        print(f"   ⚠️  警告: .env 文件中包含旧值 'company-datalake'")
    else:
        print(f"   ℹ️  .env 文件不存在（将使用环境变量或默认值）")
    
    print("\n" + "=" * 60)
    print("检查完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
