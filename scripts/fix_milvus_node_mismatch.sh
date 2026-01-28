#!/bin/bash
# 快速修复 Milvus 节点不匹配错误
# 错误: node not match[expectedNodeID=X][actualNodeID=Y]

set -e

echo "=================================================================================="
echo "修复 Milvus 节点不匹配错误"
echo "=================================================================================="
echo
echo "错误: node not match[expectedNodeID=X][actualNodeID=Y]"
echo
echo "此错误通常是因为 Milvus 重启后节点 ID 变化，但 etcd 中仍保留旧的节点信息。"
echo "解决方案：清理 etcd 数据，让 Milvus 重新初始化。"
echo
echo "⚠️  警告："
echo "  - 这会删除 etcd 中的所有配置数据"
echo "  - 不会影响 Milvus 中存储的向量数据（存储在 MinIO）"
echo "  - Milvus 会重新初始化所有节点信息"
echo

read -p "确认继续? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "取消操作"
    exit 0
fi

echo
echo "步骤 1: 停止 Milvus 和 etcd 服务..."
docker-compose stop milvus etcd || true

echo
echo "步骤 2: 清理 etcd 数据..."
# 方法1: 删除 etcd volume（推荐）
if docker volume ls | grep -q finnet_etcd_data; then
    echo "  删除 etcd volume..."
    docker volume rm finnet_etcd_data || true
else
    echo "  etcd volume 不存在，跳过"
fi

# 方法2: 如果 volume 删除失败，尝试清理容器内数据
echo "  清理 etcd 容器内数据..."
docker exec finnet-etcd sh -c 'rm -rf /etcd/*' 2>/dev/null || true

echo
echo "步骤 3: 重新启动 etcd..."
docker-compose up -d etcd

echo
echo "等待 etcd 启动（5秒）..."
sleep 5

echo
echo "步骤 4: 检查 etcd 状态..."
if docker ps --filter "name=finnet-etcd" --format "{{.Status}}" | grep -q "healthy\|Up"; then
    echo "  ✅ etcd 已启动"
else
    echo "  ⚠️  etcd 可能还在启动中"
fi

echo
echo "步骤 5: 重新启动 Milvus..."
docker-compose up -d milvus

echo
echo "=================================================================================="
echo "✅ 修复完成！"
echo "=================================================================================="
echo
echo "请等待几秒钟让 Milvus 完全启动，然后检查状态："
echo "  docker-compose ps"
echo
echo "查看 Milvus 日志："
echo "  docker-compose logs -f milvus"
echo
