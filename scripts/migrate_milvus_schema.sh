#!/bin/bash
# Milvus Schema 迁移脚本
# 将 Collection 从使用自动生成 ID 迁移到使用 chunk_id 作为主键

set -e  # 遇到错误立即退出

echo "=================================="
echo "Milvus Schema 迁移工具"
echo "=================================="
echo ""
echo "此脚本将："
echo "  1. 备份当前状态"
echo "  2. 删除旧 Collection"
echo "  3. 清空 PostgreSQL 向量化记录"
echo "  4. 提示重新运行向量化"
echo ""
echo "⚠️  警告：此操作不可逆！"
echo "   建议先在测试环境验证。"
echo ""

# 确认执行
read -p "是否继续？(yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "操作已取消"
    exit 0
fi

echo ""
echo "=================================="
echo "步骤 1/4: 备份当前状态"
echo "=================================="

# 创建备份目录
BACKUP_DIR="backups/milvus_migration_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "备份目录: $BACKUP_DIR"

# 备份 Milvus 统计
echo "备份 Milvus 统计信息..."
./scripts/check_milvus_direct.sh > "$BACKUP_DIR/milvus_before.txt" 2>&1 || true

# 备份 PostgreSQL 统计
echo "备份 PostgreSQL 统计信息..."
python scripts/check_vectorized_chunks.py > "$BACKUP_DIR/postgres_before.txt" 2>&1 || true

echo "✓ 备份完成: $BACKUP_DIR"
echo ""

echo "=================================="
echo "步骤 2/4: 删除旧 Collection"
echo "=================================="

echo "正在删除 Milvus Collections..."
./scripts/delete_milvus_collections.sh

echo "✓ Collection 已删除"
echo ""

echo "=================================="
echo "步骤 3/4: 清空 PostgreSQL 向量化记录"
echo "=================================="

echo "正在清空 vector_id 字段..."

psql -h localhost -U finnet -d finnet << 'EOF'
-- 清空 vector_id（标记为未向量化）
UPDATE document_chunks SET vector_id = NULL, embedding_model = NULL;

-- 显示结果
SELECT 
    COUNT(*) as total_chunks,
    COUNT(vector_id) as vectorized_chunks,
    COUNT(*) - COUNT(vector_id) as unvectorized_chunks
FROM document_chunks;
EOF

echo "✓ PostgreSQL 记录已清空"
echo ""

echo "=================================="
echo "步骤 4/4: 准备重新向量化"
echo "=================================="

echo ""
echo "✅ 迁移准备完成！"
echo ""
echo "下一步操作："
echo "  1. 新的 Collection 会在首次向量化时自动创建（使用新 Schema）"
echo "  2. 在 Dagster UI 中运行向量化作业："
echo "     → 访问 http://localhost:3000"
echo "     → 运行 vectorize_documents_job"
echo ""
echo "  或者运行："
echo "     python scripts/init_milvus_collection.py  # 手动创建 Collection"
echo ""
echo "验证命令："
echo "  ./scripts/check_milvus_direct.sh            # 检查 Milvus"
echo "  python scripts/check_vectorized_chunks.py   # 检查 PostgreSQL"
echo ""
echo "备份位置: $BACKUP_DIR"
echo ""
echo "=================================="
echo "迁移完成！"
echo "=================================="
