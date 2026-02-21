-- 迁移：us_listed_companies 主键从 code 改为 org_id
-- 日期：2025-02-21
-- 描述：org_id 为主键，同一 CIK 下多 ticker 合并为一行
-- 注意：SEC 中一个 org_id(CIK) 可对应多个 ticker，需合并

BEGIN;

-- 1. 创建新表（org_id 为主键）
CREATE TABLE us_listed_companies_new (
    org_id VARCHAR(10) PRIMARY KEY,
    code VARCHAR(20),                    -- 主 ticker（取第一个）
    tickers VARCHAR(500),                -- 所有 ticker，逗号分隔
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

-- 2. 按 org_id 合并数据（取每个 org_id 的第一行，合并 tickers）
INSERT INTO us_listed_companies_new (
    org_id, code, tickers, name,
    entity_type, sic, sic_desc, exchanges, fiscal_year_end,
    state_of_incorporation, state_of_incorporation_description,
    created_at, updated_at
)
SELECT
    org_id,
    (array_agg(code ORDER BY code))[1] AS code,
    STRING_AGG(DISTINCT code, ',' ORDER BY code) AS tickers,
    (array_agg(name ORDER BY code))[1] AS name,
    (array_agg(entity_type ORDER BY code))[1],
    (array_agg(sic ORDER BY code))[1],
    (array_agg(sic_desc ORDER BY code))[1],
    (array_agg(exchanges ORDER BY code))[1],
    (array_agg(fiscal_year_end ORDER BY code))[1],
    (array_agg(state_of_incorporation ORDER BY code))[1],
    (array_agg(state_of_incorporation_description ORDER BY code))[1],
    MIN(created_at),
    MAX(updated_at)
FROM us_listed_companies
GROUP BY org_id;

-- 3. 删除原表
DROP TABLE us_listed_companies;

-- 4. 重命名新表
ALTER TABLE us_listed_companies_new RENAME TO us_listed_companies;

-- 5. 为 code 添加唯一索引（用于按 code 查询）
CREATE UNIQUE INDEX IF NOT EXISTS idx_us_listed_companies_code ON us_listed_companies(code) WHERE code IS NOT NULL;

-- 6. 添加注释
COMMENT ON TABLE us_listed_companies IS '美股上市公司表（org_id 为主键，一个 CIK 对应一行）';
COMMENT ON COLUMN us_listed_companies.org_id IS 'SEC CIK（主键）';
COMMENT ON COLUMN us_listed_companies.code IS '主 Ticker（同一 CIK 下取第一个）';
COMMENT ON COLUMN us_listed_companies.tickers IS '所有 Ticker，逗号分隔';

COMMIT;
