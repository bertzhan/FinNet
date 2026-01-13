# 爬虫模块整合说明

## 概述

本模块按照 `plan.md` 的设计，将A股爬虫代码整合到统一的数据采集架构中，为后续港股、美股爬虫预留接口。

## 目录结构

```
src/crawler/
├── __init__.py              # 模块导出
├── base_crawler.py          # 爬虫基类接口
├── config.py                # 配置管理
├── validation.py            # 数据验证体系
├── storage.py               # 存储路径管理
├── minio_storage.py         # MinIO对象存储集成
├── dagster_jobs.py          # Dagster调度作业
├── requirements.txt          # Python依赖
├── zh/                      # A股爬虫
│   ├── __init__.py
│   ├── cninfo_crawler.py   # CNINFO爬虫适配器
│   ├── main.py             # 核心爬虫逻辑
│   ├── scheduler.py        # 调度器
│   ├── state_db.py         # 状态管理（SQLite）
│   └── company_list.csv    # 公司列表
├── hk/                      # 港股爬虫（待实现）
└── us/                      # 美股爬虫（待实现）
```

## 核心组件

### 1. BaseCrawler（基类接口）

定义了统一的爬虫接口，所有市场爬虫都应继承此类：

```python
from src.crawler.base_crawler import BaseCrawler, Market, DocType, CrawlTask, CrawlResult

class MyCrawler(BaseCrawler):
    def crawl(self, task: CrawlTask) -> CrawlResult:
        # 实现爬取逻辑
        pass
    
    def crawl_batch(self, tasks: List[CrawlTask]) -> List[CrawlResult]:
        # 实现批量爬取
        pass
    
    def validate_result(self, result: CrawlResult) -> Tuple[bool, Optional[str]]:
        # 实现验证逻辑
        pass
```

### 2. CNInfoCrawler（A股爬虫适配器）

将现有的 `main.py` 逻辑封装为统一接口，支持下载一条上传一条的实时上传策略：

```python
from src.crawler.zh import CNInfoCrawler
from src.crawler.base_crawler import CrawlTask, Market, DocType

crawler = CNInfoCrawler(
    output_root="/data/finnet",
    workers=6
)

task = CrawlTask(
    stock_code="000001",
    company_name="平安银行",
    year=2023,
    quarter=1,
    doc_type=DocType.QUARTERLY_REPORT,
    market=Market.A_SHARE
)

result = crawler.crawl(task)
```

### 3. StorageManager（存储管理）

按照plan.md规范管理存储路径：

```python
from src.crawler.storage import StorageManager
from src.crawler.base_crawler import Market, DocType

storage = StorageManager("/data/finnet")

# 获取Bronze层路径
path = storage.get_bronze_path(
    market=Market.A_SHARE,
    doc_type=DocType.QUARTERLY_REPORT,
    stock_code="000001",
    year=2023,
    quarter="Q1",
    filename="report.pdf"
)
# 输出: /data/finnet/bronze/zh_stock/quarterly_reports/2023/Q1/000001/report.pdf

# 移动到隔离区
quarantine_path = storage.move_to_quarantine(
    source_path="/path/to/file.pdf",
    failure_stage="validation_failed",
    reason="invalid_format"
)
```

### 4. MinIO集成

支持将文件上传到MinIO对象存储，文件在下载完成后立即上传：

```python
# 设置环境变量启用MinIO
export USE_MINIO=true
export MINIO_ENDPOINT=http://localhost:9000
export MINIO_ACCESS_KEY=admin
export MINIO_SECRET_KEY=admin123456
export MINIO_BUCKET=company-datalake

# 运行爬虫，文件会自动上传到MinIO
python src/crawler/zh/scheduler.py \
    --mode history \
    --start-year 2023 \
    --end-year 2024 \
    --company-list src/crawler/zh/company_list.csv \
    --out reports \
    --workers 6
```

### 5. Dagster集成

通过Dagster调度系统管理爬虫任务：

```bash
# 启动 Dagster UI
bash scripts/start_dagster.sh
# 或
dagster dev -m src.crawler.dagster_jobs

# 访问 http://localhost:3000
```

**主要功能：**
- `crawl_a_share_reports_job`: A股报告爬取作业（爬取 + 验证）
- `daily_crawl_schedule`: 每日定时调度（每天凌晨2点）
- `manual_trigger_sensor`: 手动触发传感器

