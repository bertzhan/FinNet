#!/bin/bash

# NebulaGraph 部署状态检查脚本

echo "=========================================="
echo "NebulaGraph 部署状态检查"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SUCCESS_COUNT=0
FAIL_COUNT=0

# 检查函数
check_item() {
    local name=$1
    local command=$2
    
    echo -n "检查 $name ... "
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 通过${NC}"
        ((SUCCESS_COUNT++))
        return 0
    else
        echo -e "${RED}✗ 失败${NC}"
        ((FAIL_COUNT++))
        return 1
    fi
}

# 1. 检查容器状态
echo "1. 容器状态检查:"
echo "----------------------------------------"
check_item "Meta 容器运行" "docker ps --filter 'name=finnet-nebula-metad' --filter 'status=running' --format '{{.Names}}' | grep -q finnet-nebula-metad"
check_item "Storage 容器运行" "docker ps --filter 'name=finnet-nebula-storaged' --filter 'status=running' --format '{{.Names}}' | grep -q finnet-nebula-storaged"
check_item "Graph 容器运行" "docker ps --filter 'name=finnet-nebula-graphd' --filter 'status=running' --format '{{.Names}}' | grep -q finnet-nebula-graphd"
echo ""

# 2. 检查端口监听
echo "2. 端口监听检查:"
echo "----------------------------------------"
check_item "Meta 端口 9559" "nc -z localhost 9559 2>/dev/null || timeout 1 bash -c '</dev/tcp/localhost/9559' 2>/dev/null"
check_item "Meta HTTP 端口 19559" "curl -sf http://localhost:19559/status > /dev/null 2>&1"
check_item "Storage 端口 9779" "nc -z localhost 9779 2>/dev/null || timeout 1 bash -c '</dev/tcp/localhost/9779' 2>/dev/null"
check_item "Storage HTTP 端口 19779" "curl -sf http://localhost:19779/status > /dev/null 2>&1"
check_item "Graph 端口 9669" "nc -z localhost 9669 2>/dev/null || timeout 1 bash -c '</dev/tcp/localhost/9669' 2>/dev/null"
check_item "Graph HTTP 端口 19669" "curl -sf http://localhost:19669/status > /dev/null 2>&1"
echo ""

