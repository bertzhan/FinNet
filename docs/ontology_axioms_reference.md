# Ontology 公理规则参考

本文档汇总 Ontology 中定义的推理规则、推导规则和一致性约束，包含 condition/action 描述及 SQL 实现。

---

## 推理规则 (inference)

### indirect_control（间接控制推理）

| 字段 | 内容 |
|------|------|
| 条件 | Person X 控制 Company A，且 A 持股 B 超过50% |
| 动作 | 推导 Person X 间接控制 Company B |
| 依赖 | company_shareholders, company_relationships 表（Phase 4 实现） |

```sql
WITH direct_control AS (
    SELECT controller_id, company_id FROM company_relationships
    WHERE relation_type = 'CONTROLS'
),
major_holdings AS (
    SELECT holder_id, company_id FROM company_shareholders
    WHERE share_pct > 50
)
SELECT dc.controller_id, mh.company_id, 'indirect' as control_type
FROM direct_control dc
JOIN major_holdings mh ON dc.company_id = mh.holder_id
WHERE NOT EXISTS (
    SELECT 1 FROM company_relationships cr
    WHERE cr.controller_id = dc.controller_id
    AND cr.company_id = mh.company_id
    AND cr.relation_type = 'CONTROLS'
)
```

---

### related_party_shared_officer（共同董事关联方）

| 字段 | 内容 |
|------|------|
| 条件 | 同一人在 A 和 B 任职 |
| 动作 | A 和 B 互为关联方 |
| 依赖 | company_officers 表（Phase 4 实现） |

```sql
SELECT DISTINCT co1.unified_company_id as company_a,
       co2.unified_company_id as company_b,
       co1.person_name, 'shared_officer' as basis
FROM company_officers co1
JOIN company_officers co2
    ON co1.person_name = co2.person_name
    AND co1.unified_company_id < co2.unified_company_id
```

---

## 推导规则 (derivation)

### peer_derivation（同业关系推导）

| 字段 | 内容 |
|------|------|
| 条件 | Company A 和 Company B 的主行业相同 |
| 动作 | 互为同业，物化为 v_peer_companies 视图 |

```sql
CREATE OR REPLACE VIEW v_peer_companies AS
SELECT ci1.unified_company_id as company_a,
       ci2.unified_company_id as company_b,
       ci1.classification_id as shared_industry,
       'industry_peer' as peer_type
FROM company_industries ci1
JOIN company_industries ci2
    ON ci1.classification_id = ci2.classification_id
    AND ci1.is_primary = true AND ci2.is_primary = true
    AND ci1.unified_company_id < ci2.unified_company_id
```

---

### industry_mapping_propagation（行业归属映射传递）

| 字段 | 内容 |
|------|------|
| 条件 | Company X 属于申万行业 Y，且 Y 映射到 GICS 行业 Z |
| 动作 | Company X 也属于 GICS 行业 Z（来源标记为 derived） |

```sql
SELECT ci.unified_company_id, im.target_id as classification_id,
       false as is_primary, 'derived' as source
FROM company_industries ci
JOIN industry_mappings im ON ci.classification_id = im.source_id
WHERE ci.is_primary = true
AND NOT EXISTS (
    SELECT 1 FROM company_industries ci2
    WHERE ci2.unified_company_id = ci.unified_company_id
    AND ci2.classification_id = im.target_id
)
```

---

## 一致性约束 (constraint)

### balance_sheet_equation（资产负债表恒等式）

| 字段 | 内容 |
|------|------|
| 条件 | total_assets, total_liabilities, total_equity 均非空 |
| 动作 | 检测 \|资产 - 负债 - 权益\| / 资产 > 0.5% 的记录，标记为数据质量问题 |

```sql
SELECT id, unified_company_id, fiscal_period_id,
    total_assets, total_liabilities, total_equity,
    ABS(total_assets - total_liabilities - total_equity)
      / NULLIF(total_assets, 0) as error_pct
FROM financial_snapshots
WHERE total_assets IS NOT NULL AND total_liabilities IS NOT NULL
  AND total_equity IS NOT NULL
  AND ABS(total_assets - total_liabilities - total_equity)
      / NULLIF(total_assets, 0) > 0.005
```

---

### shareholding_sum_limit（持股比例合计约束）

| 字段 | 内容 |
|------|------|
| 条件 | 单公司单日持股记录 |
| 动作 | 检测合计 > 100.5% 的情况 |
| 依赖 | company_shareholders 表（Phase 4 实现） |

```sql
SELECT company_id, as_of_date, SUM(share_pct) as total_pct
FROM company_shareholders
GROUP BY company_id, as_of_date
HAVING SUM(share_pct) > 100.5
```

---

### valuation_anomaly_flag（估值异常标记）

| 字段 | 内容 |
|------|------|
| 条件 | PE 为负，或偏离行业中位数 5x，或低于中位数 10% |
| 动作 | 标记 anomaly_type: negative_pe / extreme_premium / extreme_discount |

```sql
SELECT vs.unified_company_id, vs.pe_ttm, b.median_pe,
    CASE
        WHEN vs.pe_ttm < 0 THEN 'negative_pe'
        WHEN vs.pe_ttm > b.median_pe * 5 THEN 'extreme_premium'
        WHEN vs.pe_ttm < b.median_pe * 0.1 THEN 'extreme_discount'
    END as anomaly_type
FROM valuation_snapshots vs
JOIN company_industries ci ON vs.unified_company_id = ci.unified_company_id
    AND ci.is_primary = true
JOIN mv_industry_benchmark b ON ci.classification_id = b.classification_id
    AND vs.market_listing_id IN (
        SELECT id FROM market_listings WHERE market = b.market
    )
WHERE vs.pe_ttm < 0
   OR vs.pe_ttm > b.median_pe * 5
   OR vs.pe_ttm < b.median_pe * 0.1
```