**详细文档：**
- [Dagster 快速开始](DAGSTER_QUICKSTART.md)
- [Dagster 完整指南](DAGSTER_GUIDE.md)

## 存储路径规范

按照plan.md设计，数据存储路径遵循以下规范：

### Bronze层（原始数据）

```
bronze/
├── zh_stock/                    # A股（原a_share）
│   ├── quarterly_reports/      # 季报（Q1, Q3）
│   │   └── {year}/{quarter}/{stock_code}/{filename}
│   ├── interim_reports/         # 半年报（Q2）
│   │   └── {year}/{quarter}/{stock_code}/{filename}
│   └── annual_reports/          # 年报（Q4）
│       └── {year}/{quarter}/{stock_code}/{filename}
├── hk_stock/                    # 港股（待实现）
└── us_stock/                    # 美股（待实现）
```

**路径格式说明：**
- 使用 `zh_stock` 代替 `a_share`
- 去掉 `key=value` 格式，直接使用值
- 使用 `quarter` 代替 `month`
- 文件名格式：`{stock_code}_{year}_{quarter}.pdf`（不包含发布日期）

### 隔离区

```
quarantine/
├── ingestion_failed/      # 采集阶段失败
├── validation_failed/     # 验证失败
└── content_failed/        # 内容验证失败
```

## 文件元数据

文件上传到MinIO时，会包含以下元数据：

- `X-Amz-Meta-Stock-Code`: 股票代码
- `X-Amz-Meta-Year`: 年份
- `X-Amz-Meta-Quarter`: 季度
- `X-Amz-Meta-Publish-Date`: 发布日期（ISO格式）

发布日期存储在元数据中，而不是文件名中。

## 使用示例

### 1. 直接使用爬虫

```python
from src.crawler.zh import CNInfoCrawler
from src.crawler.base_crawler import CrawlTask, Market, DocType

# 创建爬虫实例
crawler = CNInfoCrawler(
    output_root="/data/finnet",
    workers=6
)

# 创建任务
tasks = [
    CrawlTask(
        stock_code="000001",
        company_name="平安银行",
        year=2023,
        quarter=1,
        doc_type=DocType.QUARTERLY_REPORT,
        market=Market.A_SHARE
    )
]

# 执行爬取
results = crawler.crawl_batch(tasks)

# 检查结果
for result in results:
    if result.success:
        print(f"成功: {result.file_path}")
    else:
        print(f"失败: {result.error_message}")
```

### 2. 使用调度器

```bash
# 自动模式（抓取上一季度 + 当前季度）
python src/crawler/zh/scheduler.py \
    --company-list src/crawler/zh/company_list.csv \
    --out ./reports \
    --workers 6

# 历史模式（抓取指定年份和季度）
python src/crawler/zh/scheduler.py \
    --mode history \
    --start-year 2023 \
    --end-year 2024 \
    --start-quarter 1 \
    --end-quarter 3 \
    --company-list src/crawler/zh/company_list.csv \
    --out ./reports \
    --workers 6
```

### 3. 启用MinIO上传

```bash
# 方式1: 使用便捷脚本（自动设置环境变量）
bash src/crawler/run_with_minio.sh \
    --mode history \
    --start-year 2023 \
    --end-year 2024 \
    --company-list src/crawler/zh/company_list.csv \
    --out reports \
    --workers 6

# 方式2: 手动设置环境变量
export USE_MINIO=true
export MINIO_ENDPOINT=http://localhost:9000
export MINIO_ACCESS_KEY=admin
export MINIO_SECRET_KEY=admin123456
export MINIO_BUCKET=company-datalake

python src/crawler/zh/scheduler.py \
    --mode history \
    --start-year 2023 \
    --end-year 2024 \
    --company-list src/crawler/zh/company_list.csv \
    --out reports \
    --workers 6
```

### 4. 上传已有文件到MinIO

如果之前已经下载了文件但没有上传到MinIO：

```bash
# 设置环境变量
export USE_MINIO=true
export MINIO_ENDPOINT=http://localhost:9000
export MINIO_ACCESS_KEY=admin
export MINIO_SECRET_KEY=admin123456
export MINIO_BUCKET=company-datalake

# 预览要上传的文件
python src/crawler/upload_existing_files.py

# 实际上传
python src/crawler/upload_existing_files.py --upload
```

