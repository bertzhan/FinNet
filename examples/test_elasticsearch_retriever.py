#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 Elasticsearch 检索器
验证全文检索功能是否正常工作
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.application.rag.elasticsearch_retriever import ElasticsearchRetriever


def test_basic_retrieval():
    """测试基本检索功能"""
    print("=" * 60)
    print("测试 1: 基本全文检索")
    print("=" * 60)
    
    try:
        retriever = ElasticsearchRetriever()
        
        # 执行检索
        results = retriever.retrieve(
            query="营业收入",
            top_k=5
        )
        
        print(f"\n✅ 检索成功，返回 {len(results)} 个结果\n")
        
        # 显示结果
        for i, result in enumerate(results, 1):
            print(f"结果 {i}:")
            print(f"  分数: {result.score:.4f}")
            print(f"  股票代码: {result.metadata.get('stock_code', 'N/A')}")
            print(f"  公司名称: {result.metadata.get('company_name', 'N/A')}")
            print(f"  文档类型: {result.metadata.get('doc_type', 'N/A')}")
            print(f"  年份: {result.metadata.get('year', 'N/A')}")
            print(f"  文本片段: {result.chunk_text[:100]}...")
            print()
        
        return len(results) > 0
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_filtered_retrieval():
    """测试带过滤条件的检索"""
    print("=" * 60)
    print("测试 2: 带过滤条件的检索")
    print("=" * 60)
    
    try:
        retriever = ElasticsearchRetriever()
        
        # 执行带过滤条件的检索
        results = retriever.retrieve(
            query="营业收入",
            top_k=5,
            filters={
                "stock_code": "300542",  # 平安银行
                "year": 2023
            }
        )
        
        print(f"\n✅ 检索成功，返回 {len(results)} 个结果\n")
        
        # 验证过滤条件
        all_match = True
        for i, result in enumerate(results, 1):
            stock_code = result.metadata.get('stock_code')
            year = result.metadata.get('year')
            
            if stock_code != "300542" or year != 2023:
                print(f"⚠️  结果 {i} 不匹配过滤条件:")
                print(f"  期望: stock_code=000001, year=2023")
                print(f"  实际: stock_code={stock_code}, year={year}")
                all_match = False
            else:
                print(f"✅ 结果 {i} 匹配过滤条件")
                print(f"  股票代码: {stock_code}, 年份: {year}")
                print(f"  文本片段: {result.chunk_text[:80]}...")
                print()
        
        return all_match and len(results) > 0
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_empty_query():
    """测试空查询"""
    print("=" * 60)
    print("测试 3: 空查询处理")
    print("=" * 60)
    
    try:
        retriever = ElasticsearchRetriever()
        
        # 执行空查询
        results = retriever.retrieve(
            query="",
            top_k=5
        )
        
        print(f"\n查询结果数量: {len(results)}")
        
        # 空查询应该返回空结果或很少的结果
        if len(results) == 0:
            print("✅ 空查询返回空结果（符合预期）")
            return True
        else:
            print("⚠️  空查询返回了结果（可能不符合预期）")
            return False
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Elasticsearch 检索器测试")
    print("=" * 60 + "\n")
    
    tests = [
        ("基本检索", test_basic_retrieval),
        ("过滤检索", test_filtered_retrieval),
        ("空查询", test_empty_query),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ 测试 '{name}' 执行失败: {e}")
            results.append((name, False))
        print()
    
    # 汇总结果
    print("=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")


if __name__ == "__main__":
    main()
