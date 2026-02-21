-- 迁移：添加美股上市公司表
-- 日期：2025-02-14
-- 描述：创建 us_listed_companies 表，存储 NYSE/NASDAQ 等美股上市公司信息

-- 创建美股上市公司表
CREATE TABLE IF NOT EXISTS us_listed_companies (
    -- 标识符（优先）
    code VARCHAR(20) PRIMARY KEY,                           -- Ticker（股票代码，如：AAPL）
    org_id VARCHAR(10) NOT NULL,                             -- SEC CIK（中央索引键，用于SEC API查询）
    tickers VARCHAR(200),                                    -- tickers 数组，逗号分隔

    -- 基本信息
    name VARCHAR(200) NOT NULL,                             -- 公司名称（英文）

    -- SEC submissions 详情（来自 data.sec.gov/submissions/CIK{org_id}.json）
    entity_type VARCHAR(50),                                 -- entityType
    sic VARCHAR(10),                                         -- SIC行业代码
    sic_desc VARCHAR(200),                                   -- sicDescription
    exchanges VARCHAR(200),                                  -- 交易所列表，逗号分隔
    fiscal_year_end VARCHAR(4),                              -- 财年结束日 MMDD
    state_of_incorporation VARCHAR(20),                      -- stateOfIncorporation
    state_of_incorporation_description VARCHAR(100),         -- stateOfIncorporationDescription

    -- 时间戳
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_us_org_id ON us_listed_companies(org_id);                  -- org_id索引（SEC API查询）

-- 添加注释
COMMENT ON TABLE us_listed_companies IS '美股上市公司表（数据来源：SEC EDGAR API + NASDAQ/NYSE官方列表）';
COMMENT ON COLUMN us_listed_companies.code IS 'Ticker（股票代码，如：AAPL）';
COMMENT ON COLUMN us_listed_companies.name IS '公司名称（英文）';
COMMENT ON COLUMN us_listed_companies.org_id IS 'SEC CIK（中央索引键，用于SEC API查询）';
