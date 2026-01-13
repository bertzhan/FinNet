#!/bin/bash

# NebulaGraph 初始化脚本
# 用于创建知识图谱的初始空间和基本配置

echo "=========================================="
echo "NebulaGraph 初始化"
echo "=========================================="
echo ""

# 检查 NebulaGraph 所有服务是否运行
echo "检查 NebulaGraph 服务状态..."
if ! docker ps | grep -q finnet-nebula-metad; then
    echo "错误: NebulaGraph Meta 服务未运行"
    echo "请先运行: docker-compose up -d nebula-metad nebula-storaged nebula-graphd"
    exit 1
fi

if ! docker ps | grep -q finnet-nebula-storaged; then
    echo "错误: NebulaGraph Storage 服务未运行"
    echo "请先运行: docker-compose up -d nebula-storaged"
    exit 1
fi

if ! docker ps | grep -q finnet-nebula-graphd; then
    echo "错误: NebulaGraph Graph 服务未运行"
    echo "请先运行: docker-compose up -d nebula-graphd"
    exit 1
fi

echo "✓ 所有 NebulaGraph 服务正在运行"
echo "等待服务完全启动..."
sleep 10

# 自动检测网络名称（Docker Compose 创建的网络）
NETWORK_NAME=$(docker inspect finnet-nebula-graphd --format='{{range $net, $v := .NetworkSettings.Networks}}{{$net}}{{end}}' 2>/dev/null | head -n1)

if [ -z "$NETWORK_NAME" ]; then
    # 如果无法自动检测，尝试常见的网络名称
    NETWORK_NAME="finnet_finnet-network"
    echo "⚠ 无法自动检测网络名称，使用默认值: $NETWORK_NAME"
else
    echo "✓ 检测到网络: $NETWORK_NAME"
fi

# 检查并拉取 nebula-console 镜像
CONSOLE_IMAGE="vesoft/nebula-console:v3.6.0"
if ! docker image inspect "$CONSOLE_IMAGE" > /dev/null 2>&1; then
    echo "正在拉取 nebula-console 镜像..."
    docker pull "$CONSOLE_IMAGE"
    if [ $? -ne 0 ]; then
        echo "✗ 镜像拉取失败，请检查网络连接"
        exit 1
    fi
    echo "✓ 镜像拉取完成"
fi

# 检查 Storage 节点是否就绪，并添加到集群
echo "检查 Storage 节点状态..."
STORAGE_READY=false
for i in {1..30}; do
    # 检查 Storage 节点是否已添加并在线
    RESULT=$(docker run --rm --network "$NETWORK_NAME" "$CONSOLE_IMAGE" \
        -addr finnet-nebula-graphd \
        -port 9669 \
        -u root \
        -p nebula \
        -e "SHOW HOSTS;" 2>/dev/null | grep -c "ONLINE")
    
    if [ "$RESULT" -ge 1 ]; then
        STORAGE_READY=true
        echo "✓ Storage 节点已就绪"
        break
    fi
    
    # 如果 Storage 节点未添加，尝试添加
    if [ "$i" -eq 1 ]; then
        echo "添加 Storage 节点到集群..."
        ADD_RESULT=$(docker run --rm --network "$NETWORK_NAME" "$CONSOLE_IMAGE" \
            -addr finnet-nebula-graphd \
            -port 9669 \
            -u root \
            -p nebula \
            -e "ADD HOSTS \"finnet-nebula-storaged\":9779;" 2>&1)
        
        if echo "$ADD_RESULT" | grep -q "Succeeded\|already"; then
            echo "✓ Storage 节点已添加，等待节点上线..."
            sleep 10  # 增加等待时间，让节点有时间注册
        elif echo "$ADD_RESULT" | grep -q "already"; then
            echo "✓ Storage 节点已存在，等待节点上线..."
            sleep 5
        else
            echo "⚠ 添加 Storage 节点时出现警告（可能已存在）"
            echo "   输出: $ADD_RESULT"
            sleep 5
        fi
    fi
    
    echo "等待 Storage 节点启动... ($i/30)"
    sleep 2
done

if [ "$STORAGE_READY" = false ]; then
    echo ""
    echo "✗ Storage 节点未就绪（等待了 60 秒）"
    echo ""
    echo "当前节点状态:"
    docker run --rm --network "$NETWORK_NAME" "$CONSOLE_IMAGE" \
        -addr finnet-nebula-graphd \
        -port 9669 \
        -u root \
        -p nebula \
        -e "SHOW HOSTS;" 2>&1 | head -20
    
    echo ""
    echo "请尝试以下步骤:"
    echo ""
    echo "1. 手动添加 Storage 节点:"
    echo "   docker run --rm -it --network $NETWORK_NAME $CONSOLE_IMAGE \\"
    echo "     -addr finnet-nebula-graphd -port 9669 -u root -p nebula \\"
    echo "     -e \"ADD HOSTS \\\"finnet-nebula-storaged\\\":9779;\""
    echo ""
    echo "2. 等待 10-20 秒后检查节点状态:"
    echo "   docker run --rm -it --network $NETWORK_NAME $CONSOLE_IMAGE \\"
    echo "     -addr finnet-nebula-graphd -port 9669 -u root -p nebula \\"
    echo "     -e \"SHOW HOSTS;\""
    echo ""
    echo "3. 如果节点状态为 OFFLINE，查看服务日志:"
    echo "   docker-compose logs nebula-storaged"
    echo "   docker-compose logs nebula-metad"
    echo ""
    echo "4. 运行诊断脚本:"
    echo "   ./scripts/diagnose_nebula.sh"
    echo ""
    exit 1
fi

echo ""
echo "正在创建知识图谱空间..."
echo ""

# 使用 nebula-console Docker 镜像创建知识图谱空间（Space）
# 对于单机部署，replica_factor=1 需要至少1个 Storage 节点
docker run --rm -it \
    --network "$NETWORK_NAME" \
    "$CONSOLE_IMAGE" \
    -addr finnet-nebula-graphd \
    -port 9669 \
    -u root \
    -p nebula \
    -e "CREATE SPACE IF NOT EXISTS finnet_kg (partition_num=10, replica_factor=1, vid_type=FIXED_STRING(32));"

if [ $? -eq 0 ]; then
    echo ""
    echo "等待空间创建完成..."
    sleep 5
    
    # 验证空间是否创建成功
    echo "验证空间创建..."
    docker run --rm -it \
        --network "$NETWORK_NAME" \
        "$CONSOLE_IMAGE" \
        -addr finnet-nebula-graphd \
        -port 9669 \
        -u root \
        -p nebula \
        -e "SHOW SPACES;" | grep -q finnet_kg
    
    if [ $? -eq 0 ]; then
        echo "✓ 空间 finnet_kg 创建成功"
    else
        echo "⚠ 空间可能未创建成功，请手动检查"
    fi
else
    echo "✗ 空间创建失败"
    exit 1
fi

echo ""
echo "=========================================="
echo "NebulaGraph 初始化完成"
echo "=========================================="
echo ""
echo "空间名称: finnet_kg"
echo "连接信息:"
echo "  - Graph服务: localhost:9669"
echo "  - 用户名: root"
echo "  - 密码: nebula"
echo ""
echo "使用 nebula-console 连接:"
echo "  docker run --rm -it --network $NETWORK_NAME vesoft/nebula-console:v3.6.0 -addr finnet-nebula-graphd -port 9669 -u root -p nebula"
echo ""
echo "或使用 Python 客户端连接:"
echo "  pip install nebula3-python"
echo "  from nebula3.gclient.net import ConnectionPool"
echo "  from nebula3.Config import Config"
