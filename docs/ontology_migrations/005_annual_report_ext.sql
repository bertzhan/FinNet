-- 年报深度抽取（专注 API 拿不到的差异化信息）
-- 依赖：002_unified_entities.sql, 004_financial.sql (fiscal_periods)

CREATE TABLE annual_report_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    unified_company_id UUID NOT NULL REFERENCES unified_companies(id),
    fiscal_period_id UUID NOT NULL REFERENCES fiscal_periods(id),
    source_document_id UUID REFERENCES documents(id),

    -- 业务分部 (每家公司分部定义不同，用 JSONB)
    -- 示例: [{"name":"茅台酒","revenue":1095,"growth_pct":15.5,"margin_pct":94}, ...]
    business_segments JSONB,

    -- 地理区域收入
    -- 示例: [{"region":"国内","revenue":1280,"pct":98.5}, {"region":"海外","revenue":19,"pct":1.5}]
    geographic_revenue JSONB,

    -- 政府补助
    government_subsidy FLOAT,
    government_subsidy_pct_of_net_income FLOAT,

    -- 研发明细
    rd_expense_total FLOAT,
    rd_capitalized FLOAT,
    rd_expensed FLOAT,

    -- 客户/供应商集中度
    top5_customer_revenue_pct FLOAT,
    top5_supplier_purchase_pct FLOAT,

    -- 员工结构
    total_employees INTEGER,
    rd_employees INTEGER,
    sales_employees INTEGER,
    production_employees INTEGER,

    -- 抽取元数据
    extraction_model VARCHAR(50),
    extraction_confidence FLOAT,
    human_verified BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(unified_company_id, fiscal_period_id)
);
