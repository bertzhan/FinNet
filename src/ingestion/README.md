# Ingestion 层

## 概述

Ingestion 层是数据采集的入口，负责从各种数据源抓取原始文档并自动完成：

- ✅ **文件下载** - 从数据源下载原始PDF文档
- ✅ **自动上传** - 上传到 MinIO 对象存储（Bronze 层）
- ✅ **元数据记录** - 记录到 PostgreSQL 数据库
- ✅ **文件验证** - 计算哈希、检查完整性
- ✅ **断点续爬** - 支持断点续传，避免重复下载
- ✅ **多进程加速** - 支持多进程并行爬取

---

## 目录结构

```
src/ingestion/
├── base/                       # 基础模块
│   ├── base_crawler.py         # 爬虫基类（集成 storage 层）
│   └── __init__.py
├── a_share/                    # A股爬虫
│   ├── cninfo_crawler.py       # CNINFO（巨潮资讯网）爬虫
│   └── __init__.py
├── hk_stock/                   # 港股爬虫（待实现）
│   └── __init__.py
├── us_stock/                   # 美股爬虫（待实现）
│   └── __init__.py
├── README.md                   # 本文件
└── __init__.py
```

---

## 快速开始

### 1. 基本用法

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
    quarter=3
)

# 执行爬取
result = crawler.crawl(task)

if result.success:
    print(f"✅ 成功！文件: {result.local_file_path}")
    print(f"MinIO: {result.minio_object_name}")
    print(f"数据库ID: {result.document_id}")
```

### 2. 批量爬取

```python
# 创建多个任务
tasks = [
    CrawlTask(stock_code="000001", company_name="平安银行", market=Market.A_SHARE,
              doc_type=DocType.QUARTERLY_REPORT, year=2023, quarter=3),
    CrawlTask(stock_code="600519", company_name="贵州茅台", market=Market.A_SHARE,
              doc_type=DocType.QUARTERLY_REPORT, year=2023, quarter=3),
]

# 使用多进程批量爬取
crawler = CninfoAShareCrawler(workers=4)
results = crawler.crawl_batch(tasks)

# 统计结果
success_count = sum(1 for r in results if r.success)
print(f"成功: {success_count}/{len(tasks)}")
```

---

## 核心组件

### BaseCrawler（爬虫基类）

**位置**: `src/ingestion/base/base_crawler.py`

**功能**:
- 集成 MinIOClient（对象存储）
- 集成 PostgreSQLClient（元数据）
- 集成 PathManager（路径管理）
- 提供 `crawl()` 和 `crawl_batch()` 方法
- 自动处理文件哈希、上传、记录

**关键方法**:
```python
class BaseCrawler(ABC, LoggerMixin):
    @abstractmethod
    def _download_file(self, task: CrawlTask) -> Tuple[bool, Optional[str], Optional[str]]:
        """子类实现下载逻辑"""
        pass

    def crawl(self, task: CrawlTask) -> CrawlResult:
        """完整爬取流程：下载 -> 哈希 -> 上传 -> 记录"""
        pass

    def crawl_batch(self, tasks: List[CrawlTask]) -> List[CrawlResult]:
        """批量爬取"""
        pass
```

### CninfoAShareCrawler（A股爬虫）

**位置**: `src/ingestion/a_share/cninfo_crawler.py`

**功能**:
- 继承 BaseCrawler
- 实现 `_download_file()` 方法
- 复用现有 `src/crawler/zh/main.py` 的核心逻辑
- 支持单任务和多进程批量爬取

**示例**:
```python
crawler = CninfoAShareCrawler(
    enable_minio=True,      # 启用 MinIO
    enable_postgres=True,   # 启用 PostgreSQL
    workers=4,              # 4个并行进程
    old_pdf_dir="/path/to/old/reports"  # 旧文件目录（可选）
)
```

---

## 数据流

```
1. 创建 CrawlTask
   ↓
2. CninfoAShareCrawler._download_file()
   - 调用现有爬虫逻辑下载 PDF
   ↓
3. BaseCrawler.crawl()
   - 计算文件哈希和大小
   - 生成 MinIO 路径
   ↓
