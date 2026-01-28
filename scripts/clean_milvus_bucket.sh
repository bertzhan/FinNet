#!/bin/bash
# 清理 Milvus MinIO Bucket 中的数据（快速修复）

set -e

BUCKET_NAME="a-bucket"

echo "=================================================================================="
echo "清理 Milvus MinIO Bucket: $BUCKET_NAME"
echo "=================================================================================="
echo

# 检查 MinIO 容器
if ! docker ps | grep -q finnet-minio-milvus; then
    echo "❌ MinIO Milvus 容器未运行"
    exit 1
fi

# 停止 Milvus（避免数据不一致）
echo "1. 停止 Milvus 服务..."
docker stop finnet-milvus 2>/dev/null || true
echo "✅ Milvus 已停止"
echo

# 检查存储使用情况
echo "2. 检查存储使用情况..."
SIZE=$(docker exec finnet-minio-milvus sh -c "du -sh /data/$BUCKET_NAME 2>/dev/null" | awk '{print $1}' || echo "未知")
echo "   当前使用: $SIZE"
echo

# 清理选项
echo "3. 清理选项："
echo "   a) 清理临时文件（insert_log, stats_log 等，保留最近1天）"
echo "   b) 清理旧数据（7天前）"
echo "   c) 清空整个 Bucket（⚠️  危险：会删除所有 Milvus 数据）"
echo "   d) 退出"
echo
read -p "请选择 (a/b/c/d): " choice

case $choice in
    a)
        echo
        echo "清理临时文件..."
        # 使用 find 命令清理旧文件
        docker exec finnet-minio-milvus sh -c "
            find /data/$BUCKET_NAME -type f -name '*insert_log*' -mtime +1 -delete 2>/dev/null || true
            find /data/$BUCKET_NAME -type f -name '*stats_log*' -mtime +1 -delete 2>/dev/null || true
        "
        echo "✅ 临时文件清理完成"
        ;;
    b)
        echo
        echo "清理7天前的数据..."
        docker exec finnet-minio-milvus sh -c "
            find /data/$BUCKET_NAME -type f -mtime +7 -delete 2>/dev/null || true
        "
        echo "✅ 旧数据清理完成"
        ;;
    c)
        echo
        read -p "⚠️  警告：这将删除整个 Bucket 的所有数据！"
        read -p "确认清空 $BUCKET_NAME? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            docker exec finnet-minio-milvus sh -c "rm -rf /data/$BUCKET_NAME/*" 2>/dev/null || true
            echo "✅ Bucket 已清空"
        else
            echo "取消操作"
            exit 0
        fi
        ;;
    d)
        echo "退出"
        exit 0
        ;;
    *)
        echo "❌ 无效选择"
        exit 1
        ;;
esac

# 检查清理后的空间
echo
echo "4. 检查清理后的存储使用情况..."
NEW_SIZE=$(docker exec finnet-minio-milvus sh -c "du -sh /data/$BUCKET_NAME 2>/dev/null" | awk '{print $1}' || echo "未知")
echo "   清理后使用: $NEW_SIZE"
echo

# 重启 Milvus
echo "5. 重启 Milvus 服务..."
docker start finnet-milvus
echo "✅ Milvus 已启动"
echo

# 等待服务启动
echo "6. 等待服务启动（30秒）..."
sleep 30

# 检查服务状态
echo "7. 检查服务状态..."
if docker ps | grep -q finnet-milvus; then
    echo "✅ Milvus 服务正在运行"
    echo
    echo "检查日志（最后5行，过滤错误）..."
    docker logs finnet-milvus --tail 20 2>&1 | grep -E "(ERROR|WARN|Storage backend)" | tail -5 || echo "   未发现存储相关错误 ✅"
else
    echo "❌ Milvus 服务未运行"
    echo "   查看日志: docker logs finnet-milvus"
fi

echo
echo "=================================================================================="
echo "修复完成！"
echo "=================================================================================="
