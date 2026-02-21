-- 迁移：将 listed_companies 表重命名为 hs_listed_companies
-- 日期：2025-02-21
-- 描述：与 hk_listed_companies、us_listed_companies 命名统一（hs=沪深A股）

BEGIN;

ALTER TABLE listed_companies RENAME TO hs_listed_companies;

-- 重建 code 唯一索引（表重命名后索引名可能需更新）
DROP INDEX IF EXISTS idx_listed_companies_code;
CREATE UNIQUE INDEX IF NOT EXISTS idx_hs_listed_companies_code ON hs_listed_companies(code) WHERE code IS NOT NULL;

COMMENT ON TABLE hs_listed_companies IS 'A股上市公司表（数据来源：akshare stock_individual_basic_info_xq）';

COMMIT;
