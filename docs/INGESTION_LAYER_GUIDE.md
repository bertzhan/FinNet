# Ingestion 层使用指南

## 📦 概述

Ingestion 层负责从各种数据源采集原始数据，并自动完成：
- **文件下载** - 从数据源下载原始文档
- **MinIO 上传** - 自动上传到对象存储（Bronze 层）
- **元数据记录** - 自动记录到 PostgreSQL
- **文件验证** - 自动计算哈希、检查文件完整性

---

## 🏗️ 架构设计

### 核心组件

```
src/ingestion/
├── base/                   # 基础模块
│   ├── base_crawler.py     # 爬虫基类（集成 storage 层）
│   └── __init__.py
├── a_share/                # A股爬虫
│   ├── cninfo_crawler.py   # CNINFO 爬虫实现
│   └── __init__.py
├── hk_stock/               # 港股爬虫（待实现）
├── us_stock/               # 美股爬虫（待实现）
└── __init__.py
```

### 类层次结构

```
BaseCrawler (抽象基类)
├── 集成 MinIOClient（对象存储）
├── 集成 PostgreSQLClient（元数据）
├── 集成 PathManager（路径管理）
└── 提供 crawl() 和 crawl_batch() 方法

CninfoAShareCrawler (A股实现)
├── 继承 BaseCrawler
├── 实现 _download_file() 方法
├── 复用现有 src/crawler/zh/main.py 逻辑
└── 支持单任务和多进程批量爬取
```

---

## 🚀 快速开始

### 1. 环境准备

确保已安装依赖：

```bash
pip install requests beautifulsoup4 tqdm minio psycopg2-binary sqlalchemy pymilvus pydantic-settings
```

设置环境变量（参考 `env.example`）：

```bash
# MinIO
export MINIO_ENDPOINT=localhost:9000
export MINIO_ACCESS_KEY=admin
export MINIO_SECRET_KEY=admin123456
export MINIO_BUCKET=company-datalake

# PostgreSQL
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=finnet
export POSTGRES_USER=finnet
export POSTGRES_PASSWORD=finnet123456
```

### 2. 基本使用

```python
from src.ingestion import CninfoAShareCrawler, CrawlTask
from src.common.constants import Market, DocType

# 创建爬虫实例
crawler = CninfoAShareCrawler(
    enable_minio=True,      # 启用 MinIO 上传
    enable_postgres=True,   # 启用 PostgreSQL 记录
    workers=4               # 多进程数量
)

# 创建爬取任务
task = CrawlTask(
    stock_code="000001",
    company_name="平安银行",
    market=Market.A_SHARE,
    doc_type=DocType.QUARTERLY_REPORT,
    year=2023,
    quarter=3
)

# 执行爬取
result = crawler.crawl(task)

# 检查结果
if result.success:
    print(f"✅ 成功！")
    print(f"本地路径: {result.local_file_path}")
    print(f"MinIO路径: {result.minio_object_path}")
    print(f"数据库ID: {result.document_id}")
else:
    print(f"❌ 失败：{result.error_message}")
```

---

## 📚 详细用法

### 单任务爬取

```python
from src.ingestion import CninfoAShareCrawler, CrawlTask
from src.common.constants import Market, DocType

# 创建爬虫
crawler = CninfoAShareCrawler()

# 创建任务
task = CrawlTask(
    stock_code="000001",
    company_name="平安银行",
    market=Market.A_SHARE,
    doc_type=DocType.QUARTERLY_REPORT,
    year=2023,
    quarter=3,
    metadata={"source": "manual"}  # 自定义元数据
)

# 执行爬取（自动完成下载、上传、记录）
result = crawler.crawl(task)
```

### 批量爬取（多进程）

```python
from src.ingestion import CninfoAShareCrawler, CrawlTask
from src.common.constants import Market, DocType

# 创建爬虫（启用多进程）
crawler = CninfoAShareCrawler(workers=8)

# 批量创建任务
tasks = [
    CrawlTask(
        stock_code="000001",
        company_name="平安银行",
        market=Market.A_SHARE,
        doc_type=DocType.QUARTERLY_REPORT,
        year=2023,
        quarter=3
    ),
    CrawlTask(
        stock_code="600519",
        company_name="贵州茅台",
        market=Market.A_SHARE,
        doc_type=DocType.QUARTERLY_REPORT,
        year=2023,
        quarter=3
    ),
    # ... 更多任务
]

# 批量爬取（8个进程并行）
results = crawler.crawl_batch(tasks)

# 统计结果
success_count = sum(1 for r in results if r.success)
print(f"成功: {success_count}/{len(tasks)}")
```

### 从 CSV 文件批量爬取

```python
import csv
from src.ingestion import CninfoAShareCrawler, CrawlTask
from src.common.constants import Market, DocType

# 读取 CSV
tasks = []
with open("companies.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        task = CrawlTask(
            stock_code=row["code"],
            company_name=row["name"],
            market=Market.A_SHARE,
            doc_type=DocType.QUARTERLY_REPORT,
            year=int(row["year"]),
            quarter=int(row["quarter"])
        )
        tasks.append(task)

# 批量爬取
crawler = CninfoAShareCrawler(workers=8)
results = crawler.crawl_batch(tasks)
```

### 验证爬取结果

```python
result = crawler.crawl(task)

# 验证结果
is_valid, error_msg = crawler.validate_result(result)

if is_valid:
    print("✅ 验证通过")
else:
    print(f"❌ 验证失败：{error_msg}")
```

