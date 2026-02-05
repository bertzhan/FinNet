# Dagster 爬虫集成指南

## 📋 概述

本文档说明如何使用 Dagster 调度系统来管理爬虫任务。Dagster 提供了：

- ✅ **定时调度**：自动在指定时间执行爬取任务
- ✅ **数据质量检查**：自动验证爬取结果
- ✅ **可视化监控**：在 UI 中查看运行历史和状态
- ✅ **数据血缘追踪**：自动追踪数据来源和去向
- ✅ **手动触发**：可以通过 UI 手动触发任务

## 🚀 快速开始

### 1. 启动 Dagster UI

```bash
# 方式1：使用启动脚本（推荐）
bash scripts/start_dagster.sh

# 方式2：手动启动
cd /Users/han/PycharmProjects/FinNet
export PYTHONPATH=".:$PYTHONPATH"
dagster dev -m src.processing.compute.dagster
```

然后访问：**http://localhost:3000**

### 2. 查看 Jobs

在 Dagster UI 中，你可以看到以下 Jobs：

- **`crawl_a_share_reports_job`** - A股定期报告爬取作业
- **`crawl_a_share_ipo_job`** - A股IPO招股说明书爬取作业

### 3. 手动触发任务

1. 在 UI 中点击 Job 名称
2. 点击右上角 **"Launch Run"** 按钮
3. 配置参数（可选）
4. 点击 **"Launch"** 执行

### 4. 查看运行结果

- 在 **"Runs"** 标签页查看所有运行历史
- 点击运行记录查看详细日志
- 查看数据质量指标和资产物化记录

## 📝 配置说明

### 默认配置

```python
# 默认配置值
company_list_path: "src/crawler/zh/company_list.csv"
output_root: "downloads/"
workers: 4
enable_minio: True
enable_postgres: True
```

### 通过 UI 配置

在 Dagster UI 中触发任务时，可以修改配置：

```yaml
ops:
  crawl_a_share_reports_op:
    config:
      company_list_path: "src/crawler/zh/company_list.csv"
      output_root: "./downloads"
      workers: 4
      year: null  # null = 自动计算当前和上一季度
      quarter: null  # null = 自动计算
      # 注意：文档类型会根据季度自动判断（Q1/Q3=季度报告，Q2=半年报，Q4=年报）
      enable_minio: true
      enable_postgres: true
```

### 通过配置文件

创建 `dagster_config.yaml`：

```yaml
ops:
  crawl_a_share_reports_op:
    config:
      company_list_path: "src/crawler/zh/company_list.csv"
      output_root: "./downloads"
      workers: 6
      enable_minio: true
      # 文档类型会根据季度自动判断（Q1/Q3=季度报告，Q2=半年报，Q4=年报）
      enable_postgres: true
```

然后通过命令行运行：

```bash
dagster job execute \
  -j crawl_a_share_reports_job \
  -m src.processing.compute.dagster \
  -c dagster_config.yaml
```

## ⏰ 定时调度

### 启用定时调度

#### 方式1：通过 UI

1. 进入 **"Schedules"** 标签页
2. 找到 `daily_crawl_reports_schedule` 或 `daily_crawl_ipo_schedule`
3. 点击 **"Start"** 按钮

#### 方式2：通过命令行

```bash
# 启用报告爬取调度（每天凌晨2点）
dagster schedule start daily_crawl_reports_schedule -m src.processing.compute.dagster

# 启用IPO爬取调度（每天凌晨3点）
dagster schedule start daily_crawl_ipo_schedule -m src.processing.compute.dagster
```

### 修改调度时间

编辑 `src/processing/compute/dagster/jobs/crawl_jobs.py`：

```python
@schedule(
    job=crawl_a_share_reports_job,
    cron_schedule="0 3 * * *",  # 改为每天凌晨3点
    default_status=DefaultScheduleStatus.RUNNING,  # 默认启动
)
```

### Cron 表达式说明

- `0 2 * * *` - 每天凌晨2点
- `0 */6 * * *` - 每6小时执行一次
- `0 0 * * 1` - 每周一凌晨执行
- `0 0 1 * *` - 每月1号凌晨执行

