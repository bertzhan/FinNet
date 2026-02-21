-- 迁移：将 us_listed_companies 表 sic_desc 重命名为 industry
-- 日期：2025-02-21
-- 描述：与 hs_listed_companies、hk_listed_companies 的行业字段统一命名为 industry

BEGIN;

ALTER TABLE us_listed_companies RENAME COLUMN sic_desc TO industry;

COMMENT ON COLUMN us_listed_companies.industry IS 'SIC行业描述（与 sic 代码对应）';

COMMIT;
