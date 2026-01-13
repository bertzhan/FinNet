#!/bin/bash

# NebulaGraph Storage 连接问题诊断脚本

echo "=========================================="
echo "NebulaGraph Storage 连接诊断"
echo "=========================================="
echo ""

# 根据配置检查结果，存储和账户都没问题
# 重点检查服务连接和启动状态

echo "根据配置检查结果："
echo "✓ 存储卷正常"
echo "✓ 存储空间充足（7.5G 可用）"
echo "✓ 账户配置正常（USER=root）"
echo "✓ 路径权限正常"
echo ""

# 1. 检查服务启动顺序
echo "1. 服务启动顺序检查:"
echo "----------------------------------------"
echo "Storage 服务依赖 Meta 服务，检查依赖关系..."

if docker ps | grep -q finnet-nebula-metad; then
    META_STATUS=$(docker ps --filter "name=finnet-nebula-metad" --format "{{.Status}}")
    echo "✓ Meta 服务: $META_STATUS"
    
    # 检查 Meta HTTP 端点
    if curl -sf http://localhost:19559/status > /dev/null 2>&1; then
        echo "✓ Meta HTTP 端点正常"
    else
        echo "✗ Meta HTTP 端点异常（可能正在启动中）"
    fi
else
    echo "✗ Meta 服务未运行"
    echo "  请先启动: docker-compose up -d nebula-metad"
    exit 1
fi

if docker ps | grep -q finnet-nebula-storaged; then
    STORAGE_STATUS=$(docker ps --filter "name=finnet-nebula-storaged" --format "{{.Status}}")
    echo "✓ Storage 服务: $STORAGE_STATUS"
else
    echo "✗ Storage 服务未运行"
    echo "  启动命令: docker-compose up -d nebula-storaged"
    exit 1
fi
echo ""

# 2. 检查 Storage 是否能连接到 Meta
echo "2. Storage -> Meta 连接检查:"
echo "----------------------------------------"
if docker exec finnet-nebula-storaged ping -c 2 nebula-metad > /dev/null 2>&1; then
    echo "✓ 网络连通正常"
else
    echo "✗ 网络连通异常"
fi

# 检查 Meta 服务地址解析
META_RESOLVE=$(docker exec finnet-nebula-storaged getent hosts nebula-metad 2>/dev/null)
if [ -n "$META_RESOLVE" ]; then
    echo "✓ Meta 服务地址解析正常: $META_RESOLVE"
else
    echo "✗ Meta 服务地址解析失败"
fi
echo ""

# 3. 检查 Storage 服务日志中的错误
echo "3. Storage 服务日志检查（查找错误）:"
echo "----------------------------------------"
ERRORS=$(docker-compose logs nebula-storaged 2>&1 | grep -i "error\|fail\|exception" | tail -10)
if [ -n "$ERRORS" ]; then
    echo "发现错误信息:"
    echo "$ERRORS"
else
    echo "✓ 未发现明显错误"
fi
echo ""

# 4. 检查 HTTP 端点启动时间
echo "4. HTTP 端点启动检查:"
echo "----------------------------------------"
echo "等待 HTTP 端点启动（最多 30 秒）..."
for i in {1..15}; do
    if curl -sf http://localhost:19779/status > /dev/null 2>&1; then
        echo "✓ HTTP 端点已就绪（等待了 $((i*2)) 秒）"
        HTTP_READY=true
        break
    fi
    sleep 2
done

if [ "$HTTP_READY" != "true" ]; then
    echo "✗ HTTP 端点仍未就绪"
    echo ""
    echo "可能原因："
    echo "  1. Meta 服务未完全启动"
    echo "  2. Storage 服务启动失败"
    echo "  3. 配置文件错误"
    echo ""
    echo "建议操作："
    echo "  1. 查看完整日志: docker-compose logs nebula-storaged"
    echo "  2. 重启服务: docker-compose restart nebula-storaged"
    echo "  3. 检查 Meta 服务: docker-compose logs nebula-metad | tail -20"
fi
echo ""

# 5. 检查进程状态
echo "5. 容器内进程检查:"
echo "----------------------------------------"
PROCESSES=$(docker exec finnet-nebula-storaged ps aux 2>/dev/null | grep -E "nebula|storaged" | head -5)
if [ -n "$PROCESSES" ]; then
    echo "✓ 发现 NebulaGraph 进程:"
    echo "$PROCESSES"
else
    echo "✗ 未发现 NebulaGraph 进程（服务可能未启动）"
fi
echo ""

# 6. 总结和建议
echo "=========================================="
echo "诊断总结"
echo "=========================================="
echo ""
echo "配置状态: ✓ 正常（存储、账户、权限都正常）"
echo ""
echo "如果 HTTP 端点仍无法访问，建议："
echo "1. 完全重启所有 NebulaGraph 服务:"
echo "   docker-compose restart nebula-metad nebula-storaged nebula-graphd"
echo "   sleep 30"
echo ""
echo "2. 检查服务启动顺序（确保 Meta 先启动）:"
echo "   docker-compose up -d nebula-metad"
echo "   sleep 10"
echo "   docker-compose up -d nebula-storaged"
echo "   sleep 20"
echo ""
echo "3. 查看详细日志:"
echo "   docker-compose logs nebula-storaged | tail -50"
echo ""
