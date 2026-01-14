#!/bin/bash

# MinIO 上传诊断脚本
# 用于检查为什么文件没有上传到 MinIO

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}MinIO 上传诊断${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 获取项目根目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# 检查1: 环境变量
echo -e "${BLUE}[1/6] 检查环境变量...${NC}"
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

MINIO_ENDPOINT=${MINIO_ENDPOINT:-localhost:9000}
MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY:-admin}
MINIO_SECRET_KEY=${MINIO_SECRET_KEY:-admin123456}
MINIO_BUCKET=${MINIO_BUCKET:-finnet-datalake}

echo "  MINIO_ENDPOINT: $MINIO_ENDPOINT"
echo "  MINIO_ACCESS_KEY: ${MINIO_ACCESS_KEY:0:4}..."
echo "  MINIO_SECRET_KEY: ${MINIO_SECRET_KEY:0:4}..."
echo "  MINIO_BUCKET: $MINIO_BUCKET"
echo ""

# 检查2: MinIO 服务是否运行
echo -e "${BLUE}[2/6] 检查 MinIO 服务...${NC}"
if docker-compose ps minio 2>/dev/null | grep -q "Up"; then
    echo -e "${GREEN}✅ MinIO 服务正在运行${NC}"
else
    echo -e "${RED}❌ MinIO 服务未运行${NC}"
    echo "  请运行: docker-compose up -d minio"
    exit 1
fi
echo ""

# 检查3: MinIO 连接测试
echo -e "${BLUE}[3/6] 测试 MinIO 连接...${NC}"
python3 << EOF
import sys
sys.path.insert(0, '.')
from src.storage.object_store.minio_client import MinIOClient

try:
    client = MinIOClient()
    # 测试列出桶
    buckets = client.client.list_buckets()
    print("✅ MinIO 连接成功")
    print(f"   可用桶: {[b.name for b in buckets]}")
    
    # 检查目标桶是否存在
    bucket_names = [b.name for b in buckets]
    if "$MINIO_BUCKET" in bucket_names:
        print(f"✅ 目标桶 '$MINIO_BUCKET' 存在")
    else:
        print(f"⚠️  目标桶 '$MINIO_BUCKET' 不存在，但会自动创建")
except Exception as e:
    print(f"❌ MinIO 连接失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    exit 1
fi
echo ""

# 检查4: 测试文件上传
echo -e "${BLUE}[4/6] 测试文件上传...${NC}"
python3 << EOF
import sys
import tempfile
import os
sys.path.insert(0, '.')
from src.storage.object_store.minio_client import MinIOClient

try:
    client = MinIOClient()
    
    # 创建测试文件
    test_content = b"Test file for MinIO upload"
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
        f.write(test_content)
        test_file = f.name
    
    # 上传测试文件
    test_object = "test/upload_test.txt"
    success = client.upload_file(
        object_name=test_object,
        file_path=test_file
    )
    
    if success:
        print("✅ 文件上传成功")
        
        # 验证文件是否存在
        exists = client.file_exists(test_object)
        if exists:
            print("✅ 文件验证成功（文件存在于 MinIO）")
            
            # 下载验证
            downloaded = client.download_file(test_object)
            if downloaded == test_content:
                print("✅ 文件下载验证成功（内容一致）")
            else:
                print("⚠️  文件下载验证失败（内容不一致）")
            
            # 清理测试文件
            client.delete_file(test_object)
            print("✅ 测试文件已清理")
        else:
            print("❌ 文件验证失败（文件不存在于 MinIO）")
    else:
        print("❌ 文件上传失败")
    
    # 清理本地测试文件
    os.unlink(test_file)
except Exception as e:
    print(f"❌ 上传测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    exit 1
fi
echo ""

# 检查5: 检查爬虫配置
echo -e "${BLUE}[5/6] 检查爬虫 MinIO 配置...${NC}"
python3 << EOF
import sys
sys.path.insert(0, '.')
from src.ingestion.a_share import ReportCrawler

try:
    # 创建爬虫实例（启用 MinIO）
    crawler = ReportCrawler(enable_minio=True, enable_postgres=False)
    
    print(f"  enable_minio: {crawler.enable_minio}")
    print(f"  minio_client: {'已初始化' if crawler.minio_client else '未初始化'}")
    
    if crawler.enable_minio and crawler.minio_client:
        print("✅ 爬虫 MinIO 配置正确")
    else:
        print("❌ 爬虫 MinIO 配置有问题")
        if not crawler.enable_minio:
            print("   原因: enable_minio 为 False")
        if not crawler.minio_client:
            print("   原因: minio_client 未初始化")
except Exception as e:
    print(f"❌ 检查失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    exit 1
fi
echo ""

# 检查6: 检查日志中的 MinIO 相关消息
echo -e "${BLUE}[6/6] 检查最近的日志...${NC}"
echo "提示：查看 Dagster UI 中的运行日志，查找以下关键词："
echo "  - 'MinIO 客户端初始化'"
echo "  - 'MinIO 上传成功'"
echo "  - 'MinIO 上传失败'"
echo "  - 'MinIO 上传异常'"
echo ""

# 总结
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}诊断完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}如果上传仍然失败，请检查：${NC}"
echo "1. Dagster UI 中的运行日志"
echo "2. 确保 enable_minio 配置为 true"
echo "3. 确保 MinIO 服务正常运行"
echo "4. 检查网络连接和防火墙设置"
echo ""
