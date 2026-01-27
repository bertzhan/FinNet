#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Service 单独测试脚本
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("LLM Service 测试")
print("=" * 80)
print()

# 测试1: 检查配置
print("测试1: 检查 LLM 配置")
print("-" * 80)

try:
    from src.common.config import llm_config
    
    print(f"CLOUD_LLM_ENABLED: {llm_config.CLOUD_LLM_ENABLED}")
    print(f"CLOUD_LLM_API_BASE: {llm_config.CLOUD_LLM_API_BASE}")
    print(f"CLOUD_LLM_MODEL: {llm_config.CLOUD_LLM_MODEL}")
    print(f"CLOUD_LLM_API_KEY: {'已配置' if llm_config.CLOUD_LLM_API_KEY else '未配置'}")
    print()
    print(f"LOCAL_LLM_ENABLED: {llm_config.LOCAL_LLM_ENABLED}")
    print(f"LOCAL_LLM_API_BASE: {llm_config.LOCAL_LLM_API_BASE}")
    print(f"LOCAL_LLM_MODEL: {llm_config.LOCAL_LLM_MODEL}")
    
    if llm_config.CLOUD_LLM_ENABLED:
        print("\n✅ 使用云端 LLM")
    elif llm_config.LOCAL_LLM_ENABLED:
        print("\n✅ 使用本地 LLM")
    else:
        print("\n❌ 未启用任何 LLM 服务")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ 配置检查失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# 测试2: LLM Service 初始化
print("测试2: LLM Service 初始化")
print("-" * 80)

try:
    from src.processing.ai.llm.llm_service import get_llm_service
    
    service = get_llm_service()
    print(f"✅ LLM Service 初始化成功")
    print(f"   Mode: {service.mode}")
    print(f"   Provider: {service.provider}")
    print(f"   API Base: {service.api_base}")
    print(f"   Model: {service.model}")
    print(f"   API Key: {'已配置' if service.api_key else '未配置'}")
    
except Exception as e:
    print(f"❌ LLM Service 初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# 测试3: 简单文本生成
print("测试3: 简单文本生成")
print("-" * 80)

try:
    print("   测试问题: '什么是人工智能？'")
    answer = service.generate(
        prompt="什么是人工智能？",
        system_prompt="你是一个专业的AI助手。",
        temperature=0.7,
        max_tokens=200
    )
    print(f"✅ 生成成功")
    print(f"   回答长度: {len(answer)} 字符")
    print(f"   回答内容: {answer}")
    
except Exception as e:
    print(f"❌ 文本生成失败: {e}")
    import traceback
    traceback.print_exc()

print()

# 测试4: 中文问答
print("测试4: 中文问答测试")
print("-" * 80)

try:
    print("   测试问题: '请用一句话解释什么是机器学习'")
    answer = service.generate(
        prompt="请用一句话解释什么是机器学习",
        temperature=0.7,
        max_tokens=200
    )
    print(f"✅ 生成成功")
    print(f"   回答: {answer}")
    
except Exception as e:
    print(f"❌ 中文问答失败: {e}")
    import traceback
    traceback.print_exc()

print()

# 测试5: 带系统提示词的生成
print("测试5: 带系统提示词的生成")
print("-" * 80)

try:
    system_prompt = "你是一个专业的金融分析师，擅长分析上市公司财报。"
    user_prompt = "请简单说明营业收入的定义。"
    
    print(f"   系统提示词: {system_prompt}")
    print(f"   用户问题: {user_prompt}")
    
    answer = service.generate(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=0.7,
        max_tokens=200
    )
    print(f"✅ 生成成功")
    print(f"   回答: {answer}")
    
except Exception as e:
    print(f"❌ 带系统提示词生成失败: {e}")
    import traceback
    traceback.print_exc()

print()

# 测试6: 不同温度参数测试
print("测试6: 不同温度参数测试")
print("-" * 80)

try:
    prompt = "用一句话描述Python编程语言"
    
    for temp in [0.3, 0.7, 1.0]:
        print(f"   温度={temp}:")
        answer = service.generate(
            prompt=prompt,
            temperature=temp,
            max_tokens=200
        )
        print(f"     回答: {answer[:100]}...")
        print()
    
    print("✅ 不同温度参数测试完成")
    
except Exception as e:
    print(f"❌ 温度参数测试失败: {e}")
    import traceback
    traceback.print_exc()

print()

# 测试7: URL 识别功能
print("测试7: URL 识别功能")
print("-" * 80)

try:
    test_urls = [
        "https://api.openai.com",
        "https://api.deepseek.com",
        "http://localhost:8000",
        "https://custom-proxy.com",
        service.api_base
    ]
    
    for url in test_urls:
        provider = service._identify_provider_from_url(url)
        print(f"   {url} -> {provider}")
    
    print("✅ URL 识别测试完成")
    
except Exception as e:
    print(f"❌ URL 识别测试失败: {e}")
    import traceback
    traceback.print_exc()

print()

# 测试8: 性能测试
print("测试8: 性能测试")
print("-" * 80)

try:
    import time
    
    prompt = "什么是人工智能？"
    times = []
    
    for i in range(3):
        start = time.time()
        answer = service.generate(
            prompt=prompt,
            max_tokens=200
        )
        elapsed = time.time() - start
        times.append(elapsed)
        print(f"   第 {i+1} 次: {elapsed:.2f}s, 回答长度: {len(answer)} 字符")
    
    avg_time = sum(times) / len(times)
    print(f"   平均响应时间: {avg_time:.2f}s")
    print(f"✅ 性能测试完成")
    
except Exception as e:
    print(f"❌ 性能测试失败: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("LLM Service 测试完成!")
print("=" * 80)