# 3. 检查服务健康状态
echo "3. 服务健康状态:"
echo "----------------------------------------"
META_STATUS=$(curl -sf http://localhost:19559/status 2>/dev/null)
if [ -n "$META_STATUS" ]; then
    echo -e "Meta 服务: ${GREEN}✓ 健康${NC}"
    ((SUCCESS_COUNT++))
else
    echo -e "Meta 服务: ${RED}✗ 不健康${NC}"
    ((FAIL_COUNT++))
fi

STORAGE_STATUS=$(curl -sf http://localhost:19779/status 2>/dev/null)
if [ -n "$STORAGE_STATUS" ]; then
    echo -e "Storage 服务: ${GREEN}✓ 健康${NC}"
    ((SUCCESS_COUNT++))
else
    echo -e "Storage 服务: ${RED}✗ 不健康${NC}"
    ((FAIL_COUNT++))
fi

GRAPH_STATUS=$(curl -sf http://localhost:19669/status 2>/dev/null)
if [ -n "$GRAPH_STATUS" ]; then
    echo -e "Graph 服务: ${GREEN}✓ 健康${NC}"
    ((SUCCESS_COUNT++))
else
    echo -e "Graph 服务: ${RED}✗ 不健康${NC}"
    ((FAIL_COUNT++))
fi
echo ""

# 4. 检查节点状态（需要 nebula-console）
echo "4. 节点状态检查:"
echo "----------------------------------------"
NETWORK_NAME=$(docker inspect finnet-nebula-graphd --format='{{range $net, $v := .NetworkSettings.Networks}}{{$net}}{{end}}' 2>/dev/null | head -n1)
if [ -z "$NETWORK_NAME" ]; then
    NETWORK_NAME="finnet_finnet-network"
fi

CONSOLE_IMAGE="vesoft/nebula-console:v3.6.0"
if docker image inspect "$CONSOLE_IMAGE" > /dev/null 2>&1; then
    HOSTS_OUTPUT=$(docker run --rm --network "$NETWORK_NAME" "$CONSOLE_IMAGE" \
        -addr finnet-nebula-graphd \
        -port 9669 \
        -u root \
        -p nebula \
        -e "SHOW HOSTS;" 2>/dev/null)
    
    if echo "$HOSTS_OUTPUT" | grep -q "ONLINE"; then
        echo -e "Storage 节点状态: ${GREEN}✓ ONLINE${NC}"
        echo ""
        echo "节点详情:"
        echo "$HOSTS_OUTPUT" | grep -A 10 "Host\|Status"
        ((SUCCESS_COUNT++))
    else
        echo -e "Storage 节点状态: ${RED}✗ OFFLINE 或未添加${NC}"
        echo ""
        echo "节点详情:"
        echo "$HOSTS_OUTPUT" | grep -A 10 "Host\|Status" || echo "无法获取节点信息"
        ((FAIL_COUNT++))
    fi
else
    echo -e "${YELLOW}⚠ nebula-console 镜像不存在，跳过节点状态检查${NC}"
    echo "  运行: docker pull vesoft/nebula-console:v3.6.0"
fi
echo ""

# 5. 检查空间（如果已创建）
echo "5. 知识图谱空间检查:"
echo "----------------------------------------"
if docker image inspect "$CONSOLE_IMAGE" > /dev/null 2>&1; then
    SPACES_OUTPUT=$(docker run --rm --network "$NETWORK_NAME" "$CONSOLE_IMAGE" \
        -addr finnet-nebula-graphd \
        -port 9669 \
        -u root \
        -p nebula \
        -e "SHOW SPACES;" 2>/dev/null)
    
    if echo "$SPACES_OUTPUT" | grep -q "finnet_kg"; then
        echo -e "空间 finnet_kg: ${GREEN}✓ 已创建${NC}"
        echo ""
        echo "空间列表:"
        echo "$SPACES_OUTPUT" | grep -A 5 "Name"
        ((SUCCESS_COUNT++))
    else
        echo -e "空间 finnet_kg: ${YELLOW}⚠ 未创建${NC}"
        echo "  运行: ./scripts/init_nebula.sh"
    fi
else
    echo -e "${YELLOW}⚠ nebula-console 镜像不存在，跳过空间检查${NC}"
fi
echo ""

# 6. 检查网络连接
echo "6. 网络连接检查:"
echo "----------------------------------------"
if docker exec finnet-nebula-storaged ping -c 1 nebula-metad > /dev/null 2>&1; then
    echo -e "Storage -> Meta: ${GREEN}✓ 连通${NC}"
    ((SUCCESS_COUNT++))
else
    echo -e "Storage -> Meta: ${RED}✗ 不通${NC}"
    ((FAIL_COUNT++))
fi

if docker exec finnet-nebula-graphd ping -c 1 nebula-metad > /dev/null 2>&1; then
    echo -e "Graph -> Meta: ${GREEN}✓ 连通${NC}"
    ((SUCCESS_COUNT++))
else
    echo -e "Graph -> Meta: ${RED}✗ 不通${NC}"
    ((FAIL_COUNT++))
fi

if docker exec finnet-nebula-graphd ping -c 1 nebula-storaged > /dev/null 2>&1; then
    echo -e "Graph -> Storage: ${GREEN}✓ 连通${NC}"
    ((SUCCESS_COUNT++))
else
    echo -e "Graph -> Storage: ${RED}✗ 不通${NC}"
    ((FAIL_COUNT++))
fi
echo ""

# 总结
echo "=========================================="
echo "检查总结"
echo "=========================================="
echo -e "通过: ${GREEN}$SUCCESS_COUNT${NC}"
echo -e "失败: ${RED}$FAIL_COUNT${NC}"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}✓ NebulaGraph 部署成功！${NC}"
    exit 0
else
    echo -e "${RED}✗ NebulaGraph 部署存在问题，请检查上述失败项${NC}"
    echo ""
    echo "排查建议:"
    echo "1. 查看服务日志: docker-compose logs nebula-metad nebula-storaged nebula-graphd"
    echo "2. 重启服务: docker-compose restart"
    echo "3. 运行修复脚本: ./scripts/fix_storage.sh"
    exit 1
fi