## 🔍 数据质量检查

Dagster 自动执行以下数据质量检查：

1. **文件完整性**：检查 MinIO 路径是否存在
2. **元数据完整性**：检查数据库 ID 是否存在
3. **成功率统计**：计算爬取成功率

检查结果会在 Dagster UI 中显示，并记录为 **Asset Materialization**。

## 📊 数据血缘追踪

Dagster 通过 AssetMaterialization 自动追踪完整的数据血缘，实现从原始数据（Bronze层）到应用数据（Gold层）的完整数据流转追踪。

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

### 资产命名规范

所有资产遵循统一的命名格式：`[layer, category, market?, doc_type?, stock_code?, year?, quarter?]`

- **Bronze层**: `["bronze", "a_share", "annual_report", "2023", "Q4"]`
- **Silver层**: `["silver", "parsed_documents", "a_share", "annual_report", "000001", "2023", "Q4"]`
- **Gold层**: `["gold", "graph_nodes", "a_share", "annual_report", "000001"]`

### 依赖关系建立

每个 AssetMaterialization 的 `metadata` 中包含 `parent_asset_key` 字段，建立显式的上游依赖关系：

```python
AssetMaterialization(
    asset_key=["silver", "parsed_documents", ...],
    metadata={
        "parent_asset_key": MetadataValue.text("bronze/a_share/annual_report/2023/Q4"),
        # ... 其他元数据
    }
)
```

### 在 Dagster UI 中查看

1. 打开 Dagster UI
2. 点击 **"Assets"** 标签页
3. 可以看到完整的数据血缘图：
   - `bronze/` - 原始数据层
   - `silver/` - 加工数据层
   - `gold/` - 应用数据层
   - `quality_metrics/` - 质量指标

4. 点击任意资产，在 **Lineage** 标签页可以查看：
   - **Upstream**: 上游资产（依赖的数据源）
   - **Downstream**: 下游资产（使用此数据的目标）

### 详细文档

更多关于数据血缘的信息，请参考 [DATA_LINEAGE.md](./DATA_LINEAGE.md)。

## 🎯 使用场景

### 场景1：每日自动爬取最新报告

1. 启用 `daily_crawl_reports_schedule`
2. 系统每天凌晨2点自动爬取当前季度和上一季度的报告
3. 自动上传到 MinIO 和记录到 PostgreSQL
4. 自动执行数据质量检查

### 场景2：手动爬取指定季度

1. 在 UI 中手动触发 `crawl_a_share_reports_job`
2. 配置参数：
   ```yaml
   year: 2023
   quarter: 3
   ```
3. 执行爬取

### 场景3：批量爬取IPO招股说明书

1. 手动触发 `crawl_a_share_ipo_job`
2. 系统自动爬取所有公司的IPO招股说明书
3. 自动验证和存储

## 🐛 故障排查

### 问题1：Job 执行失败

**检查**：
1. 查看 Dagster UI 中的错误日志
2. 检查 MinIO 和 PostgreSQL 连接
3. 检查公司列表文件是否存在

**解决**：
```bash
# 检查服务状态
docker-compose ps

# 检查日志
docker-compose logs minio
docker-compose logs postgres
```

### 问题2：爬取速度慢

**优化**：
- 增加 `workers` 参数（建议 4-8）
- 检查网络连接
- 检查 API 限流

### 问题3：数据质量检查失败

**检查**：
1. MinIO 服务是否正常
2. PostgreSQL 服务是否正常
3. 文件是否成功上传

## 📚 相关文档

- [plan.md](../plan.md) - 完整架构设计
- [INGESTION_LAYER_GUIDE.md](INGESTION_LAYER_GUIDE.md) - 爬虫使用指南
- [STORAGE_LAYER_GUIDE.md](STORAGE_LAYER_GUIDE.md) - 存储层指南

## 🔗 参考链接

- [Dagster 官方文档](https://docs.dagster.io/)
- [Dagster 最佳实践](https://docs.dagster.io/concepts)

---

*最后更新: 2025-01-13*
