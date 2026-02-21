-- 迁移：删除 country，添加 tickers、state_of_incorporation_description
-- 日期：2025-02-21
-- 描述：country 改为 tickers 和 stateOfIncorporationDescription

ALTER TABLE us_listed_companies DROP COLUMN IF EXISTS country;
ALTER TABLE us_listed_companies ADD COLUMN IF NOT EXISTS tickers VARCHAR(200);
ALTER TABLE us_listed_companies ADD COLUMN IF NOT EXISTS state_of_incorporation_description VARCHAR(100);

COMMENT ON COLUMN us_listed_companies.tickers IS 'SEC tickers 数组，逗号分隔（同一 CIK 下所有证券代码）';
COMMENT ON COLUMN us_listed_companies.state_of_incorporation_description IS 'stateOfIncorporationDescription';
