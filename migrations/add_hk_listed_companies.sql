-- 港股上市公司表迁移脚本
-- 创建 hk_listed_companies 表

-- 1. 创建表
CREATE TABLE IF NOT EXISTS hk_listed_companies (
    -- 基本信息
    code VARCHAR(10) PRIMARY KEY,              -- 股票代码（如：00001），5位数字
    name VARCHAR(200) NOT NULL,                -- 公司名称（中文繁体）
    name_en VARCHAR(200),                      -- 公司名称（英文）
    
    -- 披露易信息
    stock_id INTEGER,                          -- 披露易 stockId（用于查询报告）
    
    -- 分类信息
    board VARCHAR(50),                         -- 板块：主板/创业板
    category VARCHAR(50),                      -- 分类（如：股本）
    sub_category VARCHAR(100),                 -- 次分类（如：股本證券(主板)）
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 2. 创建索引
CREATE INDEX IF NOT EXISTS idx_hk_stock_id ON hk_listed_companies(stock_id);
CREATE INDEX IF NOT EXISTS idx_hk_board ON hk_listed_companies(board);

-- 3. 添加表注释
COMMENT ON TABLE hk_listed_companies IS '港股上市公司表';
COMMENT ON COLUMN hk_listed_companies.code IS '股票代码（5位数字，如：00001）';
COMMENT ON COLUMN hk_listed_companies.name IS '公司名称（中文繁体）';
COMMENT ON COLUMN hk_listed_companies.name_en IS '公司名称（英文）';
COMMENT ON COLUMN hk_listed_companies.stock_id IS '披露易 stockId（用于查询报告）';
COMMENT ON COLUMN hk_listed_companies.board IS '板块（主板/创业板）';
COMMENT ON COLUMN hk_listed_companies.category IS '分类';
COMMENT ON COLUMN hk_listed_companies.sub_category IS '次分类';

-- 4. 创建更新时间触发器
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

-- 5. 确认迁移成功
SELECT 'hk_listed_companies 表创建成功' AS status;
