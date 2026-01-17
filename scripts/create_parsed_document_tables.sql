-- 创建 ParsedDocument、Image 和 ImageAnnotation 表的 SQL 脚本
-- 执行方式: psql -U postgres -d finnet -f scripts/create_parsed_document_tables.sql

-- ==================== ParsedDocument 表 ====================
CREATE TABLE IF NOT EXISTS parsed_documents (
    id SERIAL PRIMARY KEY,
    
    -- 关联字段
    document_id INTEGER NOT NULL,
    parse_task_id INTEGER NOT NULL,
    
    -- 路径信息
    content_json_path VARCHAR(500) NOT NULL,
    markdown_path VARCHAR(500),
    image_folder_path VARCHAR(500),
    
    -- 哈希值字段
    content_json_hash VARCHAR(64) NOT NULL,
    markdown_hash VARCHAR(64),
    source_document_hash VARCHAR(64) NOT NULL,
    
    -- 解析结果统计
    text_length INTEGER DEFAULT 0,
    tables_count INTEGER DEFAULT 0,
    images_count INTEGER DEFAULT 0,
    pages_count INTEGER DEFAULT 0,
    
    -- 解析器信息
    parser_type VARCHAR(50) NOT NULL,
    parser_version VARCHAR(100),
    
    -- 解析质量指标
    parsing_quality_score FLOAT,
    has_tables BOOLEAN DEFAULT FALSE,
    has_images BOOLEAN DEFAULT FALSE,
    
    -- 时间戳
    parsed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    
    -- 状态
    status VARCHAR(50) DEFAULT 'active',
    
    -- 外键约束
    CONSTRAINT fk_parsed_document_document 
        FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    CONSTRAINT fk_parsed_document_parse_task 
        FOREIGN KEY (parse_task_id) REFERENCES parse_tasks(id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_document_parsed ON parsed_documents(document_id, parsed_at);
CREATE INDEX IF NOT EXISTS idx_parse_task ON parsed_documents(parse_task_id);
CREATE INDEX IF NOT EXISTS idx_source_hash ON parsed_documents(source_document_hash);
CREATE INDEX IF NOT EXISTS idx_json_hash ON parsed_documents(content_json_hash);
CREATE INDEX IF NOT EXISTS idx_text_length ON parsed_documents(text_length);
CREATE INDEX IF NOT EXISTS idx_document_id ON parsed_documents(document_id);

-- ==================== Image 表 ====================
CREATE TABLE IF NOT EXISTS images (
    id SERIAL PRIMARY KEY,
    
    -- 关联字段
    parsed_document_id INTEGER NOT NULL,
    document_id INTEGER NOT NULL,
    
    -- 图片基本信息
    image_index INTEGER NOT NULL,
    filename VARCHAR(200) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    
    -- 图片元数据
    page_number INTEGER NOT NULL,
    bbox JSONB,
    description VARCHAR(500),
    
    -- 图片属性
    width INTEGER,
    height INTEGER,
    file_size BIGINT,
    file_hash VARCHAR(64),
    
    -- 时间戳
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    extracted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- 外键约束
    CONSTRAINT fk_image_parsed_document 
        FOREIGN KEY (parsed_document_id) REFERENCES parsed_documents(id) ON DELETE CASCADE,
    CONSTRAINT fk_image_document 
        FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_parsed_doc_image ON images(parsed_document_id, image_index);
CREATE INDEX IF NOT EXISTS idx_image_document_id ON images(document_id);
CREATE INDEX IF NOT EXISTS idx_image_file_hash ON images(file_hash);

-- ==================== ImageAnnotation 表 ====================
CREATE TABLE IF NOT EXISTS image_annotations (
    id SERIAL PRIMARY KEY,
    
    -- 关联字段
    image_id INTEGER NOT NULL,
    annotation_version INTEGER NOT NULL DEFAULT 1,
    
    -- 标注信息
    category VARCHAR(100) NOT NULL,
    subcategory VARCHAR(100),
    confidence FLOAT,
    
    -- 标注者信息
    annotator_type VARCHAR(50) NOT NULL,
    annotator_id VARCHAR(100),
    annotator_name VARCHAR(200),
    
    -- 标注状态
    status VARCHAR(50) DEFAULT 'pending',
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP,
    
    -- 标注内容
    annotation_text TEXT,
    tags JSONB,
    extra_metadata JSONB,
    
    -- 时间戳
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    
    -- 外键约束
    CONSTRAINT fk_annotation_image 
        FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
    
    -- 唯一约束
    CONSTRAINT uq_image_version UNIQUE (image_id, annotation_version)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_image_version ON image_annotations(image_id, annotation_version);
CREATE INDEX IF NOT EXISTS idx_annotation_category ON image_annotations(category);
CREATE INDEX IF NOT EXISTS idx_annotation_status ON image_annotations(status);
CREATE INDEX IF NOT EXISTS idx_annotation_annotator ON image_annotations(annotator_type, annotator_id);

-- 添加注释
COMMENT ON TABLE parsed_documents IS 'Silver 层解析文档表，存储解析后的文档信息和路径';
COMMENT ON TABLE images IS '图片元数据表，存储从 PDF 提取的图片信息';
COMMENT ON TABLE image_annotations IS '图片标注表，存储图片的分类标注信息，支持版本管理';
