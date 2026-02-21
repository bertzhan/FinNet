-- 迁移：重排 hs_listed_companies 表列顺序
-- 日期：2025-02-21
-- 描述：标识符优先 → 公司名称 → 业务 → 地区 → 日期/人员 → 行业 → 时间戳
-- 说明：PostgreSQL 不支持 ALTER COLUMN ... AFTER，需通过重建表实现

BEGIN;

-- 1. 创建临时表（新列顺序）
CREATE TABLE hs_listed_companies_new (
    org_id VARCHAR(100) PRIMARY KEY,
    code VARCHAR(20),
    name VARCHAR(100) NOT NULL,
    org_name_cn VARCHAR(100),
    org_short_name_cn VARCHAR(100),
    org_name_en VARCHAR(100),
    org_short_name_en VARCHAR(100),
    pre_name_cn VARCHAR(100),
    main_operation_business TEXT,
    operating_scope TEXT,
    org_cn_introduction TEXT,
    provincial_name VARCHAR(10),
    established_date DATE,
    listed_date DATE,
    staff_num INTEGER,
    industry_code VARCHAR(50),
    industry VARCHAR(200),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 2. 复制数据（需先执行 split、alter_established_listed_to_date）
INSERT INTO hs_listed_companies_new (
    org_id, code, name, org_name_cn, org_short_name_cn, org_name_en, org_short_name_en, pre_name_cn,
    main_operation_business, operating_scope, org_cn_introduction,
    provincial_name, established_date, listed_date, staff_num,
    industry_code, industry,
    created_at, updated_at
)
SELECT
    org_id, code, name, org_name_cn, org_short_name_cn, org_name_en, org_short_name_en, pre_name_cn,
    main_operation_business, operating_scope, org_cn_introduction,
    provincial_name,
    CASE WHEN established_date IS NOT NULL AND established_date::text ~ '^\d{10,}$'
         THEN to_timestamp(least(established_date::numeric, 99999999999) / 1000.0)::date
         WHEN established_date IS NOT NULL THEN established_date::date
         ELSE NULL END,
    CASE WHEN listed_date IS NOT NULL AND listed_date::text ~ '^\d{10,}$'
         THEN to_timestamp(least(listed_date::numeric, 99999999999) / 1000.0)::date
         WHEN listed_date IS NOT NULL THEN listed_date::date
         ELSE NULL END,
    staff_num,
    industry_code, industry,
    created_at, updated_at
FROM hs_listed_companies;

-- 3. 删除原表
DROP TABLE hs_listed_companies;

-- 4. 重命名临时表
ALTER TABLE hs_listed_companies_new RENAME TO hs_listed_companies;

-- 5. 重建 code 唯一索引
CREATE UNIQUE INDEX IF NOT EXISTS idx_hs_listed_companies_code ON hs_listed_companies(code) WHERE code IS NOT NULL;

-- 6. 添加注释
COMMENT ON TABLE hs_listed_companies IS 'A股上市公司表（数据来源：akshare stock_individual_basic_info_xq）';
COMMENT ON COLUMN hs_listed_companies.org_id IS '机构ID（主键）';
COMMENT ON COLUMN hs_listed_companies.code IS '股票代码（如：000001）';
COMMENT ON COLUMN hs_listed_companies.name IS '公司简称（如：平安银行）';
COMMENT ON COLUMN hs_listed_companies.industry_code IS '行业代码（如：BK0055）';
COMMENT ON COLUMN hs_listed_companies.industry IS '行业名称（如：银行）';

COMMIT;
