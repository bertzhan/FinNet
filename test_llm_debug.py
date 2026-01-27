#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Service 调试脚本
查看API实际返回的内容
"""

import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.processing.ai.llm.llm_service import get_llm_service
from src.common.config import llm_config
import logging

# 设置DEBUG级别日志
logging.basicConfig(level=logging.DEBUG)

print("=" * 80)
print("LLM Service 调试")
print("=" * 80)
print()

print(f"配置:")
print(f"  API Base: {llm_config.CLOUD_LLM_API_BASE}")
print(f"  Model: {llm_config.CLOUD_LLM_MODEL}")
print(f"  API Key: {'已配置' if llm_config.CLOUD_LLM_API_KEY else '未配置'}")
print()

service = get_llm_service()

# 手动调用API查看响应
import requests

url = service.api_base
headers = {
    "Authorization": f"Bearer {service.api_key}",
    "Content-Type": "application/json"
}

payload = {
    "model": service.model,
    "messages": [
        {"role": "user", "content": "你好"}
    ],
    "temperature": 0.7,
    "max_tokens": 20
}

print(f"请求URL: {url}")
print(f"请求Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
print()

try:
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    print(f"响应状态码: {response.status_code}")
    print(f"响应头: {dict(response.headers)}")
    print()
    
    if response.status_code == 200:
        result = response.json()
        print(f"响应JSON结构:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print()
        
        # 尝试解析
        if "choices" in result and len(result["choices"]) > 0:
            choice = result["choices"][0]
            print(f"Choice 结构: {list(choice.keys())}")
            if "message" in choice:
                print(f"Message 结构: {list(choice['message'].keys())}")
                print(f"Content: {repr(choice['message'].get('content', ''))}")
    else:
        print(f"错误响应: {response.text}")
        
except Exception as e:
    print(f"请求失败: {e}")
    import traceback
    traceback.print_exc()
