#!/bin/bash
# Quick check script for Elasticsearch service

echo "=========================================="
echo "Elasticsearch 服务状态检查"
echo "=========================================="
echo

# Check Docker container status
echo "1. 检查 Docker 容器状态:"
docker-compose ps elasticsearch
echo

# Check if port is accessible
echo "2. 检查端口 9200 是否可访问:"
if curl -s -f http://localhost:9200/_cluster/health > /dev/null 2>&1; then
    echo "✅ Elasticsearch 服务可访问"
    echo
    echo "集群健康状态:"
    curl -s http://localhost:9200/_cluster/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost:9200/_cluster/health
else
    echo "❌ Elasticsearch 服务不可访问"
    echo "   请检查："
    echo "   - 容器是否正在运行: docker-compose ps elasticsearch"
    echo "   - 查看日志: docker-compose logs elasticsearch | tail -20"
fi
echo

# Check container logs
echo "3. 最近的容器日志（最后10行）:"
docker-compose logs --tail=10 elasticsearch 2>/dev/null || echo "无法获取日志"
echo

echo "=========================================="
