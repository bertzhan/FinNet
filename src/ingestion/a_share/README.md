# A股爬虫模块 (CNINFO)

## 概述

本模块提供 A股 CNINFO（巨潮资讯网）爬虫的完整实现，采用模块化设计，完全独立于 `src/crawler` 目录。支持定期报告（年报、季报）和IPO招股说明书的自动爬取、存储和管理。

### 核心特性

- ✅ **模块化架构**：清晰的职责分离，易于维护和扩展
- ✅ **自动存储集成**：自动上传到 MinIO 对象存储，记录到 PostgreSQL 元数据库
- ✅ **高性能**：支持多进程并行爬取，SQLite 状态管理
- ✅ **容错机制**：重试、断点续传、状态缓存
- ✅ **灵活配置**：可独立启用/禁用 MinIO 和 PostgreSQL

## 目录结构

```
src/ingestion/a_share/
├── __init__.py                    # 模块导出
├── config.py                      # 配置和常量（API URLs、Headers、重试策略等）
├── crawlers/                      # 爬虫实现层
│   ├── __init__.py
│   ├── base_cninfo_crawler.py    # CNINFO爬虫基类（公共逻辑）
│   ├── report_crawler.py         # 定期报告爬虫（年报、季报）
│   └── ipo_crawler.py            # IPO招股说明书爬虫
├── processor/                     # 任务处理器层（工作流编排）
│   ├── __init__.py
│   ├── report_processor.py       # 定期报告任务处理器（含CLI入口）
│   └── ipo_processor.py          # IPO任务处理器（含CLI入口）
├── downloader/                     # 下载器层（纯粹的下载功能）
│   ├── __init__.py
│   ├── pdf_downloader.py         # PDF下载器（重试、错误处理）
│   └── html_downloader.py        # HTML下载器（编码检测、文本提取）
├── api/                           # API客户端层
│   ├── __init__.py
│   ├── client.py                 # 定期报告API客户端
│   ├── ipo_client.py             # IPO API客户端
│   └── orgid_resolver.py         # OrgID解析器（多种策略）
├── utils/                         # 工具函数层
│   ├── __init__.py
│   ├── code_utils.py             # 股票代码处理（规范化、交易所检测、代码变更）
│   ├── text_utils.py             # 文本处理（规范化、标题过滤）
│   ├── time_utils.py              # 时间处理（时间窗口、格式化）
│   ├── file_utils.py             # 文件操作（会话管理、CSV读取、缓存构建）
│   └── cache_utils.py            # 缓存工具（代码变更缓存）
├── state/                         # 状态管理层
│   ├── __init__.py
│   └── shared_state.py           # 共享状态管理（JSON/SQLite双模式）
├── orgid_cache.json              # OrgID缓存（自动生成）
├── orgid_cache_ipo.json          # IPO OrgID缓存（自动生成）
├── code_change_cache.json        # 代码变更缓存（自动生成）
└── README.md                      # 本文档
```

## 架构设计

### 分层架构

```
┌─────────────────────────────────────────────────────────┐
│                    Crawler Layer                        │
│  (ReportCrawler / CninfoIPOProspectusCrawler)          │
│  - 任务接收和结果返回                                     │
│  - 文件处理（哈希、MinIO上传、PostgreSQL记录）          │
│  - 批量爬取协调                                          │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  Processor Layer                        │
│  (report_processor / ipo_processor)                     │
│  - 工作流编排（API调用 → 下载 → 状态更新）              │
│  - 多进程任务分发                                        │
│  - 失败处理和重试                                        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│              API & Downloader Layers                   │
│  - API客户端：公告查询、OrgID解析                        │
│  - 下载器：PDF/HTML下载（重试、编码处理）              │
└─────────────────────────────────────────────────────────┘
```

### 类继承关系

```
BaseCrawler (src/ingestion/base/base_crawler.py)
  └── CninfoBaseCrawler (crawlers/base_cninfo_crawler.py)
      ├── ReportCrawler (crawlers/report_crawler.py)
      └── CninfoIPOProspectusCrawler (crawlers/ipo_crawler.py)
```

## 核心组件

### 1. 爬虫类 (Crawlers)

#### ReportCrawler - 定期报告爬虫

**功能**：
- 爬取年报、季报（Q1-Q4）
- 自动上传到 MinIO（Bronze层）
- 自动记录到 PostgreSQL（文档元数据）
- 支持单任务和多进程批量爬取
- 支持旧PDF目录检查（避免重复下载）

