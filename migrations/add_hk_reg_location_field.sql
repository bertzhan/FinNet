-- 添加注册地字段到 hk_listed_companies 表

-- 添加注册地字段
ALTER TABLE hk_listed_companies 
ADD COLUMN IF NOT EXISTS reg_location VARCHAR(100);

-- 添加字段注释
COMMENT ON COLUMN hk_listed_companies.reg_location IS '注册地（与注册地址不同，注册地通常是地区名称，如"香港"、"开曼群岛"等）';

-- 确认迁移成功
SELECT 'hk_listed_companies 表添加 reg_location 字段成功' AS status;
