#!/bin/bash
# 重置 Milvus 相关服务（清空所有数据）
# 包括：milvus, etcd, minio-milvus

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=================================================================================="
echo "重置 Milvus 服务"
echo "=================================================================================="
echo
echo "⚠️  警告：此操作将删除 Milvus 中的所有数据！"
echo
echo "将要重置的服务："
echo "  - milvus (向量数据库)"
echo "  - etcd (元数据存储)"
echo "  - minio-milvus (对象存储)"
echo
echo "=================================================================================="

# 检查是否有 --force 参数
if [[ "$1" != "--force" ]]; then
    read -p "确认重置 Milvus？输入 'yes' 继续: " confirm
    if [[ "$confirm" != "yes" ]]; then
        echo "操作已取消"
        exit 0
    fi
fi

echo
echo "步骤 1/4: 停止容器..."
echo "--------------------------------------------------------------------------------"
docker-compose stop milvus etcd minio-milvus 2>/dev/null || true
echo "✓ 容器已停止"

echo
echo "步骤 2/4: 删除容器..."
echo "--------------------------------------------------------------------------------"
docker-compose rm -f milvus etcd minio-milvus 2>/dev/null || true
echo "✓ 容器已删除"

echo
echo "步骤 3/4: 删除数据卷..."
echo "--------------------------------------------------------------------------------"
docker volume rm finnet_milvus_data 2>/dev/null && echo "  ✓ finnet_milvus_data 已删除" || echo "  - finnet_milvus_data 不存在"
docker volume rm finnet_minio_milvus_data 2>/dev/null && echo "  ✓ finnet_minio_milvus_data 已删除" || echo "  - finnet_minio_milvus_data 不存在"
docker volume rm finnet_etcd_data 2>/dev/null && echo "  ✓ finnet_etcd_data 已删除" || echo "  - finnet_etcd_data 不存在"
echo "✓ 数据卷清理完成"

echo
echo "步骤 4/4: 重新启动容器..."
echo "--------------------------------------------------------------------------------"
docker-compose up -d minio-milvus etcd milvus
echo "✓ 容器已启动"

echo
echo "=================================================================================="
echo "等待服务就绪..."
echo "=================================================================================="

# 等待 Milvus 就绪
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker exec finnet-milvus curl -s http://localhost:9091/healthz > /dev/null 2>&1; then
        echo "✓ Milvus 服务就绪"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "  等待 Milvus 就绪... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "⚠️  警告：Milvus 可能尚未完全就绪，请稍后检查"
fi

echo
echo "=================================================================================="
echo "验证服务状态"
echo "=================================================================================="

# 检查容器状态
echo
echo "容器状态："
docker-compose ps milvus etcd minio-milvus 2>/dev/null || docker ps --filter "name=finnet-milvus" --filter "name=finnet-etcd" --filter "name=finnet-minio-milvus"

# 检查 Milvus Collections
echo
echo "Milvus Collections："
docker exec finnet-milvus python3 -c "
from pymilvus import connections, utility
connections.connect(host='localhost', port='19530')
collections = utility.list_collections()
if collections:
    print(f'  找到 {len(collections)} 个 Collection(s)')
    for c in collections:
        print(f'    - {c}')
else:
    print('  ✓ 没有 Collection（已清空）')
connections.disconnect('default')
" 2>/dev/null || echo "  ⚠️  无法检查 Collections"

echo
echo "=================================================================================="
echo "✅ Milvus 重置完成！"
echo "=================================================================================="
echo
echo "下一步："
echo "  1. 在 Dagster UI (http://localhost:3000) 运行 vectorize_documents_job"
echo "  2. 或使用 force_revectorize=true 重新向量化所有分块"
echo
