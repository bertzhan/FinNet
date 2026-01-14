#!/bin/bash

# 安装项目依赖脚本

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}安装 FinNet 项目依赖${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 获取项目根目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ 未找到 python3${NC}"
    exit 1
fi

# 检查 requirements.txt
REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo -e "${RED}❌ 未找到 requirements.txt${NC}"
    exit 1
fi

echo -e "${BLUE}项目根目录: $PROJECT_ROOT${NC}"
echo -e "${BLUE}依赖文件: $REQUIREMENTS_FILE${NC}"
echo ""

# 安装依赖
echo -e "${BLUE}正在安装依赖...${NC}"
pip3 install -r "$REQUIREMENTS_FILE"

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ 依赖安装成功！${NC}"
    echo ""
    echo -e "${BLUE}已安装的主要包：${NC}"
    python3 -c "
import sys
packages = ['pydantic_settings', 'dagster', 'minio', 'psycopg2', 'sqlalchemy', 'pymilvus']
for pkg in packages:
    try:
        mod = __import__(pkg.replace('-', '_'))
        version = getattr(mod, '__version__', 'unknown')
        print(f'  ✅ {pkg}: {version}')
    except ImportError:
        print(f'  ❌ {pkg}: 未安装')
" 2>/dev/null || echo "  (无法检查版本)"
else
    echo ""
    echo -e "${RED}❌ 依赖安装失败${NC}"
    echo ""
    echo -e "${YELLOW}提示：${NC}"
    echo "1. 检查网络连接"
    echo "2. 尝试使用国内镜像: pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}安装完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}下一步：${NC}"
echo "1. 运行测试: bash scripts/test_dagster_integration.sh"
echo "2. 启动 Dagster UI: bash scripts/start_dagster.sh"
echo ""
