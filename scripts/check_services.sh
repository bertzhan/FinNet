#!/bin/bash

# FinNet MVP 服务连通性检查脚本

echo "=========================================="
echo "FinNet MVP 服务健康检查"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查函数
check_service() {
    local service_name=$1
    local check_command=$2
    
    echo -n "检查 $service_name ... "
    if eval "$check_command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 正常${NC}"
        return 0
    else
        echo -e "${RED}✗ 失败${NC}"
        return 1
    fi
}

# 检查MinIO
check_service "MinIO API" "curl -f http://localhost:9000/minio/health/live"
check_service "MinIO Console" "curl -f http://localhost:9001 > /dev/null"

# 检查PostgreSQL
check_service "PostgreSQL" "PGPASSWORD=finnet123456 psql -h localhost -U finnet -d finnet -c 'SELECT 1' > /dev/null 2>&1"

# 检查Milvus
check_service "Milvus" "curl -f http://localhost:9091/healthz > /dev/null 2>&1"

# 检查etcd
check_service "etcd" "docker exec finnet-etcd etcdctl endpoint health > /dev/null 2>&1"

echo ""
echo "=========================================="
echo "检查完成"
echo "=========================================="
