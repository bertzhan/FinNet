# 文档URL保存功能

## 功能说明

爬虫在爬取文档时，会自动将文档的原始URL保存到数据库的 `documents` 表的 `source_url` 字段中。

## 数据库迁移

在开始使用此功能前，需要先执行数据库迁移，添加 `source_url` 字段。

### 方式1: 使用Python脚本（推荐）

```bash
python scripts/add_document_source_url.py
```

### 方式2: 使用SQL脚本

```bash
psql -U postgres -d finnet -f scripts/add_document_source_url.sql
```

## 功能特性

1. **自动提取URL**: 
   - 如果直接传入 `source_url` 参数，会直接使用
   - 如果未传入，会从 `metadata` 中提取（支持 `source_url`、`doc_url`、`pdf_url` 字段）

2. **支持多种URL格式**:
   - IPO招股说明书：HTML或PDF的完整URL
   - 定期报告：PDF的完整URL

3. **向后兼容**:
   - 如果文档没有URL，`source_url` 字段为 `NULL`（允许为空）

## 测试

运行测试脚本验证功能：

```bash
python tests/test_document_url_save.py
```

测试包括：
1. 直接传入 `source_url` 参数
2. 从 `metadata` 中的 `source_url` 字段提取
3. 从 `metadata` 中的 `doc_url` 字段提取
4. 查询包含URL的文档
5. 创建没有URL的文档（向后兼容）

## 代码修改说明

### 1. 模型层 (`src/storage/metadata/models.py`)
- 添加了 `source_url = Column(String(1000), nullable=True, index=True)` 字段

### 2. CRUD层 (`src/storage/metadata/crud.py`)
- `create_document` 函数添加了 `source_url` 参数
- 支持从 `metadata` 中自动提取URL

### 3. Processor层
- `ipo_processor.py`: 在保存metadata时添加 `source_url`
- `report_processor.py`: 在保存metadata时添加 `source_url`

### 4. Crawler层
- `base_crawler.py`: 从metadata文件读取URL并添加到 `task.metadata`
- `ipo_crawler.py`: 从metadata文件读取URL
- `base_cninfo_crawler.py`: 通过 `task.metadata` 传递URL

## 使用示例

### 在爬虫中使用

```python
from src.ingestion.a_share.crawlers.ipo_crawler import CninfoIPOProspectusCrawler
from src.ingestion.base.base_crawler import CrawlTask
from src.common.constants import Market, DocType

crawler = CninfoIPOProspectusCrawler(
    enable_minio=True,
    enable_postgres=True
)

task = CrawlTask(
    stock_code="688111",
    company_name="金山办公",
    market=Market.A_SHARE,
    doc_type=DocType.IPO_PROSPECTUS
)

result = crawler.crawl(task)
# URL会自动保存到数据库
```

### 直接创建文档记录

```python
from src.storage.metadata import crud
from src.storage.metadata.postgres_client import get_postgres_client

pg_client = get_postgres_client()
with pg_client.get_session() as session:
    doc = crud.create_document(
        session=session,
        stock_code="000001",
        company_name="平安银行",
        market="a_share",
        doc_type="quarterly_reports",
        year=2024,
        quarter=1,
        minio_object_path="bronze/a_share/quarterly_reports/2024/Q1/000001/report.pdf",
        source_url="https://www.cninfo.com.cn/new/disclosure/detail?plate=&orgId=xxx&stockCode=000001&announcementId=xxx"
    )
    print(f"文档ID: {doc.id}, URL: {doc.source_url}")
```

## 查询文档URL

```python
from src.storage.metadata.models import Document
from src.storage.metadata.postgres_client import get_postgres_client

pg_client = get_postgres_client()
with pg_client.get_session() as session:
    # 通过ID查询
    doc = session.query(Document).filter(Document.id == 1).first()
    print(f"文档URL: {doc.source_url}")
    
    # 通过URL查询文档
    docs = session.query(Document).filter(
        Document.source_url == "https://www.cninfo.com.cn/..."
    ).all()
    print(f"找到 {len(docs)} 个文档")
```

## 注意事项

1. **数据库迁移**: 首次使用前必须执行数据库迁移脚本
2. **URL长度**: URL最大长度为1000字符（VARCHAR(1000)）
3. **索引**: `source_url` 字段已创建索引，可以快速查询
4. **向后兼容**: 旧数据没有URL是正常的，字段允许为NULL
