#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单检查 Milvus 连接状态（不依赖 pymilvus）
"""

import sys
import socket
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.common.config import milvus_config


def check_port(host: str, port: int, timeout: int = 3) -> bool:
    """检查端口是否可连接"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        print(f"  检查端口时出错: {e}")
        return False


def check_milvus_connection():
    """检查 Milvus 连接状态"""
    print("=" * 80)
    print("检查 Milvus 连接状态")
    print("=" * 80)
    print()
    
    # 显示配置信息
    print("Milvus 配置信息:")
    print(f"  Host: {milvus_config.MILVUS_HOST}")
    print(f"  Port: {milvus_config.MILVUS_PORT}")
    print(f"  User: {milvus_config.MILVUS_USER or 'None'}")
    print(f"  Password: {'***' if milvus_config.MILVUS_PASSWORD else 'None'}")
    print()
    
    # 检查端口是否开放
    print("检查端口连接...")
    host = milvus_config.MILVUS_HOST
    port = milvus_config.MILVUS_PORT
    
    if check_port(host, port):
        print(f"✅ 端口 {host}:{port} 可连接（服务可能正在运行）")
        print()
        print("提示: 端口可连接，但需要安装 pymilvus 才能进行完整测试")
        print("      安装命令: pip install pymilvus")
        return True
    else:
        print(f"❌ 端口 {host}:{port} 无法连接（服务可能未运行）")
        print()
        print("可能的原因:")
        print("  1. Milvus 服务未启动")
        print("  2. 端口配置错误")
        print("  3. 防火墙阻止连接")
        print()
        print("启动 Milvus 的方法:")
        print("  - Docker: docker run -d --name milvus -p 19530:19530 milvusdb/milvus:latest")
        print("  - 或使用 docker-compose 启动")
        return False


if __name__ == "__main__":
    success = check_milvus_connection()
    sys.exit(0 if success else 1)
