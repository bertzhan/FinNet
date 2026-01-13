#!/bin/bash

# NebulaGraph 清理脚本
# 用于停止并删除 NebulaGraph 相关的容器和卷

echo "=========================================="
echo "NebulaGraph 清理工具"
echo "=========================================="
echo ""

read -p "确认要删除 NebulaGraph 相关的容器和卷吗？(y/N): " confirm

if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "取消操作"
    exit 0
fi

echo ""
echo "1. 停止 NebulaGraph 容器..."
echo "----------------------------------------"
docker-compose stop nebula-metad nebula-storaged nebula-graphd 2>/dev/null
docker stop finnet-nebula-metad finnet-nebula-storaged finnet-nebula-graphd 2>/dev/null
echo "✓ 容器已停止"
echo ""

echo "2. 删除 NebulaGraph 容器..."
echo "----------------------------------------"
docker-compose rm -f nebula-metad nebula-storaged nebula-graphd 2>/dev/null
docker rm -f finnet-nebula-metad finnet-nebula-storaged finnet-nebula-graphd 2>/dev/null
echo "✓ 容器已删除"
echo ""

echo "3. 删除 NebulaGraph 数据卷..."
echo "----------------------------------------"
read -p "是否删除数据卷（会丢失所有数据）？(y/N): " delete_volumes

if [ "$delete_volumes" = "y" ] || [ "$delete_volumes" = "Y" ]; then
    docker volume rm finnet_nebula_metad_data finnet_nebula_metad_logs \
        finnet_nebula_storaged_data finnet_nebula_storaged_logs \
        finnet_nebula_graphd_logs 2>/dev/null
    echo "✓ 数据卷已删除"
else
    echo "⚠ 保留数据卷（如需删除，手动执行）"
    echo "   docker volume rm finnet_nebula_metad_data finnet_nebula_metad_logs"
    echo "   docker volume rm finnet_nebula_storaged_data finnet_nebula_storaged_logs"
    echo "   docker volume rm finnet_nebula_graphd_logs"
fi
echo ""

echo "=========================================="
echo "清理完成"
echo "=========================================="
echo ""
echo "注意: docker-compose.yml 中的 NebulaGraph 配置已移除"
echo "如需重新添加，请参考 plan.md 中的配置"
