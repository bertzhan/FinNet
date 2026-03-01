-- 财务期间 + 财务快照 + 估值快照
-- 依赖：002_unified_entities.sql (unified_companies, market_listings)

CREATE TABLE fiscal_periods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    period_id VARCHAR(20) NOT NULL UNIQUE,   -- 2024-FY, 2024-Q3
    fiscal_year INTEGER NOT NULL,
    period_type VARCHAR(5) NOT NULL,         -- FY / H1 / Q1-Q3 / LTM
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    filing_date DATE,                        -- 实际申报日（避免前视偏差）
    is_audited BOOLEAN DEFAULT FALSE
);

CREATE TABLE financial_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    unified_company_id UUID NOT NULL REFERENCES unified_companies(id),
    market_listing_id UUID NOT NULL REFERENCES market_listings(id),
    fiscal_period_id UUID NOT NULL REFERENCES fiscal_periods(id),
    source_document_id UUID REFERENCES documents(id),  -- 数据溯源
    data_version VARCHAR(20) DEFAULT 'as_reported',    -- as_reported / standardized
    accounting_standard VARCHAR(10),
    reporting_currency VARCHAR(5),
    exchange_rate_to_usd FLOAT,
    data_source VARCHAR(20),                 -- tushare / yfinance / wind / extracted

    -- 利润表
    revenue FLOAT, cost_of_revenue FLOAT, gross_profit FLOAT,
    operating_income FLOAT, ebit FLOAT, ebitda FLOAT,
    net_income FLOAT, eps_basic FLOAT, eps_diluted FLOAT,

    -- 资产负债表
    total_assets FLOAT, total_liabilities FLOAT, total_equity FLOAT,
    cash_and_equivalents FLOAT, total_debt FLOAT, net_debt FLOAT,
    current_assets FLOAT, current_liabilities FLOAT,

    -- 现金流量表
    operating_cashflow FLOAT, investing_cashflow FLOAT,
    financing_cashflow FLOAT, free_cashflow FLOAT, capex FLOAT,

    -- 盈利能力
    gross_margin FLOAT, operating_margin FLOAT, net_margin FLOAT,
    roe FLOAT, roa FLOAT, roic FLOAT,

    -- 偿债与营运
    current_ratio FLOAT, quick_ratio FLOAT,
    debt_to_equity FLOAT, interest_coverage FLOAT,

    -- 增长指标
    revenue_growth_yoy FLOAT, net_income_growth_yoy FLOAT,
    revenue_cagr_3y FLOAT,

    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(unified_company_id, market_listing_id, fiscal_period_id, data_version)
);

CREATE TABLE valuation_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    unified_company_id UUID NOT NULL REFERENCES unified_companies(id),
    market_listing_id UUID NOT NULL REFERENCES market_listings(id),
    snapshot_date DATE NOT NULL,
    fiscal_period_id UUID REFERENCES fiscal_periods(id),

    market_cap FLOAT, market_cap_usd FLOAT, enterprise_value FLOAT,
    shares_outstanding BIGINT, float_shares BIGINT,

    pe_ttm FLOAT, pe_forward FLOAT, pb FLOAT, ps_ttm FLOAT,
    ev_ebitda FLOAT, ev_revenue FLOAT, peg FLOAT,
    dividend_yield FLOAT,

    price_return_1m FLOAT, price_return_3m FLOAT,
    price_return_ytd FLOAT, price_return_1y FLOAT,
    beta_1y FLOAT,

    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(unified_company_id, market_listing_id, snapshot_date)
);
