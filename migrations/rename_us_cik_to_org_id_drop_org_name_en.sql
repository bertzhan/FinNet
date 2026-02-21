-- 迁移：us_listed_companies 表 cik 改名为 org_id，删除 org_name_en
-- 日期：2025-02-21
-- 描述：cik 重命名为 org_id（与 hk_listed_companies 等表统一），删除 org_name_en

-- 删除旧索引
DROP INDEX IF EXISTS idx_us_cik;

-- 重命名列
ALTER TABLE us_listed_companies RENAME COLUMN cik TO org_id;

-- 删除 org_name_en
ALTER TABLE us_listed_companies DROP COLUMN IF EXISTS org_name_en;

-- 创建新索引
CREATE INDEX IF NOT EXISTS idx_us_org_id ON us_listed_companies(org_id);

-- 更新注释
COMMENT ON COLUMN us_listed_companies.org_id IS 'SEC CIK（中央索引键，10位，用于SEC API查询）';
