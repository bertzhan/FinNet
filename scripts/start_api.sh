#!/bin/bash
# 启动 FinNet API 服务

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "=========================================="
echo "启动 FinNet API 服务"
echo "=========================================="
echo "项目目录: $PROJECT_DIR"
echo ""

# 检查 Python 环境
if ! command -v python &> /dev/null; then
    echo "错误: 未找到 Python"
    exit 1
fi

# 检查依赖
echo "检查依赖..."
python -c "import uvicorn" 2>/dev/null || {
    echo "错误: 未安装 uvicorn"
    echo "请运行: pip install uvicorn"
    exit 1
}

# 设置环境变量（如果未设置）
export API_HOST="${API_HOST:-0.0.0.0}"
export API_PORT="${API_PORT:-8000}"
export API_RELOAD="${API_RELOAD:-true}"

echo "配置:"
echo "  - 主机: $API_HOST"
echo "  - 端口: $API_PORT"
echo "  - 热重载: $API_RELOAD"
echo ""

# 启动服务
echo "启动 API 服务..."
echo "访问地址: http://localhost:$API_PORT"
echo "API 文档: http://localhost:$API_PORT/docs"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

python -m uvicorn src.api.main:app \
    --host "$API_HOST" \
    --port "$API_PORT" \
    --reload
