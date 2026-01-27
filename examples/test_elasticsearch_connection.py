#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的 Elasticsearch 连接测试
用于诊断连接问题
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("Elasticsearch 连接诊断")
print("=" * 60)
print()

# 测试 1: 直接使用 elasticsearch 库
print("1. 测试直接使用 elasticsearch 库...")
try:
    from elasticsearch import Elasticsearch
    
    # 最简单的连接
    print("   尝试连接: http://localhost:9200")
    es = Elasticsearch(["http://localhost:9200"])
    
    print("   执行 ping...")
    result = es.ping()
    print(f"   ✅ Ping 成功: {result}")
    
    # 获取集群信息
    info = es.info()
    print(f"   ✅ 集群名称: {info.get('cluster_name')}")
    print(f"   ✅ 版本: {info.get('version', {}).get('number')}")
    
except Exception as e:
    print(f"   ❌ 连接失败: {e}")
    import traceback
    traceback.print_exc()

print()

# 测试 2: 使用我们的客户端
print("2. 测试使用我们的 ElasticsearchClient...")
try:
    from src.storage.elasticsearch import get_elasticsearch_client
    
    client = get_elasticsearch_client()
    print("   ✅ 客户端创建成功")
    
    # 测试 ping
    if client.client.ping():
        print("   ✅ Ping 成功")
    else:
        print("   ❌ Ping 失败")
        
except Exception as e:
    print(f"   ❌ 连接失败: {e}")
    import traceback
    traceback.print_exc()

print()

# 测试 3: 检查配置
print("3. 检查配置...")
try:
    from src.common.config import elasticsearch_config
    
    print(f"   ELASTICSEARCH_HOSTS: {elasticsearch_config.ELASTICSEARCH_HOSTS}")
    print(f"   hosts_list: {elasticsearch_config.hosts_list}")
    print(f"   ELASTICSEARCH_USER: {elasticsearch_config.ELASTICSEARCH_USER}")
    print(f"   ELASTICSEARCH_PASSWORD: {'***' if elasticsearch_config.ELASTICSEARCH_PASSWORD else 'None'}")
    print(f"   ELASTICSEARCH_USE_SSL: {elasticsearch_config.ELASTICSEARCH_USE_SSL}")
    
except Exception as e:
    print(f"   ❌ 配置读取失败: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
