# FinNet 项目状态报告

## 📊 整体进度

| 模块 | 状态 | 完成度 | 说明 |
|-----|------|-------|------|
| 项目目录结构 | ✅ 完成 | 100% | 按 plan.md 四层架构创建 |
| common 公共模块 | ✅ 完成 | 100% | config、logger、constants、utils |
| storage 存储层 | 🚧 进行中 | 20% | PathManager 完成，客户端待实现 |
| ingestion 采集层 | ⏰ 待重构 | 50% | 现有爬虫代码需整合到新架构 |
| processing 处理层 | ⏰ 待实现 | 0% | AI 引擎、Dagster 调度 |
| service 服务层 | ⏰ 待实现 | 0% | 数据目录、血缘、质量监控 |
| application 应用层 | ⏰ 待实现 | 0% | RAG、LLM 训练数据 |
| API Gateway | ⏰ 待实现 | 0% | FastAPI 路由 |

---

## ✅ 已完成功能

### 1. 项目目录结构

按照 plan.md 的四层架构，创建了完整的目录树：

```
src/
├── common/              ✅ 公共模块
├── ingestion/           ✅ 采集层（目录已创建）
├── storage/             ✅ 存储层（目录已创建）
├── processing/          ✅ 处理层（目录已创建）
├── service/             ✅ 服务层（目录已创建）
├── application/         ✅ 应用层（目录已创建）
└── api/                 ✅ API 层（目录已创建）
```

### 2. common 公共模块

#### `constants.py` - 全局常量定义
```python
# 市场类型
Market.A_SHARE, Market.HK_STOCK, Market.US_STOCK

# 文档类型
DocType.ANNUAL_REPORT, DocType.QUARTERLY_REPORT, DocType.IPO_PROSPECTUS

# 数据层次
DataLayer.BRONZE, DataLayer.SILVER, DataLayer.GOLD, DataLayer.APPLICATION

# 文档状态
DocumentStatus.PENDING, DocumentStatus.PARSING, DocumentStatus.PARSED
```

#### `config.py` - 统一配置管理
```python
# 使用方式
from src.common.config import minio_config, postgres_config

print(minio_config.MINIO_ENDPOINT)  # localhost:9000
print(postgres_config.database_url)  # postgresql://...
```

支持的配置类：
- `MinIOConfig` - MinIO 对象存储
- `PostgreSQLConfig` - PostgreSQL 元数据库
- `MilvusConfig` - Milvus 向量数据库
- `NebulaGraphConfig` - NebulaGraph 图数据库
- `EmbeddingConfig` - BGE/BCE Embedding
- `LLMConfig` - Qwen/GLM 本地 LLM + 云端 API
- `PDFParserConfig` - MinerU/Docling 解析器
- `DagsterConfig` - Dagster 调度

#### `logger.py` - 日志工具
```python
# 使用方式
from src.common.logger import get_logger

logger = get_logger(__name__)
logger.info("This is a log message")
```

特性：
- ✅ 彩色控制台输出
- ✅ 文件日志支持
- ✅ 可配置日志级别
- ✅ LoggerMixin 类（为其他类提供日志功能）

#### `utils.py` - 工具函数
```python
from src.common.utils import (
    get_current_quarter,         # 获取当前季度
    calculate_file_hash,         # 计算文件哈希
    safe_filename,               # 清理文件名
    ensure_dir,                  # 确保目录存在
    load_json, save_json,        # JSON 操作
    clean_text,                  # 文本清洗
    is_valid_stock_code,         # 股票代码验证
    retry_on_exception,          # 重试装饰器
)
```

### 3. storage/object_store - 对象存储路径管理

#### `path_manager.py` - 路径管理器

严格遵循 plan.md 5.2 存储路径规范：

```python
from src.common.constants import Market, DocType
from src.storage.object_store.path_manager import PathManager

pm = PathManager()

# Bronze 层路径（原始数据）
bronze_path = pm.get_bronze_path(
    market=Market.A_SHARE,
    doc_type=DocType.QUARTERLY_REPORT,
    stock_code="000001",
    year=2023,
    quarter=3,
    filename="000001_2023_Q3.pdf"
)
# 输出: bronze/a_share/quarterly_reports/2023/Q3/000001/000001_2023_Q3.pdf

# Silver 层路径（清洗数据）
silver_path = pm.get_silver_path(
    market=Market.A_SHARE,
    doc_type=DocType.QUARTERLY_REPORT,
    stock_code="000001",
    year=2023,
    quarter=3,
    filename="000001_2023_Q3_parsed.json",
    subdir="text_cleaned"
)
# 输出: silver/text_cleaned/a_share/quarterly_reports/2023/Q3/000001/000001_2023_Q3_parsed.json

# Gold 层路径（聚合数据）
gold_path = pm.get_gold_path(
    category="company_profiles",
    market=Market.A_SHARE,
    stock_code="000001",
    filename="profile.json"
)
# 输出: gold/company_profiles/a_share/000001/profile.json

# Application 层路径（AI 应用数据）
app_path = pm.get_application_path(
    app_type="training_corpus",
    subdir="chinese",
    filename="corpus_2023.jsonl"
)
# 输出: application/training_corpus/chinese/corpus_2023.jsonl

# 隔离区路径（验证失败数据）
from src.common.constants import QuarantineReason
quarantine_path = pm.get_quarantine_path(
    reason=QuarantineReason.VALIDATION_FAILED,
    original_path="bronze/a_share/quarterly_reports/2023/Q3/000001/bad.pdf"
)
# 输出: quarantine/validation_failed/bronze/a_share/quarterly_reports/2023/Q3/000001/bad.pdf
```

