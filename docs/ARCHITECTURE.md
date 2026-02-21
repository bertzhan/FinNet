# FinNet 项目架构文档

## 📐 架构概览

FinNet 严格遵循 `plan.md` 的四层架构设计：

```
应用层 (Application Layer)
    ↓
数据服务层 (Data Service Layer)
    ↓
数据处理层 (Processing Layer)
    ↓
数据存储层 (Storage Layer)
    ↓
数据采集层 (Ingestion Layer)
```

---

## 📂 目录结构映射

### 核心模块

| 目录 | 对应层次 | 职责 |
|-----|---------|------|
| `src/common/` | 公共模块 | 配置、日志、常量、工具 |
| `src/ingestion/` | 数据采集层 | A股/港股/美股数据爬取 |
| `src/storage/` | 数据存储层 | MinIO、PostgreSQL、Milvus、NebulaGraph |
| `src/processing/` | 数据处理层 | Spark、Dagster、AI 引擎 |
| `src/service/` | 数据服务层 | 数据目录、血缘、质量监控 |
| `src/application/` | 应用层 | LLM 训练、RAG、标注 |
| `src/api/` | API Gateway | FastAPI REST API |

---

## 🔧 已完成模块

### 1. common/ - 公共模块 ✅

#### `constants.py` - 全局常量
- **Market**: 市场类型枚举（A股、港股、美股）
- **DocType**: 文档类型枚举（年报、季报、招股书等）
- **DataLayer**: 数据层次枚举（Bronze、Silver、Gold、Application）
- **DocumentStatus**: 文档处理状态
- **ValidationLevel/Stage**: 验证级别和阶段

#### `config.py` - 配置管理
- `CommonConfig`: 项目根目录、数据目录
- `MinIOConfig`: MinIO 对象存储配置
- `PostgreSQLConfig`: PostgreSQL 配置（含连接 URL 生成）
- `MilvusConfig`: Milvus 向量数据库配置
- `NebulaGraphConfig`: NebulaGraph 图数据库配置
- `CrawlerConfig`: 爬虫配置
- `EmbeddingConfig`: Embedding 向量化配置
- `LLMConfig`: 本地 LLM + 云端 API 配置
- `PDFParserConfig`: PDF 解析器配置（MinerU/Docling）
- `DagsterConfig`: Dagster 调度配置
- `APIConfig`: API 服务配置

#### `logger.py` - 日志工具
- `ColoredFormatter`: 彩色日志格式化器
- `setup_logger()`: 创建日志记录器（支持文件 + 控制台）
- `get_logger()`: 便捷方法
- `LoggerMixin`: 日志 Mixin 类

#### `utils.py` - 工具函数
- **日期处理**: `get_current_quarter()`, `get_previous_quarter()`, `quarter_to_string()`
- **文件操作**: `calculate_file_hash()`, `safe_filename()`, `ensure_dir()`
- **JSON 操作**: `load_json()`, `save_json()`
- **文本处理**: `clean_text()`, `truncate_text()`
- **验证**: `is_valid_stock_code()`
- **重试**: `retry_on_exception()` 装饰器

### 2. storage/object_store/ - 对象存储层 ✅

#### `path_manager.py` - 路径管理器
严格遵循 plan.md 5.2 存储路径规范：

- `get_bronze_path()`: 生成 Bronze 层路径（原始数据）
  ```
  bronze/{market}/{doc_type}/{year}/{quarter}/{stock_code}/{filename}
  ```

- `get_silver_path()`: 生成 Silver 层路径（清洗数据）
  ```
  silver/{subdir}/{market}/{doc_type}/{year}/{quarter}/{stock_code}/{filename}
  ```

- `get_gold_path()`: 生成 Gold 层路径（聚合数据）
  ```
  gold/{category}/{market}/{stock_code}/{filename}
  ```

- `get_application_path()`: 生成 Application 层路径（AI 应用数据）
  ```
  application/{app_type}/{subdir}/{filename}
  ```

- `get_quarantine_path()`: 生成隔离区路径
  ```
  quarantine/{reason}/{original_path}
  ```

- `parse_bronze_path()`: 解析 Bronze 层路径，提取元数据

---

## 🚧 待实现模块

### 1. storage 层（剩余部分）

- `storage/object_store/minio_client.py` - MinIO 客户端（封装上传/下载/删除）
- `storage/metadata/postgres_client.py` - PostgreSQL 客户端（元数据 CRUD）
- `storage/metadata/models.py` - SQLAlchemy 模型（documents、tasks、logs）
- `storage/vector/milvus_client.py` - Milvus 客户端（向量插入/检索）
- `storage/graph/nebula_client.py` - NebulaGraph 客户端（图谱操作）

### 2. ingestion 层（重构现有代码）

将现有 `src/crawler/` 重构为：
- `ingestion/base/` - 爬虫基类、验证器
- `ingestion/hs/` - A股爬虫（整合现有 cninfo_crawler）
- `ingestion/hk_stock/` - 港股爬虫（待实现）
- `ingestion/us_stock/` - 美股爬虫（待实现）

### 3. processing 层

- **AI 引擎**:
  - `processing/ai/pdf_parser/` - MinerU + Docling 解析器
  - `processing/ai/embedding/` - BGE Embedding 服务
  - `processing/ai/llm/` - Qwen 本地 LLM
- **Dagster 调度**:
  - `processing/compute/dagster/` - 统一调度入口（整合所有 Jobs）

### 4. application 层

