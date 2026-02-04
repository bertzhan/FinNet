#!/bin/bash
# 实时监控 Parse Job 运行状态

echo "=========================================="
echo "Parse Job 实时监控"
echo "=========================================="
echo ""

# 查找正在运行的 parse job 进程
echo "1. 查找正在运行的 Parse Job 进程..."
echo "------------------------------------------"
PARSE_PROCS=$(ps aux | grep -E "parse_pdf_job|parse_documents_op" | grep -v grep)

if [ -z "$PARSE_PROCS" ]; then
    echo "❌ 未找到正在运行的 Parse Job 进程"
    echo ""
    echo "可能的原因:"
    echo "1. Job 已经完成"
    echo "2. Job 还未启动"
    echo "3. Job 运行失败"
    echo ""
    echo "建议: 在 Dagster UI 中检查 Runs 列表"
else
    echo "✅ 找到运行中的 Parse Job:"
    echo "$PARSE_PROCS"
    echo ""

    # 提取进程 ID
    PID=$(echo "$PARSE_PROCS" | head -1 | awk '{print $2}')
    echo "主进程 PID: $PID"
    echo ""
fi

# 查找 Dagster webserver 进程及其 home 目录
echo "2. 查找 Dagster Web Server..."
echo "------------------------------------------"
WEB_PROCS=$(ps aux | grep dagster_webserver | grep "61879" | grep -v grep)

if [ -z "$WEB_PROCS" ]; then
    echo "❌ 未找到端口 61879 的 Dagster Web Server"
else
    WEB_PID=$(echo "$WEB_PROCS" | awk '{print $2}')
    echo "✅ Web Server PID: $WEB_PID"

    # 尝试从进程参数中提取 home 目录
    HOME_DIR=$(ps -p $WEB_PID -o command= | grep -oE 'base_dir: [^\\n]+' | head -1 | sed 's/base_dir: //' | tr -d '\n')

    if [ ! -z "$HOME_DIR" ]; then
        echo "📁 Dagster Home: $HOME_DIR"
        echo ""

        # 检查 storage 目录
        if [ -d "$HOME_DIR" ]; then
            echo "3. 检查运行记录..."
            echo "------------------------------------------"

            # 查找最新的运行
            if [ -d "$HOME_DIR" ]; then
                LATEST_RUN=$(ls -t "$HOME_DIR" 2>/dev/null | grep -E '^[a-f0-9\-]+$' | head -1)

                if [ ! -z "$LATEST_RUN" ]; then
                    echo "✅ 最新运行 ID: $LATEST_RUN"

                    # 检查日志目录
                    LOG_DIR="$HOME_DIR/$LATEST_RUN/compute_logs"
                    if [ -d "$LOG_DIR" ]; then
                        echo "📂 日志目录: $LOG_DIR"
                        echo ""

                        # 列出日志文件
                        echo "4. 日志文件:"
                        echo "------------------------------------------"
                        ls -lh "$LOG_DIR" 2>/dev/null
                        echo ""

                        # 显示最新的错误日志
                        ERR_FILE=$(ls -t "$LOG_DIR"/*.err 2>/dev/null | head -1)
                        if [ ! -z "$ERR_FILE" ] && [ -f "$ERR_FILE" ]; then
                            echo "5. 最新错误日志 (最后 20 行):"
                            echo "------------------------------------------"
                            tail -20 "$ERR_FILE"
                            echo ""
                        fi

                        # 显示最新的输出日志
                        OUT_FILE=$(ls -t "$LOG_DIR"/*.out 2>/dev/null | head -1)
                        if [ ! -z "$OUT_FILE" ] && [ -f "$OUT_FILE" ]; then
                            echo "6. 最新输出日志 (最后 20 行):"
                            echo "------------------------------------------"
                            tail -20 "$OUT_FILE"
                            echo ""
                        fi

                        # 提供实时监控命令
                        echo "=========================================="
                        echo "实时监控命令"
                        echo "=========================================="
                        echo ""
                        echo "要实时查看日志更新，运行:"
                        echo ""
                        if [ ! -z "$ERR_FILE" ]; then
                            echo "错误日志:"
                            echo "  tail -f \"$ERR_FILE\""
                            echo ""
                        fi
                        if [ ! -z "$OUT_FILE" ]; then
                            echo "输出日志:"
                            echo "  tail -f \"$OUT_FILE\""
                            echo ""
                        fi
                        echo "同时监控两个日志:"
                        echo "  tail -f \"$LOG_DIR\"/*.{err,out}"
                        echo ""
                    else
                        echo "❌ 日志目录不存在: $LOG_DIR"
                    fi
                else
                    echo "❌ 未找到运行记录"
                fi
            fi
        else
            echo "❌ Dagster Home 目录不存在: $HOME_DIR"
        fi
    fi
fi

echo ""
echo "=========================================="
echo "故障排查建议"
echo "=========================================="
echo ""
echo "如果看不到运行记录:"
echo ""
echo "1. 刷新浏览器页面 (Cmd+R)"
echo "2. 检查浏览器开发者工具的 Console 是否有错误 (F12)"
echo "3. 确认你访问的是正确的 Dagster UI: http://127.0.0.1:61879"
echo "4. 尝试点击 UI 中的 'Runs' 标签页"
echo "5. 如果问题持续，重启 Dagster:"
echo "   ./scripts/restart_dagster_clean.sh"
echo ""
