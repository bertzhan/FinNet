# 删除 MinIO Bucket 指南

本文档介绍如何删除 MinIO 中的 `company-datalake` bucket。

## 方法 1: 使用 Python 脚本（推荐）

### 基本用法

```bash
# 删除空的 bucket
python scripts/delete_minio_bucket.py company-datalake

# 强制删除（包括所有对象）
python scripts/delete_minio_bucket.py company-datalake --force

# 跳过确认提示（谨慎使用）
python scripts/delete_minio_bucket.py company-datalake --force --confirm
```

### 脚本功能

- ✅ 检查 bucket 是否存在
- ✅ 检查 bucket 是否为空（非强制模式）
- ✅ 支持强制删除（先删除所有对象，再删除 bucket）
- ✅ 安全确认提示
- ✅ 详细的日志输出

## 方法 2: 使用 MinIO 客户端 (mc)

### 安装 MinIO 客户端

```bash
# macOS
brew install minio/stable/mc

# Linux
wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc
sudo mv mc /usr/local/bin/
```

### 配置 MinIO 客户端

```bash
# 添加 MinIO 服务器别名
mc alias set local http://localhost:9000 admin admin123456

# 或者使用环境变量中的配置
mc alias set local \
  http://${MINIO_ENDPOINT} \
  ${MINIO_ACCESS_KEY} \
  ${MINIO_SECRET_KEY}
```

### 删除 Bucket

```bash
# 列出所有 bucket
mc ls local/

# 删除空的 bucket
mc rb local/company-datalake

# 强制删除（包括所有对象）
mc rb --force local/company-datalake
```

## 方法 3: 使用 MinIO Web UI

1. 打开 MinIO Web UI（通常是 http://localhost:9001）
2. 登录（使用 `MINIO_ROOT_USER` 和 `MINIO_ROOT_PASSWORD`）
3. 在左侧导航栏找到 `company-datalake` bucket
4. 点击 bucket 名称进入详情页
5. 点击右上角的 "..." 菜单
6. 选择 "Delete Bucket"
7. 确认删除

**注意**: 如果 bucket 不为空，需要先删除所有对象。

## 方法 4: 使用 Python 代码

```python
from minio import Minio
from minio.error import S3Error

# 创建客户端
client = Minio(
    "localhost:9000",
    access_key="admin",
    secret_key="admin123456",
    secure=False
)

bucket_name = "company-datalake"

# 检查 bucket 是否存在
if client.bucket_exists(bucket_name):
    # 删除所有对象（如果需要）
    objects = client.list_objects(bucket_name, recursive=True)
    for obj in objects:
        client.remove_object(bucket_name, obj.object_name)
    
    # 删除 bucket
    client.remove_bucket(bucket_name)
    print(f"✅ 成功删除 bucket '{bucket_name}'")
else:
    print(f"Bucket '{bucket_name}' 不存在")
```

## 注意事项

⚠️ **重要警告**:

1. **数据备份**: 删除 bucket 前，请确保已备份重要数据
2. **不可恢复**: 删除操作不可恢复，请谨慎操作
3. **权限要求**: 需要 MinIO 管理员权限才能删除 bucket
4. **空 bucket**: 非强制模式下，只能删除空的 bucket

## 删除前检查

在删除前，建议先检查 bucket 的内容：

```bash
# 使用 Python 脚本检查
python scripts/check_minio_files.sh

# 使用 mc 客户端检查
mc ls local/company-datalake --recursive

# 使用 Python 代码检查
python -c "
from src.storage.object_store.minio_client import MinIOClient
client = MinIOClient()
objects = client.list_objects('company-datalake')
for obj in objects:
    print(obj.object_name)
"
```

## 常见问题

### Q: 删除时提示 "bucket 不为空"

A: 使用 `--force` 参数强制删除：
```bash
python scripts/delete_minio_bucket.py company-datalake --force
```

### Q: 删除失败，提示权限不足

A: 检查 MinIO 访问密钥是否有管理员权限，或使用 root 用户。

### Q: 如何批量删除多个 bucket？

A: 可以修改脚本或使用循环：
```bash
for bucket in company-datalake old-bucket-1 old-bucket-2; do
    python scripts/delete_minio_bucket.py $bucket --force --confirm
done
```

## 相关脚本

- `scripts/delete_minio_bucket.py` - 删除 bucket 脚本
- `scripts/check_minio_files.sh` - 检查 bucket 内容
- `scripts/check_minio_config.py` - 检查 MinIO 配置
