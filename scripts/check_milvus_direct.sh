#!/bin/bash
# 直接使用 Docker 检查 Milvus 向量数量

echo "=================================="
echo "检查 Milvus 向量数据库"
echo "=================================="
echo ""

# 检查 Milvus 容器是否运行
if ! docker ps | grep -q finnet-milvus; then
    echo "错误: Milvus 容器未运行"
    echo "请先启动 Milvus: docker-compose up -d milvus"
    exit 1
fi

echo "✓ Milvus 容器正在运行"
echo ""

# 使用 Python 和 pymilvus 查询（在 Docker 中执行，或者本地执行）
echo "正在连接 Milvus..."
echo ""

# 尝试使用本地 Python 脚本
python3 - <<'EOF'
try:
    from pymilvus import connections, utility, Collection
    
    # 连接到 Milvus
    connections.connect(
        alias="default",
        host="localhost",
        port="19530"
    )
    
    print("✓ 已连接到 Milvus (localhost:19530)")
    print("")
    
    # 列出所有 collections
    collections = utility.list_collections()
    
    if not collections:
        print("⚠️  Milvus 中没有任何 collection")
    else:
        print(f"发现 {len(collections)} 个 Collection(s):")
        print("=" * 80)
        
        total_vectors = 0
        for collection_name in collections:
            collection = Collection(collection_name)
            num_entities = collection.num_entities
            total_vectors += num_entities
            
            print(f"\nCollection: {collection_name}")
            print(f"  向量数量: {num_entities:,}")
            
            # 获取 schema 信息
            schema = collection.schema
            for field in schema.fields:
                if field.dtype.name == 'FLOAT_VECTOR':
                    print(f"  向量维度: {field.params.get('dim', 'N/A')}")
                    break
        
        print("")
        print("=" * 80)
        print(f"总向量数量: {total_vectors:,}")
        print("=" * 80)
    
    connections.disconnect("default")
    
except ImportError:
    print("错误: 未安装 pymilvus 库")
    print("请安装: pip install pymilvus")
    exit(1)
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
EOF