**使用示例**：
```python
from src.ingestion.a_share import ReportCrawler
from src.ingestion.base.base_crawler import CrawlTask
from src.common.constants import Market, DocType

# 创建爬虫实例
crawler = ReportCrawler(
    enable_minio=True,      # 启用MinIO上传
    enable_postgres=True,   # 启用PostgreSQL记录
    workers=4,              # 多进程数量
    old_pdf_dir="/path/to/old/pdfs"  # 可选：旧PDF目录
)

# 单任务爬取
task = CrawlTask(
    stock_code="000001",
    company_name="平安银行",
    market=Market.A_SHARE,
    doc_type=DocType.QUARTERLY_REPORT,
    year=2023,
    quarter=3
)

result = crawler.crawl(task)
if result.success:
    print(f"✅ 成功：{result.minio_object_name}")
    print(f"   文档ID：{result.document_id}")

# 批量爬取
tasks = [
    CrawlTask(stock_code="000001", company_name="平安银行", 
              market=Market.A_SHARE, doc_type=DocType.ANNUAL_REPORT, year=2023, quarter=4),
    CrawlTask(stock_code="000002", company_name="万科A", 
              market=Market.A_SHARE, doc_type=DocType.QUARTERLY_REPORT, year=2023, quarter=3),
]
results = crawler.crawl_batch(tasks)
```

#### CninfoIPOProspectusCrawler - IPO招股说明书爬虫

**功能**：
- 爬取IPO招股说明书（PDF格式）
- 自动过滤HTML格式文件（不保存）
- 从文件名提取年份（IPO不需要year/quarter参数）
- 其他功能与ReportCrawler相同

**使用示例**：
```python
from src.ingestion.a_share import CninfoIPOProspectusCrawler
from src.ingestion.base.base_crawler import CrawlTask
from src.common.constants import Market, DocType

crawler = CninfoIPOProspectusCrawler(
    enable_minio=True,
    enable_postgres=True,
    workers=4
)

# IPO任务不需要year和quarter
task = CrawlTask(
    stock_code="688111",
    company_name="金山办公",
    market=Market.A_SHARE,
    doc_type=DocType.IPO_PROSPECTUS,
    year=None,      # IPO不需要年份
    quarter=None    # IPO不需要季度
)

result = crawler.crawl(task)
```

### 2. 任务处理器 (Processor)

**职责**：协调完整的工作流程

#### report_processor.py

**核心函数**：
- `process_single_task()`: 处理单个定期报告任务
  - 获取/缓存 OrgID
  - 查询公告列表
  - 下载PDF文件
  - 更新状态（checkpoint、缓存）
- `run_multiprocessing()`: 多进程批量处理
- `run()`: CLI入口（顺序执行模式）

**工作流程**：
```
1. 检查checkpoint（是否已完成）
2. 检查旧PDF目录（避免重复下载）
3. 获取OrgID（缓存优先）
4. 处理代码变更（股票代码变更历史）
5. 查询公告列表（按季度类别）
6. 筛选最新公告（标题过滤）
7. 下载PDF文件
8. 保存checkpoint
```

#### ipo_processor.py

**核心函数**：
- `process_single_ipo_task()`: 处理单个IPO任务
  - 获取/缓存 OrgID
  - 查询IPO公告列表
  - 下载PDF/HTML文件（HTML不保存）
  - 更新状态
- `run_ipo_multiprocessing()`: 多进程批量处理
- `run_ipo()`: CLI入口

**工作流程**：
```
1. 检查checkpoint
2. 获取OrgID
3. 查询IPO公告列表（首次公开发行类别）
4. 筛选招股说明书（关键词过滤）
5. 下载文件（PDF优先，HTML作为备选）
6. HTML文件自动跳过保存
7. 保存checkpoint
```

### 3. API客户端 (API)

#### client.py - 定期报告API

**核心函数**：
- `fetch_anns_by_category()`: 按类别查询公告
- `fetch_anns()`: 通用公告查询
- `pick_latest()`: 筛选最新公告

**API端点**：
- `https://www.cninfo.com.cn/new/hisAnnouncement/query`

#### ipo_client.py - IPO API

**核心函数**：
- `fetch_ipo_announcements()`: 查询IPO公告
- `pick_latest_ipo()`: 筛选最新IPO招股说明书

