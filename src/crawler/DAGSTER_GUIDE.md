# Dagster 使用指南

## 目录

1. [什么是 Dagster](#什么是-dagster)
2. [安装和配置](#安装和配置)
3. [启动 Dagster](#启动-dagster)
4. [使用 Dagster UI](#使用-dagster-ui)
5. [运行作业](#运行作业)
6. [配置调度](#配置调度)
7. [手动触发](#手动触发)
8. [监控和日志](#监控和日志)
9. [常见问题](#常见问题)

## 什么是 Dagster

Dagster 是一个数据编排框架，用于构建、部署和监控数据管道。在本项目中，Dagster 用于：

- **调度爬虫任务**：定时自动执行A股报告爬取
- **工作流管理**：管理爬取 → 验证的完整流程
- **监控和追踪**：查看任务执行状态、日志和结果
- **手动触发**：通过UI手动执行任务

## 安装和配置

### 1. 安装依赖

Dagster 已经包含在 `requirements.txt` 中：

```bash
pip install -r src/crawler/requirements.txt
```

或者单独安装：

```bash
pip install dagster>=1.5.0 dagster-webserver
```

### 2. 配置环境变量

创建 `.env` 文件（参考 `env.example`）：

```bash
# 数据存储路径
FINNET_DATA_ROOT=/data/finnet

# 爬虫配置
CRAWLER_WORKERS=6
CRAWLER_OUTPUT_ROOT=/data/finnet

# MinIO配置（可选）
USE_MINIO=true
MINIO_ENDPOINT=http://localhost:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=admin123456
MINIO_BUCKET=company-datalake
```

### 3. 准备公司列表文件

确保 `src/crawler/zh/company_list.csv` 文件存在，格式如下：

```csv
code,name
000001,平安银行
000002,万科A
600519,贵州茅台
```

## 启动 Dagster

### 方式1：使用 Dagster UI（推荐）

Dagster UI 提供了可视化的界面来管理和监控作业。

#### 启动命令

```bash
# 进入项目根目录
cd /Users/han/PycharmProjects/FinNet

# 启动 Dagster UI
dagster dev -m src.crawler.dagster_jobs
```

或者使用完整路径：

```bash
dagster dev -f src/crawler/dagster_jobs.py
```

#### 访问 UI

启动后，打开浏览器访问：

```
http://localhost:3000
```

### 方式2：使用命令行运行作业

不启动UI，直接运行作业：

```bash
dagster job execute -j crawl_a_share_reports_job -m src.crawler.dagster_jobs
```

### 方式3：使用 Python API

```python
from dagster import execute_job
from src.crawler.dagster_jobs import crawl_a_share_reports_job

result = execute_job(crawl_a_share_reports_job)
print(result)
```

## 使用 Dagster UI

### 1. 查看作业列表

在 UI 主页可以看到：
- **crawl_a_share_reports_job**：A股报告爬取作业
- **daily_crawl_schedule**：每日定时调度（默认停止）
- **manual_trigger_sensor**：手动触发传感器（默认停止）

### 2. 查看作业详情

点击作业名称可以查看：
- **Graph**：作业的依赖关系图
- **Runs**：历史运行记录
- **Schedules**：调度配置
- **Sensors**：传感器配置

### 3. 手动触发作业

1. 点击作业名称进入详情页
2. 点击右上角的 **"Launch Run"** 按钮
3. 配置运行参数（可选）：
   ```yaml
   ops:
     crawl_a_share_quarterly_reports:
       config:
         output_root: "/data/finnet"
         workers: 6
   ```
4. 点击 **"Launch"** 开始执行

### 4. 查看运行状态

在 **Runs** 标签页可以：
- 查看所有运行记录
- 查看运行状态（Queued、Running、Success、Failed）
- 查看运行日志
- 查看运行结果和元数据

### 5. 启用调度

1. 进入 **Schedules** 标签页
2. 找到 **daily_crawl_schedule**
3. 点击 **"Start"** 启用调度
4. 调度将在每天凌晨2点自动执行

### 6. 启用手动触发传感器

1. 进入 **Sensors** 标签页
2. 找到 **manual_trigger_sensor**
3. 点击 **"Start"** 启用传感器
4. 之后可以通过UI手动触发作业

## 运行作业

### 1. 通过 UI 运行

在 Dagster UI 中点击 **"Launch Run"** 按钮。

### 2. 通过命令行运行

```bash
# 基本运行
dagster job execute -j crawl_a_share_reports_job -m src.crawler.dagster_jobs

# 带配置运行
dagster job execute \
  -j crawl_a_share_reports_job \
  -m src.crawler.dagster_jobs \
  -c config.yaml
```

`config.yaml` 示例：

```yaml
ops:
  crawl_a_share_quarterly_reports:
    config:
      output_root: "/data/finnet"
      workers: 6
      old_pdf_dir: null
```

### 3. 通过 Python 运行

```python
from dagster import execute_job, RunConfig
from src.crawler.dagster_jobs import crawl_a_share_reports_job

# 基本运行
result = execute_job(crawl_a_share_reports_job)

# 带配置运行
result = execute_job(
    crawl_a_share_reports_job,
    run_config=RunConfig(
        ops={
            "crawl_a_share_quarterly_reports": {
                "config": {
                    "output_root": "/data/finnet",
                    "workers": 6
                }
            }
        }
    )
)

print(f"运行结果: {result.success}")
```

## 配置调度

### 当前调度配置

项目中的调度配置在 `dagster_jobs.py` 中：

```python
@schedule(
    job=crawl_a_share_reports_job,
    cron_schedule="0 2 * * *",  # 每天凌晨2点执行
    default_status=DefaultSensorStatus.STOPPED,  # 默认停止
)
def daily_crawl_schedule(context):
    return RunRequest()
```

### Cron 表达式说明

- `0 2 * * *`：每天凌晨2点
- `0 */6 * * *`：每6小时执行一次
- `0 0 * * 1`：每周一凌晨执行
- `0 0 1 * *`：每月1号凌晨执行

### 修改调度时间

编辑 `src/crawler/dagster_jobs.py`，修改 `cron_schedule` 参数：

```python
@schedule(
    job=crawl_a_share_reports_job,
    cron_schedule="0 3 * * *",  # 改为每天凌晨3点
    default_status=DefaultSensorStatus.RUNNING,  # 默认启动
)
```

### 启用调度

#### 方式1：通过 UI

1. 启动 Dagster UI
2. 进入 **Schedules** 标签页
3. 找到 **daily_crawl_schedule**
4. 点击 **"Start"** 按钮

#### 方式2：通过命令行

```bash
dagster schedule start daily_crawl_schedule -m src.crawler.dagster_jobs
```

#### 方式3：修改代码默认状态

将 `default_status` 改为 `DefaultSensorStatus.RUNNING`：

```python
@schedule(
    job=crawl_a_share_reports_job,
    cron_schedule="0 2 * * *",
    default_status=DefaultSensorStatus.RUNNING,  # 默认启动
)
```

## 手动触发

### 方式1：通过 UI 手动触发

1. 启动 Dagster UI
2. 进入作业详情页
3. 点击 **"Launch Run"** 按钮
4. 配置参数（可选）
5. 点击 **"Launch"**

### 方式2：使用传感器

启用 `manual_trigger_sensor` 后，可以通过UI的传感器页面手动触发。

### 方式3：命令行触发

```bash
dagster sensor tick manual_trigger_sensor -m src.crawler.dagster_jobs
```

## 监控和日志

### 1. 在 UI 中查看日志

- 进入运行详情页
- 点击 **"Logs"** 标签
- 查看实时日志输出

### 2. 查看运行结果

运行完成后，在运行详情页可以查看：
- **输出结果**：作业返回的数据
- **资产物化**：成功爬取的文件记录
- **元数据**：文件路径、大小等信息

### 3. 查看作业统计

在作业列表页可以看到：
- 总运行次数
- 成功/失败次数
- 平均运行时间
- 最近运行时间

### 4. 配置日志级别

在 `dagster_jobs.py` 中使用 `get_dagster_logger()`：

```python
from dagster import get_dagster_logger

logger = get_dagster_logger()
logger.info("信息日志")
logger.warning("警告日志")
logger.error("错误日志")
```

## 作业流程说明

### crawl_a_share_reports_job 流程

1. **crawl_a_share_quarterly_reports**（爬取阶段）
   - 自动计算上一季度和当前季度
   - 读取公司列表文件
   - 批量爬取所有公司的季度报告
   - 返回爬取结果统计

2. **validate_crawled_data**（验证阶段）
   - 接收爬取结果
   - 对每个成功爬取的文件进行验证
   - 验证失败的文件移动到隔离区
   - 返回验证统计

### 数据流向

```
公司列表 → 爬取任务 → PDF文件 → 验证 → Bronze层存储
                                    ↓
                              验证失败 → 隔离区
```

## 常见问题

### 1. 如何修改输出目录？

**方式1：通过 UI 配置**

在运行作业时，在配置中添加：

```yaml
ops:
  crawl_a_share_quarterly_reports:
    config:
      output_root: "/your/custom/path"
```

**方式2：修改代码默认值**

编辑 `dagster_jobs.py`：

```python
class CrawlerConfig(Config):
    output_root: str = "/your/custom/path"  # 修改这里
```

### 2. 如何修改并发数？

在配置中设置 `workers` 参数：

```yaml
ops:
  crawl_a_share_quarterly_reports:
    config:
      workers: 8  # 修改为8个并发
```

### 3. 如何只爬取特定公司？

修改 `dagster_jobs.py` 中的 `crawl_a_share_quarterly_reports` 函数，添加过滤逻辑：

```python
# 只爬取特定股票代码
target_codes = ["000001", "000002"]
tasks = [task for task in tasks if task.stock_code in target_codes]
```

### 4. 如何查看失败原因？

1. 在 UI 中进入失败的运行记录
2. 查看 **Logs** 标签页的错误日志
3. 查看运行结果中的 `error` 字段

### 5. 如何重新运行失败的作业？

1. 在 UI 中找到失败的运行记录
2. 点击 **"Re-execute"** 按钮
3. 或者手动触发新的运行

### 6. Dagster UI 无法启动？

检查：
- Python 环境是否正确
- 依赖是否安装完整：`pip install dagster dagster-webserver`
- 端口 3000 是否被占用
- 模块路径是否正确：`-m src.crawler.dagster_jobs`

### 7. 如何添加新的作业？

在 `dagster_jobs.py` 中添加：

```python
@op
def my_new_op(context):
    logger = get_dagster_logger()
    logger.info("执行新操作")
    return {"result": "success"}

@job
def my_new_job():
    result = my_new_op()
    # 可以连接其他操作
    # other_op(result)
```

### 8. 如何配置作业依赖？

使用 Dagster 的依赖语法：

```python
@job
def my_job():
    result1 = op1()
    result2 = op2(result1)  # op2 依赖 op1 的结果
    op3(result2)  # op3 依赖 op2 的结果
```

## 最佳实践

1. **开发环境**：使用 `dagster dev` 启动 UI，方便调试和测试
2. **生产环境**：使用 `dagster-daemon` 作为后台服务运行
3. **配置管理**：使用配置文件而不是硬编码
4. **错误处理**：在作业中添加适当的错误处理和重试逻辑
5. **监控告警**：配置监控和告警，及时发现问题
6. **日志记录**：使用 `get_dagster_logger()` 记录关键信息

## 参考资源

- [Dagster 官方文档](https://docs.dagster.io/)
- [Dagster 概念指南](https://docs.dagster.io/concepts)
- [Dagster API 参考](https://docs.dagster.io/api-reference)

## 下一步

- 添加更多作业（如港股、美股爬虫）
- 配置更复杂的调度策略
- 集成告警和通知
- 添加数据质量检查
- 配置资源限制和优先级
