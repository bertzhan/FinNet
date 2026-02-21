-- 迁移：listed_companies 表精简字段，保留标识符/公司名称/业务/省份/日期/员工数/行业/时间戳
-- 日期：2025-02-21
-- 描述：删除联系、管理、证券等 22 列，仅保留 18 列
-- 说明：PostgreSQL 不支持 ALTER COLUMN ... AFTER，需通过重建表实现

BEGIN;

-- 1. 创建临时表（仅保留需要的列）
CREATE TABLE listed_companies_new (
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
    established_date BIGINT,
    listed_date BIGINT,
    staff_num INTEGER,
    affiliate_industry JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 2. 复制数据（仅保留列）
INSERT INTO listed_companies_new (
    org_id, code, name, org_name_cn, org_short_name_cn, org_name_en, org_short_name_en, pre_name_cn,
    main_operation_business, operating_scope, org_cn_introduction,
    provincial_name, established_date, listed_date, staff_num, affiliate_industry,
    created_at, updated_at
)
SELECT
    org_id, code, name, org_name_cn, org_short_name_cn, org_name_en, org_short_name_en, pre_name_cn,
    main_operation_business, operating_scope, org_cn_introduction,
    provincial_name, established_date, listed_date, staff_num,
    affiliate_industry::jsonb,
    created_at, updated_at
FROM listed_companies;

-- 3. 删除原表
DROP TABLE listed_companies;

-- 4. 重命名临时表
ALTER TABLE listed_companies_new RENAME TO listed_companies;

-- 5. 重建 code 唯一索引
CREATE UNIQUE INDEX IF NOT EXISTS idx_listed_companies_code ON listed_companies(code) WHERE code IS NOT NULL;

-- 6. 添加注释
COMMENT ON TABLE listed_companies IS 'A股上市公司表（数据来源：akshare stock_individual_basic_info_xq）';
COMMENT ON COLUMN listed_companies.org_id IS '机构ID（主键）';
COMMENT ON COLUMN listed_companies.code IS '股票代码（如：000001）';
COMMENT ON COLUMN listed_companies.name IS '公司简称（如：平安银行）';
COMMENT ON COLUMN listed_companies.provincial_name IS '省份名称';
COMMENT ON COLUMN listed_companies.established_date IS '成立日期（毫秒时间戳）';
COMMENT ON COLUMN listed_companies.listed_date IS '上市日期（毫秒时间戳）';

COMMIT;
