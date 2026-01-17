-- 添加 documents 表的 publish_date 字段
-- 执行方式: psql -U postgres -d finnet -f scripts/add_document_publish_date.sql

-- 1. 添加 publish_date 字段
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS publish_date TIMESTAMP;

-- 2. 创建索引
CREATE INDEX IF NOT EXISTS idx_documents_publish_date 
    ON documents(publish_date);

-- 3. 添加注释
COMMENT ON COLUMN documents.publish_date IS '文档发布日期（文档在原始网站发布的日期）';

-- 4. 验证字段已添加
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns
WHERE table_name = 'documents' 
    AND column_name = 'publish_date';
