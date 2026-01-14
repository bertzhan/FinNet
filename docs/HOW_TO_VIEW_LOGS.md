# 如何查看日志

## 📋 概述

FinNet 项目的日志分布在多个位置，根据不同的运行方式，日志查看方法也不同。

## 🔍 方法1：Dagster UI 中查看日志（推荐）

### 步骤

1. **启动 Dagster UI**：
   ```bash
   bash scripts/start_dagster.sh
   ```
   或
   ```bash
   dagster dev -m src.processing.compute.dagster
   ```

2. **访问 UI**：
   打开浏览器访问：**http://localhost:3000**

3. **查看运行日志**：
   - 点击左侧 **"Runs"** 标签页
   - 找到你要查看的运行记录（最新的在最上面）
   - 点击运行记录进入详情页
   - 在详情页中可以看到：
     - **Logs** 标签页：所有日志输出
     - **Graph** 标签页：执行流程图
     - **Assets** 标签页：数据资产信息

4. **搜索关键日志**：
   在日志页面使用 `Ctrl+F` (Mac: `Cmd+F`) 搜索：
   - `MinIO` - 查找 MinIO 相关日志
   - `上传成功` - 查找上传成功的记录
   - `上传失败` - 查找上传失败的记录
   - `爬虫配置` - 查找配置信息
   - `ERROR` - 查找错误信息

### 关键日志示例

```
爬虫配置: enable_minio=True, enable_postgres=True, workers=4
✅ MinIO 已启用且客户端初始化成功
生成 100 个爬取任务（50 家公司 × 2 个季度）
开始爬取: 000001 2023 Q3
✅ MinIO 上传成功: bronze/a_share/quarterly_reports/2023/Q3/000001/000001_2023_Q3.pdf
爬取完成: 成功 95, 失败 5
MinIO 上传: 成功 95, 失败 0
```

## 🔍 方法2：命令行查看 Dagster 日志

### 查看实时日志

```bash
# 启动 Dagster 时会自动显示日志
dagster dev -m src.processing.compute.dagster
```

### 查看特定 Job 的执行日志

```bash
# 执行 Job 并查看输出
dagster job execute \
  -j crawl_a_share_reports_job \
  -m src.processing.compute.dagster \
  --log-level DEBUG
```

## 🔍 方法3：查看本地日志文件

### 爬虫日志文件

爬虫模块可能会写入日志文件：

```bash
# 查看爬虫错误日志
cat src/ingestion/a_share/error.log

# 实时查看日志（如果存在）
tail -f src/ingestion/a_share/error.log
```

### Python 日志文件

如果配置了文件日志，通常在：
- `logs/` 目录下
- 或项目根目录的 `.log` 文件

```bash
# 查找日志文件
find . -name "*.log" -type f

# 查看最新的日志文件
ls -lt logs/*.log | head -1 | xargs tail -f
```

## 🔍 方法4：查看 Docker 容器日志

### MinIO 日志

```bash
# 查看 MinIO 容器日志
docker-compose logs minio

# 实时查看
docker-compose logs -f minio

# 查看最近100行
docker-compose logs --tail=100 minio
```

### PostgreSQL 日志

```bash
# 查看 PostgreSQL 容器日志
docker-compose logs postgres

# 实时查看
docker-compose logs -f postgres
```

### 所有服务日志

```bash
# 查看所有服务日志
docker-compose logs

# 实时查看所有服务日志
docker-compose logs -f
```

## 🔍 方法5：在代码中添加日志

### 临时调试日志

在代码中添加 `print` 语句（会在 Dagster UI 中显示）：

```python
logger = get_dagster_logger()
logger.info("这是信息日志")
logger.warning("这是警告日志")
logger.error("这是错误日志")
logger.debug("这是调试日志")
```

### 查看特定组件的日志

```python
# 在爬虫代码中
from src.common.logger import get_logger
logger = get_logger(__name__)
logger.info("爬虫日志")
```

## 📊 日志级别

### Dagster 日志级别

在启动时设置日志级别：

```bash
# DEBUG 级别（最详细）
dagster dev -m src.processing.compute.dagster --log-level DEBUG

# INFO 级别（默认）
dagster dev -m src.processing.compute.dagster --log-level INFO

# WARNING 级别（只显示警告和错误）
dagster dev -m src.processing.compute.dagster --log-level WARNING
```

## 🔎 查找特定信息的技巧

### 在 Dagster UI 中搜索

1. 打开运行详情页
2. 点击 **"Logs"** 标签页
3. 使用浏览器搜索功能（`Ctrl+F` / `Cmd+F`）
4. 搜索关键词：
   - `MinIO` - MinIO 相关
   - `上传` - 上传相关
   - `ERROR` - 错误信息
   - `WARNING` - 警告信息
   - `成功` - 成功信息
   - `失败` - 失败信息

### 使用 grep 过滤日志

```bash
# 从文件中过滤 MinIO 相关日志
grep -i "minio" logs/*.log

# 过滤错误日志
grep -i "error" logs/*.log

# 过滤上传相关日志
grep -i "上传" logs/*.log
```

## 📝 常见日志位置总结

| 日志类型 | 位置 | 查看方法 |
|---------|------|---------|
| Dagster Job 日志 | Dagster UI | http://localhost:3000 → Runs |
| 爬虫错误日志 | `src/ingestion/a_share/error.log` | `cat src/ingestion/a_share/error.log` |
| MinIO 日志 | Docker 容器 | `docker-compose logs minio` |
| PostgreSQL 日志 | Docker 容器 | `docker-compose logs postgres` |
| Python 应用日志 | `logs/` 目录 | `tail -f logs/*.log` |

## 🎯 快速检查清单

### 检查 MinIO 上传日志

1. ✅ 打开 Dagster UI: http://localhost:3000
2. ✅ 进入最新的运行记录
3. ✅ 搜索 `MinIO 上传`
4. ✅ 查看是否有 `✅ MinIO 上传成功` 或 `❌ MinIO 上传失败`

### 检查配置日志

1. ✅ 搜索 `爬虫配置`
2. ✅ 确认 `enable_minio=True`
3. ✅ 确认 `✅ MinIO 已启用`

### 检查错误日志

1. ✅ 搜索 `ERROR` 或 `错误`
2. ✅ 查看错误堆栈信息
3. ✅ 根据错误信息排查问题

## 💡 提示

- **实时查看**：使用 `-f` 参数可以实时查看日志更新
- **过滤日志**：使用 `grep` 或 Dagster UI 的搜索功能
- **日志级别**：设置 `DEBUG` 级别可以看到更详细的信息
- **保存日志**：在 Dagster UI 中可以导出日志

---

*最后更新: 2025-01-13*
