-- 修复：移除 us_listed_companies.cik 的 UNIQUE 约束
-- 日期：2025-02-15
-- 描述：多个证券（stocks, warrants, units）可能共享同一个 CIK
--       例如：DNMX, DNMXU, DNMXW 都属于同一家公司，共享 CIK
--
-- 原因分析：
--   CIK (Central Index Key) 是公司级别的标识符
--   同一家公司可能发行多种证券：
--   - 普通股 (Common Stock): DNMX
--   - 单位 (Units): DNMXU
--   - 认股权证 (Warrants): DNMXW
--   所有这些证券共享同一个 CIK，但有不同的 Ticker

-- 开始事务
BEGIN;

-- 检查并删除 UNIQUE 约束
DO $$
DECLARE
    constraint_name TEXT;
BEGIN
    -- 查找 cik 字段的 UNIQUE 约束名称
    SELECT tc.constraint_name INTO constraint_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.constraint_column_usage ccu
        ON tc.constraint_name = ccu.constraint_name
        AND tc.table_schema = ccu.table_schema
    WHERE tc.table_name = 'us_listed_companies'
        AND ccu.column_name = 'cik'
        AND tc.constraint_type = 'UNIQUE';

    -- 如果找到约束，删除它
    IF constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE us_listed_companies DROP CONSTRAINT %I', constraint_name);
        RAISE NOTICE '已删除 UNIQUE 约束: %', constraint_name;
    ELSE
        RAISE NOTICE 'cik 字段没有 UNIQUE 约束，无需删除';
    END IF;

    -- 确保索引仍然存在（用于查询性能）
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_us_cik') THEN
        CREATE INDEX idx_us_cik ON us_listed_companies(cik);
        RAISE NOTICE '已创建索引: idx_us_cik';
    ELSE
        RAISE NOTICE '索引 idx_us_cik 已存在';
    END IF;
END $$;

-- 提交事务
COMMIT;

-- 验证：显示共享 CIK 的证券
SELECT
    cik,
    COUNT(*) as ticker_count,
    STRING_AGG(code, ', ' ORDER BY code) as tickers
FROM us_listed_companies
GROUP BY cik
HAVING COUNT(*) > 1
ORDER BY ticker_count DESC
LIMIT 10;

RAISE NOTICE '上述查询显示了共享 CIK 的证券（这是正常的）';
