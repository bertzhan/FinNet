#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenAI 兼容性测试脚本
测试 FinNet API 的 OpenAI 兼容接口
"""

import sys
import json
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("OpenAI 兼容性测试")
print("=" * 80)
print()

# 配置
API_BASE_URL = "http://localhost:8000"
API_KEY = "test-key"  # 如果启用了 API 密钥验证，请设置正确的密钥

def test_non_streaming():
    """测试非流式响应"""
    print("测试1: 非流式响应")
    print("-" * 80)
    
    url = f"{API_BASE_URL}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    payload = {
        "model": "finnet-rag",
        "messages": [
            {"role": "user", "content": "平安银行2023年第三季度的营业收入是多少？"}
        ],
        "temperature": 0.7,
        "max_tokens": 1000,
        "stream": False
    }
    
    try:
        print(f"请求 URL: {url}")
        print(f"请求 Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        print()
        
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        print("✅ 请求成功")
        print(f"响应结构: {list(result.keys())}")
        print()
        
        # 验证响应格式
        assert "id" in result, "缺少 id 字段"
        assert "object" in result, "缺少 object 字段"
        assert result["object"] == "chat.completion", f"object 应为 'chat.completion'，实际为 '{result['object']}'"
        assert "choices" in result, "缺少 choices 字段"
        assert len(result["choices"]) > 0, "choices 为空"
        
        choice = result["choices"][0]
        assert "message" in choice, "缺少 message 字段"
        assert choice["message"]["role"] == "assistant", "role 应为 'assistant'"
        assert "content" in choice["message"], "缺少 content 字段"
        
        print("✅ 响应格式验证通过")
        print(f"响应 ID: {result['id']}")
        print(f"模型: {result.get('model', 'N/A')}")
        print(f"答案长度: {len(choice['message']['content'])} 字符")
        print(f"答案预览: {choice['message']['content'][:100]}...")
        
        if "usage" in result:
            usage = result["usage"]
            print(f"Token 使用: {usage.get('total_tokens', 'N/A')}")
        
        print()
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求失败: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"错误详情: {json.dumps(error_detail, ensure_ascii=False, indent=2)}")
            except:
                print(f"响应内容: {e.response.text}")
        return False
    except AssertionError as e:
        print(f"❌ 验证失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_streaming():
    """测试流式响应"""
    print("测试2: 流式响应")
    print("-" * 80)
    
    url = f"{API_BASE_URL}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    payload = {
        "model": "finnet-rag",
        "messages": [
            {"role": "user", "content": "什么是人工智能？"}
        ],
        "temperature": 0.7,
        "max_tokens": 500,
        "stream": True
    }
    
    try:
        print(f"请求 URL: {url}")
        print(f"请求 Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        print()
        print("接收流式响应...")
        print()
        
        response = requests.post(url, json=payload, headers=headers, timeout=60, stream=True)
        response.raise_for_status()
        
        chunks = []
        response_id = None
        
        for line in response.iter_lines():
            if not line:
                continue
            
            line_text = line.decode('utf-8')
            if line_text.startswith('data: '):
                data_str = line_text[6:]  # 移除 "data: " 前缀
                
                if data_str.strip() == '[DONE]':
                    print("✅ 收到结束标记 [DONE]")
                    break
                
                try:
                    data = json.loads(data_str)
                    
                    # 保存 response_id
                    if response_id is None and "id" in data:
                        response_id = data["id"]
                    
                    # 提取内容
                    if "choices" in data and len(data["choices"]) > 0:
                        choice = data["choices"][0]
                        if "delta" in choice:
                            delta = choice["delta"]
                            content = delta.get("content", "")
                            if content:
                                chunks.append(content)
                                print(content, end="", flush=True)
                        elif "message" in choice:
                            content = choice["message"].get("content", "")
                            if content:
                                chunks.append(content)
                                print(content, end="", flush=True)
                
                except json.JSONDecodeError as e:
                    print(f"\n⚠️  解析 JSON 失败: {e}, 数据: {data_str[:100]}")
                    continue
        
        print()
        print()
        print("✅ 流式响应接收完成")
        print(f"响应 ID: {response_id}")
        print(f"接收到的块数: {len(chunks)}")
        print(f"总内容长度: {sum(len(c) for c in chunks)} 字符")
        print()
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求失败: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"错误详情: {json.dumps(error_detail, ensure_ascii=False, indent=2)}")
            except:
                print(f"响应内容: {e.response.text}")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_handling():
    """测试错误处理"""
    print("测试3: 错误处理")
    print("-" * 80)
    
    url = f"{API_BASE_URL}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    # 测试空消息列表
    payload = {
        "model": "finnet-rag",
        "messages": [],
        "stream": False
    }
    
    try:
        print("测试空消息列表...")
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        
        if response.status_code == 400:
            print("✅ 正确返回 400 错误")
            error_detail = response.json()
            print(f"错误信息: {json.dumps(error_detail, ensure_ascii=False, indent=2)}")
        else:
            print(f"⚠️  预期 400 错误，实际状态码: {response.status_code}")
        
        print()
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print(f"API 基础 URL: {API_BASE_URL}")
    print(f"API Key: {API_KEY[:10]}..." if len(API_KEY) > 10 else f"API Key: {API_KEY}")
    print()
    
    # 检查 API 是否可访问
    try:
        health_url = f"{API_BASE_URL}/health"
        response = requests.get(health_url, timeout=5)
        if response.status_code == 200:
            print("✅ API 服务可访问")
        else:
            print(f"⚠️  API 服务响应异常: {response.status_code}")
    except Exception as e:
        print(f"❌ 无法连接到 API 服务: {e}")
        print("   请确保 FinNet API 服务正在运行")
        sys.exit(1)
    
    print()
    
    # 运行测试
    results = []
    
    results.append(("非流式响应", test_non_streaming()))
    print()
    
    results.append(("流式响应", test_streaming()))
    print()
    
    results.append(("错误处理", test_error_handling()))
    print()
    
    # 总结
    print("=" * 80)
    print("测试总结")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    print()
    print(f"总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！")
        return 0
    else:
        print("⚠️  部分测试失败，请检查上述错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
