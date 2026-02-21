-- 迁移：将 listed_companies 表 affiliate_industry 重命名为 industry
-- 日期：2025-02-21
-- 描述：与 hk_listed_companies、us_listed_companies 的行业字段统一命名为 industry
-- 注意：执行本迁移后，需执行 rename_listed_companies_to_hs_listed_companies.sql 将表重命名

BEGIN;

ALTER TABLE listed_companies RENAME COLUMN affiliate_industry TO industry;

COMMENT ON COLUMN listed_companies.industry IS '所属行业（JSON格式，含 ind_code/ind_name）';

COMMIT;
