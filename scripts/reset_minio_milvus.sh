#!/bin/bash
# 重置 MinIO Milvus 配置，统一使用 admin/admin123456

set -e

echo "=================================================================================="
echo "重置 MinIO Milvus 配置"
echo "=================================================================================="
echo
echo "此脚本将："
echo "  1. 停止 Milvus 和 MinIO 服务"
echo "  2. 删除 MinIO volume（会丢失 MinIO 中的数据，但向量数据可以重新生成）"
echo "  3. 重新启动服务，使用统一的 admin/admin123456 凭据"
echo
echo "⚠️  警告：这会删除 MinIO 中的所有数据！"
echo "   如果向量数据可以重新生成（通过重新运行 vectorize job），这是安全的。"
echo

read -p "确认继续? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "取消操作"
    exit 0
fi

echo
echo "步骤 1: 停止所有相关服务..."
docker-compose stop milvus minio-milvus || true

echo
echo "步骤 2: 等待容器完全停止..."
sleep 3

echo
echo "步骤 3: 删除 MinIO volume..."
docker volume rm finnet_minio_milvus_data 2>&1 || {
    echo "⚠️  Volume 删除失败，可能仍在使用中"
    echo "   尝试强制删除..."
    # 如果 volume 仍在使用，尝试找到并停止使用它的容器
    docker ps -a --filter volume=finnet_minio_milvus_data --format "{{.ID}}" | xargs -r docker rm -f 2>/dev/null || true
    sleep 2
    docker volume rm finnet_minio_milvus_data 2>&1 || {
        echo "❌ 无法删除 volume，请手动检查："
        echo "   docker volume inspect finnet_minio_milvus_data"
        echo "   然后手动删除："
        echo "   docker volume rm finnet_minio_milvus_data"
        exit 1
    }
}

echo
echo "步骤 4: 重新启动 MinIO..."
docker-compose up -d minio-milvus

echo
echo "等待 MinIO 启动（5秒）..."
sleep 5

echo
echo "步骤 5: 检查 MinIO 状态..."
if docker ps --filter "name=finnet-minio-milvus" --format "{{.Status}}" | grep -q "healthy\|Up"; then
    echo "  ✅ MinIO 已启动"
else
    echo "  ⚠️  MinIO 可能还在启动中"
fi

echo
echo "步骤 6: 重新启动 Milvus..."
docker-compose up -d milvus

echo
echo "=================================================================================="
echo "✅ 重置完成！"
echo "=================================================================================="
echo
echo "请等待几秒钟让 Milvus 完全启动，然后检查状态："
echo "  docker-compose ps"
echo
echo "查看 Milvus 日志（检查是否还有 MinIO 错误）："
echo "  docker-compose logs -f milvus | grep -E '(ERROR|MinIO|bucket)'"
echo
