-- 行业分类 + 跨体系映射 + 公司-行业归属
-- 依赖：002_unified_entities.sql (unified_companies)

CREATE TABLE industry_classifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(20) NOT NULL,
    name_cn VARCHAR(100),
    name_en VARCHAR(100),
    taxonomy VARCHAR(10) NOT NULL,           -- GICS / SW / HSI
    level INTEGER NOT NULL,                  -- 1-4
    parent_id UUID REFERENCES industry_classifications(id),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(taxonomy, code)
);

CREATE TABLE industry_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES industry_classifications(id),
    target_id UUID NOT NULL REFERENCES industry_classifications(id),
    mapping_quality VARCHAR(20) NOT NULL,    -- exact / approximate / partial
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE company_industries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    unified_company_id UUID NOT NULL REFERENCES unified_companies(id),
    classification_id UUID NOT NULL REFERENCES industry_classifications(id),
    is_primary BOOLEAN DEFAULT TRUE,
    effective_date DATE,
    source VARCHAR(20),                      -- tushare / wind / manual / derived
    confidence FLOAT,
    UNIQUE(unified_company_id, classification_id)
);

-- 同业关系推导视图（主行业相同则互为同业）
CREATE OR REPLACE VIEW v_peer_companies AS
SELECT ci1.unified_company_id as company_a,
       ci2.unified_company_id as company_b,
       ci1.classification_id as shared_industry,
       'industry_peer' as peer_type
FROM company_industries ci1
JOIN company_industries ci2
    ON ci1.classification_id = ci2.classification_id
    AND ci1.is_primary = true AND ci2.is_primary = true
    AND ci1.unified_company_id < ci2.unified_company_id;
