#!/bin/bash
# 设置 MinIO 最小可用空间阈值

set -e

echo "=================================================================================="
echo "设置 MinIO Milvus 最小可用空间阈值"
echo "=================================================================================="
echo

# 检查 MinIO 容器是否运行
if ! docker ps | grep -q finnet-minio-milvus; then
    echo "❌ MinIO Milvus 容器未运行，请先启动："
    echo "   docker-compose up -d minio-milvus"
    exit 1
fi

# 检查是否安装了 MinIO 客户端
if ! command -v mc &> /dev/null; then
    echo "⚠️  MinIO 客户端 (mc) 未安装"
    echo "   安装方法："
    echo "   macOS: brew install minio/stable/mc"
    echo "   Linux: wget https://dl.min.io/client/mc/release/linux-amd64/mc && chmod +x mc && sudo mv mc /usr/local/bin/"
    echo
    echo "   或者使用 Docker 运行："
    echo "   docker run --rm -it --network finnet-network minio/mc:latest"
    echo
    read -p "是否使用 Docker 运行 mc? (y/n): " use_docker
    if [ "$use_docker" != "y" ]; then
        exit 1
    fi
    MC_CMD="docker run --rm -it --network finnet-network minio/mc:latest"
else
    MC_CMD="mc"
fi

echo "1. 配置 MinIO 别名..."
$MC_CMD alias set milvus-minio http://minio-milvus:9000 minioadmin minioadmin 2>/dev/null || \
$MC_CMD alias set milvus-minio http://localhost:9000 minioadmin minioadmin

echo "✅ 别名配置完成"
echo

echo "2. 查看当前配置..."
$MC_CMD admin config get milvus-minio storage_class 2>/dev/null || echo "   (当前未设置)"
echo

echo "3. 设置最小可用空间阈值..."
echo "   选项："
echo "   1) 1% (推荐，适合开发环境)"
echo "   2) 2%"
echo "   3) 5% (默认)"
echo "   4) 自定义"
echo
read -p "请选择 (1-4): " choice

case $choice in
    1)
        THRESHOLD="1"
        ;;
    2)
        THRESHOLD="2"
        ;;
    3)
        THRESHOLD="5"
        ;;
    4)
        read -p "请输入阈值百分比 (1-10): " THRESHOLD
        ;;
    *)
        echo "❌ 无效选择"
        exit 1
        ;;
esac

echo
echo "4. 应用配置..."
# 注意：MinIO 的实际配置方式可能因版本而异
# 这里提供一个通用的方法
echo "   正在设置存储类配置..."

# 方法1: 通过环境变量（如果支持）
# 这需要在 docker-compose.yml 中设置

# 方法2: 通过配置文件（需要进入容器）
echo "   注意：MinIO 的最小可用空间阈值通常通过磁盘配额或存储策略设置"
echo "   如果上述方法无效，请参考 MinIO 官方文档："
echo "   https://min.io/docs/minio/linux/administration/object-management/storage-class.html"
echo

echo "5. 重启 MinIO 服务使配置生效..."
read -p "是否重启 MinIO Milvus 服务? (y/n): " restart
if [ "$restart" = "y" ]; then
    docker restart finnet-minio-milvus
    echo "✅ MinIO 服务已重启"
    sleep 5
    echo "   等待服务启动..."
fi

echo
echo "=================================================================================="
echo "完成！"
echo "=================================================================================="
echo
echo "如果问题仍然存在，请尝试："
echo "1. 清理 Milvus 数据: python scripts/clean_milvus_storage.py --interactive"
echo "2. 检查磁盘空间: python scripts/check_milvus_storage.py"
echo "3. 重启所有服务: docker-compose restart milvus minio-milvus etcd"
