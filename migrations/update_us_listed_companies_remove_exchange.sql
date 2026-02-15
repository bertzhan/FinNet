-- 迁移：从 us_listed_companies 表删除 exchange 字段
-- 日期：2025-02-15
-- 描述：移除 exchange 字段，因为 SEC API 不提供交易所信息

-- 开始事务
BEGIN;

-- 检查表是否存在
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'us_listed_companies') THEN
        RAISE NOTICE '表 us_listed_companies 存在，开始迁移...';

        -- 删除旧的索引（如果存在）
        IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_us_exchange') THEN
            DROP INDEX idx_us_exchange;
            RAISE NOTICE '已删除索引: idx_us_exchange';
        END IF;

        -- 删除 exchange 字段（如果存在）
        IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'us_listed_companies'
            AND column_name = 'exchange'
        ) THEN
            ALTER TABLE us_listed_companies DROP COLUMN exchange;
            RAISE NOTICE '已删除字段: exchange';
        END IF;

        -- 添加新的索引（如果不存在）
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_us_active') THEN
            CREATE INDEX idx_us_active ON us_listed_companies(is_active);
            RAISE NOTICE '已创建索引: idx_us_active';
        END IF;

        RAISE NOTICE '迁移完成！';
    ELSE
        RAISE NOTICE '表 us_listed_companies 不存在，无需迁移。';
        RAISE NOTICE '请先执行 migrations/add_us_listed_companies.sql 创建表。';
    END IF;
END $$;

-- 提交事务
COMMIT;

-- 验证结果
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'us_listed_companies'
ORDER BY ordinal_position;

-- 显示索引
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'us_listed_companies'
ORDER BY indexname;
