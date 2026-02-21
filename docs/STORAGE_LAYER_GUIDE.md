# Storage 层使用指南

## 📦 概述

Storage 层提供了对所有存储系统的统一封装，包括：
- **MinIO** - 对象存储（文件存储）
- **PostgreSQL** - 元数据存储（关系型数据）
- **Milvus** - 向量存储（Embedding 向量）

---

## 🗂️ MinIO 对象存储

### 基本使用

```python
from src.storage.object_store.minio_client import MinIOClient
from src.storage.object_store.path_manager import PathManager
from src.common.constants import Market, DocType

# 创建客户端
minio_client = MinIOClient()

# 创建路径管理器
path_mgr = PathManager()

# 生成路径
object_name = path_mgr.get_bronze_path(
    market=Market.HS,
    doc_type=DocType.QUARTERLY_REPORT,
    stock_code="000001",
    year=2023,
    quarter=3,
    filename="000001_2023_Q3.pdf"
)
# 输出: bronze/hs/quarterly_reports/2023/Q3/000001/000001_2023_Q3.pdf
```

### 上传文件

```python
# 方式1：从文件路径上传
success = minio_client.upload_file(
    object_name="bronze/hs/test.pdf",
    file_path="/tmp/test.pdf",
    metadata={"stock_code": "000001", "year": "2023"}
)

# 方式2：从字节数据上传
with open("/tmp/test.pdf", "rb") as f:
    data = f.read()

success = minio_client.upload_file(
    object_name="bronze/hs/test.pdf",
    data=data,
    content_type="application/pdf"
)

# 方式3：上传 JSON 数据
data_dict = {"key": "value", "array": [1, 2, 3]}
success = minio_client.upload_json(
    object_name="silver/text_cleaned/test.json",
    data=data_dict
)
```

### 下载文件

```python
# 方式1：下载到文件
minio_client.download_file(
    object_name="bronze/hs/test.pdf",
    file_path="/tmp/downloaded.pdf"
)

# 方式2：下载到内存
data = minio_client.download_file(
    object_name="bronze/hs/test.pdf"
)

# 方式3：下载 JSON 数据
data_dict = minio_client.download_json(
    object_name="silver/text_cleaned/test.json"
)
print(data_dict["key"])
```

### 文件操作

```python
# 检查文件是否存在
exists = minio_client.file_exists("bronze/hs/test.pdf")

# 获取文件信息
info = minio_client.get_file_info("bronze/hs/test.pdf")
print(f"文件大小: {info['size']}, 类型: {info['content_type']}")

# 列出文件
files = minio_client.list_files(
    prefix="bronze/hs/",
    max_results=10
)
for file in files:
    print(f"{file['name']}: {file['size']} bytes")

# 复制文件
minio_client.copy_file(
    source_object="bronze/hs/test.pdf",
    dest_object="backup/test.pdf"
)

# 移动文件
minio_client.move_file(
    source_object="bronze/hs/test.pdf",
    dest_object="quarantine/validation_failed/bronze/hs/test.pdf"
)

# 删除文件
minio_client.delete_file("bronze/hs/test.pdf")

# 生成预签名 URL（临时访问）
from datetime import timedelta
url = minio_client.get_presigned_url(
    object_name="bronze/hs/test.pdf",
    expires=timedelta(hours=1)
)
print(f"临时访问链接: {url}")
```

---

## 🗄️ PostgreSQL 元数据存储

### 基本使用

```python
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import Document
from src.storage.metadata import crud

# 获取客户端
pg_client = get_postgres_client()

# 测试连接
if pg_client.test_connection():
    print("数据库连接成功")

# 创建所有表
pg_client.create_tables()
```

### 文档 CRUD

```python
# 使用会话
with pg_client.get_session() as session:
    # 创建文档
    doc = crud.create_document(
        session=session,
        stock_code="000001",
        company_name="平安银行",
        market="hs",
        doc_type="quarterly_reports",
        year=2023,
        quarter=3,
        minio_object_path="bronze/hs/quarterly_reports/2023/Q3/000001/report.pdf",
        file_size=1024000,
        file_hash="a1b2c3d4...",
        metadata={"publish_date": "2023-10-31"}
    )
    print(f"创建文档: id={doc.id}")

    # 查询文档（按 ID）
    doc = crud.get_document_by_id(session, document_id=1)
    print(f"文档: {doc.stock_code}, {doc.year} Q{doc.quarter}")

    # 查询文档（按状态）
    pending_docs = crud.get_documents_by_status(
        session,
        status="pending",
        limit=10
    )
    for doc in pending_docs:
        print(f"{doc.id}: {doc.stock_code}")

    # 更新文档状态
    from datetime import datetime
    crud.update_document_status(
        session,
        document_id=1,
        status="parsed",
        parsed_at=datetime.now()
    )

    # 查询指定股票的文档
    docs = crud.get_documents_by_stock(
        session,
        stock_code="000001",
        year=2023
    )
```