- `application/rag/` - RAG 检索 + 问答系统
- `application/llm_training/` - LLM 训练数据生成

### 5. API Gateway

- `api/routes/` - FastAPI 路由（health, search, qa）
- `api/schemas/` - Pydantic 模型

---

## 📊 数据血缘追踪

FinNet 使用 Dagster 的 AssetMaterialization 功能建立完整的数据血缘追踪体系，实现从原始数据（Bronze层）到应用数据（Gold层）的完整数据流转追踪。

### 数据流依赖关系

```
crawl_jobs (Bronze)
    ↓
parse_jobs (Silver: parsed_documents)
    ↓
chunk_jobs (Silver: chunked_documents)
    ├─→ vectorize_jobs (Silver: vectorized_chunks)
    ├─→ graph_jobs (Gold: graph_nodes)
    └─→ elasticsearch_jobs (Gold: elasticsearch_index)
```

### 关键特性

1. **完整的资产记录**: 所有 Dagster 作业都记录 AssetMaterialization，包括：
   - `crawl_jobs.py` - 爬虫作业（Bronze层）
   - `parse_jobs.py` - PDF解析作业（Silver层）
   - `chunk_jobs.py` - 文本分块作业（Silver层）
   - `vectorize_jobs.py` - 向量化作业（Silver层）
   - `graph_jobs.py` - 图构建作业（Gold层）
   - `elasticsearch_jobs.py` - Elasticsearch索引作业（Gold层）

2. **显式依赖关系**: 通过 `parent_asset_key` 字段建立上游依赖关系

3. **统一命名规范**: 所有资产遵循 `[layer, category, market?, doc_type?, stock_code?, year?, quarter?]` 格式

4. **质量指标关联**: 质量指标资产关联到具体的数据资产

### 在 Dagster UI 中查看

- **Assets 页面**: 查看所有资产的层次结构
- **Lineage 标签**: 查看每个资产的上游和下游依赖关系
- **Materializations**: 查看所有物化事件和元数据

### 详细文档

更多关于数据血缘的信息，请参考 [DATA_LINEAGE.md](./DATA_LINEAGE.md)。

---

## 🔄 数据流转示例

### 场景：爬取 A股平安银行 2023 Q3 季报

```python
from src.common.constants import Market, DocType
from src.storage.object_store.path_manager import PathManager

pm = PathManager()

# 1. 爬虫下载 PDF → Bronze 层
bronze_path = pm.get_bronze_path(
    market=Market.HS,
    doc_type=DocType.QUARTERLY_REPORT,
    stock_code="000001",
    year=2023,
    quarter=3,
    filename="000001_2023_Q3.pdf"
)
# 输出: bronze/hs/quarterly_reports/2023/Q3/000001/000001_2023_Q3.pdf

# 2. MinerU 解析 → Silver 层
silver_path = pm.get_silver_path(
    market=Market.HS,
    doc_type=DocType.QUARTERLY_REPORT,
    stock_code="000001",
    year=2023,
    quarter=3,
    filename="000001_2023_Q3_parsed.json",
    subdir="text_cleaned"
)
# 输出: silver/text_cleaned/hs/quarterly_reports/2023/Q3/000001/000001_2023_Q3_parsed.json

# 3. 公司画像 → Gold 层
gold_path = pm.get_gold_path(
    category="company_profiles",
    market=Market.HS,
    stock_code="000001",
    filename="profile.json"
)
# 输出: gold/company_profiles/hs/000001/profile.json

# 4. 训练语料 → Application 层
app_path = pm.get_application_path(
    app_type="training_corpus",
    subdir="chinese",
    filename="corpus_2023_q3.jsonl"
)
# 输出: application/training_corpus/chinese/corpus_2023_q3.jsonl
```

---

## 📝 下一步工作

### 优先级 1：完成 Storage 层
1. 实现 `minio_client.py`（MinIO 上传/下载）
2. 实现 `postgres_client.py`（文档元数据表）
3. 实现 `milvus_client.py`（向量插入/检索）

### 优先级 2：重构 Ingestion 层
1. 将现有 `src/crawler/` 迁移到 `src/ingestion/`
2. 统一使用 `PathManager` 生成路径
3. 集成数据验证体系

### 优先级 3：实现 Processing 层
1. 部署 MinerU PDF 解析服务
2. 部署 BGE Embedding 服务
3. 创建 Dagster 统一调度入口

### 优先级 4：实现 RAG 应用
1. 实现向量检索器
2. 实现 LLM 问答接口
3. 创建 FastAPI 服务

---

## 🔗 技术栈映射

| plan.md 组件 | 代码位置 | 状态 |
|-------------|---------|------|
| MinIO | `storage/object_store/` | ✅ PathManager 已完成 |
| PostgreSQL | `storage/metadata/` | ⏳ 待实现 |
| Milvus | `storage/vector/` | ⏳ 待实现 |
| NebulaGraph | `storage/graph/` | ⏳ 待实现 |
| MinerU | `processing/ai/pdf_parser/` | ⏳ 待实现 |
| BGE | `processing/ai/embedding/` | ⏳ 待实现 |
| Qwen | `processing/ai/llm/` | ⏳ 待实现 |
| Dagster | `processing/compute/dagster/` | ⏳ 待实现 |

---

## 📚 参考文档

- [plan.md](../plan.md) - 完整架构设计文档
- [README.md](../README.md) - 项目说明
- [env.example](../env.example) - 环境变量模板

---

*文档版本: 1.0*
*更新日期: 2025-01-13*
