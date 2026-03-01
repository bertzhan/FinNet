-- Ontology 元数据层：概念、关系、公理表定义及初始数据
-- 依赖：无

CREATE TABLE ontology_concepts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    name_cn VARCHAR(100),
    parent_id UUID REFERENCES ontology_concepts(id),
    description TEXT,
    mapped_table VARCHAR(100),          -- 映射到哪张PG数据表
    mapped_filter JSONB,                -- 过滤条件
    properties_schema JSONB,            -- 该概念特有的属性定义
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ontology_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    name_cn VARCHAR(100),
    domain_concept_id UUID REFERENCES ontology_concepts(id),
    range_concept_id UUID REFERENCES ontology_concepts(id),
    cardinality VARCHAR(10),            -- '1:1','1:N','M:N'
    is_transitive BOOLEAN DEFAULT FALSE,
    is_symmetric BOOLEAN DEFAULT FALSE,
    inverse_relation_id UUID REFERENCES ontology_relations(id),
    properties_schema JSONB,            -- 关系属性定义
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ontology_axioms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    name_cn VARCHAR(100),
    axiom_type VARCHAR(20) NOT NULL,     -- 'inference' / 'constraint' / 'derivation'
    priority INTEGER DEFAULT 0,
    condition_description TEXT,           -- 人类可读的规则条件
    action_description TEXT,             -- 人类可读的规则动作
    sql_implementation TEXT,             -- SQL 实现（可执行）
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
