#!/bin/bash
# 删除 Milvus 向量数据库中的所有数据

set -e

echo "=================================================================================="
echo "删除 Milvus 向量数据库数据"
echo "=================================================================================="
echo

# 检查 Milvus 容器是否运行
if ! docker ps | grep -q finnet-milvus; then
    echo "⚠️  Milvus 容器未运行，但可以继续清理存储数据"
fi

echo "⚠️  警告：此操作将删除 Milvus 中的所有数据！"
echo
echo "将执行以下操作："
echo "  1. 停止 Milvus 服务"
echo "  2. 清空 MinIO Milvus 存储（a-bucket）"
echo "  3. 清空 Milvus 本地数据"
echo "  4. 清空 etcd 数据（Milvus 元数据）"
echo
read -p "确认删除所有 Milvus 数据? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "取消操作"
    exit 0
fi

echo
echo "=================================================================================="
echo "开始删除数据"
echo "=================================================================================="
echo

# 1. 停止 Milvus
echo "1. 停止 Milvus 服务..."
docker stop finnet-milvus 2>/dev/null || echo "  Milvus 已停止"
echo "✅ Milvus 已停止"
echo

# 2. 清空 MinIO Milvus 存储
echo "2. 清空 MinIO Milvus 存储..."
if docker ps | grep -q finnet-minio-milvus; then
    docker exec finnet-minio-milvus sh -c "rm -rf /data/a-bucket/*" 2>/dev/null || true
    echo "✅ MinIO Milvus 存储已清空"
else
    echo "⚠️  MinIO Milvus 容器未运行，跳过"
fi
echo

# 3. 清空 Milvus 本地数据
echo "3. 清空 Milvus 本地数据..."
if docker ps -a | grep -q finnet-milvus; then
    docker exec finnet-milvus sh -c "rm -rf /var/lib/milvus/*" 2>/dev/null || \
    docker run --rm -v finnet_milvus_data:/var/lib/milvus alpine sh -c "rm -rf /var/lib/milvus/*" 2>/dev/null || true
    echo "✅ Milvus 本地数据已清空"
else
    echo "⚠️  Milvus 容器不存在，跳过"
fi
echo

# 4. 清空 etcd 数据（可选，更彻底）
echo "4. 清空 etcd 数据（Milvus 元数据）..."
read -p "是否也清空 etcd 数据? (y/n): " clear_etcd
if [ "$clear_etcd" = "y" ]; then
    docker stop finnet-etcd 2>/dev/null || true
    docker exec finnet-etcd sh -c "rm -rf /etcd/*" 2>/dev/null || \
    docker run --rm -v finnet_etcd_data:/etcd alpine sh -c "rm -rf /etcd/*" 2>/dev/null || true
    echo "✅ etcd 数据已清空"
else
    echo "  跳过 etcd 数据清理"
fi
echo

# 5. 重启服务
echo "5. 重启服务..."
read -p "是否重启 Milvus 服务? (y/n): " restart
if [ "$restart" = "y" ]; then
    if [ "$clear_etcd" = "y" ]; then
        docker start finnet-etcd
        echo "✅ etcd 已启动"
        sleep 5
    fi
    
    docker start finnet-milvus
    echo "✅ Milvus 已启动"
    echo
    echo "等待服务启动（30秒）..."
    sleep 30
    
    echo
    echo "检查服务状态..."
    docker ps | grep -E "(milvus|etcd)" || echo "  服务未运行"
fi

echo
echo "=================================================================================="
echo "✅ 数据删除完成！"
echo "=================================================================================="
echo
echo "注意："
echo "  - 所有 Milvus Collections 已被删除"
echo "  - 所有向量数据已被清空"
echo "  - 需要重新创建 Collection 才能使用"
echo
echo "重新创建 Collection："
echo "  python scripts/init_milvus_collection.py"