4. MinIOClient.upload_file()
   - 上传到 Bronze 层
   - 路径: bronze/a_share/quarterly_reports/2023/Q3/000001/*.pdf
   ↓
5. PostgreSQLClient + crud.create_document()
   - 记录文档元数据到数据库
   - 状态: crawled
   ↓
6. 返回 CrawlResult
   - success: 是否成功
   - local_file_path: 本地路径
   - minio_object_name: MinIO 对象名
   - document_id: 数据库 ID
   - file_size, file_hash: 文件信息
```

---

## 配置

### 环境变量

参考 `env.example`：

```bash
# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=admin123456
MINIO_BUCKET=company-datalake

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=finnet
POSTGRES_USER=finnet
POSTGRES_PASSWORD=finnet123456
```

### 禁用组件

```python
# 仅下载，不上传到 MinIO 和 PostgreSQL
crawler = CninfoAShareCrawler(
    enable_minio=False,
    enable_postgres=False
)
```

---

## 性能优化

### 多进程配置

```python
# workers 参数控制并行进程数
crawler = CninfoAShareCrawler(workers=8)

# 建议：
# - CPU 密集型：workers = CPU核心数
# - I/O 密集型：workers = CPU核心数 * 2
# - 网络爬虫：workers = 4-8（避免被封IP）
```

### 断点续爬

现有爬虫已支持 checkpoint 机制：

```python
# 第一次运行：下载 100 个文件
results = crawler.crawl_batch(tasks)

# 第二次运行：自动跳过已下载的文件
results = crawler.crawl_batch(tasks)  # 仅下载失败的任务
```

---

## 扩展新市场

### 1. 创建目录

```bash
mkdir -p src/ingestion/hk_stock
touch src/ingestion/hk_stock/__init__.py
touch src/ingestion/hk_stock/hkex_crawler.py
```

### 2. 实现爬虫类

```python
# src/ingestion/hk_stock/hkex_crawler.py
from src.ingestion.base import BaseCrawler, CrawlTask, CrawlResult
from src.common.constants import Market

class HkexCrawler(BaseCrawler):
    def __init__(self, enable_minio=True, enable_postgres=True):
        super().__init__(
            market=Market.HK_STOCK,
            enable_minio=enable_minio,
            enable_postgres=enable_postgres
        )

    def _download_file(self, task: CrawlTask) -> Tuple[bool, Optional[str], Optional[str]]:
        """实现港股文件下载逻辑"""
        # TODO: 实现下载逻辑
        pass
```

### 3. 导出类

```python
# src/ingestion/hk_stock/__init__.py
from .hkex_crawler import HkexCrawler
__all__ = ['HkexCrawler']

# src/ingestion/__init__.py
from .hk_stock import HkexCrawler
__all__ = [..., 'HkexCrawler']
```

---

## 完整示例

参考 `examples/ingestion_demo.py`：

```bash
# 运行所有示例
python examples/ingestion_demo.py --mode all

# 单任务示例
python examples/ingestion_demo.py --mode single

# 批量任务示例
python examples/ingestion_demo.py --mode batch

# 存储连接检查
python examples/ingestion_demo.py --mode storage
```

---

## 相关文档

- [INGESTION_LAYER_GUIDE.md](../../docs/INGESTION_LAYER_GUIDE.md) - 详细使用指南
- [STORAGE_LAYER_GUIDE.md](../../docs/STORAGE_LAYER_GUIDE.md) - Storage 层文档
- [ARCHITECTURE.md](../../docs/ARCHITECTURE.md) - 系统架构设计

---

## 技术栈

- **网络请求**: requests, urllib3
- **HTML解析**: BeautifulSoup4
- **对象存储**: MinIO (minio)
- **数据库**: PostgreSQL (psycopg2-binary, SQLAlchemy)
- **配置管理**: Pydantic Settings
- **日志**: Python logging
- **并发**: multiprocessing, concurrent.futures

---

## 开发状态

| 组件 | 状态 | 说明 |
|------|------|------|
| BaseCrawler | ✅ 完成 | 爬虫基类，集成 storage 层 |
| CninfoAShareCrawler | ✅ 完成 | A股爬虫（CNINFO） |
| HkexCrawler | ⏰ 待实现 | 港股爬虫（HKEX） |
| SecCrawler | ⏰ 待实现 | 美股爬虫（SEC EDGAR） |
| MinIO 集成 | ✅ 完成 | 自动上传到 Bronze 层 |
| PostgreSQL 集成 | ✅ 完成 | 自动记录元数据 |
| 多进程支持 | ✅ 完成 | 支持并行爬取 |
| 断点续爬 | ✅ 完成 | 基于 checkpoint 机制 |

---

*最后更新: 2025-01-13*
