-- 迁移：删除 us_listed_companies 表中未使用的字段
-- 日期：2025-02-21
-- 描述：删除 org_name_cn, sic_code, sic_description, is_foreign_filer, country, is_active

-- 删除索引（删除列前需先删除依赖的索引）
DROP INDEX IF EXISTS idx_us_foreign;
DROP INDEX IF EXISTS idx_us_active;

-- 删除列（使用 IF EXISTS 防止列不存在时报错）
ALTER TABLE us_listed_companies DROP COLUMN IF EXISTS org_name_cn;
ALTER TABLE us_listed_companies DROP COLUMN IF EXISTS sic_code;
ALTER TABLE us_listed_companies DROP COLUMN IF EXISTS sic_description;
ALTER TABLE us_listed_companies DROP COLUMN IF EXISTS is_foreign_filer;
ALTER TABLE us_listed_companies DROP COLUMN IF EXISTS country;
ALTER TABLE us_listed_companies DROP COLUMN IF EXISTS is_active;
