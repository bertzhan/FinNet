-- 统一公司实体 + 多市场上市记录
-- 依赖：无
-- 说明：不动现有三张公司表，在上层叠加。通过 market_listings.local_org_id 反查原表

CREATE TABLE unified_companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name_cn VARCHAR(200),
    canonical_name_en VARCHAR(200),
    lei_code VARCHAR(20),
    country_of_incorporation VARCHAR(10),
    established_date DATE,
    entity_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE market_listings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    unified_company_id UUID NOT NULL REFERENCES unified_companies(id),
    market VARCHAR(5) NOT NULL,              -- CN / HK / US
    stock_code VARCHAR(20) NOT NULL,
    exchange VARCHAR(20),                    -- SSE / SZSE / HKEX / NYSE / NASDAQ
    local_org_id VARCHAR(50),               -- 反查原表的 ID
    accounting_standard VARCHAR(10),         -- CAS / IFRS / US-GAAP
    reporting_currency VARCHAR(5),           -- CNY / HKD / USD
    listing_date DATE,
    delisting_date DATE,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(market, stock_code)
);

-- 给 documents 表加外键（不改原表结构，只加字段）
ALTER TABLE documents ADD COLUMN unified_company_id UUID REFERENCES unified_companies(id);
