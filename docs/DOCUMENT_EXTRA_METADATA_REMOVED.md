# Document 表 extra_metadata 字段删除说明

## 变更说明

`documents` 表中的 `extra_metadata` 字段已被删除。相关数据已迁移到独立字段中。

## 迁移内容

### 原 extra_metadata 中的数据

原 `extra_metadata` 字段存储的数据包括：

**IPO 招股说明书**:
- `publication_date`: 发布日期（DDMMYYYY格式）
- `publication_year`: 发布年份（YYYY格式）
- `publication_date_iso`: 发布日期（ISO格式）
- `source_url`: 文档来源URL

**定期报告**:
- `source_url`: 文档来源URL
- `publication_date_iso`: 发布日期（ISO格式）
- `stock_code`: 股票代码
- `year`: 年份
- `quarter`: 季度

### 迁移后的字段

重要数据已迁移到独立字段：

1. **source_url** (VARCHAR(1000))
   - 存储文档的原始来源URL
   - 已创建索引，支持快速查询

2. **publish_date** (TIMESTAMP)
   - 存储文档的发布日期
   - 已创建索引，支持日期范围查询

## 代码变更

### 1. 模型变更

**文件**: `src/storage/metadata/models.py`

- 删除了 `extra_metadata = Column(JSON, default={})` 字段

### 2. CRUD 变更

**文件**: `src/storage/metadata/crud.py`

- `create_document` 函数不再保存 `extra_metadata`
- `metadata` 参数仍然保留，用于提取 `source_url` 和 `publish_date`，但不会保存到数据库

### 3. 数据库迁移

**迁移脚本**: `scripts/remove_document_extra_metadata.py`

执行方式：
```bash
python scripts/remove_document_extra_metadata.py --yes
```

## 影响分析

### 已迁移的功能

✅ **URL 查询**: 使用 `source_url` 字段
✅ **日期查询**: 使用 `publish_date` 字段
✅ **数据提取**: `metadata` 参数仍可用于提取数据到独立字段

### 不再支持的功能

❌ **存储任意元数据**: 不再支持在 `extra_metadata` 中存储任意JSON数据
❌ **向后兼容**: 旧代码中访问 `doc.extra_metadata` 会报错

## 迁移建议

如果您的代码中有使用 `extra_metadata` 的地方，请按以下方式迁移：

### 1. 访问 source_url

**之前**:
```python
source_url = doc.extra_metadata.get('source_url')
```

**现在**:
```python
source_url = doc.source_url
```

### 2. 访问 publish_date

**之前**:
```python
publish_date_str = doc.extra_metadata.get('publication_date_iso')
publish_date = datetime.fromisoformat(publish_date_str) if publish_date_str else None
```

**现在**:
```python
publish_date = doc.publish_date
```

### 3. 查询文档

**之前**:
```python
# 通过extra_metadata查询
docs = session.query(Document).filter(
    Document.extra_metadata['source_url'].astext == url
).all()
```

**现在**:
```python
# 通过source_url字段查询（更快，有索引）
docs = session.query(Document).filter(
    Document.source_url == url
).all()
```

## 相关文档

- [POSTGRESQL_DATA.md](./POSTGRESQL_DATA.md) - PostgreSQL 数据存储说明（已更新）
- [DOCUMENT_URL_FEATURE.md](./DOCUMENT_URL_FEATURE.md) - 文档URL保存功能说明
