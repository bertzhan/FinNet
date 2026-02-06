-- 重命名 hk_listed_companies 表的注册地址字段
-- 将 reg_address_cn 重命名为 reg_address

-- 重命名字段
ALTER TABLE hk_listed_companies 
RENAME COLUMN reg_address_cn TO reg_address;

-- 更新字段注释
COMMENT ON COLUMN hk_listed_companies.reg_address IS '注册地址';

-- 删除旧的 reg_address_en 字段（如果不需要英文地址）
-- ALTER TABLE hk_listed_companies DROP COLUMN IF EXISTS reg_address_en;

-- 确认迁移成功
SELECT 'hk_listed_companies 表字段重命名成功' AS status;
