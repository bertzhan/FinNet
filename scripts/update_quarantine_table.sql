-- 更新 quarantine_records 表结构
-- 添加新字段以支持完整的隔离管理功能

-- 1. 添加新字段
ALTER TABLE quarantine_records
    ADD COLUMN IF NOT EXISTS source_type VARCHAR(50),
    ADD COLUMN IF NOT EXISTS doc_type VARCHAR(50),
    ADD COLUMN IF NOT EXISTS original_path VARCHAR(500),
    ADD COLUMN IF NOT EXISTS quarantine_path VARCHAR(500),
    ADD COLUMN IF NOT EXISTS failure_stage VARCHAR(50),
    ADD COLUMN IF NOT EXISTS failure_reason VARCHAR(500),
    ADD COLUMN IF NOT EXISTS failure_details TEXT,
    ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS handler VARCHAR(100),
    ADD COLUMN IF NOT EXISTS resolution TEXT,
    ADD COLUMN IF NOT EXISTS quarantine_time TIMESTAMP DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS resolution_time TIMESTAMP,
    ADD COLUMN IF NOT EXISTS extra_metadata JSONB;

-- 2. 修改 document_id 允许为空（支持文档未入库的情况）
ALTER TABLE quarantine_records
    ALTER COLUMN document_id DROP NOT NULL;

-- 3. 删除旧的 UNIQUE 约束（document_id 允许为空后不需要唯一约束）
ALTER TABLE quarantine_records
    DROP CONSTRAINT IF EXISTS quarantine_records_document_id_key;

-- 4. 创建新索引
CREATE INDEX IF NOT EXISTS idx_quarantine_status_time
    ON quarantine_records (status, quarantine_time);

CREATE INDEX IF NOT EXISTS idx_quarantine_failure_stage
    ON quarantine_records (failure_stage);

CREATE INDEX IF NOT EXISTS idx_quarantine_document_id
    ON quarantine_records (document_id);

-- 5. 删除旧索引
DROP INDEX IF EXISTS idx_quarantine_status;

-- 6. 数据迁移：将旧字段的数据复制到新字段（如果存在旧数据）
UPDATE quarantine_records
SET
    failure_reason = COALESCE(failure_reason, reason),
    quarantine_time = COALESCE(quarantine_time, quarantined_at),
    resolution_time = COALESCE(resolution_time, released_at),
    handler = COALESCE(handler, released_by),
    extra_metadata = COALESCE(extra_metadata, details)
WHERE
    failure_reason IS NULL
    OR quarantine_time IS NULL;

-- 7. 注释说明
COMMENT ON COLUMN quarantine_records.source_type IS '数据来源: a_share/hk_stock/us_stock';
COMMENT ON COLUMN quarantine_records.doc_type IS '文档类型';
COMMENT ON COLUMN quarantine_records.original_path IS '原始MinIO路径';
COMMENT ON COLUMN quarantine_records.quarantine_path IS '隔离区MinIO路径';
COMMENT ON COLUMN quarantine_records.failure_stage IS '失败阶段: ingestion_failed/validation_failed/content_failed';
COMMENT ON COLUMN quarantine_records.failure_reason IS '失败原因简述';
COMMENT ON COLUMN quarantine_records.failure_details IS '失败详细信息';
COMMENT ON COLUMN quarantine_records.status IS '状态: pending/processing/resolved/discarded';
COMMENT ON COLUMN quarantine_records.handler IS '处理人';
COMMENT ON COLUMN quarantine_records.resolution IS '处理说明';
COMMENT ON COLUMN quarantine_records.quarantine_time IS '隔离时间';
COMMENT ON COLUMN quarantine_records.resolution_time IS '处理时间';
COMMENT ON COLUMN quarantine_records.extra_metadata IS '额外元数据（JSON）';

-- 8. 旧字段标记为废弃（保留以兼容）
COMMENT ON COLUMN quarantine_records.reason IS '(废弃) 使用 failure_reason';
COMMENT ON COLUMN quarantine_records.details IS '(废弃) 使用 extra_metadata';
COMMENT ON COLUMN quarantine_records.quarantined_at IS '(废弃) 使用 quarantine_time';
COMMENT ON COLUMN quarantine_records.released_at IS '(废弃) 使用 resolution_time';
COMMENT ON COLUMN quarantine_records.released_by IS '(废弃) 使用 handler';
