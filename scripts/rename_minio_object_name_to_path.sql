-- 重命名 documents 表的 minio_object_name 字段为 minio_object_path
-- 执行方式: psql -U postgres -d finnet -f scripts/rename_minio_object_name_to_path.sql

-- 1. 重命名字段
ALTER TABLE documents
    RENAME COLUMN minio_object_name TO minio_object_path;

-- 2. 重命名索引（如果有）
ALTER INDEX IF EXISTS documents_minio_object_name_key 
    RENAME TO documents_minio_object_path_key;

-- 3. 验证字段已重命名
SELECT 
    column_name, 
    data_type
FROM information_schema.columns
WHERE table_name = 'documents' 
    AND column_name IN ('minio_object_name', 'minio_object_path');

-- 应该只看到 minio_object_path，不应该看到 minio_object_name
