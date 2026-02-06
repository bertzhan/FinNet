-- 港股上市公司表字段扩展迁移脚本
-- 添加 akshare 公司详细信息字段

-- 1. 添加公司名称信息字段
ALTER TABLE hk_listed_companies 
ADD COLUMN IF NOT EXISTS org_name_cn VARCHAR(200),
ADD COLUMN IF NOT EXISTS org_short_name_cn VARCHAR(200),
ADD COLUMN IF NOT EXISTS org_name_en VARCHAR(200),
ADD COLUMN IF NOT EXISTS org_short_name_en VARCHAR(200),
ADD COLUMN IF NOT EXISTS pre_name_cn VARCHAR(200);

-- 2. 添加业务信息字段
ALTER TABLE hk_listed_companies 
ADD COLUMN IF NOT EXISTS main_operation_business TEXT,
ADD COLUMN IF NOT EXISTS operating_scope TEXT,
ADD COLUMN IF NOT EXISTS org_cn_introduction TEXT;

-- 3. 添加联系信息字段
ALTER TABLE hk_listed_companies 
ADD COLUMN IF NOT EXISTS telephone VARCHAR(100),
ADD COLUMN IF NOT EXISTS postcode VARCHAR(20),
ADD COLUMN IF NOT EXISTS fax VARCHAR(50),
ADD COLUMN IF NOT EXISTS email VARCHAR(50),
ADD COLUMN IF NOT EXISTS org_website VARCHAR(100),
ADD COLUMN IF NOT EXISTS reg_address_cn VARCHAR(200),
ADD COLUMN IF NOT EXISTS reg_address_en VARCHAR(200),
ADD COLUMN IF NOT EXISTS office_address_cn VARCHAR(200),
ADD COLUMN IF NOT EXISTS office_address_en VARCHAR(200);

-- 4. 添加管理信息字段
ALTER TABLE hk_listed_companies 
ADD COLUMN IF NOT EXISTS legal_representative VARCHAR(50),
ADD COLUMN IF NOT EXISTS general_manager VARCHAR(50),
ADD COLUMN IF NOT EXISTS secretary VARCHAR(50),
ADD COLUMN IF NOT EXISTS chairman VARCHAR(50);

-- 5. 添加财务信息字段
ALTER TABLE hk_listed_companies 
ADD COLUMN IF NOT EXISTS established_date BIGINT,
ADD COLUMN IF NOT EXISTS listed_date BIGINT,
ADD COLUMN IF NOT EXISTS reg_asset FLOAT,
ADD COLUMN IF NOT EXISTS staff_num INTEGER;

-- 6. 添加其他信息字段
ALTER TABLE hk_listed_companies 
ADD COLUMN IF NOT EXISTS currency VARCHAR(20),
ADD COLUMN IF NOT EXISTS industry VARCHAR(100);

-- 7. 添加字段注释
COMMENT ON COLUMN hk_listed_companies.org_name_cn IS '公司全称（中文）';
COMMENT ON COLUMN hk_listed_companies.org_short_name_cn IS '公司简称（中文）';
COMMENT ON COLUMN hk_listed_companies.org_name_en IS '公司全称（英文）';
COMMENT ON COLUMN hk_listed_companies.org_short_name_en IS '公司简称（英文）';
COMMENT ON COLUMN hk_listed_companies.pre_name_cn IS '曾用名';
COMMENT ON COLUMN hk_listed_companies.main_operation_business IS '主营业务';
COMMENT ON COLUMN hk_listed_companies.operating_scope IS '经营范围';
COMMENT ON COLUMN hk_listed_companies.org_cn_introduction IS '公司简介';
COMMENT ON COLUMN hk_listed_companies.telephone IS '电话';
COMMENT ON COLUMN hk_listed_companies.postcode IS '邮编';
COMMENT ON COLUMN hk_listed_companies.fax IS '传真';
COMMENT ON COLUMN hk_listed_companies.email IS '邮箱';
COMMENT ON COLUMN hk_listed_companies.org_website IS '网站';
COMMENT ON COLUMN hk_listed_companies.reg_address_cn IS '注册地址（中文）';
COMMENT ON COLUMN hk_listed_companies.reg_address_en IS '注册地址（英文）';
COMMENT ON COLUMN hk_listed_companies.office_address_cn IS '办公地址（中文）';
COMMENT ON COLUMN hk_listed_companies.office_address_en IS '办公地址（英文）';
COMMENT ON COLUMN hk_listed_companies.legal_representative IS '法定代表人';
COMMENT ON COLUMN hk_listed_companies.general_manager IS '总经理';
COMMENT ON COLUMN hk_listed_companies.secretary IS '董事会秘书';
COMMENT ON COLUMN hk_listed_companies.chairman IS '董事长';
COMMENT ON COLUMN hk_listed_companies.established_date IS '成立日期（时间戳）';
COMMENT ON COLUMN hk_listed_companies.listed_date IS '上市日期（时间戳）';
COMMENT ON COLUMN hk_listed_companies.reg_asset IS '注册资本';
COMMENT ON COLUMN hk_listed_companies.staff_num IS '员工人数';
COMMENT ON COLUMN hk_listed_companies.currency IS '货币';
COMMENT ON COLUMN hk_listed_companies.industry IS '所属行业';

-- 8. 确认迁移成功
SELECT 'hk_listed_companies 表字段扩展成功' AS status;
