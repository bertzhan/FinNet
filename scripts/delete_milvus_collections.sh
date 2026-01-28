#!/bin/bash
# 仅删除 Milvus Collections（保留服务数据）

set -e

echo "=================================================================================="
echo "删除 Milvus Collections"
echo "=================================================================================="
echo

# 检查是否可以使用 Python 脚本
if command -v python3 &> /dev/null; then
    # 尝试使用 Python 脚本
    echo "尝试使用 Python 脚本列出 Collections..."
    cd /Users/han/PycharmProjects/FinNet
    PYTHONPATH=/Users/han/PycharmProjects/FinNet:$PYTHONPATH python3 -c "
import sys
sys.path.insert(0, '/Users/han/PycharmProjects/FinNet')
try:
    from pymilvus import connections, utility
    connections.connect(alias='default', host='localhost', port='19530')
    collections = utility.list_collections()
    if collections:
        print(f'找到 {len(collections)} 个 Collections:')
        for col in collections:
            print(f'  - {col}')
        print()
        confirm = input('确认删除所有 Collections? (yes/no): ')
        if confirm.lower() == 'yes':
            for col in collections:
                try:
                    utility.drop_collection(col)
                    print(f'✅ 已删除: {col}')
                except Exception as e:
                    print(f'❌ 删除 {col} 失败: {e}')
        else:
            print('取消操作')
    else:
        print('没有找到任何 Collection')
    connections.disconnect('default')
except ImportError:
    print('⚠️  pymilvus 未安装，无法使用 Python 脚本')
    sys.exit(1)
except Exception as e:
    print(f'❌ 操作失败: {e}')
    sys.exit(1)
" 2>&1 || echo "Python 脚本执行失败，使用 Docker 方式"
else
    echo "⚠️  Python3 未找到"
fi

echo
echo "=================================================================================="
echo "如果 Python 方式失败，可以使用以下 Docker 方式："
echo "=================================================================================="
echo
echo "方式1: 清空 MinIO 存储（会删除所有数据）"
echo "  docker exec finnet-minio-milvus sh -c 'rm -rf /data/a-bucket/*'"
echo
echo "方式2: 完全重置 Milvus（推荐）"
echo "  bash scripts/delete_milvus_data.sh"
echo
