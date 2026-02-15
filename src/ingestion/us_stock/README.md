# US Stock Ingestion Module

美股数据采集模块，负责从SEC EDGAR API爬取美股上市公司的财报数据。

## 📋 功能概述

本模块提供以下功能：

1. **公司列表同步**：从SEC获取所有13,000+上市公司信息
2. **财报爬取**：下载10-K、10-Q、20-F、40-F、6-K等SEC表单
3. **HTML处理**：保留原始编码，本地化图片路径
4. **数据存储**：自动上传到MinIO，元数据写入PostgreSQL

## 🏗️ 架构设计

### 目录结构

```
src/ingestion/us_stock/
├── __init__.py
├── crawlers/
│   ├── __init__.py
│   ├── sec_api_client.py          # SEC EDGAR API客户端
│   ├── sec_filings_crawler.py     # 财报爬虫（继承BaseCrawler）
│   └── utils/
│       ├── http_client.py         # HTTP/2客户端（连接池）
│       ├── rate_limiter.py        # SEC限流器（10 req/s）
│       └── html_processor.py      # HTML处理和图片本地化
├── jobs/
│   ├── __init__.py
│   ├── sync_us_companies_job.py   # Job 1: 公司列表同步
│   └── crawl_us_filings_job.py    # Job 2: 财报爬取（待实现）
├── dagster_assets.py              # Dagster调度定义（待实现）
└── README.md                       # 本文件
```

### 数据模型

#### USListedCompany（us_listed_companies表）

```python
- code (PK)              # Ticker（如：AAPL），主键
- name                   # 公司名称
- cik (INDEXED)          # SEC CIK（10位，注意：多个证券可能共享同一CIK）
- org_name_en            # 公司全称
- sic_code               # SIC行业代码
- is_foreign_filer       # 是否外国公司（20-F/40-F）
- country                # 注册国家
- is_active              # 是否活跃
```

**注意**：CIK 是公司级别的标识符，同一家公司可能有多个证券（普通股、认股权证、单位等），它们共享同一个 CIK 但有不同的 Ticker。例如：
- `DNMX` (普通股), `DNMXU` (单位), `DNMXW` (认股权证) 都属于同一家公司，共享 CIK `0002081125`

#### Document（复用现有documents表）

通过`market='us_stock'`区分美股数据：

```python
- stock_code             # Ticker
- company_name           # 公司名称
- market                 # 'us_stock'
- doc_type               # '10k', '10q', '20f'等
- year                   # 财报年份
- quarter                # 季度（1-4或NULL）
- minio_object_path      # MinIO路径
- source_url             # SEC EDGAR URL（包含accession_number）
- publish_date           # 提交日期
- metadata               # JSON（包含images、accession_number等）
```

## 🚀 快速开始

### 1. 环境配置

在`.env`文件中配置SEC相关参数：

```bash
# SEC API配置（必需）
SEC_USER_AGENT="YourCompany contact@yourcompany.com"  # 必须包含邮箱

# SEC限流配置
SEC_RATE_LIMIT=10                 # SEC要求≤10 req/s
SEC_TIMEOUT=30                    # 请求超时（秒）
SEC_RETRY_MAX=3                   # 最大重试次数
SEC_CACHE_TTL_HOURS=12            # 缓存TTL（小时）

# 并发配置
SEC_HTML_WORKERS=8                # HTML下载并发数
SEC_IMAGE_WORKERS=4               # 图片下载并发数
SEC_BATCH_SIZE=50                 # 批量处理大小
```

### 2. 数据库迁移

执行数据库迁移创建`us_listed_companies`表：

```bash
psql -h localhost -U finnet -d finnet -f migrations/add_us_listed_companies.sql
```

### 3. 同步公司列表

```python
from src.ingestion.us_stock.jobs.sync_us_companies_job import sync_us_companies_job

# 同步所有SEC上市公司（约13,000家）
result = sync_us_companies_job()
print(result)
# {
#     'total_companies': 13000,
#     'companies_added': 13000,
#     'companies_updated': 0,
#     'duration_seconds': 45
# }
```

### 4. 爬取财报（待实现）

```python
from src.ingestion.us_stock.jobs.crawl_us_filings_job import crawl_us_filings_job

# 爬取指定公司的财报
result = crawl_us_filings_job(
    tickers=['AAPL', 'MSFT'],
    form_types=['10-K', '10-Q'],
    start_date='2023-01-01',
    end_date='2024-12-31'
)
```

## 📊 SEC表单类型

### 国内公司（Domestic）

- **10-K**：年报
- **10-Q**：季报
- **8-K**：临时公告
- **S-1**：IPO招股书
- **DEF 14A**：代理声明（股东大会）

### 外国公司（Foreign Private Issuers）

- **20-F**：外国公司年报
- **40-F**：加拿大公司年报
- **6-K**：外国公司临时报告

## 🔧 核心组件

### SECAPIClient

SEC EDGAR API客户端，提供以下功能：

- `fetch_company_tickers()`：获取所有公司列表
- `fetch_company_submissions(cik)`：获取公司所有提交记录
- `parse_filings(data, form_types, start_date, end_date)`：解析财报列表
- `download_file(url, output_path)`：下载文件（限流）
- `construct_document_url(cik, accession, filename)`：构造文档URL

### SECFilingsCrawler

继承`BaseCrawler`，实现SEC财报爬取：

- 自动下载HTML和图片
- 自动上传到MinIO
- 自动写入PostgreSQL
- 支持批量爬取

### SECRateLimiter

SEC限流器（10 req/s）：

- 线程安全
- 429响应处理
- Retry-After头部支持

### HTMLProcessor

HTML处理工具：

- 保留原始编码（ASCII/UTF-8）
- 图片路径本地化
- 使用html.parser避免字符标准化

## ⚠️ 注意事项

### SEC合规性

1. **必须配置SEC_USER_AGENT**：格式为`CompanyName email@domain.com`
2. **严格遵守10 req/s限流**：SEC会封禁违规IP
3. **使用HTTP/2**：减少连接开销，提高效率

### 数据去重

- 通过`source_url`（包含accession_number）去重
- Accession Number是SEC的唯一标识符
- 同一份财报的修正版（Amendment）有不同的Accession Number

### 存储优化

- HTML文件：直接存储到MinIO
- 图片文件：作为子对象存储，路径记录在`metadata`
- XBRL文件：可选下载（用于财务数据提取）

## 📈 性能指标

- **公司列表同步**：约45秒（13,000家公司）
- **单个财报爬取**：约2-5秒（含图片下载）
- **批量爬取**：约300-500份/小时（受SEC限流限制）

## 🔜 TODO

- [ ] 实现`crawl_us_filings_job.py`（财报爬取Job）
- [ ] 完善图片下载和HTML路径更新逻辑
- [ ] 实现XBRL文件下载和解析
- [ ] 创建Dagster调度定义
- [ ] 添加单元测试和集成测试
- [ ] 支持增量更新（每周扫描最近7天）
- [ ] 支持NASDAQ/NYSE官方列表丰富exchange字段

## 📚 参考资料

- [SEC EDGAR API文档](https://www.sec.gov/edgar/sec-api-documentation)
- [SEC表单类型](https://www.sec.gov/forms)
- [SEC限流政策](https://www.sec.gov/privacy.htm#security)
