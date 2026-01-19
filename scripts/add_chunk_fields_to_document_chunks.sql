-- 为 document_chunks 表添加 heading_index 和 is_table 字段
-- 执行方式: psql -h localhost -U finnet -d finnet -f scripts/add_chunk_fields_to_document_chunks.sql

-- 添加 heading_index 字段（标题索引）
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS heading_index INTEGER;

-- 添加 is_table 字段（是否是表格分块）
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS is_table BOOLEAN DEFAULT FALSE;

-- 添加注释
COMMENT ON COLUMN document_chunks.heading_index IS '标题索引（在文档结构中的索引位置）';
COMMENT ON COLUMN document_chunks.is_table IS '是否是表格分块';

-- 为 heading_index 添加索引（如果需要按标题索引查询）
CREATE INDEX IF NOT EXISTS idx_document_chunks_heading_index ON document_chunks(heading_index);

-- 为 is_table 添加索引（如果需要查询表格分块）
CREATE INDEX IF NOT EXISTS idx_document_chunks_is_table ON document_chunks(is_table);
