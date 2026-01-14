# MinIO 上传问题排查指南

## 🔍 问题：Job 运行完没有存入 MinIO

### 可能的原因

1. **MinIO 客户端初始化失败**
   - 检查：查看日志中是否有 "MinIO 客户端初始化失败"
   - 解决：检查环境变量和 MinIO 服务状态

2. **enable_minio 配置为 False**
   - 检查：在 Dagster UI 中查看配置
   - 解决：确保 `enable_minio: true`

3. **MinIO 服务未运行**
   - 检查：`docker-compose ps minio`
   - 解决：启动服务 `docker-compose up -d minio`

4. **上传失败但被静默处理**
   - 检查：查看日志中的警告信息
   - 解决：检查 MinIO 连接和权限

## 🚀 快速诊断

运行诊断脚本：

```bash
bash scripts/diagnose_minio_upload.sh
```

这个脚本会检查：
1. ✅ 环境变量配置
2. ✅ MinIO 服务状态
3. ✅ MinIO 连接测试
4. ✅ 文件上传测试
5. ✅ 爬虫配置检查

## 📋 检查清单

### 1. 检查 MinIO 服务

```bash
# 检查服务状态
docker-compose ps minio

# 查看日志
docker-compose logs minio

# 访问 MinIO Console
# http://localhost:9001
# 默认账号: admin / admin123456
```

### 2. 检查环境变量

确保 `.env` 文件中有：

```bash
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=admin123456
MINIO_BUCKET=company-datalake
```

### 3. 检查 Dagster 配置

在 Dagster UI 中，确保配置中 `enable_minio: true`：

```yaml
ops:
  crawl_a_share_reports_op:
    config:
      enable_minio: true  # ✅ 确保为 true
      enable_postgres: true
```

### 4. 查看日志

在 Dagster UI 中查看运行日志，查找：

- ✅ `MinIO 客户端初始化成功` - 客户端正常
- ✅ `MinIO 上传成功: bronze/...` - 上传成功
- ⚠️ `MinIO 上传失败: ...` - 上传失败
- ❌ `MinIO 上传异常: ...` - 上传异常

## 🔧 常见问题解决

### 问题1: MinIO 客户端初始化失败

**错误信息**：
```
MinIO 客户端初始化失败: ...
```

**解决方法**：
1. 检查 MinIO 服务是否运行
2. 检查环境变量是否正确
3. 检查网络连接

### 问题2: 上传失败但没有错误信息

**可能原因**：
- MinIO 连接超时
- 权限不足
- 桶不存在

**解决方法**：
1. 运行诊断脚本：`bash scripts/diagnose_minio_upload.sh`
2. 检查 MinIO Console：http://localhost:9001
3. 手动测试上传

### 问题3: enable_minio 配置被忽略

**检查**：
```python
# 在代码中检查
crawler = ReportCrawler(enable_minio=True)
print(crawler.enable_minio)  # 应该是 True
print(crawler.minio_client)  # 应该不是 None
```

**解决**：
确保在 Dagster 配置中明确设置 `enable_minio: true`

## 🧪 手动测试上传

### Python 测试脚本

```python
from src.storage.object_store.minio_client import MinIOClient
import tempfile

# 创建客户端
client = MinIOClient()

# 创建测试文件
with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
    f.write(b"test content")
    test_file = f.name

# 上传
success = client.upload_file(
    object_name="test/upload_test.txt",
    file_path=test_file
)

print(f"上传结果: {success}")

# 验证
exists = client.file_exists("test/upload_test.txt")
print(f"文件存在: {exists}")

# 清理
import os
os.unlink(test_file)
client.delete_file("test/upload_test.txt")
```

## 📊 验证上传结果

### 方式1: MinIO Console

1. 访问 http://localhost:9001
2. 登录（admin / admin123456）
3. 进入 `company-datalake` 桶
4. 查看 `bronze/a_share/...` 目录

### 方式2: Python 脚本

```python
from src.storage.object_store.minio_client import MinIOClient

client = MinIOClient()

# 列出文件
objects = client.list_objects(prefix="bronze/a_share/")
for obj in objects:
    print(f"{obj.object_name} ({obj.size} bytes)")
```

### 方式3: 命令行工具

```bash
# 使用 mc (MinIO Client)
mc ls local/company-datalake/bronze/a_share/
```

## 🔗 相关文档

- [STORAGE_LAYER_GUIDE.md](STORAGE_LAYER_GUIDE.md) - 存储层使用指南
- [DAGSTER_INTEGRATION.md](DAGSTER_INTEGRATION.md) - Dagster 集成指南

---

*最后更新: 2025-01-13*
