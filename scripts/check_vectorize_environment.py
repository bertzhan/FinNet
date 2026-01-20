#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查向量化作业环境
验证配置、依赖和数据库状态
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_dependencies():
    """检查依赖"""
    print("=" * 60)
    print("1. 检查依赖")
    print("=" * 60)
    print()
    
    dependencies = {
        "pymilvus": "pymilvus",
        "sqlalchemy": "sqlalchemy",
    }
    
    missing = []
    for name, module in dependencies.items():
        try:
            __import__(module)
            print(f"✅ {name}")
        except ImportError:
            print(f"❌ {name} (未安装)")
            missing.append(name)
        except Exception as e:
            print(f"⚠️  {name} (检查时出错: {type(e).__name__})")
    
    # 单独检查 sentence-transformers（可能因为torch权限问题失败）
    print()
    print("检查 sentence-transformers (可能因权限问题失败)...")
    try:
        import sentence_transformers
        print(f"✅ sentence-transformers")
    except ImportError:
        print(f"❌ sentence-transformers (未安装)")
        missing.append("sentence-transformers")
    except Exception as e:
        print(f"⚠️  sentence-transformers (检查失败: {type(e).__name__})")
        print(f"   这可能是权限问题，不影响实际使用")
    
    print()
    if missing:
        print(f"⚠️  缺少依赖: {', '.join(missing)}")
        print(f"   安装命令: pip install {' '.join(missing)}")
    else:
        print("✅ 核心依赖已安装")
    print()
    
    return len(missing) == 0


def check_config():
    """检查配置"""
    print("=" * 60)
    print("2. 检查配置")
    print("=" * 60)
    print()
    
    try:
        from src.common.config import embedding_config, milvus_config
        
        print("Embedding 配置:")
        print(f"   模型: {embedding_config.EMBEDDING_MODEL}")
        print(f"   维度: {embedding_config.EMBEDDING_DIM}")
        print(f"   批量大小: {embedding_config.EMBEDDING_BATCH_SIZE}")
        print(f"   设备: {embedding_config.EMBEDDING_DEVICE}")
        print(f"   BGE模型路径: {embedding_config.BGE_MODEL_PATH}")
        print()
        
        print("Milvus 配置:")
        print(f"   主机: {milvus_config.MILVUS_HOST}")
        print(f"   端口: {milvus_config.MILVUS_PORT}")
        print()
        
        return True
    except Exception as e:
        print(f"❌ 配置检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_database():
    """检查数据库连接"""
    print("=" * 60)
    print("3. 检查数据库连接")
    print("=" * 60)
    print()
    
    try:
        from src.storage.metadata.postgres_client import get_postgres_client
        from src.storage.metadata.models import DocumentChunk, Document
        
        pg_client = get_postgres_client()
        
        with pg_client.get_session() as session:
            # 检查总分块数
            total_chunks = session.query(DocumentChunk).count()
            print(f"总分块数: {total_chunks}")
            
            # 检查未向量化分块数
            unvectorized = session.query(DocumentChunk).filter(
                DocumentChunk.vector_id.is_(None)
            ).count()
            print(f"未向量化分块数: {unvectorized}")
            
            # 检查已向量化分块数
            vectorized = session.query(DocumentChunk).filter(
                DocumentChunk.vector_id.isnot(None)
            ).count()
            print(f"已向量化分块数: {vectorized}")
            print()
            
            if total_chunks == 0:
                print("⚠️  数据库中没有分块数据")
                print("   需要先运行分块作业: chunk_documents_job")
            elif unvectorized == 0:
                print("✅ 所有分块都已向量化")
            else:
                print(f"✅ 有 {unvectorized} 个分块待向量化")
            
            print()
            return True
    except Exception as e:
        print(f"❌ 数据库检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_milvus():
    """检查 Milvus 连接"""
    print("=" * 60)
    print("4. 检查 Milvus 连接")
    print("=" * 60)
    print()
    
    try:
        from src.storage.vector.milvus_client import get_milvus_client
        from src.common.constants import MilvusCollection
        
        milvus_client = get_milvus_client()
        collection_name = MilvusCollection.DOCUMENTS
        
        # 检查 Collection
        collection = milvus_client.get_collection(collection_name)
        
        if collection:
            print(f"✅ Collection 存在: {collection_name}")
            stats = milvus_client.get_collection_stats(collection_name)
            print(f"   向量数量: {stats.get('row_count', 0)}")
        else:
            print(f"⚠️  Collection 不存在: {collection_name}")
            print(f"   Vectorizer 会在首次使用时自动创建")
        
        print()
        return True
    except Exception as e:
        print(f"❌ Milvus 检查失败: {e}")
        print(f"   请检查 Milvus 服务是否启动")
        import traceback
        traceback.print_exc()
        return False


def check_embedder():
    """检查 Embedder（可选，需要模型）"""
    print("=" * 60)
    print("5. 检查 Embedder（可选）")
    print("=" * 60)
    print()
    
    try:
        from src.processing.ai.embedding.bge_embedder import get_embedder
        
        print("正在初始化 Embedder（可能需要下载模型）...")
        embedder = get_embedder()
        
        print(f"✅ Embedder 初始化成功")
        print(f"   模型名称: {embedder.get_model_name()}")
        print(f"   向量维度: {embedder.get_model_dim()}")
        print()
        
        # 简单测试
        test_text = "测试"
        vector = embedder.embed_text(test_text)
        print(f"✅ 向量化测试成功，维度: {len(vector)}")
        print()
        
        return True
    except Exception as e:
        print(f"⚠️  Embedder 检查失败: {e}")
        print(f"   这可能是正常的（模型未下载或权限问题）")
        print(f"   可以在实际使用时再测试")
        print()
        return False


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("向量化作业环境检查")
    print("=" * 60)
    print()
    
    results = []
    
    # 1. 检查依赖
    results.append(("依赖", check_dependencies()))
    
    # 2. 检查配置
    results.append(("配置", check_config()))
    
    # 3. 检查数据库
    results.append(("数据库", check_database()))
    
    # 4. 检查 Milvus
    results.append(("Milvus", check_milvus()))
    
    # 5. 检查 Embedder（可选）
    results.append(("Embedder", check_embedder()))
    
    # 汇总
    print("=" * 60)
    print("检查结果汇总")
    print("=" * 60)
    print()
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {name}")
    
    print()
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"总计: {passed}/{total} 通过")
    print()
    
    if passed == total:
        print("✅ 环境检查通过，可以开始测试向量化作业")
        print()
        print("下一步:")
        print("  1. 运行快速测试: python tests/test_vectorize_quick.py")
        print("  2. 运行完整测试: python tests/test_vectorize_job.py")
        print("  3. 在 Dagster UI 中运行: vectorize_documents_job")
    else:
        print("⚠️  部分检查未通过，请根据上述信息修复问题")
    print()


if __name__ == "__main__":
    main()
