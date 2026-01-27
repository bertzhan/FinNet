#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG 查询示例
展示如何使用 RAG 系统进行问答
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.application.rag.rag_pipeline import RAGPipeline
from src.common.logger import get_logger

logger = get_logger(__name__)


def main():
    """主函数"""
    print("=" * 80)
    print("RAG 查询示例")
    print("=" * 80)
    print()

    # 初始化 RAG Pipeline
    print("初始化 RAG Pipeline...")
    try:
        pipeline = RAGPipeline()
        print("✅ RAG Pipeline 初始化成功")
    except Exception as e:
        print(f"❌ RAG Pipeline 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return

    print()

    # 示例查询
    examples = [
        {
            "question": "平安银行2023年第三季度的营业收入是多少？",
            "filters": {
                "stock_code": "000001",
                "year": 2023,
                "quarter": 3
            },
            "description": "带过滤条件的查询"
        },
        {
            "question": "什么是营业收入？",
            "filters": None,
            "description": "通用查询（无过滤条件）"
        },
        {
            "question": "2023年有哪些公司发布了季度报告？",
            "filters": {
                "year": 2023
            },
            "description": "按年份过滤"
        }
    ]

    for i, example in enumerate(examples, 1):
        print("-" * 80)
        print(f"示例 {i}: {example['description']}")
        print("-" * 80)
        print(f"问题: {example['question']}")
        if example['filters']:
            print(f"过滤条件: {example['filters']}")
        print()

        try:
            # 执行查询
            response = pipeline.query(
                question=example['question'],
                filters=example['filters'],
                top_k=5,
                temperature=0.7
            )

            # 显示结果
            print("答案:")
            print(response.answer)
            print()

            if response.sources:
                print(f"引用来源 ({len(response.sources)} 个):")
                for j, source in enumerate(response.sources, 1):
                    print(f"  {j}. {source.company_name} ({source.stock_code}) - {source.title or '无标题'}")
                    print(f"     相似度: {source.score:.3f}")
                    print(f"     片段: {source.snippet[:100]}...")
                    print()

            print(f"元数据:")
            print(f"  检索数量: {response.metadata.get('retrieval_count', 0)}")
            print(f"  生成时间: {response.metadata.get('generation_time', 0):.2f}s")
            print(f"  模型: {response.metadata.get('model', 'N/A')}")
            print()

        except Exception as e:
            print(f"❌ 查询失败: {e}")
            import traceback
            traceback.print_exc()
            print()

    print("=" * 80)
    print("示例完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
