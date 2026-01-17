# Document 表 extra_metadata 字段说明

## 概述

`extra_metadata` 是 `documents` 表中的一个 JSON 字段，用于存储文档的额外元数据信息。这些信息主要来自爬虫过程中收集的文档相关信息。

## 字段类型

- **类型**: JSON (PostgreSQL JSONB)
- **默认值**: `{}` (空字典)
- **可空**: 否（但可以为空字典）

## 存储的数据内容

### 1. IPO 招股说明书 (IPO Prospectus)

IPO 文档的 `extra_metadata` 包含以下字段：

```json
{
  "publication_date": "01012023",                    // 发布日期（DDMMYYYY 格式）
  "publication_year": "2023",                       // 发布年份（YYYY 格式）
  "publication_date_iso": "2023-01-01T00:00:00",     // 发布日期（ISO 8601 格式）
  "source_url": "https://www.cninfo.com.cn/..."     // 文档来源URL
}
```

**数据来源**:
- `publication_date`: 从公告时间解析，格式为 DDMMYYYY（如 "01012023" 表示 2023年1月1日）
- `publication_year`: 从公告时间解析，格式为 YYYY
- `publication_date_iso`: 从公告时间解析，ISO 8601 格式（如 "2023-01-01T00:00:00"）
- `source_url`: 文档的原始下载URL

**代码位置**:
- 保存位置: `src/ingestion/a_share/processor/ipo_processor.py` (第273-280行)
- 读取位置: `src/ingestion/a_share/crawlers/ipo_crawler.py` (第117-122行)

### 2. 定期报告 (Quarterly/Annual/Interim Reports)

定期报告的 `extra_metadata` 包含以下字段：

```json
{
  "source_url": "https://www.cninfo.com.cn/...",    // 文档来源URL
  "publication_date_iso": "2023-10-01T00:00:00",    // 发布日期（ISO 8601 格式）
  "stock_code": "000001",                           // 股票代码（从MinIO metadata）
  "year": "2023",                                    // 年份（从MinIO metadata）
  "quarter": "3"                                     // 季度（从MinIO metadata，如果有）
}
```

**数据来源**:
- `source_url`: 文档的原始下载URL
- `publication_date_iso`: 从公告时间解析，ISO 8601 格式
- `stock_code`, `year`, `quarter`: 从 MinIO 上传时的 metadata 中获取

**代码位置**:
- 保存位置: `src/ingestion/a_share/processor/report_processor.py` (第252-258行)
- 读取位置: `src/ingestion/a_share/crawlers/base_cninfo_crawler.py` (第93-107行)

## 数据流程

### 1. Processor 阶段

Processor 下载文档后，会将元数据保存到 `.meta.json` 文件中：

```python
# IPO Processor
metadata_info = {
    'publication_date': pub_date,          # DDMMYYYY格式
    'publication_year': pub_year,          # YYYY格式
    'publication_date_iso': pub_date_iso,  # ISO格式
    'source_url': doc_url                 # 文档URL
}
save_json(metadata_file, metadata_info)

# Report Processor
metadata_info = {
    'source_url': pdf_url,                 # 文档URL
    'publication_date_iso': pub_date_iso  # ISO格式日期
}
save_json(metadata_file, metadata_info)
```

### 2. Crawler 阶段

Crawler 读取 `.meta.json` 文件，将数据添加到 `task.metadata`：

```python
# 从metadata文件读取
metadata_info = load_json(metadata_file, {})
for key, value in metadata_info.items():
    if key not in task.metadata:
        task.metadata[key] = value
```

### 3. 数据库保存阶段

`create_document` 函数将 `task.metadata` 保存到 `extra_metadata` 字段：

```python
doc = Document(
    # ... 其他字段 ...
    extra_metadata=metadata or {}  # task.metadata 直接保存
)
```

## 字段提取逻辑

虽然 `extra_metadata` 中存储了完整的数据，但某些字段会被提取到独立的数据库字段中：

### source_url

- 如果 `extra_metadata` 中包含 `source_url`、`doc_url` 或 `pdf_url`，会被提取到 `source_url` 字段
- 代码位置: `src/storage/metadata/crud.py` (第72-74行)

### publish_date

- 如果 `extra_metadata` 中包含 `publication_date_iso`、`pub_date_iso` 或 `publish_date_iso`，会被解析并提取到 `publish_date` 字段
- 代码位置: `src/storage/metadata/crud.py` (第76-92行)

## 使用示例

### 查询包含特定URL的文档

```python
from src.storage.metadata.models import Document
from sqlalchemy import cast, String

# 方法1: 通过source_url字段查询（推荐）
docs = session.query(Document).filter(
    Document.source_url == "https://www.cninfo.com.cn/..."
).all()

# 方法2: 通过extra_metadata JSON字段查询
docs = session.query(Document).filter(
    Document.extra_metadata['source_url'].astext == "https://www.cninfo.com.cn/..."
).all()
```

### 查询特定发布日期的文档

```python
from datetime import datetime

# 方法1: 通过publish_date字段查询（推荐）
start_date = datetime(2023, 1, 1)
end_date = datetime(2023, 12, 31)
docs = session.query(Document).filter(
    Document.publish_date >= start_date,
    Document.publish_date <= end_date
).all()

# 方法2: 通过extra_metadata JSON字段查询
docs = session.query(Document).filter(
    Document.extra_metadata['publication_date_iso'].astext.like('2023-%')
).all()
```

### 访问 extra_metadata 中的数据

```python
doc = session.query(Document).filter(Document.id == 1).first()

# 访问JSON字段
if doc.extra_metadata:
    publication_date = doc.extra_metadata.get('publication_date')
    publication_year = doc.extra_metadata.get('publication_year')
    source_url = doc.extra_metadata.get('source_url')
```

## 注意事项

1. **字段提取**: `source_url` 和 `publish_date` 已经从 `extra_metadata` 中提取到独立字段，建议优先使用独立字段进行查询和索引

2. **向后兼容**: 旧数据可能没有 `source_url` 或 `publish_date` 字段，这些信息可能只存在于 `extra_metadata` 中

3. **数据格式**: 
   - `publication_date`: DDMMYYYY 格式字符串（如 "01012023"）
   - `publication_date_iso`: ISO 8601 格式字符串（如 "2023-01-01T00:00:00"）
   - `publication_year`: YYYY 格式字符串（如 "2023"）

4. **数据完整性**: 不是所有文档都有完整的元数据，某些字段可能为空或缺失

## 相关文档

- [POSTGRESQL_DATA.md](./POSTGRESQL_DATA.md) - PostgreSQL 数据存储说明
- [DOCUMENT_URL_FEATURE.md](./DOCUMENT_URL_FEATURE.md) - 文档URL保存功能说明
