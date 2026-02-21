-- 迁移：hk_listed_companies 主键从 code 改为 org_id
-- 日期：2025-02-21
-- 描述：org_id 为主键，code 改为可空并添加唯一索引
-- 注意：org_id 为空的记录用 code 的数值填充（港股 code 为 5 位数字）

BEGIN;

-- 1. org_id 为空的记录用 code 的整数值填充（如 00001 -> 1）
UPDATE hk_listed_companies SET org_id = code::integer WHERE org_id IS NULL;

-- 2. 将 org_id 设为 NOT NULL
ALTER TABLE hk_listed_companies ALTER COLUMN org_id SET NOT NULL;

-- 3. 删除原主键约束（必须先删除才能修改 code）
ALTER TABLE hk_listed_companies DROP CONSTRAINT IF EXISTS hk_listed_companies_pkey;

-- 4. 将 code 改为可空
ALTER TABLE hk_listed_companies ALTER COLUMN code DROP NOT NULL;

-- 5. 添加 org_id 为主键
ALTER TABLE hk_listed_companies ADD PRIMARY KEY (org_id);

-- 6. 为 code 添加唯一索引（用于按 code 查询）
CREATE UNIQUE INDEX IF NOT EXISTS idx_hk_listed_companies_code ON hk_listed_companies(code) WHERE code IS NOT NULL;

COMMIT;
