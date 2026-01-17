-- 删除 documents 表的 extra_metadata 字段
-- 执行方式: psql -U postgres -d finnet -f scripts/remove_document_extra_metadata.sql

-- 1. 删除 extra_metadata 字段
ALTER TABLE documents
    DROP COLUMN IF EXISTS extra_metadata;

-- 2. 验证字段已删除
SELECT 
    column_name, 
    data_type
FROM information_schema.columns
WHERE table_name = 'documents' 
    AND column_name = 'extra_metadata';

-- 如果查询结果为空，说明字段已成功删除
