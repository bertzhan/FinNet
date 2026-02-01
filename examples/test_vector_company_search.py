# -*- coding: utf-8 -*-
"""
测试基于向量的公司名称搜索功能
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.processing.ai.embedding.embedder_factory import get_embedder_by_mode
from src.storage.vector import get_milvus_client
from src.common.constants import MilvusCollection
from collections import Counter


def test_vector_company_search(company_name: str, top_k: int = 10):
    """测试向量搜索公司名称"""
    print(f"=" * 60)
    print(f"测试公司名称: {company_name}")
    print(f"=" * 60)
    
    # 1. 基础预处理
    company_name_query = company_name.strip().replace(" ", "").replace("　", "")
    print(f"\n1. 预处理后的查询: '{company_name_query}'")
    
    # 2. 向量化
    print("\n2. 向量化查询...")
    try:
        embedder = get_embedder_by_mode()
        query_vector = embedder.embed_text(company_name_query)
        
        if not query_vector:
            print("❌ 向量化失败")
            return None
        
        print(f"✅ 向量化成功，向量维度: {len(query_vector)}")
    except Exception as e:
        print(f"❌ 向量化失败: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # 3. Milvus 向量搜索
    print(f"\n3. Milvus 向量搜索 (top_k={top_k})...")
    try:
        milvus_client = get_milvus_client()
        search_results = milvus_client.search_vectors(
            collection_name=MilvusCollection.DOCUMENTS,
            query_vectors=[query_vector],
            top_k=top_k,
            output_fields=["chunk_id", "stock_code", "company_name"]
        )
        
        if not search_results or not search_results[0]:
            print("❌ 未找到相关文档")
            return None
        
        hits = search_results[0]
        print(f"✅ 找到 {len(hits)} 个相关文档")
        
        # 4. 显示搜索结果
        print("\n4. 搜索结果:")
        stock_codes = []
        for i, hit in enumerate(hits[:5], 1):  # 只显示前5个
            entity = hit.get('entity', {})
            stock_code = entity.get('stock_code', 'N/A')
            company_name_found = entity.get('company_name', 'N/A')
            distance = hit.get('distance', 0.0)
            
            print(f"   {i}. stock_code={stock_code}, company_name={company_name_found}, distance={distance:.4f}")
            
            if stock_code:
                stock_codes.append(stock_code)
        
        # 5. 投票统计
        print("\n5. 投票统计:")
        if stock_codes:
            stock_code_counter = Counter(stock_codes)
            print(f"   总文档数: {len(stock_codes)}")
            print(f"   候选股票代码:")
            for stock_code, count in stock_code_counter.most_common():
                confidence = count / len(stock_codes)
                print(f"     - {stock_code}: {count} 票 (置信度: {confidence:.2%})")
            
            # 6. 最可能的股票代码
            most_common = stock_code_counter.most_common(1)
            most_likely = most_common[0][0] if most_common else None
            print(f"\n✅ 最可能的股票代码: {most_likely}")
            return most_likely
        else:
            print("❌ 没有找到有效的股票代码")
            return None
            
    except Exception as e:
        print(f"❌ Milvus 搜索失败: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="测试基于向量的公司名称搜索")
    parser.add_argument("--company-name", type=str, required=True, help="公司名称")
    parser.add_argument("--top-k", type=int, default=10, help="检索文档数量")
    args = parser.parse_args()
    
    result = test_vector_company_search(args.company_name, args.top_k)
    
    if result:
        print(f"\n🎉 测试成功！股票代码: {result}")
    else:
        print("\n❌ 测试失败")
