#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 Milvus 连接状态
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.vector.milvus_client import get_milvus_client
from src.common.config import milvus_config
from pymilvus import connections, utility, MilvusException


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
    
    # 方法1：尝试创建 MilvusClient
    print("方法1: 尝试创建 MilvusClient...")
    try:
        client = get_milvus_client()
        print("✅ MilvusClient 创建成功")
        
        # 尝试列出 Collections
        print("\n尝试列出 Collections...")
        try:
            collections = client.list_collections()
            print(f"✅ 连接成功！找到 {len(collections)} 个 Collections:")
            for col in collections:
                print(f"  - {col}")
        except Exception as e:
            print(f"❌ 列出 Collections 失败: {e}")
            
    except MilvusException as e:
        print(f"❌ Milvus 连接失败: {e}")
        print(f"   错误类型: {type(e).__name__}")
        if hasattr(e, 'code'):
            print(f"   错误代码: {e.code}")
        return False
    except Exception as e:
        print(f"❌ 创建 MilvusClient 失败: {e}")
        print(f"   错误类型: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False
    
    # 方法2：直接测试连接
    print("\n" + "=" * 80)
    print("方法2: 直接测试连接...")
    try:
        connections.connect(
            alias="test_connection",
            host=milvus_config.MILVUS_HOST,
            port=str(milvus_config.MILVUS_PORT),
            user=milvus_config.MILVUS_USER,
            password=milvus_config.MILVUS_PASSWORD
        )
        print("✅ 直接连接成功")
        
        # 测试列出 Collections
        try:
            collections = utility.list_collections(using="test_connection")
            print(f"✅ 找到 {len(collections)} 个 Collections: {collections}")
        except Exception as e:
            print(f"⚠️  列出 Collections 失败: {e}")
        
        # 断开测试连接
        connections.disconnect("test_connection")
        print("✅ 测试连接已断开")
        
    except MilvusException as e:
        print(f"❌ 直接连接失败: {e}")
        print(f"   错误类型: {type(e).__name__}")
        if hasattr(e, 'code'):
            print(f"   错误代码: {e.code}")
        return False
    except Exception as e:
        print(f"❌ 连接异常: {e}")
        print(f"   错误类型: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 80)
    print("✅ Milvus 连接检查完成，连接正常！")
    print("=" * 80)
    return True


if __name__ == "__main__":
    success = check_milvus_connection()
    sys.exit(0 if success else 1)
