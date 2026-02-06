-- 删除 hk_listed_companies 表中未使用的字段

-- 删除 name_en 字段
ALTER TABLE hk_listed_companies DROP COLUMN IF EXISTS name_en;

-- 删除 board 字段（同时删除相关索引）
DROP INDEX IF EXISTS idx_hk_board;
ALTER TABLE hk_listed_companies DROP COLUMN IF EXISTS board;

-- 删除其他未使用的字段
ALTER TABLE hk_listed_companies DROP COLUMN IF EXISTS org_short_name_cn;
ALTER TABLE hk_listed_companies DROP COLUMN IF EXISTS org_short_name_en;
ALTER TABLE hk_listed_companies DROP COLUMN IF EXISTS pre_name_cn;
ALTER TABLE hk_listed_companies DROP COLUMN IF EXISTS main_operation_business;
ALTER TABLE hk_listed_companies DROP COLUMN IF EXISTS operating_scope;
ALTER TABLE hk_listed_companies DROP COLUMN IF EXISTS postcode;
ALTER TABLE hk_listed_companies DROP COLUMN IF EXISTS office_address_en;
ALTER TABLE hk_listed_companies DROP COLUMN IF EXISTS legal_representative;
ALTER TABLE hk_listed_companies DROP COLUMN IF EXISTS general_manager;
ALTER TABLE hk_listed_companies DROP COLUMN IF EXISTS listed_date;
ALTER TABLE hk_listed_companies DROP COLUMN IF EXISTS reg_asset;
ALTER TABLE hk_listed_companies DROP COLUMN IF EXISTS currency;

-- 确认迁移成功
SELECT 'hk_listed_companies 表删除未使用字段成功' AS status;
