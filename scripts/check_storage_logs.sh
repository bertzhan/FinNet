#!/bin/bash

# NebulaGraph Storage 日志检查脚本

echo "=========================================="
echo "NebulaGraph Storage 日志检查"
echo "=========================================="
echo ""

# 1. 检查容器是否存在
echo "1. 容器状态检查:"
echo "----------------------------------------"
if docker ps -a | grep -q finnet-nebula-storaged; then
    echo "容器存在，状态："
    docker ps -a --filter "name=finnet-nebula-storaged" --format "table {{.Names}}\t{{.Status}}\t{{.CreatedAt}}"
else
    echo "✗ 容器不存在"
    echo "  请先启动: docker-compose up -d nebula-storaged"
    exit 1
fi
echo ""

# 2. 检查容器是否运行
echo "2. 容器运行状态:"
echo "----------------------------------------"
if docker ps | grep -q finnet-nebula-storaged; then
    echo "✓ 容器正在运行"
    CONTAINER_RUNNING=true
else
    echo "✗ 容器未运行"
    CONTAINER_RUNNING=false
fi
echo ""

# 3. 尝试多种方式获取日志
echo "3. 日志获取尝试:"
echo "----------------------------------------"

# 方式1: docker-compose logs
echo "方式1: docker-compose logs"
echo "----------------------------------------"
LOGS1=$(docker-compose logs --tail=50 nebula-storaged 2>&1)
if [ -n "$LOGS1" ]; then
    echo "$LOGS1"
else
    echo "无日志输出"
fi
echo ""

# 方式2: docker logs
echo "方式2: docker logs"
echo "----------------------------------------"
LOGS2=$(docker logs --tail=50 finnet-nebula-storaged 2>&1)
if [ -n "$LOGS2" ]; then
    echo "$LOGS2"
else
    echo "无日志输出"
fi
echo ""

# 方式3: 检查日志文件（如果容器运行）
if [ "$CONTAINER_RUNNING" = true ]; then
    echo "方式3: 容器内日志文件"
    echo "----------------------------------------"
    LOG_FILES=$(docker exec finnet-nebula-storaged ls -lh /logs 2>/dev/null)
    if [ -n "$LOG_FILES" ]; then
        echo "日志文件列表:"
        echo "$LOG_FILES"
        echo ""
        echo "最新日志文件内容（最后20行）:"
        LATEST_LOG=$(docker exec finnet-nebula-storaged ls -t /logs/*.log 2>/dev/null | head -1)
        if [ -n "$LATEST_LOG" ]; then
            docker exec finnet-nebula-storaged tail -20 "$LATEST_LOG" 2>/dev/null || echo "无法读取日志文件"
        else
            echo "未找到日志文件"
        fi
    else
        echo "日志目录为空或无法访问"
    fi
    echo ""
fi

# 4. 检查容器启动时间
echo "4. 容器启动信息:"
echo "----------------------------------------"
if docker ps -a | grep -q finnet-nebula-storaged; then
    CREATED=$(docker inspect finnet-nebula-storaged --format='{{.Created}}' 2>/dev/null)
    STARTED=$(docker inspect finnet-nebula-storaged --format='{{.State.StartedAt}}' 2>/dev/null)
    echo "创建时间: $CREATED"
    echo "启动时间: $STARTED"
    
    # 计算运行时长
    if [ "$CONTAINER_RUNNING" = true ] && [ -n "$STARTED" ]; then
        echo "运行时长: $(docker inspect finnet-nebula-storaged --format='{{.State.Status}}' 2>/dev/null)"
    fi
fi
echo ""

# 5. 检查日志配置
echo "5. 日志配置检查:"
echo "----------------------------------------"
if [ "$CONTAINER_RUNNING" = true ]; then
    echo "日志目录权限:"
    docker exec finnet-nebula-storaged ls -ld /logs 2>/dev/null || echo "无法访问日志目录"
    
    echo ""
    echo "日志目录内容:"
    docker exec finnet-nebula-storaged ls -la /logs 2>/dev/null || echo "日志目录为空"
    
    echo ""
    echo "进程信息（查看是否有日志写入进程）:"
    docker exec finnet-nebula-storaged ps aux 2>/dev/null | grep -E "nebula|storaged" | head -5 || echo "未找到相关进程"
fi
echo ""

# 6. 建议
echo "=========================================="
echo "诊断建议"
echo "=========================================="
echo ""

if [ "$CONTAINER_RUNNING" = false ]; then
    echo "容器未运行，请启动:"
    echo "  docker-compose up -d nebula-storaged"
    echo ""
    echo "然后查看启动日志:"
    echo "  docker-compose logs -f nebula-storaged"
elif [ -z "$LOGS1" ] && [ -z "$LOGS2" ]; then
    echo "可能的原因："
    echo "1. 容器刚启动，还没有日志输出"
    echo "2. 日志被重定向到文件而不是 stdout"
    echo "3. 服务启动失败，没有产生日志"
    echo ""
    echo "建议操作："
    echo "1. 等待 10-20 秒后重试:"
    echo "   sleep 20 && docker-compose logs nebula-storaged"
    echo ""
    echo "2. 实时查看日志:"
    echo "   docker-compose logs -f nebula-storaged"
    echo ""
    echo "3. 检查容器内日志文件:"
    echo "   docker exec finnet-nebula-storaged ls -lh /logs"
    echo "   docker exec finnet-nebula-storaged tail -f /logs/*.log"
    echo ""
    echo "4. 检查服务是否正常启动:"
    echo "   docker exec finnet-nebula-storaged ps aux | grep nebula"
else
    echo "✓ 日志正常输出"
fi
