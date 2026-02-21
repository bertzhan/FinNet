-- 为 hk_listed_companies 表添加沪港通/深港通标的字段
-- 数据来源：akshare stock_hk_security_profile_em

ALTER TABLE hk_listed_companies
ADD COLUMN IF NOT EXISTS is_sh_hk_connect BOOLEAN,  -- 是否沪港通标的
ADD COLUMN IF NOT EXISTS is_sz_hk_connect BOOLEAN;  -- 是否深港通标的

COMMENT ON COLUMN hk_listed_companies.is_sh_hk_connect IS '是否沪港通标的';
COMMENT ON COLUMN hk_listed_companies.is_sz_hk_connect IS '是否深港通标的';

SELECT 'hk_listed_companies 表添加沪港通/深港通字段成功' AS status;
