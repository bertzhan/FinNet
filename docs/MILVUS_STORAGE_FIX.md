# Milvus 存储空间问题修复指南

## 问题描述

Milvus 报错：
```
Storage backend has reached its minimum free drive threshold. Please delete a few objects to proceed.
```

## 原因分析

Milvus 使用 MinIO 作为存储后端。MinIO 默认的最小可用空间阈值是 **5%**，当磁盘可用空间低于这个阈值时，MinIO 会拒绝写入操作，导致 Milvus 无法正常工作。

即使磁盘空间充足（如 39% 可用），如果 MinIO 的阈值设置过严，也可能触发此错误。

## 解决方案

### 方案1: 调整 MinIO 最小可用空间阈值（推荐）

#### 方法1.1: 通过环境变量（已修改 docker-compose.yml）

已在 `docker-compose.yml` 中添加配置，重启服务即可：

```bash
docker-compose restart minio-milvus milvus
```

#### 方法1.2: 通过 MinIO 客户端动态调整

```bash
# 安装 MinIO 客户端（如果未安装）
brew install minio/stable/mc  # macOS
# 或
wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc
sudo mv mc /usr/local/bin/

# 配置 MinIO 别名
mc alias set milvus-minio http://localhost:9000 minioadmin minioadmin

# 设置最小可用空间阈值为 1%（默认是 5%）
mc admin config set milvus-minio storage_class standard EC:2

# 重启 MinIO 服务使配置生效
docker restart finnet-minio-milvus
```

### 方案2: 清理 Milvus 数据

#### 2.1 删除不需要的 Collection

```bash
# 列出所有 Collections
python scripts/clean_milvus_storage.py --stats

# 交互式删除
python scripts/clean_milvus_storage.py --interactive

# 删除指定 Collection
python scripts/clean_milvus_storage.py --drop collection_name1 collection_name2
```

#### 2.2 清理 Milvus 日志

```bash
# 清理容器内日志
docker exec finnet-milvus sh -c 'find /var/lib/milvus/logs -name "*.log" -type f -exec truncate -s 0 {} \;'

# 或删除旧日志
docker exec finnet-milvus sh -c 'find /var/lib/milvus/logs -name "*.log" -mtime +7 -delete'
```

#### 2.3 清理 MinIO Milvus 存储

```bash
# 进入 MinIO 容器
docker exec -it finnet-minio-milvus sh

# 查看存储使用情况
du -sh /data

# 清理不需要的对象（需要 MinIO 客户端）
mc ls milvus-minio/milvus-bucket --recursive
mc rm milvus-minio/milvus-bucket/path/to/old/data --recursive
```

### 方案3: 扩展存储空间

如果磁盘空间确实不足：

1. **增加磁盘容量**
2. **迁移到更大的存储卷**
3. **使用外部存储**（如 NFS、云存储）

### 方案4: 重启服务（临时方案）

有时重启可以释放一些临时文件：

```bash
docker restart finnet-milvus finnet-minio-milvus finnet-etcd
```

## 验证修复

### 1. 检查存储空间

```bash
python scripts/check_milvus_storage.py
```

### 2. 测试 Milvus 连接

```bash
python scripts/check_milvus_connection_simple.py
```

### 3. 测试向量化 Job

运行一个简单的向量化任务，确认 Milvus 可以正常写入数据。

## 预防措施

1. **监控磁盘空间**：定期检查磁盘使用情况
2. **设置告警**：当磁盘使用超过 80% 时发送告警
3. **定期清理**：定期清理不需要的 Collection 和日志
4. **合理配置阈值**：根据实际需求调整 MinIO 的最小可用空间阈值

## 相关脚本

- `scripts/check_milvus_storage.py` - 检查存储空间使用情况
- `scripts/check_milvus_connection_simple.py` - 检查 Milvus 连接
- `scripts/clean_milvus_storage.py` - 清理 Milvus 数据
- `scripts/fix_milvus_storage.py` - 修复存储问题的综合脚本

## 参考文档

- [MinIO Storage Class Configuration](https://min.io/docs/minio/linux/administration/object-management/storage-class.html)
- [Milvus Storage Configuration](https://milvus.io/docs/configure-docker.md)
