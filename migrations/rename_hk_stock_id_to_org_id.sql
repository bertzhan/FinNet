-- 将 hk_listed_companies 表的 stock_id 字段重命名为 org_id

-- 1. 删除旧索引
DROP INDEX IF EXISTS idx_hk_stock_id;

-- 2. 重命名字段
ALTER TABLE hk_listed_companies 
RENAME COLUMN stock_id TO org_id;

-- 3. 创建新索引
CREATE INDEX IF NOT EXISTS idx_hk_org_id ON hk_listed_companies(org_id);

-- 4. 更新字段注释
COMMENT ON COLUMN hk_listed_companies.org_id IS '披露易 orgId（用于查询报告）';

-- 5. 确认迁移成功
SELECT 'hk_listed_companies 表字段重命名成功: stock_id -> org_id' AS status;