### 文档分块 CRUD

```python
with pg_client.get_session() as session:
    # 创建分块
    chunk = crud.create_document_chunk(
        session=session,
        document_id=1,
        chunk_index=0,
        chunk_text="这是第一个分块的文本...",
        chunk_size=512,
        vector_id="vec_001",
        embedding_model="bge-large-zh-v1.5",
        metadata={"page": 1}
    )

    # 查询文档的所有分块
    chunks = crud.get_document_chunks(session, document_id=1)
    for chunk in chunks:
        print(f"分块 {chunk.chunk_index}: {len(chunk.chunk_text)} 字符")

    # 更新分块的向量 ID
    crud.update_chunk_vector_id(
        session,
        chunk_id=1,
        vector_id="vec_001",
        embedding_model="bge-large-zh-v1.5"
    )
```

### 爬取任务 CRUD

```python
with pg_client.get_session() as session:
    # 创建爬取任务
    task = crud.create_crawl_task(
        session=session,
        task_type="daily",
        stock_code="000001",
        company_name="平安银行",
        market="hs",
        doc_type="quarterly_reports",
        year=2023,
        quarter=3
    )

    # 更新任务状态
    crud.update_crawl_task_status(
        session,
        task_id=task.id,
        status="completed",
        success=True,
        document_id=1
    )
```

### 验证日志 CRUD

```python
with pg_client.get_session() as session:
    # 创建验证日志
    log = crud.create_validation_log(
        session=session,
        document_id=1,
        validation_stage="bronze",
        validation_rule="file_size_check",
        validation_level="info",
        passed=True,
        message="文件大小正常: 1.2 MB"
    )

    # 查询验证日志
    logs = crud.get_validation_logs(
        session,
        document_id=1,
        validation_stage="bronze"
    )
```

### 隔离记录 CRUD

```python
with pg_client.get_session() as session:
    # 创建隔离记录
    record = crud.create_quarantine_record(
        session=session,
        document_id=1,
        source_type="hs",
        doc_type="quarterly_reports",
        original_path="bronze/hs/test.pdf",
        quarantine_path="quarantine/validation_failed/bronze/hs/test.pdf",
        failure_stage="validation_failed",
        failure_reason="文件损坏",
        failure_details="PDF 无法解析"
    )

    # 查询隔离记录
    records = crud.get_quarantine_records(
        session,
        status="pending",
        limit=10
    )
```

### 数据库统计

```python
# 获取表记录数
count = pg_client.get_table_count("documents")
print(f"文档数量: {count}")

# 获取所有表统计
info = pg_client.get_table_info()
for table, count in info.items():
    print(f"{table}: {count} 条记录")

# 获取数据库大小
size = pg_client.get_database_size()
print(f"数据库大小: {size}")

# 优化表
pg_client.vacuum_analyze("documents")
```

---

## 🔍 Milvus 向量存储

### 基本使用

```python
from src.storage.vector.milvus_client import get_milvus_client

# 获取客户端
milvus_client = get_milvus_client()

# 创建 Collection
collection = milvus_client.create_collection(
    collection_name="financial_documents",
    dimension=1024,  # BGE 向量维度
    description="金融文档向量集合",
    index_type="IVF_FLAT",
    metric_type="L2"
)
```

### 插入向量

```python
# 准备数据
embeddings = [
    [0.1] * 1024,  # 第一个向量
    [0.2] * 1024,  # 第二个向量
]

document_ids = [1, 1]
chunk_ids = [1, 2]
stock_codes = ["000001", "000001"]
years = [2023, 2023]
quarters = [3, 3]

# 插入向量
vector_ids = milvus_client.insert_vectors(
    collection_name="financial_documents",
    embeddings=embeddings,
    document_ids=document_ids,
    chunk_ids=chunk_ids,
    stock_codes=stock_codes,
    years=years,
    quarters=quarters
)

print(f"插入了 {len(vector_ids)} 个向量")
```

### 检索向量

```python
# 准备查询向量
query_vector = [[0.15] * 1024]

# 基本检索
results = milvus_client.search_vectors(
    collection_name="financial_documents",
    query_vectors=query_vector,
    top_k=5
)

# 查看结果
for hits in results:
    for hit in hits:
        print(f"距离: {hit['distance']:.4f}")
        print(f"实体: {hit['entity']}")
        print("---")

# 带过滤条件的检索
results = milvus_client.search_vectors(
    collection_name="financial_documents",
    query_vectors=query_vector,
    top_k=5,
    expr="stock_code == '000001' and year == 2023",
    output_fields=["document_id", "chunk_id", "stock_code", "year", "quarter"]
)
```

