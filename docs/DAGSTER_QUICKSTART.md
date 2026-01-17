# Dagster 爬虫集成 - 快速开始

## ✅ 已完成的工作

### 1. 创建了 Dagster Jobs

**文件位置**: `src/processing/compute/dagster/jobs/crawl_jobs.py`

**包含的 Jobs**:
- ✅ `crawl_a_share_reports_job` - A股定期报告爬取作业
- ✅ `crawl_a_share_ipo_job` - A股IPO招股说明书爬取作业

**包含的 Ops**:
- ✅ `crawl_a_share_reports_op` - 爬取定期报告
- ✅ `crawl_a_share_ipo_op` - 爬取IPO招股说明书
- ✅ `validate_crawl_results_op` - 验证爬取结果（数据质量检查）

**包含的 Schedules**:
- ✅ `daily_crawl_reports_schedule` - 每天凌晨2点自动爬取报告
- ✅ `daily_crawl_ipo_schedule` - 每天凌晨3点自动爬取IPO

**包含的 Sensors**:
- ✅ `manual_trigger_reports_sensor` - 手动触发报告爬取
- ✅ `manual_trigger_ipo_sensor` - 手动触发IPO爬取

### 2. 更新了启动脚本

**文件**: `scripts/start_dagster.sh`

- ✅ 支持新的 Dagster 模块路径
- ✅ 自动检测并使用新/旧模块
- ✅ 环境变量检查

### 3. 创建了文档

- ✅ `docs/DAGSTER_INTEGRATION.md` - 完整集成指南
- ✅ `docs/DAGSTER_QUICKSTART.md` - 快速开始（本文件）
- ✅ `examples/dagster_crawl_test.py` - 测试脚本

## 🚀 快速开始

### 步骤1：启动 Dagster UI

```bash
bash scripts/start_dagster.sh
```

或者手动启动：

```bash
cd /Users/han/PycharmProjects/FinNet
export PYTHONPATH=".:$PYTHONPATH"
dagster dev -m src.processing.compute.dagster
```

访问：**http://localhost:3000**

### 步骤2：查看 Jobs

在 Dagster UI 中，你应该能看到：

- **`crawl_a_share_reports_job`** - A股定期报告爬取
- **`crawl_a_share_ipo_job`** - A股IPO爬取

### 步骤3：手动触发任务

1. 点击 Job 名称（如 `crawl_a_share_reports_job`）
2. 点击右上角 **"Launch Run"**
3. 配置参数（可选）：
   ```yaml
   ops:
     crawl_a_share_reports_op:
       config:
         workers: 4
         year: 2023
         quarter: 3
   ```
4. 点击 **"Launch"** 执行

### 步骤4：查看结果

- **Runs** 标签页：查看运行历史
- **Assets** 标签页：查看数据血缘
- **Logs**：查看详细日志

## 📝 配置说明

### 默认配置

```python
company_list_path: "src/crawler/zh/company_list.csv"
output_root: "downloads/"
workers: 4
enable_minio: True
enable_postgres: True
```

### 通过 UI 配置

在触发任务时，可以修改配置：

```yaml
ops:
  crawl_a_share_reports_op:
    config:
      workers: 6
      year: 2023
      quarter: 3
      # year 和 quarter 为 null 时，自动计算当前和上一季度
      # 注意：文档类型会根据季度自动判断（Q1/Q3=季度报告，Q2=半年报，Q4=年报）
```

## ⏰ 启用定时调度

### 方式1：通过 UI

1. 进入 **"Schedules"** 标签页
2. 找到 `daily_crawl_reports_schedule`
3. 点击 **"Start"** 按钮

### 方式2：通过命令行

```bash
dagster schedule start daily_crawl_reports_schedule -m src.processing.compute.dagster
```

## 🔍 数据质量检查

Dagster 自动执行以下检查：

1. ✅ MinIO 路径是否存在
2. ✅ 数据库 ID 是否存在
3. ✅ 成功率统计

检查结果在 UI 中显示为 **Asset Materialization**。

## 📊 数据血缘追踪

Dagster 自动追踪：

```
crawl_a_share_reports_op
  ↓
bronze/a_share/quarterly_reports/2023/Q3/...
  ↓
validate_crawl_results_op
  ↓
quality_metrics/crawl_validation
```

在 **"Assets"** 标签页查看完整血缘图。

## 🐛 常见问题

### Q: 启动失败，提示找不到模块？

**A**: 确保设置了 PYTHONPATH：
```bash
export PYTHONPATH=".:$PYTHONPATH"
```

### Q: 爬取失败，提示 MinIO 连接失败？

**A**: 检查 MinIO 服务是否运行：
```bash
docker-compose ps minio
```

### Q: 如何修改调度时间？

**A**: 编辑 `src/processing/compute/dagster/jobs/crawl_jobs.py`：
```python
@schedule(
    cron_schedule="0 3 * * *",  # 改为凌晨3点
)
```

## 📚 下一步

1. ✅ **已完成**：爬虫集成到 Dagster
2. ⏰ **下一步**：集成 PDF 解析到 Dagster
3. ⏰ **再下一步**：集成向量化到 Dagster
4. ⏰ **最终**：完整的数据管道

## 🔗 相关文档

- [DAGSTER_INTEGRATION.md](DAGSTER_INTEGRATION.md) - 完整集成指南
- [INGESTION_LAYER_GUIDE.md](INGESTION_LAYER_GUIDE.md) - 爬虫使用指南
- [plan.md](../plan.md) - 架构设计文档

---

*最后更新: 2025-01-13*
