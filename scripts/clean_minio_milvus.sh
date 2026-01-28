#!/bin/bash
# 清理 MinIO Milvus 存储中的数据

set -e

echo "=================================================================================="
echo "清理 MinIO Milvus 存储"
echo "=================================================================================="
echo

# 检查 MinIO 容器是否运行
if ! docker ps | grep -q finnet-minio-milvus; then
    echo "❌ MinIO Milvus 容器未运行"
    exit 1
fi

# 检查是否安装了 MinIO 客户端
if ! command -v mc &> /dev/null; then
    echo "⚠️  MinIO 客户端 (mc) 未安装，使用 Docker 运行..."
    MC_CMD="docker run --rm -it --network finnet-network minio/mc:latest"
else
    MC_CMD="mc"
fi

echo "1. 配置 MinIO 别名..."
$MC_CMD alias set milvus-minio http://minio-milvus:9000 minioadmin minioadmin 2>/dev/null || \
$MC_CMD alias set milvus-minio http://localhost:9000 minioadmin minioadmin

echo "✅ 别名配置完成"
echo

echo "2. 列出所有 Buckets..."
BUCKETS=$($MC_CMD ls milvus-minio 2>/dev/null | awk '{print $5}' || echo "")
if [ -z "$BUCKETS" ]; then
    echo "   ⚠️  未找到任何 Bucket"
else
    echo "$BUCKETS"
fi
echo

echo "3. 检查存储使用情况..."
for bucket in $BUCKETS; do
    echo "   Bucket: $bucket"
    $MC_CMD du milvus-minio/$bucket 2>/dev/null | head -5 || echo "      (无法获取大小)"
done
echo

echo "4. 清理选项："
echo "   a) 清理 Milvus 临时文件（insert_log, stats_log 等）"
echo "   b) 清理指定 Bucket 的旧数据（7天前）"
echo "   c) 清空指定 Bucket（危险操作）"
echo "   d) 退出"
echo
read -p "请选择 (a/b/c/d): " choice

case $choice in
    a)
        echo
        echo "清理 Milvus 临时文件..."
        for bucket in $BUCKETS; do
            echo "  清理 $bucket 中的临时文件..."
            # 清理 insert_log（保留最近1天的）
            $MC_CMD find milvus-minio/$bucket --name "insert_log" --older-than 1d --exec "$MC_CMD rm {}" 2>/dev/null || true
            # 清理 stats_log（保留最近1天的）
            $MC_CMD find milvus-minio/$bucket --name "stats_log" --older-than 1d --exec "$MC_CMD rm {}" 2>/dev/null || true
        done
        echo "✅ 临时文件清理完成"
        ;;
    b)
        echo
        read -p "请输入要清理的 Bucket 名称: " bucket_name
        read -p "清理多少天前的数据? (默认7天): " days
        days=${days:-7}
        echo "清理 $bucket_name 中 $days 天前的数据..."
        $MC_CMD find milvus-minio/$bucket_name --older-than ${days}d --exec "$MC_CMD rm {}" 2>/dev/null || true
        echo "✅ 清理完成"
        ;;
    c)
        echo
        read -p "⚠️  警告：这将删除整个 Bucket 的所有数据！"
        read -p "请输入要清空的 Bucket 名称: " bucket_name
        read -p "确认清空 $bucket_name? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            $MC_CMD rm --recursive --force milvus-minio/$bucket_name 2>/dev/null || true
            echo "✅ Bucket 已清空"
        else
            echo "取消操作"
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

echo
echo "5. 重启 Milvus 服务..."
read -p "是否重启 Milvus 服务? (y/n): " restart
if [ "$restart" = "y" ]; then
    docker restart finnet-milvus
    echo "✅ Milvus 服务已重启"
    echo "   等待服务启动..."
    sleep 10
    echo "   检查服务状态..."
    docker ps | grep finnet-milvus
fi

echo
echo "=================================================================================="
echo "完成！"
echo "=================================================================================="
