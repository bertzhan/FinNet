#!/bin/bash

# NebulaGraph Storage OFFLINE 状态修复脚本

echo "=========================================="
echo "NebulaGraph Storage OFFLINE 状态修复"
echo "=========================================="
echo ""

# 检查容器状态
echo "1. 检查容器状态:"
echo "----------------------------------------"
docker ps --filter "name=finnet-nebula" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

# 检查 Storage 容器是否运行
if ! docker ps | grep -q finnet-nebula-storaged; then
    echo "✗ Storage 容器未运行，正在启动..."
    docker-compose up -d nebula-storaged
    echo "等待 Storage 服务启动..."
    sleep 10
fi

# 检查 Meta 容器是否运行
if ! docker ps | grep -q finnet-nebula-metad; then
    echo "✗ Meta 容器未运行，正在启动..."
    docker-compose up -d nebula-metad
    echo "等待 Meta 服务启动..."
    sleep 10
fi

# 检查 Graph 容器是否运行
if ! docker ps | grep -q finnet-nebula-graphd; then
    echo "✗ Graph 容器未运行，正在启动..."
    docker-compose up -d nebula-graphd
    echo "等待 Graph 服务启动..."
    sleep 10
fi

echo ""

# 检查网络连接
echo "2. 检查网络连接:"
echo "----------------------------------------"
NETWORK_NAME=$(docker inspect finnet-nebula-graphd --format='{{range $net, $v := .NetworkSettings.Networks}}{{$net}}{{end}}' 2>/dev/null | head -n1)
if [ -z "$NETWORK_NAME" ]; then
    NETWORK_NAME="finnet_finnet-network"
fi
echo "网络名称: $NETWORK_NAME"

# 检查 Storage 容器是否在网络上
STORAGE_IP=$(docker inspect finnet-nebula-storaged --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null)
if [ -n "$STORAGE_IP" ]; then
    echo "Storage 容器 IP: $STORAGE_IP"
else
    echo "✗ 无法获取 Storage 容器 IP"
fi
echo ""

# 检查服务日志
echo "3. 检查 Storage 服务日志（最后 20 行）:"
echo "----------------------------------------"
docker-compose logs --tail=20 nebula-storaged 2>&1 | grep -E "(ERROR|WARN|started|ready|listening)" || echo "无关键日志信息"
echo ""

# 检查 Meta 服务日志
echo "4. 检查 Meta 服务日志（最后 20 行）:"
echo "----------------------------------------"
docker-compose logs --tail=20 nebula-metad 2>&1 | grep -E "(ERROR|WARN|started|ready|listening)" || echo "无关键日志信息"
echo ""

# 尝试重启 Storage 服务
echo "5. 尝试重启 Storage 服务:"
echo "----------------------------------------"
echo "正在重启 Storage 服务..."
docker-compose restart nebula-storaged
echo "等待服务启动..."
sleep 15
echo ""

# 检查节点状态
CONSOLE_IMAGE="vesoft/nebula-console:v3.6.0"
if ! docker image inspect "$CONSOLE_IMAGE" > /dev/null 2>&1; then
    docker pull "$CONSOLE_IMAGE" > /dev/null 2>&1
fi

echo "6. 检查节点状态:"
echo "----------------------------------------"
docker run --rm --network "$NETWORK_NAME" "$CONSOLE_IMAGE" \
    -addr finnet-nebula-graphd \
    -port 9669 \
    -u root \
    -p nebula \
    -e "SHOW HOSTS;" 2>&1 | grep -A 10 "Host\|Status"
echo ""

# 如果仍然是 OFFLINE，提供进一步建议
echo "7. 如果节点仍然是 OFFLINE，请尝试:"
echo "----------------------------------------"
echo "1. 完全重启所有 NebulaGraph 服务:"
echo "   docker-compose restart nebula-metad nebula-storaged nebula-graphd"
echo ""
echo "2. 检查端口是否被占用:"
echo "   lsof -i :9779"
echo "   lsof -i :9559"
echo ""
echo "3. 检查容器网络连接:"
echo "   docker exec finnet-nebula-metad ping -c 2 finnet-nebula-storaged"
echo ""
echo "4. 查看完整日志:"
echo "   docker-compose logs nebula-storaged"
echo "   docker-compose logs nebula-metad"
echo ""
