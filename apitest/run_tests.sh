#!/bin/bash
# FinNet API 测试运行脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "======================================================================"
echo "FinNet API 测试套件"
echo "======================================================================"
echo ""
echo "项目路径: $PROJECT_ROOT"
echo "测试路径: $SCRIPT_DIR"
echo ""

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 python3 命令${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1)
echo "Python版本: $PYTHON_VERSION"
echo ""

# 检查API服务是否运行
echo "检查API服务状态..."
if curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ API服务正在运行${NC}"
else
    echo -e "${RED}✗ API服务未运行或无法访问${NC}"
    echo ""
    echo "请先启动API服务:"
    echo "  cd $PROJECT_ROOT"
    echo "  python -m src.api.main"
    echo ""
    exit 1
fi

echo ""
echo "======================================================================"
echo "开始运行测试..."
echo "======================================================================"
echo ""

# 进入测试目录
cd "$SCRIPT_DIR"

# 运行测试
if python3 run_all_tests.py; then
    echo ""
    echo "======================================================================"
    echo -e "${GREEN}✅ 所有测试完成！${NC}"
    echo "======================================================================"
    exit 0
else
    EXIT_CODE=$?
    echo ""
    echo "======================================================================"
    echo -e "${RED}❌ 测试失败（退出码: $EXIT_CODE）${NC}"
    echo "======================================================================"
    exit $EXIT_CODE
fi