---

## 🚧 下一步工作

### 优先级 1：完成 storage 层（今天）
- [ ] `storage/object_store/minio_client.py` - MinIO 客户端
- [ ] `storage/metadata/postgres_client.py` - PostgreSQL 客户端
- [ ] `storage/metadata/models.py` - SQLAlchemy 模型
- [ ] `storage/vector/milvus_client.py` - Milvus 客户端

### 优先级 2：重构 ingestion 层（明天）
- [ ] 将 `src/crawler/` 迁移到 `src/ingestion/`
- [ ] 统一使用 `PathManager` 生成路径
- [ ] 整合数据验证体系

### 优先级 3：实现 processing 层（2-3天）
- [ ] `processing/ai/pdf_parser/mineru_parser.py` - MinerU 解析器
- [ ] `processing/ai/embedding/bge_embedder.py` - BGE Embedding
- [ ] `processing/compute/dagster/` - Dagster 统一调度

### 优先级 4：实现 RAG 应用（3-4天）
- [ ] `application/rag/retriever.py` - 向量检索器
- [ ] `application/rag/rag_pipeline.py` - RAG Pipeline
- [ ] `api/routes/search.py` - 检索 API
- [ ] `api/routes/qa.py` - 问答 API

---

## 📦 依赖安装

### 已添加依赖
```bash
pip install pydantic-settings  # 配置管理
```

### 待添加依赖（后续模块需要）
```bash
# Storage 层
pip install minio psycopg2-binary sqlalchemy pymilvus nebula3-python

# Processing 层（AI 引擎）
pip install torch transformers sentence-transformers

# API 层
pip install fastapi uvicorn pydantic

# Dagster
pip install dagster dagster-webserver

# 工具
pip install python-dotenv loguru tenacity
```

---

## 🔍 代码示例

### 示例 1：使用配置管理

```python
from src.common.config import minio_config, postgres_config
from src.common.logger import get_logger

logger = get_logger(__name__)

# 打印 MinIO 配置
logger.info(f"MinIO Endpoint: {minio_config.MINIO_ENDPOINT}")
logger.info(f"MinIO Bucket: {minio_config.MINIO_BUCKET}")

# 打印 PostgreSQL 连接 URL
logger.info(f"Database URL: {postgres_config.database_url}")
```

### 示例 2：使用路径管理器

```python
from src.common.constants import Market, DocType
from src.storage.object_store.path_manager import PathManager
from src.common.logger import get_logger

logger = get_logger(__name__)
pm = PathManager()

# 生成 Bronze 层路径
path = pm.get_bronze_path(
    market=Market.A_SHARE,
    doc_type=DocType.QUARTERLY_REPORT,
    stock_code="000001",
    year=2023,
    quarter=3,
    filename="report.pdf"
)

logger.info(f"Generated path: {path}")
# 输出: Generated path: bronze/a_share/quarterly_reports/2023/Q3/000001/report.pdf
```

### 示例 3：使用工具函数

```python
from src.common.utils import (
    get_current_quarter,
    calculate_file_hash,
    safe_filename,
    ensure_dir
)

# 获取当前季度
year, quarter = get_current_quarter()
print(f"当前: {year} 年 Q{quarter}")

# 计算文件哈希
hash_value = calculate_file_hash("test.pdf")
print(f"文件哈希: {hash_value}")

# 清理文件名
clean_name = safe_filename("平安银行<2023>年报.pdf")
print(f"清理后: {clean_name}")  # 输出: 平安银行_2023_年报.pdf

# 确保目录存在
ensure_dir("/data/bronze/a_share")
```

---

## 📚 文档

- [plan.md](../plan.md) - 完整架构设计文档
- [ARCHITECTURE.md](ARCHITECTURE.md) - 架构详解
- [README.md](../README.md) - 项目说明

---

## 🎯 MVP 目标（14天计划）

| Day | 任务 | 状态 |
|-----|------|------|
| 1-2 | ✅ 基础框架搭建（目录结构、common 模块） | 完成 |
| 3-4 | 🚧 Storage 层实现（MinIO、PostgreSQL、Milvus 客户端） | 进行中 |
| 5-6 | ⏰ Processing 层实现（MinerU 解析、BGE Embedding） | 待开始 |
| 7-8 | ⏰ Dagster 调度集成（统一 Jobs、Sensors） | 待开始 |
| 9-10 | ⏰ RAG 层实现（检索器、上下文构建） | 待开始 |
| 11-12 | ⏰ LLM 问答集成（Qwen 本地 LLM） | 待开始 |
| 13 | ⏰ API 服务实现（FastAPI 路由） | 待开始 |
| 14 | ⏰ 端到端测试 + 文档 | 待开始 |

---

*报告生成时间: 2025-01-13*
*当前进度: Day 2 - Storage 层实现中*