#### orgid_resolver.py - OrgID解析器

**解析策略**（按优先级）：
1. **构造方法**：根据股票代码和交易所构造（`gssz0000001`格式）
2. **搜索API**：通过CNINFO搜索API获取
3. **HTML解析**：从搜索结果页面解析

**缓存机制**：
- 全局OrgID缓存（`orgid_cache.json` / `orgid_cache_ipo.json`）
- 避免重复API调用

### 4. 下载器 (Downloader)

#### pdf_downloader.py

**功能**：
- 重试机制（3次，指数退避）
- 错误处理（403、502、503、504自动重试）
- 会话管理（连接池、超时设置）

#### html_downloader.py

**功能**：
- 多级编码检测（Meta标签 → requests编码 → 常见中文编码 → chardet → UTF-8）
- HTML转文本提取
- 详情页HTML提取（处理iframe、嵌入内容）

**特殊处理**：
- IPO招股说明书可能以HTML格式提供
- HTML文件会被检测并跳过保存（仅保存PDF）

### 5. 状态管理 (State)

#### shared_state.py

**两种实现模式**：

1. **SharedState (JSON模式)**
   - 使用JSON文件存储
   - 多进程锁机制
   - 兼容性好

2. **SharedStateSQLite (SQLite模式)** ⭐推荐
   - 使用SQLite数据库
   - 自动并发控制（WAL模式）
   - 性能更好，无文件锁冲突
   - 自动从JSON迁移

**管理的数据**：
- **Checkpoint**：已完成任务记录（避免重复下载）
- **OrgID缓存**：股票代码 → OrgID映射
- **代码变更缓存**：OrgID → 历史股票代码列表

### 6. 工具函数 (Utils)

- **code_utils.py**: 股票代码规范化、交易所检测、代码变更检测
- **text_utils.py**: 文本规范化、标题过滤（排除摘要、英文版等）
- **time_utils.py**: 时间窗口构建、时间戳转换
- **file_utils.py**: HTTP会话管理、CSV读取、PDF缓存构建
- **cache_utils.py**: 代码变更缓存管理

## 数据流

### 单任务爬取流程

```
CrawlTask
  ↓
ReportCrawler._download_file()
  ↓
processor.process_single_task()
  ├─→ api.orgid_resolver.get_orgid()      # 获取OrgID
  ├─→ api.client.fetch_anns()              # 查询公告
  ├─→ downloader.pdf_downloader.download() # 下载文件
  └─→ state.shared_state.save_checkpoint()  # 更新状态
  ↓
ReportCrawler._find_downloaded_file()     # 查找下载的文件
  ↓
CninfoBaseCrawler._process_downloaded_file()
  ├─→ 计算文件哈希
  ├─→ MinIO上传 (bronze层)
  └─→ PostgreSQL记录 (文档元数据)
  ↓
CrawlResult
```

### 批量爬取流程

```
List[CrawlTask]
  ↓
ReportCrawler.crawl_batch()
  ├─→ 单任务 → super().crawl_batch()      # 单任务模式
  └─→ 多任务 → _crawl_batch_multiprocessing()
      ├─→ 创建临时CSV
      ├─→ processor.run_multiprocessing()  # 多进程处理
      ├─→ 读取失败记录
      ├─→ 处理成功文件（MinIO + PostgreSQL）
      └─→ 清理临时文件
  ↓
List[CrawlResult]
```

## 配置说明

### config.py

**API配置**：
- `CNINFO_API`: 公告查询API端点
- `CNINFO_STATIC`: 静态文件CDN
- `CATEGORY_MAP`: 季度类别映射

**HTTP配置**：
- `HEADERS_API`: API请求头
- `HEADERS_HTML`: HTML请求头
- `PROXIES`: 代理配置（可选）

**重试配置**：
- `RETRY_TIMES`: 重试次数（默认3次）
- `RETRY_STATUS`: 需要重试的HTTP状态码

**限流配置**：
- `INTER_COMBO_SLEEP_RANGE`: 组合间睡眠时间（2-3秒）
- `INTER_SAME_STOCK_GAP`: 同一股票间隔（1秒）

**过滤配置**：
- `EXCLUDE_IN_TITLE`: 定期报告排除关键词
- `IPO_KEYWORDS`: IPO关键词
- `EXCLUDE_IN_TITLE_IPO`: IPO排除关键词

## 存储路径

### MinIO路径结构

