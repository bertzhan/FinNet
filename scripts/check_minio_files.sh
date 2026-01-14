#!/bin/bash

# 检查 MinIO 中的文件脚本
# 用于验证爬取的文件是否已上传到 MinIO

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}检查 MinIO 中的文件${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 获取项目根目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# 加载环境变量
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

MINIO_BUCKET=${MINIO_BUCKET:-finnet-datalake}

echo -e "${BLUE}检查 MinIO 桶: $MINIO_BUCKET${NC}"
echo ""

python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from src.storage.object_store.minio_client import MinIOClient
from collections import defaultdict

try:
    client = MinIOClient()
    
    # 统计各路径的文件数量
    stats = defaultdict(int)
    total_size = 0
    files = []
    
    # 列出所有 bronze 层的文件
    file_list = client.list_files(prefix="bronze/", recursive=True)
    
    for file_info in file_list:
        obj_name = file_info['name']
        obj_size = file_info['size']
        
        path_parts = obj_name.split('/')
        if len(path_parts) >= 2:
            category = f"{path_parts[0]}/{path_parts[1]}"  # bronze/a_share
            stats[category] += 1
        total_size += obj_size
        files.append((obj_name, obj_size))
    
    print(f"✅ 找到 {len(files)} 个文件，总大小: {total_size / 1024 / 1024:.2f} MB")
    print("")
    
    # 按类别统计
    if stats:
        print("📊 文件分布:")
        for category, count in sorted(stats.items()):
            print(f"  {category}: {count} 个文件")
        print("")
    
    # 显示最近的文件（最多10个）
    if files:
        print("📄 最近的文件（最多显示10个）:")
        for obj_name, size in files[:10]:
            print(f"  {obj_name} ({size / 1024:.2f} KB)")
        
        if len(files) > 10:
            print(f"  ... 还有 {len(files) - 10} 个文件")
    else:
        print("⚠️  未找到任何文件")
        print("")
        print("可能的原因:")
        print("1. 文件还未上传")
        print("2. 路径前缀不匹配")
        print("3. MinIO 配置不正确")
        print("")
        print("建议:")
        print("1. 检查 Dagster UI 中的运行日志")
        print("2. 查看是否有 'MinIO 上传成功' 的日志")
        print("3. 确认 enable_minio 配置为 true")
    
except Exception as e:
    print(f"❌ 检查失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}检查完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}提示：${NC}"
echo "1. 如果文件数量为 0，请检查 Dagster UI 中的日志"
echo "2. 访问 MinIO Console: http://localhost:9001"
echo "3. 查看详细日志: 在 Dagster UI 中查找 'MinIO 上传' 相关日志"
echo ""
