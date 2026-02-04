#!/bin/bash
# 一键重启 Dagster - 清理所有旧实例

echo "=========================================="
echo "Dagster 一键重启脚本"
echo "=========================================="
echo ""

# 1. 停止所有 Dagster 进程
echo "1. 停止所有 Dagster 进程..."
pkill -f dagster
sleep 3

# 2. 检查是否还有残留进程
REMAINING=$(ps aux | grep dagster | grep -v grep | wc -l | tr -d ' ')
if [ "$REMAINING" -gt 0 ]; then
    echo "⚠️  还有 $REMAINING 个 Dagster 进程，尝试强制停止..."
    pkill -9 -f dagster
    sleep 2
fi

# 3. 验证所有进程已停止
REMAINING=$(ps aux | grep dagster | grep -v grep | wc -l | tr -d ' ')
if [ "$REMAINING" -eq 0 ]; then
    echo "✅ 所有 Dagster 进程已停止"
else
    echo "❌ 仍有 $REMAINING 个进程运行，请手动检查:"
    ps aux | grep dagster | grep -v grep
    exit 1
fi

echo ""
echo "2. 启动新的 Dagster 实例..."
echo "------------------------------------------"

# 4. 进入项目目录
cd /Users/han/PycharmProjects/FinNet || exit 1

# 5. 启动 Dagster
echo "启动 Dagster dev..."
echo ""
echo "✅ Dagster 正在启动..."
echo "📡 UI 地址: http://127.0.0.1:3000"
echo ""
echo "提示:"
echo "- 在浏览器中访问上面的地址"
echo "- 按 Ctrl+C 停止 Dagster"
echo ""

dagster dev
