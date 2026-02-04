#!/bin/bash
# 修复 Dagster 多实例问题

echo "=========================================="
echo "Dagster 多实例修复工具"
echo "=========================================="
echo ""

# 1. 显示所有 Dagster webserver 实例
echo "1. 当前运行的所有 Dagster Web Server 实例："
echo "------------------------------------------"
ps aux | grep dagster_webserver | grep -v grep | while read line; do
    PID=$(echo "$line" | awk '{print $2}')
    HOME_DIR=$(echo "$line" | grep -oE '\.tmp_dagster_home_[a-z0-9]+' | head -1)
    PORT=$(lsof -p $PID 2>/dev/null | grep LISTEN | awk '{print $9}' | grep -oE ':[0-9]+' | head -1 | tr -d ':')
    echo "PID: $PID | Home: $HOME_DIR | Port: ${PORT:-未知}"
done
echo ""

# 2. 找到有活动运行的实例
echo "2. 检查哪些实例有活动的任务运行："
echo "------------------------------------------"
for home_dir in /Users/han/PycharmProjects/FinNet/.tmp_dagster_home_*/; do
    if [ -d "$home_dir/storage" ]; then
        HOME_NAME=$(basename "$home_dir")
        RUN_COUNT=$(ls "$home_dir/storage" 2>/dev/null | wc -l | tr -d ' ')
        if [ "$RUN_COUNT" -gt 0 ]; then
            LATEST_RUN=$(ls -t "$home_dir/storage" 2>/dev/null | head -1)
            if [ ! -z "$LATEST_RUN" ]; then
                echo "$HOME_NAME: $RUN_COUNT 个运行记录, 最新: $LATEST_RUN"

                # 检查是否有正在运行的任务
                COMPUTE_LOGS="$home_dir/storage/$LATEST_RUN/compute_logs"
                if [ -d "$COMPUTE_LOGS" ]; then
                    COMPLETE_FILES=$(ls "$COMPUTE_LOGS"/*.complete 2>/dev/null | wc -l | tr -d ' ')
                    TOTAL_FILES=$(ls "$COMPUTE_LOGS"/*.err 2>/dev/null | wc -l | tr -d ' ')
                    if [ "$TOTAL_FILES" -gt 0 ]; then
                        if [ "$COMPLETE_FILES" -lt "$TOTAL_FILES" ]; then
                            echo "  ⚠️  可能有任务正在运行 (${COMPLETE_FILES}/${TOTAL_FILES} 完成)"

                            # 找到这个实例的端口
                            PID=$(ps aux | grep dagster_webserver | grep "$HOME_NAME" | grep -v grep | awk '{print $2}' | head -1)
                            if [ ! -z "$PID" ]; then
                                PORT=$(lsof -p $PID 2>/dev/null | grep LISTEN | awk '{print $9}' | grep -oE ':[0-9]+' | head -1 | tr -d ':')
                                echo "  📡 UI 地址: http://127.0.0.1:${PORT}"
                            fi
                        fi
                    fi
                fi
            fi
        fi
    fi
done
echo ""

# 3. 建议操作
echo "=========================================="
echo "建议操作"
echo "=========================================="
echo ""
echo "你有以下选择："
echo ""
echo "选项 1: 清理所有 Dagster 进程并重新启动"
echo "  1. 停止所有 Dagster 进程:"
echo "     pkill -f dagster"
echo "  2. 等待几秒钟"
echo "  3. 重新启动:"
echo "     dagster dev"
echo ""
echo "选项 2: 访问正在运行任务的正确实例"
echo "  - 查看上面显示的 UI 地址，访问有运行任务的那个实例"
echo ""
echo "选项 3: 手动停止多余的实例"
echo "  - 使用 kill <PID> 停止不需要的实例"
echo ""
