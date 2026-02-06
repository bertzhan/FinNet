-- 为 hk_listed_companies 表添加证券基本信息字段
-- 数据来源：akshare.stock_hk_security_profile_em

-- 财务信息字段
ALTER TABLE hk_listed_companies 
ADD COLUMN IF NOT EXISTS listed_date BIGINT,  -- 上市日期（时间戳）
ADD COLUMN IF NOT EXISTS fiscal_year_end VARCHAR(20);  -- 年结日（如：12-31）

-- 证券信息字段
ALTER TABLE hk_listed_companies 
ADD COLUMN IF NOT EXISTS security_type VARCHAR(50),  -- 证券类型（如：非H股）
ADD COLUMN IF NOT EXISTS issue_price FLOAT,  -- 发行价
ADD COLUMN IF NOT EXISTS issue_amount BIGINT,  -- 发行量(股)
ADD COLUMN IF NOT EXISTS lot_size INTEGER,  -- 每手股数
ADD COLUMN IF NOT EXISTS par_value VARCHAR(50),  -- 每股面值（如：1 HKD）
ADD COLUMN IF NOT EXISTS isin VARCHAR(50),  -- ISIN（国际证券识别编码）
ADD COLUMN IF NOT EXISTS is_sh_hk_connect BOOLEAN,  -- 是否沪港通标的
ADD COLUMN IF NOT EXISTS is_sz_hk_connect BOOLEAN;  -- 是否深港通标的

-- 添加索引（如果需要）
-- CREATE INDEX IF NOT EXISTS idx_hk_isin ON hk_listed_companies(isin);
-- CREATE INDEX IF NOT EXISTS idx_hk_sh_hk_connect ON hk_listed_companies(is_sh_hk_connect);
-- CREATE INDEX IF NOT EXISTS idx_hk_sz_hk_connect ON hk_listed_companies(is_sz_hk_connect);

-- 确认迁移成功
SELECT 'hk_listed_companies 表添加证券基本信息字段成功' AS status;
