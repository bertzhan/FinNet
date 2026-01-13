#!/bin/bash

# NebulaGraph Storage 节点快速修复脚本

echo "=========================================="
echo "NebulaGraph Storage 节点修复工具"
echo "=========================================="
echo ""

# 检查服务是否运行
if ! docker ps | grep -q finnet-nebula-graphd; then
    echo "错误: NebulaGraph 服务未运行"
    echo "请先运行: docker-compose up -d"
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

# 步骤1: 显示当前节点状态
echo "1. 当前节点状态:"
echo "----------------------------------------"
docker run --rm --network "$NETWORK_NAME" "$CONSOLE_IMAGE" \
    -addr finnet-nebula-graphd \
    -port 9669 \
    -u root \
    -p nebula \
    -e "SHOW HOSTS;" 2>&1
echo ""

# 步骤2: 添加 Storage 节点
echo "2. 添加 Storage 节点到集群..."
echo "----------------------------------------"
ADD_OUTPUT=$(docker run --rm --network "$NETWORK_NAME" "$CONSOLE_IMAGE" \
    -addr finnet-nebula-graphd \
    -port 9669 \
    -u root \
    -p nebula \
    -e "ADD HOSTS \"finnet-nebula-storaged\":9779;" 2>&1)

echo "$ADD_OUTPUT"
echo ""

# 步骤3: 等待节点上线
echo "3. 等待 Storage 节点上线（最多等待 30 秒）..."
echo "----------------------------------------"
for i in {1..15}; do
    RESULT=$(docker run --rm --network "$NETWORK_NAME" "$CONSOLE_IMAGE" \
        -addr finnet-nebula-graphd \
        -port 9669 \
        -u root \
        -p nebula \
        -e "SHOW HOSTS;" 2>/dev/null | grep -c "ONLINE")
    
    if [ "$RESULT" -ge 1 ]; then
        echo "✓ Storage 节点已上线！"
        echo ""
        echo "当前节点状态:"
        docker run --rm --network "$NETWORK_NAME" "$CONSOLE_IMAGE" \
            -addr finnet-nebula-graphd \
            -port 9669 \
            -u root \
            -p nebula \
            -e "SHOW HOSTS;" 2>&1
        echo ""
        echo "=========================================="
        echo "修复完成！现在可以运行 init_nebula.sh 创建空间"
        echo "=========================================="
        exit 0
    fi
    
    echo "等待中... ($i/15)"
    sleep 2
done

# 如果仍未上线
echo ""
echo "✗ Storage 节点仍未上线"
echo ""
echo "请检查以下内容:"
echo "1. Storage 服务是否正常运行:"
echo "   docker ps | grep nebula-storaged"
echo ""
echo "2. Storage 服务日志:"
echo "   docker-compose logs nebula-storaged | tail -50"
echo ""
echo "3. Meta 服务日志:"
echo "   docker-compose logs nebula-metad | tail -50"
echo ""
echo "4. 检查网络连接:"
echo "   docker network inspect $NETWORK_NAME | grep -A 5 nebula-storaged"
echo ""
