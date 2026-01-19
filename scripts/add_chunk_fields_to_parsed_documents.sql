-- 为 parsed_documents 表添加分块相关字段
-- 执行方式: python3 scripts/add_chunk_fields_to_parsed_documents.py

-- 1. 添加路径字段（每个列单独添加）
ALTER TABLE parsed_documents ADD COLUMN IF NOT EXISTS structure_json_path VARCHAR(500);
ALTER TABLE parsed_documents ADD COLUMN IF NOT EXISTS chunks_json_path VARCHAR(500);

-- 2. 添加哈希值字段（每个列单独添加）
ALTER TABLE parsed_documents ADD COLUMN IF NOT EXISTS structure_json_hash VARCHAR(64);
ALTER TABLE parsed_documents ADD COLUMN IF NOT EXISTS chunks_json_hash VARCHAR(64);

-- 3. 添加分块统计字段
ALTER TABLE parsed_documents ADD COLUMN IF NOT EXISTS chunks_count INTEGER DEFAULT 0;

-- 4. 添加分块时间字段
ALTER TABLE parsed_documents ADD COLUMN IF NOT EXISTS chunked_at TIMESTAMP;

-- 5. 创建索引（在列添加完成后）
CREATE INDEX IF NOT EXISTS idx_parsed_documents_structure_hash ON parsed_documents(structure_json_hash);
CREATE INDEX IF NOT EXISTS idx_parsed_documents_chunks_hash ON parsed_documents(chunks_json_hash);
CREATE INDEX IF NOT EXISTS idx_parsed_documents_chunks_count ON parsed_documents(chunks_count);

-- 6. 添加注释
COMMENT ON COLUMN parsed_documents.structure_json_path IS 'structure.json 文件路径（Silver 层）';
COMMENT ON COLUMN parsed_documents.chunks_json_path IS 'chunks.json 文件路径（Silver 层）';
COMMENT ON COLUMN parsed_documents.structure_json_hash IS 'structure.json 文件哈希（SHA256）';
COMMENT ON COLUMN parsed_documents.chunks_json_hash IS 'chunks.json 文件哈希（SHA256）';
COMMENT ON COLUMN parsed_documents.chunks_count IS '分块数量';
COMMENT ON COLUMN parsed_documents.chunked_at IS '分块时间';
