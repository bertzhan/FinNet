#!/bin/bash

# NebulaGraph Storage 端口诊断脚本

echo "=========================================="
echo "NebulaGraph Storage 端口诊断"
echo "=========================================="
echo ""

PORT=19779

echo "检查端口 $PORT 的状态..."
echo ""

# 1. 检查容器状态
echo "1. 容器状态:"
echo "----------------------------------------"
if docker ps --filter "name=finnet-nebula-storaged" --format "{{.Names}}\t{{.Status}}" | grep -q finnet-nebula-storaged; then
    docker ps --filter "name=finnet-nebula-storaged" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo "✓ 容器正在运行"
else
    echo "✗ 容器未运行"
    echo "  启动命令: docker-compose up -d nebula-storaged"
    exit 1
fi
echo ""

# 2. 检查端口映射
echo "2. 端口映射检查:"
echo "----------------------------------------"
PORTS=$(docker port finnet-nebula-storaged 2>/dev/null | grep $PORT)
if [ -n "$PORTS" ]; then
    echo "✓ 端口映射正常:"
    echo "$PORTS"
else
    echo "✗ 端口映射异常"
fi
echo ""

# 3. 检查主机端口监听
echo "3. 主机端口监听状态:"
echo "----------------------------------------"
if lsof -i :$PORT > /dev/null 2>&1; then
    echo "✓ 端口 $PORT 正在监听"
    lsof -i :$PORT
else
    echo "✗ 端口 $PORT 未监听"
fi
echo ""

# 4. 检查容器内端口监听
echo "4. 容器内端口监听状态:"
echo "----------------------------------------"
if docker exec finnet-nebula-storaged netstat -tlnp 2>/dev/null | grep -q ":$PORT"; then
    echo "✓ 容器内端口 $PORT 正在监听"
    docker exec finnet-nebula-storaged netstat -tlnp 2>/dev/null | grep ":$PORT"
else
    echo "✗ 容器内端口 $PORT 未监听"
    echo "  可能原因: 服务启动失败或正在启动中"
fi
echo ""

# 5. 测试 HTTP 端点（从容器内）
echo "5. 容器内 HTTP 端点测试:"
echo "----------------------------------------"
HTTP_TEST=$(docker exec finnet-nebula-storaged curl -sf http://localhost:$PORT/status 2>&1)
if [ $? -eq 0 ] && [ -n "$HTTP_TEST" ]; then
    echo "✓ 容器内 HTTP 端点正常"
    echo "响应: $HTTP_TEST"
else
    echo "✗ 容器内 HTTP 端点异常"
    echo "错误: $HTTP_TEST"
fi
echo ""

# 6. 测试主机到容器的连接
echo "6. 主机到容器连接测试:"
echo "----------------------------------------"
HOST_TEST=$(curl -v http://localhost:$PORT/status 2>&1 | head -20)
if echo "$HOST_TEST" | grep -q "200 OK\|HTTP"; then
    echo "✓ 主机连接正常"
else
    echo "✗ 主机连接异常"
    echo "详细输出:"
    echo "$HOST_TEST"
fi
echo ""

# 7. 检查服务日志（最后10行）
echo "7. 服务日志（最后10行）:"
echo "----------------------------------------"
docker-compose logs --tail=10 nebula-storaged 2>&1 | tail -10
echo ""

# 8. 建议
echo "=========================================="
echo "诊断建议"
echo "=========================================="
echo ""

if ! docker ps --filter "name=finnet-nebula-storaged" | grep -q "Up"; then
    echo "1. 容器未运行，请启动:"
    echo "   docker-compose up -d nebula-storaged"
elif ! docker exec finnet-nebula-storaged netstat -tlnp 2>/dev/null | grep -q ":$PORT"; then
    echo "1. 服务可能正在启动中，等待 20-30 秒后重试"
    echo "2. 如果持续失败，查看完整日志:"
    echo "   docker-compose logs nebula-storaged"
    echo "3. 检查 Meta 服务是否正常:"
    echo "   docker-compose logs nebula-metad | tail -20"
elif ! curl -sf http://localhost:$PORT/status > /dev/null 2>&1; then
    echo "1. 端口监听正常但 HTTP 服务未响应"
    echo "2. 可能原因:"
    echo "   - 服务配置错误"
    echo "   - Meta 服务连接失败"
    echo "3. 查看日志排查:"
    echo "   docker-compose logs nebula-storaged | grep -i error"
else
    echo "✓ 所有检查通过，服务正常"
fi
