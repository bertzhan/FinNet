#!/bin/bash

# NebulaGraph 诊断脚本
# 用于检查 NebulaGraph 服务状态和排查问题

echo "=========================================="
echo "NebulaGraph 诊断工具"
echo "=========================================="
echo ""

# 检查容器状态
echo "1. 检查容器状态:"
echo "----------------------------------------"
docker ps --filter "name=finnet-nebula" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

# 检查网络
echo "2. 检查网络连接:"
echo "----------------------------------------"
NETWORK_NAME=$(docker inspect finnet-nebula-graphd --format='{{range $net, $v := .NetworkSettings.Networks}}{{$net}}{{end}}' 2>/dev/null | head -n1)
if [ -z "$NETWORK_NAME" ]; then
    NETWORK_NAME="finnet_finnet-network"
fi
echo "网络名称: $NETWORK_NAME"
echo ""

# 检查 nebula-console 镜像
CONSOLE_IMAGE="vesoft/nebula-console:v3.6.0"
if docker image inspect "$CONSOLE_IMAGE" > /dev/null 2>&1; then
    echo "✓ nebula-console 镜像已存在"
else
    echo "✗ nebula-console 镜像不存在，正在拉取..."
    docker pull "$CONSOLE_IMAGE"
fi
echo ""

# 检查 Storage 节点状态
echo "3. 检查 Storage 节点状态:"
echo "----------------------------------------"
docker run --rm --network "$NETWORK_NAME" "$CONSOLE_IMAGE" \
    -addr finnet-nebula-graphd \
    -port 9669 \
    -u root \
    -p nebula \
    -e "SHOW HOSTS;" 2>&1

echo ""
echo ""

# 如果 Storage 节点未添加，提供添加命令
echo "4. 如果 Storage 节点未显示为 ONLINE，请执行:"
echo "----------------------------------------"
echo "docker run --rm -it --network $NETWORK_NAME $CONSOLE_IMAGE \\"
echo "  -addr finnet-nebula-graphd -port 9669 -u root -p nebula \\"
echo "  -e \"ADD HOSTS \\\"finnet-nebula-storaged\\\":9779;\""
echo ""

# 检查服务日志
echo "5. 查看服务日志:"
echo "----------------------------------------"
echo "Meta 服务日志:"
echo "  docker-compose logs --tail=50 nebula-metad"
echo ""
echo "Storage 服务日志:"
echo "  docker-compose logs --tail=50 nebula-storaged"
echo ""
echo "Graph 服务日志:"
echo "  docker-compose logs --tail=50 nebula-graphd"
echo ""
