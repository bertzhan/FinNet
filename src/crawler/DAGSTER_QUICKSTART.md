# Dagster 快速开始

## 快速启动

### 方式1：使用启动脚本（推荐）

```bash
bash scripts/start_dagster.sh
```

### 方式2：手动启动（模块方式）

```bash
cd /Users/han/PycharmProjects/FinNet
export PYTHONPATH=".:$PYTHONPATH"
dagster dev -m src.crawler.dagster_jobs
```

### 方式3：手动启动（文件方式，推荐）

```bash
cd /Users/han/PycharmProjects/FinNet
export PYTHONPATH=".:$PYTHONPATH"
dagster dev -f src/crawler/dagster_jobs.py
```

然后访问：http://localhost:3000

## 常用命令

### 启动 UI

```bash
dagster dev -m src.crawler.dagster_jobs
```

### 运行作业

```bash
# 通过命令行运行
dagster job execute -j crawl_a_share_reports_job -m src.crawler.dagster_jobs

# 带配置运行
dagster job execute \
  -j crawl_a_share_reports_job \
  -m src.crawler.dagster_jobs \
  -c config.yaml
```

### 启用调度

```bash
dagster schedule start daily_crawl_schedule -m src.crawler.dagster_jobs
```

### 停止调度

```bash
dagster schedule stop daily_crawl_schedule -m src.crawler.dagster_jobs
```

### 查看调度状态

```bash
dagster schedule list -m src.crawler.dagster_jobs
```

## 配置文件示例

创建 `config.yaml`：

```yaml
ops:
  crawl_a_share_quarterly_reports:
    config:
      output_root: "./reports"  # 使用相对路径，避免权限问题
      workers: 6
      old_pdf_dir: null
```

**注意：** 在 macOS 上，避免使用 `/data` 路径，因为该路径可能是只读的。建议使用：
- 相对路径：`./reports`
- 项目路径：`/Users/han/PycharmProjects/FinNet/reports`
- 或通过环境变量 `FINNET_DATA_ROOT` 设置

## 在 UI 中操作

1. **启动 UI**：运行 `bash scripts/start_dagster.sh`
2. **查看作业**：在主页点击 `crawl_a_share_reports_job`
3. **手动触发**：点击右上角 "Launch Run" 按钮
4. **查看结果**：在 "Runs" 标签页查看运行历史
5. **启用调度**：在 "Schedules" 标签页启动 `daily_crawl_schedule`

## 作业说明

### crawl_a_share_reports_job

- **功能**：爬取A股季度报告并验证
- **流程**：爬取 → 验证 → 存储
- **调度**：每天凌晨2点（需手动启用）

## MinIO 配置

要启用 MinIO 上传功能，需要设置环境变量：

```bash
# 方式1：使用 .env 文件（推荐）
# 在项目根目录创建 .env 文件，添加：
USE_MINIO=true
MINIO_ENDPOINT=http://localhost:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=admin123456
MINIO_BUCKET=company-datalake

# 方式2：手动设置环境变量
export USE_MINIO=true
export MINIO_ENDPOINT=http://localhost:9000
export MINIO_ACCESS_KEY=admin
export MINIO_SECRET_KEY=admin123456
export MINIO_BUCKET=company-datalake
```

详细说明请参考：[Dagster MinIO 配置指南](DAGSTER_MINIO_SETUP.md)

## 故障排查

### UI 无法启动

```bash
# 检查依赖
pip install dagster dagster-webserver

# 检查文件是否存在
ls -l src/crawler/dagster_jobs.py

# 如果模块导入失败，使用文件方式启动
export PYTHONPATH=".:$PYTHONPATH"
dagster dev -f src/crawler/dagster_jobs.py
```

### 文件没有上传到 MinIO

1. 检查环境变量是否设置：`echo $USE_MINIO`
2. 检查 MinIO 服务是否运行：`docker-compose ps minio`
3. 查看 Dagster 日志中的 MinIO 配置信息
4. 参考 [Dagster MinIO 配置指南](DAGSTER_MINIO_SETUP.md)

### 作业运行失败

1. 在 UI 中查看运行日志
2. 检查公司列表文件是否存在：`src/crawler/zh/company_list.csv`
3. 检查输出目录权限

## 更多信息

详细文档请参考：[DAGSTER_GUIDE.md](DAGSTER_GUIDE.md)