## 数据验证流程

按照plan.md设计，数据验证分为三个阶段：

1. **采集阶段验证（Ingestion）**
   - 来源可信度
   - 响应完整性
   - 格式正确性
   - 时效性

2. **入湖前验证（Bronze）**
   - 文件完整性（MD5/SHA256）
   - 格式验证（PDF可解析）
   - 元数据完整
   - 去重检查
   - 时间合理性
   - 文件大小

3. **内容验证（Silver）**
   - 编码正确性
   - 语言匹配
   - 内容非空
   - 关键字段提取

验证失败的数据会自动移动到隔离区。

## 工作流程

### 下载一条上传一条策略

文件在下载完成后立即上传到MinIO，无需等待所有文件下载完成：

1. 多进程并行下载PDF文件
2. 每个文件下载成功后立即：
   - 保存到本地（Bronze层）
   - 上传到MinIO（如果启用）
   - 记录元数据（包含发布日期）
3. 上传失败不影响下载流程，仅记录日志

**优势：**
- 实时性：下载完成立即上传，进度实时可见
- 容错性：单个文件上传失败不影响其他任务
- 符合规范：保留本地备份（Bronze层）+ MinIO备份

## 配置

### 环境变量

```bash
# 数据根目录
FINNET_DATA_ROOT=/data/finnet

# 爬虫配置
CRAWLER_WORKERS=6
CRAWLER_OLD_PDF_DIR=/path/to/old/pdfs
CRAWLER_ENABLE_VALIDATION=true

# MinIO配置
USE_MINIO=true
MINIO_ENDPOINT=http://localhost:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=admin123456
MINIO_BUCKET=company-datalake
MINIO_UPLOAD_ON_DOWNLOAD=true  # 是否在下载时立即上传
```

### 公司列表文件

`src/crawler/zh/company_list.csv` 格式：

```csv
code,name
000001,平安银行
000002,万科A
600519,贵州茅台
```

## 测试

```bash
# 测试MinIO连接
python src/crawler/test_minio.py

# 测试上传流程
python src/crawler/test_upload_flow.py

# 测试集成功能
python src/crawler/test_integration.py
```

## 文档

- [HOW_TO_RUN.md](HOW_TO_RUN.md) - 详细使用指南
- [MINIO_SETUP.md](MINIO_SETUP.md) - MinIO设置和配置
- [UPLOAD_FLOW.md](UPLOAD_FLOW.md) - 上传流程说明
- [UPLOAD_EXISTING_FILES.md](UPLOAD_EXISTING_FILES.md) - 上传已有文件指南
- [MINIO_METADATA.md](MINIO_METADATA.md) - MinIO元数据说明

## 后续扩展

### 添加港股爬虫

1. 在 `src/crawler/hk/` 目录下创建爬虫实现
2. 继承 `BaseCrawler` 类
3. 实现 `crawl`、`crawl_batch`、`validate_result` 方法
4. 在 `dagster_jobs.py` 中添加对应的作业

### 添加美股爬虫

1. 在 `src/crawler/us/` 目录下创建爬虫实现
2. 继承 `BaseCrawler` 类
3. 实现相应方法
4. 添加Dagster作业

## 注意事项

1. **向后兼容**：原有的 `main.py` 和 `scheduler.py` 代码保留，可以继续独立使用
2. **路径规范**：新代码遵循plan.md的存储路径规范（`zh_stock`，去掉`key=value`格式）
3. **文件名格式**：文件名不包含发布日期，发布日期存储在元数据中
4. **验证体系**：所有爬取的数据都会经过验证，失败数据进入隔离区
5. **状态管理**：使用SQLite进行状态管理，避免文件锁冲突
6. **MinIO上传**：文件下载完成后立即上传，上传失败不影响下载流程

## 故障排查

### MinIO上传问题

如果文件没有上传到MinIO：

1. 检查环境变量是否设置：`python src/crawler/debug_minio_upload.py`
2. 检查MinIO服务是否运行：`docker-compose ps minio`
3. 查看上传失败记录：`reports/minio_upload_failed.csv`

### 文件路径问题

- 确保使用 `zh_stock` 而不是 `a_share`
- 路径格式：`bronze/zh_stock/{doc_type}/{year}/{quarter}/{stock_code}/{filename}`
- 文件名格式：`{stock_code}_{year}_{quarter}.pdf`
