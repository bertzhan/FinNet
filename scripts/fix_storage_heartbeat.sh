#!/bin/bash

# 修复 Storage 节点心跳失败问题
# 错误: Heartbeat failed, status:Machine not existed!

echo "=========================================="
echo "修复 Storage 节点心跳失败"
echo "=========================================="
echo ""

# 检查 Graph 服务是否运行
if ! docker ps | grep -q finnet-nebula-graphd; then
    echo "错误: Graph 服务未运行"
    echo "请先启动: docker-compose up -d nebula-graphd"
    exit 1
fi

# 自动检测网络名称
NETWORK_NAME=$(docker inspect finnet-nebula-graphd --format='{{range $net, $v := .NetworkSettings.Networks}}{{$net}}{{end}}' 2>/dev/null | head -n1)
if [ -z "$NETWORK_NAME" ]; then
    NETWORK_NAME="finnet_finnet-network"
fi

CONSOLE_IMAGE="vesoft/nebula-console:v3.6.0"

# 检查镜像是否存在
if ! docker image inspect "$CONSOLE_IMAGE" > /dev/null 2>&1; then
    echo "正在拉取 nebula-console 镜像..."
    docker pull "$CONSOLE_IMAGE"
fi

echo "网络名称: $NETWORK_NAME"
echo ""

# 1. 检查当前节点状态
echo "1. 当前节点状态:"
echo "----------------------------------------"
docker run --rm --network "$NETWORK_NAME" "$CONSOLE_IMAGE" \
    -addr finnet-nebula-graphd \
    -port 9669 \
    -u root \
    -p nebula \
    -e "SHOW HOSTS;" 2>&1 | grep -A 10 "Host\|Status"
echo ""

# 2. 添加 Storage 节点
echo "2. 添加 Storage 节点到 Meta 服务..."
echo "----------------------------------------"
echo "执行: ADD HOSTS \"finnet-nebula-storaged\":9779;"
echo ""

ADD_OUTPUT=$(docker run --rm --network "$NETWORK_NAME" "$CONSOLE_IMAGE" \
    -addr finnet-nebula-graphd \
    -port 9669 \
    -u root \
    -p nebula \
    -e "ADD HOSTS \"finnet-nebula-storaged\":9779;" 2>&1)

echo "$ADD_OUTPUT"
echo ""

# 3. 等待节点注册（需要时间让心跳生效）
echo "3. 等待 Storage 节点注册到 Meta 服务..."
echo "----------------------------------------"
echo "等待中（最多 30 秒）..."
echo ""

for i in {1..15}; do
    HOSTS_OUTPUT=$(docker run --rm --network "$NETWORK_NAME" "$CONSOLE_IMAGE" \
        -addr finnet-nebula-graphd \
        -port 9669 \
        -u root \
        -p nebula \
        -e "SHOW HOSTS;" 2>/dev/null)
    
    if echo "$HOSTS_OUTPUT" | grep -q "ONLINE"; then
        echo "✓ Storage 节点已上线！"
        echo ""
        echo "节点状态:"
        echo "$HOSTS_OUTPUT" | grep -A 10 "Host\|Status"
        echo ""
        echo "=========================================="
        echo "修复成功！"
        echo "=========================================="
        echo ""
        echo "现在可以："
        echo "1. 运行初始化脚本创建空间: ./scripts/init_nebula.sh"
        echo "2. 检查服务状态: ./scripts/check_services.sh"
        exit 0
    fi
    
    if echo "$HOSTS_OUTPUT" | grep -q "finnet-nebula-storaged"; then
        STATUS=$(echo "$HOSTS_OUTPUT" | grep "finnet-nebula-storaged" | awk '{print $3}')
        echo "节点状态: $STATUS (等待中... $i/15)"
    else
        echo "节点未找到 (等待中... $i/15)"
    fi
    
    sleep 2
done

# 如果仍未上线
echo ""
echo "⚠ Storage 节点仍未上线"
echo ""
echo "当前节点状态:"
docker run --rm --network "$NETWORK_NAME" "$CONSOLE_IMAGE" \
    -addr finnet-nebula-graphd \
    -port 9669 \
    -u root \
    -p nebula \
    -e "SHOW HOSTS;" 2>&1 | grep -A 10 "Host\|Status"
echo ""

echo "可能原因："
echo "1. Meta 服务未正常运行"
echo "2. Storage 服务无法连接到 Meta"
echo "3. 需要更多时间让心跳生效"
echo ""
echo "建议操作："
echo "1. 检查 Meta 服务: docker-compose logs nebula-metad | tail -20"
echo "2. 重启 Storage 服务: docker-compose restart nebula-storaged"
echo "3. 等待 30 秒后再次检查: ./scripts/fix_storage_heartbeat.sh"
echo ""
