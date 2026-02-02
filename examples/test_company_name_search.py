# -*- coding: utf-8 -*-
"""
根据公司名称搜索股票代码接口测试
"""

import requests
import json
import sys
from typing import Optional


BASE_URL = "http://localhost:8000"


def test_company_name_search(company_name: str) -> bool:
    """
    测试根据公司名称搜索股票代码接口
    
    Args:
        company_name: 公司名称
        
    Returns:
        是否测试成功
    """
    print(f"\n{'='*60}")
    print(f"测试公司名称搜索接口")
    print(f"{'='*60}")
    print(f"公司名称: {company_name}")
    print()
    
    url = f"{BASE_URL}/api/v1/retrieval/company-code-search"
    payload = {
        "company_name": company_name
    }
    
    try:
        print("发送请求...")
        response = requests.post(url, json=payload, timeout=30)
        
        # 检查 HTTP 状态码
        if response.status_code != 200:
            print(f"✗ HTTP 错误: {response.status_code}")
            print(f"  响应内容: {response.text[:200]}")
            return False
        
        result = response.json()
        
        # 显示结果
        print(f"✓ 请求成功")
        print()
        print(f"查询信息:")
        print(f"  - 查询公司名称: {company_name}")
        
        stock_code = result.get('stock_code')
        message = result.get('message')
        
        if stock_code:
            print(f"  - 股票代码: {stock_code}")
            print(f"  ✅ 找到匹配的股票代码")
        else:
            print(f"  - 股票代码: null")
        
        if message:
            print(f"\n  提示消息:")
            # 如果 message 包含多行，逐行显示
            if '\n' in message:
                for line in message.split('\n'):
                    print(f"    {line}")
            else:
                print(f"    {message}")
        elif not stock_code:
            print(f"  ⚠️  未找到匹配的股票代码")
        
        print()
        
        return True
        
    except requests.exceptions.ConnectionError:
        print(f"✗ 连接失败: 无法连接到 API 服务 ({BASE_URL})")
        print(f"  请确保 FinNet API 服务正在运行")
        return False
    except requests.exceptions.Timeout:
        print(f"✗ 请求超时: API 服务响应时间过长")
        return False
    except json.JSONDecodeError as e:
        print(f"✗ JSON 解析失败: {e}")
        print(f"  响应内容: {response.text[:200]}")
        return False
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multiple_companies():
    """测试多个公司名称"""
    print(f"\n{'='*60}")
    print(f"批量测试多个公司名称")
    print(f"{'='*60}")
    
    test_cases = [
        "平安银行",
        "平安",
        "招商银行",
        "招商",
        "工商银行",
        "工商",
    ]
    
    results = []
    for company_name in test_cases:
        print(f"\n测试: {company_name}")
        success = test_company_name_search(company_name)
        results.append((company_name, success))
    
    # 汇总结果
    print(f"\n{'='*60}")
    print(f"批量测试结果汇总")
    print(f"{'='*60}")
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for company_name, success in results:
        status = "✓ 通过" if success else "✗ 失败"
        print(f"{status}: {company_name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    return passed == total


def main():
    """主函数"""
    import argparse
    
    global BASE_URL
    
    parser = argparse.ArgumentParser(description="测试根据公司名称搜索股票代码接口")
    parser.add_argument(
        "--company-name",
        type=str,
        help="要搜索的公司名称（如果不提供，将运行批量测试）"
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="运行批量测试多个公司名称"
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=BASE_URL,
        help=f"API 基础 URL（默认: {BASE_URL}）"
    )
    
    args = parser.parse_args()
    
    # 更新 BASE_URL
    BASE_URL = args.base_url
    
    # 检查 API 服务是否可访问
    try:
        health_url = f"{BASE_URL}/health"
        response = requests.get(health_url, timeout=5)
        if response.status_code == 200:
            print(f"✓ API 服务可访问: {BASE_URL}")
        else:
            print(f"⚠️  API 服务响应异常: {response.status_code}")
    except Exception as e:
        print(f"✗ 无法连接到 API 服务: {e}")
        print(f"  请确保 FinNet API 服务正在运行")
        sys.exit(1)
    
    # 运行测试
    if args.batch:
        success = test_multiple_companies()
    elif args.company_name:
        success = test_company_name_search(args.company_name)
    else:
        # 默认测试
        print("未指定公司名称，运行默认测试...")
        success = test_company_name_search("平安银行")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
