-- 迁移：将 hk_listed_companies 的 established_date、listed_date 从 BIGINT（毫秒时间戳）改为 DATE
-- 日期：2025-02-21
-- 描述：存储为实际日期值（YYYY-MM-DD），便于查询和展示

BEGIN;

-- 1. established_date: BIGINT(ms) -> DATE
ALTER TABLE hk_listed_companies
  ALTER COLUMN established_date TYPE DATE
  USING (
    CASE WHEN established_date IS NOT NULL
    THEN to_timestamp(established_date / 1000.0)::date
    ELSE NULL END
  );

-- 2. listed_date: BIGINT(ms) -> DATE
ALTER TABLE hk_listed_companies
  ALTER COLUMN listed_date TYPE DATE
  USING (
    CASE WHEN listed_date IS NOT NULL
    THEN to_timestamp(listed_date / 1000.0)::date
    ELSE NULL END
  );

-- 3. 更新注释
COMMENT ON COLUMN hk_listed_companies.established_date IS '成立日期';
COMMENT ON COLUMN hk_listed_companies.listed_date IS '上市日期';

COMMIT;
