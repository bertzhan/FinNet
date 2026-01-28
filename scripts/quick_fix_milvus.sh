#!/bin/bash
# 快速修复 Milvus 存储空间问题

set -e

echo "=================================================================================="
echo "快速修复 Milvus 存储空间问题"
echo "=================================================================================="
echo

# 1. 停止 Milvus
echo "1. 停止 Milvus 服务..."
docker stop finnet-milvus 2>/dev/null || true
echo "✅ Milvus 已停止"
echo

# 2. 清理 MinIO 中的 Milvus 临时文件
echo "2. 清理 MinIO Milvus 存储中的临时文件..."
if command -v mc &> /dev/null; then
    mc alias set milvus-minio http://localhost:9000 minioadmin minioadmin 2>/dev/null || true
    # 列出所有 buckets
    BUCKETS=$(mc ls milvus-minio 2>/dev/null | awk '{print $5}' || echo "")
    for bucket in $BUCKETS; do
        echo "  清理 $bucket 中的临时文件..."
        # 清理 1 天前的 insert_log 和 stats_log
        mc find milvus-minio/$bucket --name "insert_log" --older-than 1d --exec "mc rm {}" 2>/dev/null || true
        mc find milvus-minio/$bucket --name "stats_log" --older-than 1d --exec "mc rm {}" 2>/dev/null || true
    done
    echo "✅ 临时文件清理完成"
else
    echo "⚠️  MinIO 客户端未安装，跳过清理步骤"
    echo "   可以手动运行: bash scripts/clean_minio_milvus.sh"
fi
echo

# 3. 重启 Milvus
echo "3. 重启 Milvus 服务..."
docker start finnet-milvus
echo "✅ Milvus 已启动"
echo

# 4. 等待服务启动
echo "4. 等待服务启动（30秒）..."
sleep 30

# 5. 检查服务状态
echo "5. 检查服务状态..."
if docker ps | grep -q finnet-milvus; then
    echo "✅ Milvus 服务正在运行"
    echo
    echo "检查日志（最后10行）..."
    docker logs finnet-milvus --tail 10 2>&1 | grep -E "(ERROR|WARN|Storage backend)" || echo "   未发现存储相关错误"
else
    echo "❌ Milvus 服务未运行"
    echo "   查看日志: docker logs finnet-milvus"
fi

echo
echo "=================================================================================="
echo "修复完成！"
echo "=================================================================================="
echo
echo "如果问题仍然存在，请尝试："
echo "1. 手动清理 MinIO: bash scripts/clean_minio_milvus.sh"
echo "2. 检查磁盘空间: python scripts/check_milvus_storage.py"
echo "3. 查看详细日志: docker logs finnet-milvus --tail 100"
