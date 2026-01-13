#!/bin/bash

# NebulaGraph 配置检查脚本

echo "=========================================="
echo "NebulaGraph 配置检查"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 1. 检查存储卷
echo "1. 存储卷检查:"
echo "----------------------------------------"
VOLUMES=("nebula_metad_data" "nebula_metad_logs" "nebula_storaged_data" "nebula_storaged_logs" "nebula_graphd_logs")

for vol in "${VOLUMES[@]}"; do
    if docker volume inspect "finnet_${vol}" > /dev/null 2>&1 || docker volume inspect "${vol}" > /dev/null 2>&1; then
        echo -e "✓ 卷 $vol 存在"
        VOL_INFO=$(docker volume inspect "finnet_${vol}" 2>/dev/null || docker volume inspect "${vol}" 2>/dev/null)
        VOL_PATH=$(echo "$VOL_INFO" | grep -o '"/var/lib/docker/volumes/[^"]*"' | head -1 | tr -d '"')
        if [ -n "$VOL_PATH" ]; then
            echo "  路径: $VOL_PATH"
        fi
    else
        echo -e "${YELLOW}⚠ 卷 $vol 不存在（首次启动时会自动创建）${NC}"
    fi
done
echo ""

# 2. 检查容器内的存储路径权限
echo "2. 容器内存储路径检查:"
echo "----------------------------------------"
if docker ps | grep -q finnet-nebula-storaged; then
    echo "Storage 容器存储路径:"
    docker exec finnet-nebula-storaged ls -ld /data/storage 2>/dev/null || echo "  ✗ 路径不存在或无法访问"
    docker exec finnet-nebula-storaged ls -ld /logs 2>/dev/null || echo "  ✗ 日志路径不存在或无法访问"
    
    echo ""
    echo "Storage 容器存储空间:"
    docker exec finnet-nebula-storaged df -h /data/storage 2>/dev/null || echo "  ✗ 无法获取存储空间信息"
else
    echo "Storage 容器未运行，跳过检查"
fi
echo ""

# 3. 检查账户配置
echo "3. 账户配置检查:"
echo "----------------------------------------"
echo "NebulaGraph 默认配置:"
echo "  - 身份验证: 默认关闭（无需密码）"
echo "  - 默认用户: root"
echo "  - 默认密码: nebula（身份验证关闭时任意密码都可）"
echo ""
echo "当前配置:"
grep -A 2 "nebula-metad:" docker-compose.yml | grep "USER:" || echo "  未找到 USER 配置"
grep -A 2 "nebula-storaged:" docker-compose.yml | grep "USER:" || echo "  未找到 USER 配置"
grep -A 2 "nebula-graphd:" docker-compose.yml | grep "USER:" || echo "  未找到 USER 配置"
echo ""

# 4. 检查环境变量
echo "4. 环境变量检查:"
echo "----------------------------------------"
echo "Meta 服务环境变量:"
docker inspect finnet-nebula-metad --format='{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep -E "USER|PASSWORD|TZ" || echo "  容器未运行"
echo ""

# 5. 检查数据路径配置
echo "5. 数据路径配置检查:"
echo "----------------------------------------"
echo "Meta 服务数据路径:"
docker inspect finnet-nebula-metad --format='{{range .Mounts}}{{println .Destination}}{{end}}' 2>/dev/null | grep -E "data|log" || echo "  容器未运行"
echo ""

# 6. 检查命令参数
echo "6. 命令参数检查:"
echo "----------------------------------------"
if docker ps | grep -q finnet-nebula-storaged; then
    echo "Storage 服务启动命令:"
    docker inspect finnet-nebula-storaged --format='{{range .Args}}{{println .}}{{end}}' 2>/dev/null | head -10
else
    echo "Storage 容器未运行"
fi
echo ""

# 7. 检查磁盘空间
echo "7. 主机磁盘空间检查:"
echo "----------------------------------------"
df -h | head -2
echo ""

# 8. 建议
echo "=========================================="
echo "配置检查总结"
echo "=========================================="
echo ""
echo "存储空间:"
echo "  - Docker 卷会自动创建，无需手动分配"
echo "  - 如果卷不存在，首次启动时会自动创建"
echo ""
echo "账户密码:"
echo "  - NebulaGraph 默认身份验证关闭"
echo "  - 可以使用 root/nebula 或任意密码连接"
echo "  - 如需启用身份验证，需要修改配置文件"
echo ""
echo "如果服务仍无法启动，检查:"
echo "  1. 磁盘空间是否充足: df -h"
echo "  2. 容器日志: docker-compose logs nebula-storaged"
echo "  3. 卷权限: docker volume inspect finnet_nebula_storaged_data"
echo ""