**定期报告**：
```
bronze/a_share/{doc_type}/{year}/Q{quarter}/{stock_code}/{filename}
```

**IPO招股说明书**：
```
bronze/a_share/ipo_prospectus/{stock_code}/{filename}
```

### 本地文件结构

**定期报告**：
```
{output_root}/{exchange}/{code}/{year}/{code}_{year}_Q{quarter}.pdf
```

**IPO**：
```
{output_root}/{exchange}/{code}/{code}_{year}_{date}.pdf
```

## 状态管理

### Checkpoint机制

**定期报告**：
- Key格式：`{code}-{year}-{quarter}`
- 存储位置：输出目录的 `checkpoint.json` 或 SQLite数据库

**IPO**：
- Key格式：`{code}-IPO`
- 存储位置：输出目录的 `checkpoint_ipo.json`

### 缓存文件

**全局缓存**（位于 `a_share/` 目录）：
- `orgid_cache.json`: 定期报告OrgID缓存
- `orgid_cache_ipo.json`: IPO OrgID缓存
- `code_change_cache.json`: 代码变更缓存

**临时缓存**（位于输出目录）：
- `checkpoint.json`: 任务完成记录
- `cninfo_state.db`: SQLite状态数据库（如果使用SQLite模式）

## 使用方式

### 方式1：使用爬虫类（推荐）

```python
from src.ingestion.a_share import ReportCrawler, CninfoIPOProspectusCrawler
from src.ingestion.base.base_crawler import CrawlTask
from src.common.constants import Market, DocType

# 定期报告
crawler = ReportCrawler(enable_minio=True, enable_postgres=True, workers=4)
task = CrawlTask(stock_code="000001", company_name="平安银行",
                 market=Market.A_SHARE, doc_type=DocType.ANNUAL_REPORT,
                 year=2023, quarter=4)
result = crawler.crawl(task)

# IPO
ipo_crawler = CninfoIPOProspectusCrawler(enable_minio=True, enable_postgres=True)
ipo_task = CrawlTask(stock_code="688111", company_name="金山办公",
                    market=Market.A_SHARE, doc_type=DocType.IPO_PROSPECTUS,
                    year=None, quarter=None)
ipo_result = ipo_crawler.crawl(ipo_task)
```

### 方式2：使用处理器（CLI模式）

```bash
# 定期报告（多进程）
python -m src.ingestion.a_share.processor.report_processor \
    --input tasks.csv \
    --out ./downloads \
    --fail failed.csv \
    --workers 4 \
    --year 2024 \
    --quarter Q2

# IPO（多进程）
python -m src.ingestion.a_share.processor.ipo_processor \
    --input tasks.csv \
    --out ./downloads \
    --fail failed.csv \
    --workers 4
```

### 方式3：直接运行爬虫文件

```bash
# 定期报告测试
python src/ingestion/a_share/crawlers/report_crawler.py

# IPO测试
python src/ingestion/a_share/crawlers/ipo_crawler.py
```


## 测试

```bash
# 运行爬虫测试（需要MinIO和PostgreSQL服务）
python src/ingestion/a_share/crawlers/report_crawler.py
python src/ingestion/a_share/crawlers/ipo_crawler.py
```

## 注意事项

1. **环境要求**：
   - MinIO服务（对象存储）
   - PostgreSQL服务（元数据存储）
   - Python 3.10+

2. **配置要求**：
   - 设置 `.env` 文件中的MinIO和PostgreSQL连接信息
   - 确保数据库表已初始化（运行 `scripts/init_database.py`）

3. **IPO特殊处理**：
   - IPO任务不需要 `year` 和 `quarter` 参数
   - HTML格式的招股说明书会被自动跳过（仅保存PDF）
   - 年份从下载的文件名中提取

4. **性能优化**：
   - 推荐使用SQLite状态管理模式（自动选择）
   - 多进程爬取时建议4-8个worker进程
   - 注意API限流（已内置睡眠机制）

5. **错误处理**：
   - 下载失败会记录到失败CSV文件
   - 支持断点续传（checkpoint机制）
   - 自动重试（3次，指数退避）

## 相关文档

- [Ingestion Layer Guide](../../docs/INGESTION_LAYER_GUIDE.md)
- [Storage Layer Guide](../../docs/STORAGE_LAYER_GUIDE.md)
- [Architecture](../../docs/ARCHITECTURE.md)
