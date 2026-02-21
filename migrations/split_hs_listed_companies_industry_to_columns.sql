-- 迁移：将 hs_listed_companies 表 industry (JSON) 拆分为 industry_code、industry 两列
-- 日期：2025-02-21
-- 描述：原 industry 为 JSON {"ind_code":"BK0055","ind_name":"银行"}，拆为 industry_code VARCHAR、industry VARCHAR

BEGIN;

-- 1. 添加新列
ALTER TABLE hs_listed_companies ADD COLUMN IF NOT EXISTS industry_code VARCHAR(50);
ALTER TABLE hs_listed_companies ADD COLUMN IF NOT EXISTS industry_name VARCHAR(200);

-- 2. 迁移数据并删除旧列（仅当 industry 为 JSON/JSONB 时）
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'hs_listed_companies'
        AND column_name = 'industry' AND data_type IN ('json', 'jsonb')
    ) THEN
        UPDATE hs_listed_companies
        SET industry_code = industry->>'ind_code', industry_name = industry->>'ind_name'
        WHERE industry IS NOT NULL;
        ALTER TABLE hs_listed_companies DROP COLUMN industry;
        ALTER TABLE hs_listed_companies RENAME COLUMN industry_name TO industry;
    ELSE
        -- industry 已是 VARCHAR 或不存在，删除多余的 industry_name
        ALTER TABLE hs_listed_companies DROP COLUMN IF EXISTS industry_name;
    END IF;
END $$;

COMMENT ON COLUMN hs_listed_companies.industry_code IS '行业代码（如：BK0055）';
COMMENT ON COLUMN hs_listed_companies.industry IS '行业名称（如：银行）';

COMMIT;
