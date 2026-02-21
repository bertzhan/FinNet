-- 迁移：为 us_listed_companies 添加 SEC submissions API 字段
-- 日期：2025-02-21
-- 描述：从 https://data.sec.gov/submissions/CIK{cik}.json 获取并存储
--       entitytype, sic, sicdesc, exchanges, fiscalyearend, stateofincorporation, country

ALTER TABLE us_listed_companies ADD COLUMN IF NOT EXISTS entity_type VARCHAR(50);
ALTER TABLE us_listed_companies ADD COLUMN IF NOT EXISTS sic VARCHAR(10);
ALTER TABLE us_listed_companies ADD COLUMN IF NOT EXISTS sic_desc VARCHAR(200);
ALTER TABLE us_listed_companies ADD COLUMN IF NOT EXISTS exchanges VARCHAR(200);
ALTER TABLE us_listed_companies ADD COLUMN IF NOT EXISTS fiscal_year_end VARCHAR(4);
ALTER TABLE us_listed_companies ADD COLUMN IF NOT EXISTS state_of_incorporation VARCHAR(20);
ALTER TABLE us_listed_companies ADD COLUMN IF NOT EXISTS country VARCHAR(100);

COMMENT ON COLUMN us_listed_companies.entity_type IS 'SEC entityType (e.g. operating, holding)';
COMMENT ON COLUMN us_listed_companies.sic IS 'SIC行业代码';
COMMENT ON COLUMN us_listed_companies.sic_desc IS 'SIC行业描述';
COMMENT ON COLUMN us_listed_companies.exchanges IS '交易所列表，逗号分隔 (e.g. Nasdaq, NYSE)';
COMMENT ON COLUMN us_listed_companies.fiscal_year_end IS '财年结束日 MMDD (e.g. 0926=9月26日)';
COMMENT ON COLUMN us_listed_companies.state_of_incorporation IS '注册州/国家代码';
COMMENT ON COLUMN us_listed_companies.country IS '注册国家';
