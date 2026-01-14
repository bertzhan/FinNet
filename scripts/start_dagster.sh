#!/bin/bash

# Dagster UI 启动脚本
# 用于快速启动 Dagster Web UI

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}启动 Dagster UI${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 获取脚本所在目录的父目录（项目根目录）
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# 切换到项目根目录
cd "$PROJECT_ROOT"

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 python3，请先安装 Python${NC}"
    exit 1
fi

# 检查是否安装了 dagster
if ! python3 -c "import dagster" 2>/dev/null; then
    echo -e "${YELLOW}警告: 未检测到 dagster，正在尝试安装...${NC}"
    pip install dagster dagster-webserver
    if [ $? -ne 0 ]; then
        echo -e "${RED}错误: 安装 dagster 失败，请手动运行: pip install dagster dagster-webserver${NC}"
        exit 1
    fi
fi

# 检查新的 Dagster 模块是否存在
DAGSTER_MODULE="src.processing.compute.dagster"
DAGSTER_FILE="$PROJECT_ROOT/src/processing/compute/dagster/__init__.py"

# 如果新模块不存在，尝试使用旧的
if [ ! -f "$DAGSTER_FILE" ]; then
    OLD_DAGSTER_FILE="$PROJECT_ROOT/src/crawler/dagster_jobs.py"
    if [ -f "$OLD_DAGSTER_FILE" ]; then
        echo -e "${YELLOW}使用旧的 Dagster 模块: src.crawler.dagster_jobs${NC}"
        DAGSTER_MODULE="src.crawler.dagster_jobs"
    else
        echo -e "${RED}错误: 未找到 Dagster 模块${NC}"
        echo "  请检查: $DAGSTER_FILE 或 $OLD_DAGSTER_FILE"
        exit 1
    fi
else
    echo -e "${GREEN}使用新的 Dagster 模块: $DAGSTER_MODULE${NC}"
fi

echo "项目根目录: $PROJECT_ROOT"
echo "Dagster 模块: $DAGSTER_MODULE"
echo ""

# 设置 PYTHONPATH 确保可以导入模块
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# 检查并提示 MinIO 配置
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}检测到 .env 文件，正在加载环境变量...${NC}"
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

# 检查 MinIO 配置
if [ "${USE_MINIO:-false}" = "true" ] || [ "${MINIO_ENDPOINT:-}" != "" ]; then
    echo -e "${GREEN}✓ MinIO 已启用${NC}"
    echo "  Endpoint: ${MINIO_ENDPOINT:-localhost:9000}"
    echo "  Bucket: ${MINIO_BUCKET:-finnet-datalake}"
else
    echo -e "${YELLOW}⚠ MinIO 未启用${NC}"
    echo "  要启用 MinIO 上传，请在 .env 文件中设置："
    echo "    MINIO_ENDPOINT=localhost:9000"
    echo "    MINIO_ACCESS_KEY=admin"
    echo "    MINIO_SECRET_KEY=admin123456"
    echo "    MINIO_BUCKET=finnet-datalake"
    echo ""
fi

echo ""
echo -e "${GREEN}正在启动 Dagster UI...${NC}"
echo "访问地址: http://localhost:3000"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

# 启动 Dagster UI（使用模块方式）
dagster dev -m "$DAGSTER_MODULE"
