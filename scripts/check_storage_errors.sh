#!/bin/bash

# NebulaGraph Storage 错误日志检查脚本

echo "=========================================="
echo "NebulaGraph Storage 错误分析"
echo "=========================================="
echo ""

echo "容器状态: Up 2 minutes (unhealthy)"
echo "问题: 健康检查失败"
echo ""

# 1. 查看最新的 ERROR 日志
echo "1. 最新 ERROR 日志:"
echo "----------------------------------------"
docker exec finnet-nebula-storaged cat /logs/nebula-storaged.ERROR 2>/dev/null | tail -30
echo ""

# 2. 查看 stderr 日志（通常包含启动错误）
echo "2. stderr 日志（最后50行）:"
echo "----------------------------------------"
docker exec finnet-nebula-storaged tail -50 /logs/storaged-stderr.log 2>/dev/null
echo ""

# 3. 查看最新的 INFO 日志（了解启动过程）
echo "3. 最新 INFO 日志（最后30行）:"
echo "----------------------------------------"
docker exec finnet-nebula-storaged tail -30 /logs/nebula-storaged.INFO 2>/dev/null
echo ""

# 4. 检查健康检查端点
echo "4. 健康检查端点测试:"
echo "----------------------------------------"
echo "从容器内测试:"
docker exec finnet-nebula-storaged curl -v http://localhost:19779/status 2>&1 | head -20
echo ""

echo "从主机测试:"
curl -v http://localhost:19779/status 2>&1 | head -20
echo ""

# 5. 检查端口监听
echo "5. 端口监听检查:"
echo "----------------------------------------"
docker exec finnet-nebula-storaged netstat -tlnp 2>/dev/null | grep -E "9779|19779" || echo "端口未监听或 netstat 不可用"
echo ""

# 6. 检查 Meta 连接
echo "6. Meta 服务连接检查:"
echo "----------------------------------------"
echo "检查 Meta 服务是否可达:"
docker exec finnet-nebula-storaged ping -c 2 nebula-metad 2>&1 | head -5
echo ""

echo "检查 Meta 服务端口:"
docker exec finnet-nebula-storaged nc -zv nebula-metad 9559 2>&1 || echo "nc 命令不可用，尝试其他方式"
echo ""

# 7. 总结和建议
echo "=========================================="
echo "问题分析"
echo "=========================================="
echo ""
echo "根据日志分析，可能的问题："
echo "1. Meta 服务连接失败"
echo "2. HTTP 状态端点未启动"
echo "3. 配置错误"
echo ""
echo "请查看上面的 ERROR 和 stderr 日志找出具体错误信息"
echo ""
