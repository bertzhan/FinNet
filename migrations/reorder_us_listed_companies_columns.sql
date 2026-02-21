-- 迁移：重排 us_listed_companies 表列顺序
-- 日期：2025-02-21
-- 描述：标识符优先 order: code, org_id, tickers, name → SEC 字段 → 时间戳
-- 说明：PostgreSQL 不支持 ALTER COLUMN ... AFTER，需通过重建表实现

BEGIN;

-- 1. 创建临时表（新列顺序）
CREATE TABLE us_listed_companies_new (
    code VARCHAR(20) PRIMARY KEY,
    org_id VARCHAR(10) NOT NULL,
    tickers VARCHAR(200),
    name VARCHAR(200) NOT NULL,
    entity_type VARCHAR(50),
    sic VARCHAR(10),
    sic_desc VARCHAR(200),
    exchanges VARCHAR(200),
    fiscal_year_end VARCHAR(4),
    state_of_incorporation VARCHAR(20),
    state_of_incorporation_description VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 2. 复制数据
INSERT INTO us_listed_companies_new (
    code, org_id, tickers, name,
    entity_type, sic, sic_desc, exchanges, fiscal_year_end,
    state_of_incorporation, state_of_incorporation_description,
    created_at, updated_at
)
SELECT
    code, org_id, tickers, name,
    entity_type, sic, sic_desc, exchanges, fiscal_year_end,
    state_of_incorporation, state_of_incorporation_description,
    created_at, updated_at
FROM us_listed_companies;

-- 3. 删除原表
DROP TABLE us_listed_companies;

-- 4. 重命名临时表
ALTER TABLE us_listed_companies_new RENAME TO us_listed_companies;

-- 5. 重建 org_id 索引
CREATE INDEX IF NOT EXISTS idx_us_org_id ON us_listed_companies(org_id);

-- 6. 添加注释
COMMENT ON TABLE us_listed_companies IS '美股上市公司表（数据来源：SEC EDGAR API + NASDAQ/NYSE官方列表）';
COMMENT ON COLUMN us_listed_companies.code IS 'Ticker（股票代码，如：AAPL）';
COMMENT ON COLUMN us_listed_companies.org_id IS 'SEC CIK（中央索引键，用于SEC API查询）';
COMMENT ON COLUMN us_listed_companies.tickers IS 'SEC tickers 数组，逗号分隔';
COMMENT ON COLUMN us_listed_companies.name IS '公司名称（英文）';

COMMIT;
