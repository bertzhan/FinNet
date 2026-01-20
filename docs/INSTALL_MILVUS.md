# Milvus 依赖安装指南

## 概述

Milvus 是向量数据库，用于存储和检索 Embedding 向量。需要安装 `pymilvus` Python 客户端库。

## 安装步骤

### 1. 安装 pymilvus

#### 方式1：使用 pip（推荐）

```bash
# 激活 conda 环境
conda activate finnet

# 安装 pymilvus
pip install pymilvus

# 或指定版本
pip install pymilvus>=2.3.0
```

#### 方式2：从 requirements.txt 安装

```bash
conda activate finnet
pip install -r requirements.txt
```

#### 方式3：使用 conda（如果可用）

```bash
conda activate finnet
conda install -c conda-forge pymilvus
```

### 2. 验证安装

```bash
conda activate finnet
python -c "import pymilvus; print(f'✅ pymilvus 版本: {pymilvus.__version__}')"
```

### 3. 检查 Milvus 服务

确保 Milvus 服务已启动：

```bash
# 检查 Milvus 是否运行（如果使用 Docker）
docker ps | grep milvus

# 或检查端口（默认 19530）
netstat -an | grep 19530
```

## 配置

在 `.env` 文件中配置 Milvus 连接信息：

```bash
# Milvus 配置
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_USER=root
MILVUS_PASSWORD=Milvus
```

## 测试连接

运行测试脚本验证连接：

```python
from src.storage.vector.milvus_client import get_milvus_client

try:
    client = get_milvus_client()
    collections = client.list_collections()
    print(f"✅ Milvus 连接成功")
    print(f"   Collections: {collections}")
except Exception as e:
    print(f"❌ Milvus 连接失败: {e}")
```

## 常见问题

### Q1: 安装失败

**错误**: `ModuleNotFoundError: No module named 'pymilvus'`

**解决**:
```bash
# 确保在正确的环境中
conda activate finnet
pip install pymilvus
```

### Q2: 连接失败

**错误**: `Connection refused` 或 `Cannot connect to Milvus`

**解决**:
1. 检查 Milvus 服务是否启动
2. 检查 `MILVUS_HOST` 和 `MILVUS_PORT` 配置
3. 检查防火墙设置

### Q3: 版本不兼容

**解决**:
```bash
# 安装指定版本
pip install pymilvus==2.3.0
```

## 快速安装命令

```bash
# 一键安装
conda activate finnet && pip install pymilvus && python -c "import pymilvus; print('✅ 安装成功')"
```

## 下一步

安装完成后：

1. **测试连接**：
   ```bash
   python -c "from src.storage.vector.milvus_client import get_milvus_client; get_milvus_client()"
   ```

2. **运行完整测试**：
   ```bash
   python examples/test_vectorize_simple.py
   ```

3. **在 Dagster 中运行向量化作业**：
   - 运行 `vectorize_documents_job`
