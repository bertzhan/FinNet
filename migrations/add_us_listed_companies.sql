-- 迁移：添加美股上市公司表
-- 日期：2025-02-14
-- 描述：创建 us_listed_companies 表，存储 NYSE/NASDAQ 等美股上市公司信息

-- 创建美股上市公司表
CREATE TABLE IF NOT EXISTS us_listed_companies (
    -- 基本信息
    code VARCHAR(20) PRIMARY KEY,                           -- Ticker（股票代码，如：AAPL）
    name VARCHAR(200) NOT NULL,                             -- 公司名称（英文）

    -- SEC特定字段
    cik VARCHAR(10) NOT NULL,                               -- CIK（中央索引键，SEC唯一标识符）

    -- 公司名称信息
    org_name_en VARCHAR(200),                               -- 公司全称（英文）

    -- 行业信息
    sic_code VARCHAR(10),                                   -- SIC行业代码（Standard Industrial Classification）
    sic_description VARCHAR(200),                           -- SIC行业描述

    -- 公司分类
    is_foreign_filer BOOLEAN DEFAULT FALSE,                 -- 是否为外国公司（提交20-F/40-F）
    country VARCHAR(100),                                   -- 注册国家/地区

    -- 状态
    is_active BOOLEAN DEFAULT TRUE,                         -- 是否活跃（是否已退市）

    -- 时间戳
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_us_cik ON us_listed_companies(cik);                       -- CIK索引（SEC API查询）
CREATE INDEX IF NOT EXISTS idx_us_foreign ON us_listed_companies(is_foreign_filer);      -- 外国公司索引
CREATE INDEX IF NOT EXISTS idx_us_active ON us_listed_companies(is_active);              -- 活跃状态索引

-- 添加注释
COMMENT ON TABLE us_listed_companies IS '美股上市公司表（数据来源：SEC EDGAR API + NASDAQ/NYSE官方列表）';
COMMENT ON COLUMN us_listed_companies.code IS 'Ticker（股票代码，如：AAPL）';
COMMENT ON COLUMN us_listed_companies.name IS '公司名称（英文）';
COMMENT ON COLUMN us_listed_companies.cik IS 'CIK（中央索引键，SEC唯一标识符，用于SEC API查询）';
COMMENT ON COLUMN us_listed_companies.is_foreign_filer IS '是否为外国私人发行人（Foreign Private Issuer），提交20-F/40-F表单';
COMMENT ON COLUMN us_listed_companies.sic_code IS 'SIC行业代码（Standard Industrial Classification）';
