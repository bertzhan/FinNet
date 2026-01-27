#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接测试 Elasticsearch 客户端连接
不依赖配置，直接测试连接
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("直接测试 Elasticsearch 连接（不依赖配置）")
print("=" * 60)
print()

# 测试 1: 直接使用 elasticsearch 库
print("1. 测试直接使用 elasticsearch 库...")
try:
    from elasticsearch import Elasticsearch
    
    es = Elasticsearch(["http://localhost:9200"])
    result = es.ping()
    print(f"   ✅ Ping 成功: {result}")
    
    info = es.info()
    print(f"   ✅ 集群: {info.get('cluster_name')}, 版本: {info.get('version', {}).get('number')}")
    
except Exception as e:
    print(f"   ❌ 失败: {e}")
    import traceback
    traceback.print_exc()

print()

# 测试 2: 使用我们的客户端，但手动指定参数
print("2. 测试使用我们的客户端（手动指定参数）...")
try:
    from src.storage.elasticsearch.elasticsearch_client import ElasticsearchClient
    
    # 直接指定参数，不依赖配置
    client = ElasticsearchClient(
        hosts=["http://localhost:9200"],
        user=None,  # 不使用认证
        password=None,
        use_ssl=False
    )
    print("   ✅ 客户端创建成功")
    
    if client.client.ping():
        print("   ✅ Ping 成功")
    else:
        print("   ❌ Ping 失败")
        
except Exception as e:
    print(f"   ❌ 失败: {e}")
    import traceback
    traceback.print_exc()

print()

# 测试 3: 检查配置
print("3. 检查配置值...")
try:
    import os
    print(f"   ELASTICSEARCH_HOSTS (env): {os.getenv('ELASTICSEARCH_HOSTS', 'Not set')}")
    print(f"   ELASTICSEARCH_USER (env): {os.getenv('ELASTICSEARCH_USER', 'Not set')}")
    print(f"   ELASTICSEARCH_PASSWORD (env): {'***' if os.getenv('ELASTICSEARCH_PASSWORD') else 'Not set'}")
    
    # 尝试读取配置（可能失败）
    try:
        from src.common.config import elasticsearch_config
        print(f"   config.ELASTICSEARCH_HOSTS: {elasticsearch_config.ELASTICSEARCH_HOSTS}")
        print(f"   config.hosts_list: {elasticsearch_config.hosts_list}")
        print(f"   config.ELASTICSEARCH_USER: {elasticsearch_config.ELASTICSEARCH_USER}")
    except Exception as config_error:
        print(f"   ⚠️  配置读取失败（可能是 .env 权限问题）: {config_error}")
        
except Exception as e:
    print(f"   ❌ 失败: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
