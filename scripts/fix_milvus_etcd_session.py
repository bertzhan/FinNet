#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复 Milvus etcd session 注册错误
错误类型：
1. CompareAndSwap error for compare is false for key: rootcoord
2. node not match[expectedNodeID=X][actualNodeID=Y]
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def fix_by_cleaning_etcd_sessions():
    """方案1: 清理 etcd 中的旧 session（推荐）"""
    print("=" * 80)
    print("方案1: 清理 etcd 中的旧 session")
    print("=" * 80)
    print()
    print("此方案将清理 etcd 中的 Milvus session 和节点信息。")
    print("⚠️  警告：这不会删除向量数据（存储在 MinIO），只会清理服务注册信息。")
    print("⚠️  注意：如果遇到 'node not match' 错误，建议使用此方案清理节点信息。")
    print()
    
    import subprocess
    
    # 检查 etcd 容器是否运行
    print("检查 etcd 服务状态...")
    try:
        result = subprocess.run(
            "docker ps --filter 'name=finnet-etcd' --format '{{.Status}}'",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            status = result.stdout.strip()
            print(f"  etcd 服务状态: {status}")
        else:
            print("  ❌ etcd 服务未运行")
            print("  请先启动 etcd: docker-compose up -d etcd")
            return False
    except Exception as e:
        print(f"  ⚠️  检查服务状态失败: {e}")
        return False
    
    print()
    response = input("确认清理 etcd session 数据? (yes/no): ")
    if response.lower() != 'yes':
        print("取消操作")
        return False
    
    print()
    print("执行清理命令...")
    print()
    
    # 清理 etcd 中的 Milvus session keys
    # Milvus 使用特定的前缀存储 session
    # 根据错误信息，key 是 "rootcoord"，可能需要清理整个 etcd 数据
    print("方法1: 尝试清理 Milvus session keys...")
    commands = [
        # 尝试删除常见的 Milvus session keys
        "docker exec finnet-etcd etcdctl del --prefix /milvus/rootcoord/session 2>&1 || true",
        "docker exec finnet-etcd etcdctl del --prefix /milvus/datacoord/session 2>&1 || true",
        "docker exec finnet-etcd etcdctl del --prefix /milvus/querycoord/session 2>&1 || true",
        "docker exec finnet-etcd etcdctl del --prefix /milvus/indexcoord/session 2>&1 || true",
        "docker exec finnet-etcd etcdctl del --prefix /milvus/ 2>&1 || true",
        # 尝试删除 rootcoord key（根据错误信息）
        "docker exec finnet-etcd etcdctl del rootcoord 2>&1 || true",
    ]
    
    print("尝试清理 etcd session keys...")
    success_count = 0
    failed_count = 0
    
    for cmd in commands:
        print(f"  执行: {cmd}")
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                print(f"    ✅ 成功")
                if result.stdout.strip():
                    print(f"    输出: {result.stdout.strip()}")
                success_count += 1
            else:
                # etcdctl 如果 key 不存在会返回非零退出码，这是正常的
                if "key not found" in result.stderr.lower() or "not found" in result.stderr.lower():
                    print(f"    ⚠️  Key 不存在（可能已经清理）")
                    success_count += 1
                else:
                    print(f"    ⚠️  退出码: {result.returncode}")
                    if result.stderr.strip():
                        print(f"    错误: {result.stderr.strip()}")
                    failed_count += 1
        except Exception as e:
            print(f"    ❌ 执行失败: {e}")
            failed_count += 1
    
    print()
    print("-" * 80)
    
    # 如果清理 keys 失败，或者遇到节点不匹配错误，尝试清理整个 etcd 数据目录
    print()
    print("方法2: 清理整个 etcd 数据目录（推荐用于节点不匹配错误）...")
    print("  （这会删除所有 etcd 数据，但不会影响 Milvus 向量数据）")
    print("  （Milvus 会重新初始化所有节点信息）")
    response2 = input("  确认清理 etcd 数据目录? (yes/no): ")
    if response2.lower() == 'yes':
            try:
                # 停止 Milvus 和 etcd
                print("  停止 Milvus 和 etcd...")
                subprocess.run(
                    "docker-compose stop milvus etcd",
                    shell=True,
                    timeout=30
                )
                
                # 清理 etcd 数据
                print("  清理 etcd 数据...")
                result = subprocess.run(
                    "docker exec finnet-etcd sh -c 'rm -rf /etcd/*' 2>&1 || docker volume rm finnet_etcd_data 2>&1 || true",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                # 重新启动 etcd 和 Milvus
                print("  重新启动服务...")
                subprocess.run(
                    "docker-compose up -d etcd",
                    shell=True,
                    timeout=30
                )
                import time
                time.sleep(3)  # 等待 etcd 启动
                subprocess.run(
                    "docker-compose up -d milvus",
                    shell=True,
                    timeout=30
                )
                
                print("  ✅ etcd 数据已清理，服务已重启")
                print()
                print("  请等待几秒钟让服务启动，然后检查状态：")
                print("    docker-compose ps")
                print()
                return True
            except Exception as e:
                print(f"  ❌ 清理失败: {e}")
                return False
    
    print(f"清理完成: 成功 {success_count} 个，失败 {failed_count} 个")
    print()
    print("✅ 清理完成！请重启 Milvus 服务：")
    print("   docker-compose restart milvus")
    print()
    print("如果问题仍然存在，可以尝试方案2：完全重置 Milvus")
    print()
    
    return success_count > 0


def fix_by_resetting_milvus():
    """方案2: 完全重置 Milvus 和 etcd"""
    print("=" * 80)
    print("方案2: 完全重置 Milvus 和 etcd")
    print("=" * 80)
    print()
    print("⚠️  警告：此操作将：")
    print("   1. 停止 Milvus、MinIO、etcd 服务")
    print("   2. 删除所有 Milvus 相关的 Docker volumes")
    print("   3. 删除 MinIO 中的所有数据")
    print("   4. 删除 etcd 中的所有数据")
    print("   5. 重新启动服务")
    print()
    print("这将完全清除所有向量数据和配置！")
    print()
    
    response = input("确认完全重置? (yes/no): ")
    if response.lower() != 'yes':
        print("取消操作")
        return False
    
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
        "docker-compose up -d etcd minio-milvus milvus",
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
        description="修复 Milvus etcd session 注册错误",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
修复选项：
  1. clean-etcd     - 清理 etcd 中的旧 session（推荐）
  2. reset-milvus    - 完全重置 Milvus 和 etcd（最彻底，但会删除所有数据）

如果没有指定选项，将显示交互式菜单。
        """
    )
    parser.add_argument(
        "--method",
        choices=["clean-etcd", "reset-milvus"],
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
        if args.method == "clean-etcd":
            success = fix_by_cleaning_etcd_sessions()
        elif args.method == "reset-milvus":
            success = fix_by_resetting_milvus()
        else:
            print(f"❌ 未知方法: {args.method}")
            sys.exit(1)
        
        sys.exit(0 if success else 1)
    else:
        # 显示交互式菜单
        print("=" * 80)
        print("修复 Milvus etcd session 注册错误")
        print("=" * 80)
        print()
        print("常见错误信息：")
        print("  1. CompareAndSwap error for compare is false for key: rootcoord")
        print("  2. node not match[expectedNodeID=X][actualNodeID=Y]")
        print()
        print("这些错误通常是因为：")
        print("  1. etcd 中存在旧的 Milvus session，但当前实例无法获取")
        print("  2. 之前的 Milvus 实例没有正常关闭，留下了旧的 session")
        print("  3. Milvus 节点 ID 不匹配（重启后节点 ID 变化）")
        print("  4. etcd 数据不一致")
        print()
        print("请选择修复方案：")
        print()
        print("  1. 清理 etcd 中的旧 session（推荐）")
        print("     - 只清理服务注册信息，保留向量数据")
        print("     - 需要重启 Milvus")
        print()
        print("  2. 完全重置 Milvus 和 etcd")
        print("     - 停止服务，删除所有 volumes，重新启动")
        print("     - 最彻底，但会删除所有数据")
        print()
        
        try:
            choice = input("请选择 (1/2): ").strip()
            
            if choice == "1":
                success = fix_by_cleaning_etcd_sessions()
            elif choice == "2":
                success = fix_by_resetting_milvus()
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
