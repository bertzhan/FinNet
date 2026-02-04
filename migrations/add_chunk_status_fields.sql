-- 迁移脚本：为 DocumentChunk 添加 status 和向量化失败追踪字段
-- 日期：2026-02-03
-- 说明：添加 status、vectorization_error、vectorization_retry_count 字段

-- 1. 添加新字段
ALTER TABLE document_chunks
ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'pending',
ADD COLUMN IF NOT EXISTS vectorization_error TEXT,
ADD COLUMN IF NOT EXISTS vectorization_retry_count INTEGER DEFAULT 0;

-- 2. 创建索引（提升查询性能）
CREATE INDEX IF NOT EXISTS idx_chunk_status ON document_chunks(status);

-- 3. 初始化现有数据的状态
-- 已向量化的记录：设置为 'vectorized'
UPDATE document_chunks
SET status = 'vectorized'
WHERE vectorized_at IS NOT NULL AND status = 'pending';

-- 未向量化的记录：保持 'pending' 状态（默认值）

-- 4. 验证迁移结果
DO $$
DECLARE
    total_count INTEGER;
    vectorized_count INTEGER;
    pending_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_count FROM document_chunks;
    SELECT COUNT(*) INTO vectorized_count FROM document_chunks WHERE status = 'vectorized';
    SELECT COUNT(*) INTO pending_count FROM document_chunks WHERE status = 'pending';

    RAISE NOTICE '========================================';
    RAISE NOTICE '迁移完成统计:';
    RAISE NOTICE '总记录数: %', total_count;
    RAISE NOTICE '已向量化: %', vectorized_count;
    RAISE NOTICE '待向量化: %', pending_count;
    RAISE NOTICE '========================================';
END $$;
