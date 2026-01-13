# Dagster 中使用 MinIO 配置指南

## 问题说明

当通过 Dagster 运行爬虫作业时，文件可能没有上传到 MinIO，这是因为 MinIO 上传功能依赖于环境变量配置。

## 解决方案

### 方式1：使用启动脚本（推荐）

启动脚本会自动加载 `.env` 文件中的环境变量：

```bash
bash scripts/start_dagster.sh
```

### 方式2：手动设置环境变量

在启动 Dagster 之前设置环境变量：

```bash
# 启用 MinIO
export USE_MINIO=true
export MINIO_ENDPOINT=http://localhost:9000
export MINIO_ACCESS_KEY=admin
export MINIO_SECRET_KEY=admin123456
export MINIO_BUCKET=company-datalake

# 启动 Dagster
dagster dev -f src/crawler/dagster_jobs.py
```

### 方式3：创建 .env 文件

在项目根目录创建 `.env` 文件（参考 `env.example`）：

```bash
# MinIO对象存储配置（用于数据湖存储）
USE_MINIO=true
MINIO_ENDPOINT=http://localhost:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=admin123456
MINIO_BUCKET=company-datalake
```

然后使用启动脚本，它会自动加载 `.env` 文件。

## 验证配置

### 1. 检查 MinIO 服务是否运行

```bash
# 使用 Docker Compose
docker-compose ps minio

# 或检查端口
curl http://localhost:9000/minio/health/live
```

### 2. 检查环境变量

在 Dagster UI 中运行作业时，查看日志输出：

- 如果看到 `✓ MinIO 已启用: http://localhost:9000`，说明配置正确
- 如果看到 `ℹ MinIO 未启用`，说明需要设置环境变量

### 3. 检查上传结果

1. 访问 MinIO Console: http://localhost:9001
2. 登录（用户名/密码在 docker-compose.yml 中配置）
3. 查看 `company-datalake` bucket
4. 检查文件是否在 `bronze/zh_stock/quarterly_reports/` 路径下

## 常见问题

### Q: 为什么文件没有上传到 MinIO？

**A:** 可能的原因：

1. **环境变量未设置**
   - 检查 `USE_MINIO` 是否为 `true`
   - 检查 `MINIO_ENDPOINT`、`MINIO_ACCESS_KEY`、`MINIO_SECRET_KEY` 是否设置

2. **MinIO 服务未运行**
   - 运行 `docker-compose up -d minio` 启动 MinIO

3. **配置错误**
   - 检查 MinIO 访问密钥是否正确
   - 检查端点地址是否正确

### Q: 如何在 Dagster UI 中配置 MinIO？

**A:** 目前 MinIO 配置只能通过环境变量设置，不支持在 Dagster UI 中直接配置。建议：

1. 创建 `.env` 文件
2. 使用启动脚本自动加载
3. 或者在系统环境变量中设置

### Q: 文件上传失败怎么办？

**A:** 检查日志：

1. 在 Dagster UI 中查看运行日志
2. 查找 MinIO 相关的错误信息
3. 检查 `reports/minio_upload_failed.csv` 文件（如果存在）

上传失败不会影响文件下载，文件仍然会保存到本地。

## 配置示例

### 完整的 .env 文件示例

```bash
# MinIO 配置（Docker Compose）
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=admin123456

# MinIO对象存储配置（用于数据湖存储）
USE_MINIO=true
MINIO_ENDPOINT=http://localhost:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=admin123456
MINIO_BUCKET=company-datalake

# 爬虫配置
FINNET_DATA_ROOT=./reports
CRAWLER_WORKERS=6
```

### 启动 MinIO 服务

```bash
# 使用 Docker Compose 启动
docker-compose up -d minio

# 检查状态
docker-compose ps minio

# 查看日志
docker-compose logs minio
```

## 文件上传流程

1. **下载文件**：爬虫下载 PDF 文件到本地
2. **立即上传**：如果 `USE_MINIO=true`，文件下载完成后立即上传到 MinIO
3. **保存路径**：文件在 MinIO 中的路径格式：
   ```
   bronze/zh_stock/quarterly_reports/{year}/{quarter}/{stock_code}/{filename}
   ```
4. **元数据**：上传时包含元数据（股票代码、年份、季度、发布日期等）

## 注意事项

1. **上传失败不影响下载**：如果 MinIO 上传失败，文件仍然会保存到本地
2. **环境变量优先级**：系统环境变量 > `.env` 文件 > 默认值
3. **多进程上传**：每个工作进程独立上传文件，互不干扰
4. **去重检查**：如果文件已在 MinIO 中存在，会跳过上传

## 相关文档

- [Dagster 使用指南](DAGSTER_GUIDE.md)
- [Dagster 快速开始](DAGSTER_QUICKSTART.md)
- [MinIO 设置说明](../README.md)
