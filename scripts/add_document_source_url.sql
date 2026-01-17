-- 添加 documents 表的 source_url 字段
-- 执行方式: psql -U postgres -d finnet -f scripts/add_document_source_url.sql

-- 1. 添加 source_url 字段
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS source_url VARCHAR(1000);

-- 2. 创建索引
CREATE INDEX IF NOT EXISTS idx_documents_source_url 
    ON documents(source_url);

-- 3. 添加注释
COMMENT ON COLUMN documents.source_url IS '文档来源URL（爬取时的原始URL）';

-- 4. 验证字段已添加
SELECT 
    column_name, 
    data_type, 
    character_maximum_length,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'documents' 
    AND column_name = 'source_url';
