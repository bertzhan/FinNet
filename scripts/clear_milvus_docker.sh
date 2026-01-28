#!/bin/bash
# 通过 Docker 容器内的 Python 清空 Milvus Collections

set -e

echo "=================================================================================="
echo "清空 Milvus Collections（通过 Docker）"
echo "=================================================================================="
echo

# 检查 Milvus 容器是否运行
if ! docker ps | grep -q finnet-milvus; then
    echo "❌ 错误: Milvus 容器未运行"
    echo "请先启动 Milvus: docker-compose up -d milvus"
    exit 1
fi

echo "✓ Milvus 容器正在运行"
echo

# 在 Docker 容器内执行 Python 脚本
docker exec -i finnet-milvus python3 << 'EOF'
try:
    from pymilvus import connections, utility
    
    # 连接到 Milvus
    connections.connect(
        alias="default",
        host="localhost",
        port="19530"
    )
    
    print("✓ 已连接到 Milvus")
    print()
    
    # 列出所有 collections
    collections = utility.list_collections()
    
    if not collections:
        print("✓ Milvus 中没有任何 Collection，无需清空")
    else:
        print(f"找到 {len(collections)} 个 Collection(s):")
        for collection_name in collections:
            from pymilvus import Collection
            collection = Collection(collection_name)
            num_entities = collection.num_entities
            print(f"  - {collection_name}: {num_entities:,} 个向量")
        
        print()
        print("=" * 80)
        print("⚠️  即将删除所有 Collections！")
        print("=" * 80)
        
        # 确认删除
        try:
            confirmation = input("确认删除所有 Collections？输入 'yes' 继续: ")
            if confirmation.lower() != 'yes':
                print("操作已取消")
                exit(0)
        except:
            print("无法获取用户输入，操作取消")
            exit(0)
        
        # 删除所有 collections
        deleted_count = 0
        failed_count = 0
        
        for collection_name in collections:
            try:
                utility.drop_collection(collection_name)
                print(f"✓ 已删除: {collection_name}")
                deleted_count += 1
            except Exception as e:
                print(f"❌ 删除 {collection_name} 失败: {e}")
                failed_count += 1
        
        print()
        print("=" * 80)
        print("清空完成:")
        print(f"  成功删除: {deleted_count} 个 Collection(s)")
        if failed_count > 0:
            print(f"  删除失败: {failed_count} 个 Collection(s)")
        print("=" * 80)
    
    connections.disconnect("default")
    
except ImportError:
    print("❌ 错误: Milvus 容器内未安装 pymilvus")
    print("请检查 Milvus 容器配置")
    exit(1)
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
EOF

echo
echo "=================================================================================="
echo "完成"
echo "=================================================================================="
