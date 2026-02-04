#!/bin/bash
# Dagster UI 诊断脚本

echo "=========================================="
echo "Dagster UI 诊断工具"
echo "=========================================="
echo ""

# 1. 检查 Dagster 进程
echo "1. 检查 Dagster 进程"
echo "------------------------------------------"
ps aux | grep dagster | grep -v grep | head -5
echo ""

# 2. 检查端口占用
echo "2. 检查 Dagster UI 端口 (61879)"
echo "------------------------------------------"
lsof -i :61879 | head -5
echo ""

# 3. 查找活动的 Dagster home 目录
echo "3. 活动的 Dagster Home 目录"
echo "------------------------------------------"
ps aux | grep dagster_webserver | grep -v grep | head -1 | grep -oE '\.tmp_dagster_home_[a-z0-9]+' | head -1
DAGSTER_HOME=$(ps aux | grep dagster_webserver | grep "61879" -B5 -A5 | grep -oE '\.tmp_dagster_home_[a-z0-9]+' | head -1)
if [ -z "$DAGSTER_HOME" ]; then
    DAGSTER_HOME=$(ps aux | grep dagster_webserver | grep -v grep | head -1 | grep -oE '\.tmp_dagster_home_[a-z0-9]+' | head -1)
fi
echo "找到的 Dagster Home: $DAGSTER_HOME"
echo ""

# 4. 检查最近的运行
if [ ! -z "$DAGSTER_HOME" ]; then
    echo "4. 最近的运行记录"
    echo "------------------------------------------"
    ls -lth /Users/han/PycharmProjects/FinNet/$DAGSTER_HOME/storage/ 2>/dev/null | head -5
    echo ""

    # 5. 检查最新运行的日志
    echo "5. 最新运行的日志文件"
    echo "------------------------------------------"
    LATEST_RUN=$(ls -t /Users/han/PycharmProjects/FinNet/$DAGSTER_HOME/storage/ 2>/dev/null | head -1)
    if [ ! -z "$LATEST_RUN" ]; then
        echo "最新运行 ID: $LATEST_RUN"
        ls -lh /Users/han/PycharmProjects/FinNet/$DAGSTER_HOME/storage/$LATEST_RUN/compute_logs/ 2>/dev/null
        echo ""

        # 6. 显示最新日志的最后几行
        echo "6. 最新错误日志 (最后 10 行)"
        echo "------------------------------------------"
        tail -10 /Users/han/PycharmProjects/FinNet/$DAGSTER_HOME/storage/$LATEST_RUN/compute_logs/*.err 2>/dev/null | tail -10
        echo ""

        echo "7. 最新输出日志 (最后 10 行)"
        echo "------------------------------------------"
        tail -10 /Users/han/PycharmProjects/FinNet/$DAGSTER_HOME/storage/$LATEST_RUN/compute_logs/*.out 2>/dev/null | tail -10
        echo ""
    fi
fi

# 8. 建议
echo "=========================================="
echo "诊断建议"
echo "=========================================="
echo ""
echo "如果 Dagster UI 显示不出内容，尝试以下方法："
echo ""
echo "1. 刷新浏览器页面 (Cmd+R 或 F5)"
echo "2. 清除浏览器缓存后重新打开"
echo "3. 在 Dagster UI 中点击 'Runs' 标签页"
echo "4. 检查浏览器开发者工具的 Console 是否有错误"
echo "5. 重启 Dagster:"
echo "   - 按 Ctrl+C 停止当前的 dagster dev"
echo "   - 运行: dagster dev"
echo ""
echo "如果任务正在运行但 UI 不显示，可能需要等待："
echo "- MinerU API 解析大文件可能需要 5-30 分钟"
echo "- 检查日志目录确认任务是否真的在运行"
echo ""
