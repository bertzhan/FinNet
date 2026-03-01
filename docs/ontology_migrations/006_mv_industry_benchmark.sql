-- 行业基准物化视图（动态聚合各行业财务指标中位数）
-- 依赖：003_industry.sql, 004_financial.sql

CREATE MATERIALIZED VIEW mv_industry_benchmark AS
WITH latest_snapshots AS (
    SELECT fs.*, ci.classification_id, ic.taxonomy, ic.name_cn as industry_name,
           ml.market,
           ROW_NUMBER() OVER (PARTITION BY fs.unified_company_id ORDER BY fp.end_date DESC) as rn
    FROM financial_snapshots fs
    JOIN fiscal_periods fp ON fs.fiscal_period_id = fp.id
    JOIN company_industries ci ON fs.unified_company_id = ci.unified_company_id AND ci.is_primary = true
    JOIN industry_classifications ic ON ci.classification_id = ic.id
    JOIN market_listings ml ON fs.market_listing_id = ml.id
    WHERE fp.period_type = 'FY'
)
SELECT classification_id, industry_name, taxonomy, market,
    COUNT(*) as sample_size,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY roe) as p25_roe,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY roe) as median_roe,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY roe) as p75_roe,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY gross_margin) as median_gross_margin,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY net_margin) as median_net_margin,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY revenue_growth_yoy) as median_revenue_growth,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY debt_to_equity) as median_debt_to_equity,
    SUM(revenue) as total_industry_revenue,
    NOW() as calculated_at
FROM latest_snapshots WHERE rn = 1
GROUP BY classification_id, industry_name, taxonomy, market;