---

## 🔧 高级配置

### 禁用 MinIO 或 PostgreSQL

```python
# 仅下载文件，不上传到 MinIO
crawler = CninfoAShareCrawler(
    enable_minio=False,
    enable_postgres=False
)
```

### 指定旧文件目录（避免重复下载）

```python
# 如果文件已存在于旧目录，跳过下载
crawler = CninfoAShareCrawler(
    old_pdf_dir="/path/to/old/reports"
)
```

### 自定义文档类型

```python
from src.common.constants import DocType

# 年报
task = CrawlTask(
    stock_code="000001",
    company_name="平安银行",
    market=Market.A_SHARE,
    doc_type=DocType.ANNUAL_REPORT,  # 年报
    year=2023,
    quarter=None  # 年报不需要季度
)

# 半年报
task = CrawlTask(
    stock_code="000001",
    company_name="平安银行",
    market=Market.A_SHARE,
    doc_type=DocType.INTERIM_REPORT,  # 半年报
    year=2023,
    quarter=2  # 第二季度 = 半年报
)

# 季报
task = CrawlTask(
    stock_code="000001",
    company_name="平安银行",
    market=Market.A_SHARE,
    doc_type=DocType.QUARTERLY_REPORT,  # 季报
    year=2023,
    quarter=1  # 第一季度
)
```

---

## 📊 数据流

```
1. 用户创建 CrawlTask
   ↓
2. CninfoAShareCrawler._download_file()
   - 调用现有 src/crawler/zh/main.py 逻辑
   - 下载 PDF 到临时目录
   ↓
3. BaseCrawler.crawl()
   - 计算文件哈希和大小
   - 生成 MinIO 路径
   ↓
4. MinIOClient.upload_file()
   - 上传到 Bronze 层
   - 路径: bronze/a_share/quarterly_reports/2023/Q3/000001/000001_2023_Q3.pdf
   ↓
5. PostgreSQLClient + crud.create_document()
   - 记录文档元数据
   - 状态: crawled
   ↓
6. 返回 CrawlResult
   - success: True
   - local_file_path: 本地路径
   - minio_object_path: MinIO 对象路径
   - document_id: 数据库ID
   - file_size: 文件大小
   - file_hash: 文件哈希
```

---

## 🗃️ 存储路径规范

### MinIO 路径

遵循 plan.md 5.2 规范：

```
bronze/a_share/quarterly_reports/2023/Q3/000001/000001_2023_Q3.pdf
└─┬─┘ └──┬──┘ └────────┬────────┘ └┬┘ └┬┘ └──┬──┘ └──────┬──────┘
  │      │             │           │   │     │            │
  │      │             │           │   │     │            └─ 文件名
  │      │             │           │   │     └─ 股票代码目录
  │      │             │           │   └─ 季度目录
  │      │             │           └─ 年份目录
  │      │             └─ 文档类型目录
  │      └─ 市场目录
  └─ 数据层次（Bronze 原始数据）
```

### PostgreSQL 表结构

主要表：

- **documents** - 文档元数据
  - id, stock_code, company_name, market, doc_type
  - year, quarter, minio_object_path
  - status, crawled_at, file_size, file_hash
  - metadata (JSONB)

- **document_chunks** - 文档分块（用于后续处理）
- **crawl_tasks** - 爬取任务记录
- **validation_logs** - 验证日志

---

## ⚙️ 性能优化

### 多进程配置

```python
# 根据 CPU 核心数和网络带宽调整
crawler = CninfoAShareCrawler(workers=8)  # 8个并行进程

# 建议：
# - CPU 密集型：workers = CPU核心数
# - I/O 密集型：workers = CPU核心数 * 2
# - 网络爬虫：workers = 4-8（避免被封IP）
```

### 断点续爬

现有爬虫已支持 checkpoint 机制，自动跳过已下载的文件。

---

## 🐛 故障排查

### MinIO 连接失败

```python
# 检查 MinIO 是否运行
# docker ps | grep minio

# 测试连接
from src.storage.object_store.minio_client import MinIOClient
minio_client = MinIOClient()
files = minio_client.list_files()
```

### PostgreSQL 连接失败

```python
# 检查 PostgreSQL 是否运行
# docker ps | grep postgres

# 测试连接
from src.storage.metadata.postgres_client import get_postgres_client
pg_client = get_postgres_client()
pg_client.test_connection()
```

### 爬取失败

```python
# 启用调试日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 查看详细错误
result = crawler.crawl(task)
if not result.success:
    print(result.error_message)
    print(result.metadata)  # 查看额外信息
```

---

## 📝 完整示例

参考 `examples/ingestion_demo.py`：

```bash
# 运行所有示例
python examples/ingestion_demo.py --mode all

# 仅运行单任务示例
python examples/ingestion_demo.py --mode single

# 仅运行批量任务示例
python examples/ingestion_demo.py --mode batch

# 仅检查存储连接
python examples/ingestion_demo.py --mode storage
```

---

## 🔗 相关文档

- [STORAGE_LAYER_GUIDE.md](./STORAGE_LAYER_GUIDE.md) - Storage 层详细文档
- [ARCHITECTURE.md](./ARCHITECTURE.md) - 系统架构设计
- [plan.md](../plan.md) - 完整设计规范

---

*最后更新: 2025-01-13*
