-- FinNet MVP 数据库初始化脚本
-- 创建公告元数据表

CREATE TABLE IF NOT EXISTS announcements (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL,
    title TEXT NOT NULL,
    publish_date DATE NOT NULL,
    pdf_url TEXT,
    file_path TEXT,
    file_size BIGINT,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, parsed, failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_announcements_stock_code ON announcements(stock_code);
CREATE INDEX IF NOT EXISTS idx_announcements_publish_date ON announcements(publish_date);
CREATE INDEX IF NOT EXISTS idx_announcements_status ON announcements(status);

-- 创建文本数据表（解析后的文本）
CREATE TABLE IF NOT EXISTS parsed_texts (
    id SERIAL PRIMARY KEY,
    announcement_id INTEGER REFERENCES announcements(id),
    text_content TEXT NOT NULL,
    chunk_index INTEGER DEFAULT 0,  -- 分块索引
    chunk_size INTEGER,  -- 字符数
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_parsed_texts_announcement_id ON parsed_texts(announcement_id);

-- 创建向量元数据表（与Milvus关联）
CREATE TABLE IF NOT EXISTS vector_metadata (
    id SERIAL PRIMARY KEY,
    milvus_id BIGINT UNIQUE,  -- Milvus中的向量ID
    parsed_text_id INTEGER REFERENCES parsed_texts(id),
    stock_code VARCHAR(10),
    publish_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vector_metadata_milvus_id ON vector_metadata(milvus_id);
CREATE INDEX IF NOT EXISTS idx_vector_metadata_stock_code ON vector_metadata(stock_code);

-- 创建更新时间触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为announcements表添加更新时间触发器
CREATE TRIGGER update_announcements_updated_at BEFORE UPDATE ON announcements
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
