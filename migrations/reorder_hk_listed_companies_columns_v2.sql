-- 迁移：重排 hk_listed_companies 表列顺序，与模型定义一致
-- 日期：2026-02-21
-- 描述：按 org_id, code, name, org_name_cn, org_name_en, category, org_cn_introduction,
--       established_date, listed_date, staff_num, fiscal_year_end, industry,
--       is_sh_hk_connect, is_sz_hk_connect, created_at, updated_at 顺序排列
-- 说明：PostgreSQL 不支持 ALTER COLUMN ... AFTER，需通过重建表实现

BEGIN;

-- 0. 确保 is_sh_hk_connect、is_sz_hk_connect 存在（若 add_hk_connect_fields 未执行）
ALTER TABLE hk_listed_companies ADD COLUMN IF NOT EXISTS is_sh_hk_connect BOOLEAN;
ALTER TABLE hk_listed_companies ADD COLUMN IF NOT EXISTS is_sz_hk_connect BOOLEAN;

-- 1. 创建新表（目标列顺序）
CREATE TABLE hk_listed_companies_new (
    org_id INTEGER PRIMARY KEY,
    code VARCHAR(10),
    name VARCHAR(200) NOT NULL,
    org_name_cn VARCHAR(200),
    org_name_en VARCHAR(200),
    category VARCHAR(100),
    org_cn_introduction TEXT,
    established_date DATE,
    listed_date DATE,
    staff_num INTEGER,
    fiscal_year_end VARCHAR(20),
    industry VARCHAR(100),
    is_sh_hk_connect BOOLEAN,
    is_sz_hk_connect BOOLEAN,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 2. 复制数据
INSERT INTO hk_listed_companies_new (
    org_id, code, name, org_name_cn, org_name_en, category,
    org_cn_introduction, established_date, listed_date, staff_num, fiscal_year_end,
    industry, is_sh_hk_connect, is_sz_hk_connect, created_at, updated_at
)
SELECT
    org_id, code, name, org_name_cn, org_name_en, category,
    org_cn_introduction, established_date, listed_date, staff_num, fiscal_year_end,
    industry,
    is_sh_hk_connect,
    is_sz_hk_connect,
    created_at, updated_at
FROM hk_listed_companies;

-- 3. 删除原表
DROP TABLE hk_listed_companies;

-- 4. 重命名新表
ALTER TABLE hk_listed_companies_new RENAME TO hk_listed_companies;

-- 5. 重建 code 唯一索引
CREATE UNIQUE INDEX IF NOT EXISTS idx_hk_listed_companies_code ON hk_listed_companies(code) WHERE code IS NOT NULL;

-- 6. 重建 updated_at 触发器
CREATE OR REPLACE FUNCTION update_hk_listed_companies_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_hk_listed_companies_updated_at ON hk_listed_companies;

CREATE TRIGGER trigger_update_hk_listed_companies_updated_at
    BEFORE UPDATE ON hk_listed_companies
    FOR EACH ROW
    EXECUTE FUNCTION update_hk_listed_companies_updated_at();

-- 7. 添加注释
COMMENT ON TABLE hk_listed_companies IS '港股上市公司表（数据来源：香港交易所 + 披露易 + akshare）';
COMMENT ON COLUMN hk_listed_companies.org_id IS '披露易 orgId（主键，用于查询报告）';
COMMENT ON COLUMN hk_listed_companies.code IS '股票代码（5位数字，如：00001）';
COMMENT ON COLUMN hk_listed_companies.name IS '公司名称（简体中文）';
COMMENT ON COLUMN hk_listed_companies.org_name_cn IS '公司全称（中文）';
COMMENT ON COLUMN hk_listed_companies.org_name_en IS '公司全称（英文）';
COMMENT ON COLUMN hk_listed_companies.category IS '板块分类（从次分类提取，如：主板、創業板）';
COMMENT ON COLUMN hk_listed_companies.org_cn_introduction IS '公司简介';
COMMENT ON COLUMN hk_listed_companies.established_date IS '成立日期';
COMMENT ON COLUMN hk_listed_companies.listed_date IS '上市日期';
COMMENT ON COLUMN hk_listed_companies.staff_num IS '员工人数';
COMMENT ON COLUMN hk_listed_companies.fiscal_year_end IS '年结日（如：12-31）';
COMMENT ON COLUMN hk_listed_companies.industry IS '所属行业';
COMMENT ON COLUMN hk_listed_companies.is_sh_hk_connect IS '是否沪港通标的';
COMMENT ON COLUMN hk_listed_companies.is_sz_hk_connect IS '是否深港通标的';

COMMIT;
