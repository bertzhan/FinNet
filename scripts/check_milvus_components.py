#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 Milvus 组件状态
"""

import sys
from pathlib import Path
import time

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from pymilvus import connections, utility, MilvusException
except ImportError:
    print("❌ 错误: 未安装 pymilvus")
    print("   请运行: pip install pymilvus")
    sys.exit(1)

from src.common.config import milvus_config


def check_milvus_connection():
    """检查 Milvus 连接和组件状态"""
    print("=" * 80)
    print("检查 Milvus 组件状态")
    print("=" * 80)
    print()
    
    # 显示配置信息
    print("Milvus 配置信息:")
    print(f"  Host: {milvus_config.MILVUS_HOST}")
    print(f"  Port: {milvus_config.MILVUS_PORT}")
    print()
    
    # 尝试连接
    print("尝试连接 Milvus...")
    try:
        connections.connect(
            alias="default",
            host=milvus_config.MILVUS_HOST,
            port=str(milvus_config.MILVUS_PORT),
            user=milvus_config.MILVUS_USER,
            password=milvus_config.MILVUS_PASSWORD
        )
        print("✅ 连接成功")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        print()
        print("提示：")
        print("  - Milvus 可能还在启动中，请等待几分钟后重试")
        print("  - 检查 Milvus 日志: docker-compose logs -f milvus")
        print("  - 检查服务状态: docker-compose ps milvus")
        return False
    
    # 尝试列出 Collections
    print()
    print("检查 Collections...")
    try:
        collections = utility.list_collections()
        print(f"✅ 找到 {len(collections)} 个 Collections:")
        for col in collections:
            print(f"    - {col}")
    except Exception as e:
        print(f"⚠️  列出 Collections 失败: {e}")
        print("   这可能是因为组件还在初始化中")
    
    # 断开连接
    connections.disconnect("default")
    
    print()
    print("=" * 80)
    print("✅ 检查完成")
    print("=" * 80)
    
    return True


def wait_for_milvus_ready(max_wait_minutes=5):
    """等待 Milvus 就绪"""
    print("=" * 80)
    print("等待 Milvus 就绪")
    print("=" * 80)
    print()
    
    max_attempts = max_wait_minutes * 12  # 每 5 秒检查一次
    check_interval = 5
    
    for attempt in range(1, max_attempts + 1):
        print(f"尝试 {attempt}/{max_attempts}...", end=" ")
        
        try:
            connections.connect(
                alias="check",
                host=milvus_config.MILVUS_HOST,
                port=str(milvus_config.MILVUS_PORT),
                user=milvus_config.MILVUS_USER,
                password=milvus_config.MILVUS_PASSWORD
            )
            
            # 尝试列出 Collections（这会触发组件检查）
            try:
                collections = utility.list_collections()
                connections.disconnect("check")
                print("✅ Milvus 已就绪！")
                print(f"   找到 {len(collections)} 个 Collections")
                return True
            except Exception as e:
                connections.disconnect("check")
                print(f"⚠️  组件可能还在初始化: {e}")
                
        except Exception as e:
            print(f"❌ 连接失败: {type(e).__name__}")
        
        if attempt < max_attempts:
            time.sleep(check_interval)
    
    print()
    print("❌ Milvus 在 {max_wait_minutes} 分钟内未能就绪")
    print()
    print("建议：")
    print("  1. 检查 Milvus 日志: docker-compose logs -f milvus")
    print("  2. 检查服务状态: docker-compose ps")
    print("  3. 如果问题持续，尝试重启: docker-compose restart milvus")
    print("  4. 如果仍有问题，可能需要清理 etcd 数据并重新启动")
    
    return False


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="检查 Milvus 组件状态")
    parser.add_argument(
        "--wait",
        type=int,
        default=0,
        help="等待 Milvus 就绪的最大分钟数（0 表示不等待）"
    )
    
    args = parser.parse_args()
    
    if args.wait > 0:
        success = wait_for_milvus_ready(max_wait_minutes=args.wait)
    else:
        success = check_milvus_connection()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
