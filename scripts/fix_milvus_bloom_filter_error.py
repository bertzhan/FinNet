#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复 Milvus bloom filter 初始化错误
错误: failed to init bloom filter / NoSuchKey(key=files/stats_log/...)
"""

import sys
from pathlib import Path

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


def list_collections():
    """列出所有 Collections"""
    try:
        collections = utility.list_collections()
        return collections
    except MilvusException as e:
        print(f"❌ 列出 Collections 失败: {e}")
        return []


def drop_collection(collection_name: str):
    """删除 Collection"""
    try:
        utility.drop_collection(collection_name)
        return True
    except MilvusException as e:
        print(f"  ❌ 删除失败: {e}")
        return False


def connect_milvus_with_retry(max_retries=5, wait_seconds=3):
    """连接 Milvus，带重试机制"""
    for attempt in range(1, max_retries + 1):
        try:
            connections.connect(
                alias="default",
                host=milvus_config.MILVUS_HOST,
                port=str(milvus_config.MILVUS_PORT),
                user=milvus_config.MILVUS_USER,
                password=milvus_config.MILVUS_PASSWORD
            )
            print(f"✅ 连接成功")
            return True
        except Exception as e:
            if attempt < max_retries:
                print(f"⚠️  连接失败 (尝试 {attempt}/{max_retries})，{wait_seconds} 秒后重试...")
                print(f"   错误: {e}")
                import time
                time.sleep(wait_seconds)
            else:
                print(f"❌ 连接失败 (已重试 {max_retries} 次): {e}")
                print()
                print("提示：")
                print("  1. 请检查 Milvus 服务是否运行: docker-compose ps milvus")
                print("  2. 如果服务未运行，请启动: docker-compose up -d milvus")
                print("  3. 如果服务正在启动，请等待几秒钟后重试")
                return False
    return False


def fix_by_dropping_collections(confirm: bool = False):
    """方案1: 删除所有 Collections（推荐，如果数据可以重新生成）"""
    print("=" * 80)
    print("方案1: 删除所有 Collections")
    print("=" * 80)
    print()
    print("⚠️  警告：此操作将删除所有向量数据！")
    print("   如果数据可以重新生成（通过重新运行 vectorize job），这是最简单的修复方法。")
    print()
    
    if not confirm:
        response = input("确认删除所有 Collections? (yes/no): ")
        if response.lower() != 'yes':
            print("取消操作")
            return False
    else:
        print("自动确认删除（--yes 参数）")
    
    # 连接 Milvus（带重试）
    print()
    print("连接 Milvus...")
    if not connect_milvus_with_retry():
        return False
    
    # 列出所有 Collections
    print()
    print("列出所有 Collections...")
    collections = list_collections()
    
    if not collections:
        print("  没有找到任何 Collection")
        connections.disconnect("default")
        print()
        print("✅ 没有需要删除的 Collections")
        return True
    
    print(f"  找到 {len(collections)} 个 Collections:")
    for col in collections:
        print(f"    - {col}")
    
    # 删除所有 Collections
    print()
    print("删除 Collections...")
    success_count = 0
    failed_count = 0
    
    for col_name in collections:
        print(f"  正在删除: {col_name}...", end=" ")
        if drop_collection(col_name):
            print("✅")
            success_count += 1
        else:
            print("❌")
            failed_count += 1
    
    connections.disconnect("default")
    
    print()
    print("-" * 80)
    print(f"删除完成: 成功 {success_count} 个，失败 {failed_count} 个")
    print()
    print("✅ 修复完成！请重启 Milvus 服务：")
    print("   docker-compose restart milvus")
    print()
    
    return success_count > 0


def check_milvus_service():
    """检查 Milvus 服务状态"""
    import subprocess
    try:
        result = subprocess.run(
            "docker ps --filter 'name=finnet-milvus' --format '{{.Status}}'",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            status = result.stdout.strip()
            print(f"  Milvus 服务状态: {status}")
            if "healthy" in status.lower():
                return True
            elif "starting" in status.lower():
                print("  ⚠️  Milvus 正在启动中，请稍候...")
                return False
            else:
                print("  ⚠️  Milvus 服务状态异常")
                return False
        else:
            print("  ❌ 无法获取 Milvus 服务状态")
            return False
    except Exception as e:
        print(f"  ⚠️  检查服务状态失败: {e}")
        return False


def fix_by_cleaning_minio(confirm: bool = False):
    """方案2: 清理 MinIO 中的 stats_log 目录"""
    print("=" * 80)
    print("方案2: 清理 MinIO 中的 stats_log 目录")
    print("=" * 80)
    print()
    print("此方案将清理 MinIO 中损坏的 stats_log 文件。")
    print("⚠️  警告：这可能会删除一些统计信息，但不会删除向量数据本身。")
    print()
    
    # 检查 Milvus 服务状态
    print("检查 Milvus 服务状态...")
    check_milvus_service()
    print()
    
    if not confirm:
        response = input("确认清理 MinIO stats_log? (yes/no): ")
        if response.lower() != 'yes':
            print("取消操作")
            return False
    else:
        print("自动确认清理（--yes 参数）")
    
    print()
    print("执行清理命令...")
    print()
    
    import subprocess
    
    # 清理 stats_log 目录
    commands = [
        # 删除 stats_log 目录
        "docker exec finnet-minio-milvus sh -c 'rm -rf /data/a-bucket/files/stats_log/*'",
        # 或者删除整个 files 目录（更彻底）
        # "docker exec finnet-minio-milvus sh -c 'rm -rf /data/a-bucket/files/*'",
    ]
    
    for cmd in commands:
        print(f"执行: {cmd}")
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                print(f"✅ 成功")
                if result.stdout:
                    print(f"   输出: {result.stdout.strip()}")
            else:
                print(f"❌ 失败 (退出码: {result.returncode})")
                if result.stderr:
                    print(f"   错误: {result.stderr.strip()}")
        except Exception as e:
            print(f"❌ 执行失败: {e}")
    
    print()
    print("✅ 清理完成！请重启 Milvus 服务：")
    print("   docker-compose restart milvus")
    print()
    
    return True


def fix_by_resetting_milvus(confirm: bool = False):
    """方案3: 完全重置 Milvus"""
    print("=" * 80)
    print("方案3: 完全重置 Milvus")
    print("=" * 80)
    print()
    print("⚠️  警告：此操作将：")
    print("   1. 停止 Milvus、MinIO、etcd 服务")
    print("   2. 删除所有 Milvus 相关的 Docker volumes")
    print("   3. 删除 MinIO 中的所有数据")
    print("   4. 重新启动服务")
    print()
    print("这将完全清除所有向量数据！")
    print()
    
    if not confirm:
        response = input("确认完全重置 Milvus? (yes/no): ")
        if response.lower() != 'yes':
            print("取消操作")
            return False
    else:
        print("自动确认重置（--yes 参数）")
    
    print()
    print("执行重置命令...")
    print()
    
    import subprocess
    
    commands = [
        # 停止服务
        "docker-compose stop milvus minio-milvus etcd",
        # 删除 volumes
        "docker volume rm finnet_milvus_data finnet_milvus_config finnet_minio_milvus_data finnet_etcd_data 2>/dev/null || true",
        # 清理 MinIO 数据
        "docker exec finnet-minio-milvus sh -c 'rm -rf /data/a-bucket/*' 2>/dev/null || true",
        # 重新启动服务
        "docker-compose up -d milvus minio-milvus etcd",
    ]
    
    for cmd in commands:
        print(f"执行: {cmd}")
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                print(f"✅ 成功")
            else:
                print(f"⚠️  退出码: {result.returncode}")
                if result.stderr:
                    print(f"   错误: {result.stderr.strip()}")
        except Exception as e:
            print(f"❌ 执行失败: {e}")
    
    print()
    print("✅ 重置完成！")
    print("   请等待几秒钟让服务启动，然后检查状态：")
    print("   docker-compose ps")
    print()
    
    return True


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="修复 Milvus bloom filter 初始化错误",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
修复选项：
  1. drop-collections  - 删除所有 Collections（推荐，如果数据可以重新生成）
  2. clean-minio       - 清理 MinIO 中的 stats_log 目录
  3. reset-milvus      - 完全重置 Milvus（最彻底，但会删除所有数据）

如果没有指定选项，将显示交互式菜单。
        """
    )
    parser.add_argument(
        "--method",
        choices=["drop-collections", "clean-minio", "reset-milvus"],
        help="修复方法"
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="自动确认（不询问）"
    )
    
    args = parser.parse_args()
    
    if args.method:
        # 直接执行指定方法
        if args.method == "drop-collections":
            success = fix_by_dropping_collections(confirm=args.yes)
        elif args.method == "clean-minio":
            success = fix_by_cleaning_minio(confirm=args.yes)
        elif args.method == "reset-milvus":
            success = fix_by_resetting_milvus(confirm=args.yes)
        else:
            print(f"❌ 未知方法: {args.method}")
            sys.exit(1)
        
        sys.exit(0 if success else 1)
    else:
        # 显示交互式菜单
        print("=" * 80)
        print("修复 Milvus bloom filter 初始化错误")
        print("=" * 80)
        print()
        print("错误信息: failed to init bloom filter / NoSuchKey(key=files/stats_log/...)")
        print()
        print("此错误通常是因为：")
        print("  1. MinIO 中的统计日志文件丢失或损坏")
        print("  2. Collection 或 Segment 的状态不一致")
        print("  3. 之前的清理操作删除了必要的文件")
        print()
        print("请选择修复方案：")
        print()
        print("  1. 删除所有 Collections（推荐）")
        print("     - 如果数据可以重新生成（通过重新运行 vectorize job）")
        print("     - 这是最简单、最可靠的修复方法")
        print()
        print("  2. 清理 MinIO 中的 stats_log 目录")
        print("     - 只清理统计日志，保留向量数据")
        print("     - 可能需要重启 Milvus")
        print()
        print("  3. 完全重置 Milvus")
        print("     - 停止服务，删除所有 volumes，重新启动")
        print("     - 最彻底，但会删除所有数据")
        print()
        
        try:
            choice = input("请选择 (1/2/3): ").strip()
            
            if choice == "1":
                success = fix_by_dropping_collections(confirm=args.yes)
            elif choice == "2":
                success = fix_by_cleaning_minio(confirm=args.yes)
            elif choice == "3":
                success = fix_by_resetting_milvus(confirm=args.yes)
            else:
                print("❌ 无效选择")
                sys.exit(1)
            
            sys.exit(0 if success else 1)
        except KeyboardInterrupt:
            print("\n\n操作已取消")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ 操作失败: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