### Collection 管理

```python
# 列出所有 Collection
collections = milvus_client.list_collections()
print("所有 Collection:", collections)

# 获取 Collection 统计
stats = milvus_client.get_collection_stats("financial_documents")
print(f"向量数量: {stats['row_count']}")

# 删除向量（按条件）
milvus_client.delete_vectors(
    collection_name="financial_documents",
    expr="document_id == 1"
)

# 删除 Collection（谨慎！）
milvus_client.drop_collection("test_collection")

# 断开连接
milvus_client.disconnect()
```

---

## 🔄 完整示例：文档处理流程

```python
from src.storage.object_store.minio_client import MinIOClient
from src.storage.object_store.path_manager import PathManager
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.storage.vector.milvus_client import get_milvus_client
from src.common.constants import Market, DocType
from datetime import datetime

# 初始化客户端
minio = MinIOClient()
path_mgr = PathManager()
pg_client = get_postgres_client()
milvus = get_milvus_client()

# 1. 上传原始 PDF 到 MinIO（Bronze 层）
object_name = path_mgr.get_bronze_path(
    market=Market.HS,
    doc_type=DocType.QUARTERLY_REPORT,
    stock_code="000001",
    year=2023,
    quarter=3,
    filename="000001_2023_Q3.pdf"
)

minio.upload_file(
    object_name=object_name,
    file_path="/tmp/000001_2023_Q3.pdf",
    metadata={"publish_date": "2023-10-31"}
)

# 2. 记录文档元数据到 PostgreSQL
with pg_client.get_session() as session:
    doc = crud.create_document(
        session=session,
        stock_code="000001",
        company_name="平安银行",
        market="hs",
        doc_type="quarterly_reports",
        year=2023,
        quarter=3,
        minio_object_path=object_name,
        file_size=1024000,
        metadata={"publish_date": "2023-10-31"}
    )
    document_id = doc.id

# 3. 解析 PDF，保存到 Silver 层（假设解析完成）
parsed_data = {"text": "解析后的文本...", "tables": []}
silver_path = path_mgr.get_silver_path(
    market=Market.HS,
    doc_type=DocType.QUARTERLY_REPORT,
    stock_code="000001",
    year=2023,
    quarter=3,
    filename="000001_2023_Q3_parsed.json",
    subdir="text_cleaned"
)

minio.upload_json(silver_path, parsed_data)

# 4. 更新文档状态
with pg_client.get_session() as session:
    crud.update_document_status(
        session,
        document_id=document_id,
        status="parsed",
        parsed_at=datetime.now()
    )

# 5. 文本分块并向量化
chunks = [
    "这是第一个分块...",
    "这是第二个分块..."
]

# 生成向量（假设已经生成）
embeddings = [[0.1] * 1024, [0.2] * 1024]

# 插入向量到 Milvus
vector_ids = milvus.insert_vectors(
    collection_name="financial_documents",
    embeddings=embeddings,
    document_ids=[document_id, document_id],
    chunk_ids=[0, 1],
    stock_codes=["000001", "000001"],
    years=[2023, 2023],
    quarters=[3, 3]
)

# 6. 记录分块到 PostgreSQL
with pg_client.get_session() as session:
    for i, (chunk_text, vector_id) in enumerate(zip(chunks, vector_ids)):
        crud.create_document_chunk(
            session=session,
            document_id=document_id,
            chunk_index=i,
            chunk_text=chunk_text,
            chunk_size=len(chunk_text),
            vector_id=str(vector_id),
            embedding_model="bge-large-zh-v1.5"
        )

    # 更新文档状态为已向量化
    crud.update_document_status(
        session,
        document_id=document_id,
        status="vectorized",
        vectorized_at=datetime.now()
    )

print("✅ 文档处理完成！")
```

---

## 📝 依赖安装

```bash
# MinIO
pip install minio

# PostgreSQL
pip install psycopg2-binary sqlalchemy

# Milvus
pip install pymilvus

# 工具
pip install pydantic-settings
```

---

## 🔧 环境配置

创建 `.env` 文件：

```env
# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=admin123456
MINIO_BUCKET=company-datalake
MINIO_SECURE=false

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=finnet
POSTGRES_USER=finnet
POSTGRES_PASSWORD=finnet123456

# Milvus
MILVUS_HOST=localhost
MILVUS_PORT=19530
```

---

*最后更新: 2025-01-13*
