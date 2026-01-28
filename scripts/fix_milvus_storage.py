#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复 Milvus 存储空间问题
提供多种解决方案
"""

import sys
import subprocess
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_docker_containers():
    """检查 Docker 容器状态"""
    print("=" * 80)
    print("检查 Docker 容器状态")
    print("=" * 80)
    print()
    
    containers = ["finnet-milvus", "finnet-minio-milvus", "finnet-etcd"]
    
    for container in containers:
        try:
            result = subprocess.run(
                ["docker", "ps", "-a", "--filter", f"name={container}", "--format", "{{.Names}}\t{{.Status}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                if output:
                    print(f"  {output}")
                else:
                    print(f"  ⚠️  {container}: 容器不存在")
        except Exception as e:
            print(f"  ⚠️  检查 {container} 失败: {e}")


def restart_milvus():
    """重启 Milvus 服务"""
    print("\n" + "=" * 80)
    print("重启 Milvus 服务")
    print("=" * 80)
    print()
    
    print("重启 Milvus 容器...")
    try:
        result = subprocess.run(
            ["docker", "restart", "finnet-milvus"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print("✅ Milvus 容器已重启")
        else:
            print(f"❌ 重启失败: {result.stderr}")
    except Exception as e:
        print(f"❌ 重启失败: {e}")


def clean_milvus_logs():
    """清理 Milvus 日志"""
    print("\n" + "=" * 80)
    print("清理 Milvus 日志")
    print("=" * 80)
    print()
    
    print("清理 Milvus 容器日志...")
    try:
        # 清理日志（保留最近100行）
        result = subprocess.run(
            ["docker", "exec", "finnet-milvus", "sh", "-c", "find /var/lib/milvus/logs -name '*.log' -type f -exec truncate -s 0 {} \\;"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print("✅ 日志已清理")
        else:
            print(f"⚠️  清理日志失败: {result.stderr}")
    except Exception as e:
        print(f"⚠️  清理日志失败: {e}")


def show_solutions():
    """显示解决方案"""
    print("\n" + "=" * 80)
    print("解决方案")
    print("=" * 80)
    print()
    
    print("方案1: 调整 MinIO 最小可用空间阈值（推荐）")
    print("-" * 80)
    print("编辑 docker-compose.yml，在 minio-milvus 服务中添加环境变量:")
    print("  environment:")
    print("    MINIO_ACCESS_KEY: ${MINIO_ACCESS_KEY:-minioadmin}")
    print("    MINIO_SECRET_KEY: ${MINIO_SECRET_KEY:-minioadmin}")
    print("    MINIO_STORAGE_CLASS_STANDARD: EC:2")  # 可选：启用纠删码
    print()
    print("或者通过 MinIO 客户端设置:")
    print("  mc admin config set <alias> storage_class standard EC:2")
    print()
    
    print("方案2: 清理 Milvus 数据")
    print("-" * 80)
    print("1. 删除不需要的 Collection:")
    print("   python scripts/clean_milvus_storage.py --interactive")
    print()
    print("2. 清理 Milvus 日志:")
    print("   docker exec finnet-milvus sh -c 'rm -rf /var/lib/milvus/logs/*.log'")
    print()
    
    print("方案3: 扩展存储空间")
    print("-" * 80)
    print("1. 增加磁盘容量")
    print("2. 或迁移到更大的存储卷")
    print()
    
    print("方案4: 临时解决方案 - 重启服务")
    print("-" * 80)
    print("有时重启可以释放一些临时文件:")
    print("  docker restart finnet-milvus finnet-minio-milvus")


def main():
    """主函数"""
    print("=" * 80)
    print("修复 Milvus 存储空间问题")
    print("=" * 80)
    print()
    
    # 检查容器状态
    check_docker_containers()
    
    # 显示解决方案
    show_solutions()
    
    # 询问是否执行操作
    print("\n" + "=" * 80)
    response = input("是否重启 Milvus 服务? (yes/no): ")
    if response.lower() == 'yes':
        restart_milvus()
    
    print("\n" + "=" * 80)
    response = input("是否清理 Milvus 日志? (yes/no): ")
    if response.lower() == 'yes':
        clean_milvus_logs()
    
    print("\n" + "=" * 80)
    print("完成！")
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n操作已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 操作失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
