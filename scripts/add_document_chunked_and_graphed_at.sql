-- 添加 documents 表的 chunked_at 和 graphed_at 字段
-- 执行方式: psql -U postgres -d finnet -f scripts/add_document_chunked_and_graphed_at.sql

-- 1. 添加 chunked_at 字段（分块完成时间）
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS chunked_at TIMESTAMP;

-- 2. 添加 graphed_at 字段（图构建完成时间）
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS graphed_at TIMESTAMP;

-- 3. 添加注释
COMMENT ON COLUMN documents.chunked_at IS '分块完成时间（文档分块处理完成的时间戳）';
COMMENT ON COLUMN documents.graphed_at IS '图构建完成时间（文档图结构构建完成的时间戳）';

-- 4. 验证字段已添加
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns
WHERE table_name = 'documents' 
    AND column_name IN ('chunked_at', 'graphed_at')
ORDER BY column_name;
