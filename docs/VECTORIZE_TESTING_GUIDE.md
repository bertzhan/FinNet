# 向量化作业测试指南

## 概述

本文档说明如何测试向量化作业的各个组件和完整流程。

## 前置条件

1. **环境配置**
   - PostgreSQL 数据库已启动并配置
   - Milvus 向量数据库已启动并配置
   - 已安装依赖：`pip install sentence-transformers`

2. **数据准备**
   - 已有已分块的文档（DocumentChunk 记录）
   - 分块的 `vector_id` 字段为 NULL（未向量化）

## 测试步骤

### 1. 快速检查（不依赖 Embedding 模型）

运行快速检查脚本，验证数据库和 Milvus 连接：

```bash
python tests/test_vectorize_quick.py
```

**检查内容**：
- 未向量化分块数量
- 已向量化分块数量
- Milvus Collection 状态
- Dagster scan_op 功能

### 2. 完整测试（需要 Embedding 模型）

运行完整测试脚本：

```bash
python tests/test_vectorize_job.py
```

**测试内容**：
1. **BGE Embedder 服务测试**
   - 模型初始化
   - 单个文本向量化
   - 批量文本向量化

2. **未向量化分块检查**
   - 查询数据库中的未向量化分块
   - 显示分块信息

3. **Milvus Collection 检查**
   - 检查 Collection 是否存在
   - 获取向量统计信息

4. **单个分块向量化测试**
   - 向量化单个分块
   - 验证数据库更新

5. **批量向量化测试**
   - 批量向量化多个分块
   - 验证批量处理性能

6. **Dagster Ops 测试**
   - scan_unvectorized_chunks_op
   - vectorize_chunks_op
   - validate_vectorize_results_op

### 3. 手动测试单个组件

#### 3.1 测试 Embedder 服务

```python
from src.processing.ai.embedding.bge_embedder import get_embedder

# 初始化
embedder = get_embedder()
print(f"模型: {embedder.get_model_name()}")
print(f"维度: {embedder.get_model_dim()}")

# 单个文本向量化
text = "这是一个测试文本"
vector = embedder.embed_text(text)
print(f"向量维度: {len(vector)}")

# 批量向量化
texts = ["文本1", "文本2", "文本3"]
vectors = embedder.embed_batch(texts)
print(f"批量向量数量: {len(vectors)}")
```

#### 3.2 测试 Vectorizer 服务

```python
from src.processing.ai.embedding.vectorizer import get_vectorizer
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud

# 获取未向量化的分块
pg_client = get_postgres_client()
with pg_client.get_session() as session:
    chunks = session.query(DocumentChunk).filter(
        DocumentChunk.vector_id.is_(None)
    ).limit(5).all()
    
    chunk_ids = [chunk.id for chunk in chunks]

# 向量化
vectorizer = get_vectorizer()
result = vectorizer.vectorize_chunks(chunk_ids)

print(f"成功: {result['vectorized_count']}")
print(f"失败: {result['failed_count']}")
```

#### 3.3 测试 Dagster 作业

在 Dagster UI 中：

1. **手动触发扫描**：
   - 运行 `scan_unvectorized_chunks_op`
   - 配置：`batch_size=10, limit=20`

2. **手动触发向量化**：
   - 运行 `vectorize_chunks_op`
   - 使用 scan_op 的输出作为输入

3. **运行完整作业**：
   - 运行 `vectorize_documents_job`
   - 或使用传感器 `manual_trigger_vectorize_sensor`

### 4. 验证结果

#### 4.1 检查数据库更新

```python
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import DocumentChunk

pg_client = get_postgres_client()
with pg_client.get_session() as session:
    # 检查已向量化的分块
    vectorized = session.query(DocumentChunk).filter(
        DocumentChunk.vector_id.isnot(None)
    ).count()
    
    print(f"已向量化分块数: {vectorized}")
    
    # 查看具体分块信息
    chunk = session.query(DocumentChunk).filter(
        DocumentChunk.vector_id.isnot(None)
    ).first()
    
    if chunk:
        print(f"vector_id: {chunk.vector_id}")
        print(f"embedding_model: {chunk.embedding_model}")
        print(f"vectorized_at: {chunk.vectorized_at}")
```

#### 4.2 检查 Milvus 向量

```python
from src.storage.vector.milvus_client import get_milvus_client
from src.common.constants import MilvusCollection

milvus_client = get_milvus_client()
stats = milvus_client.get_collection_stats(MilvusCollection.DOCUMENTS)
print(f"向量数量: {stats.get('row_count', 0)}")
```

## 常见问题

### 1. 没有未向量化的分块

**原因**：
- 所有分块都已向量化
- 还没有分块数据（需要先运行分块作业）

**解决**：
- 运行分块作业：`chunk_documents_job`
- 或强制重新向量化：`force_revectorize=True`

### 2. Embedding 模型加载失败

**原因**：
- 模型文件不存在
- 网络问题（首次下载模型）
- 内存不足

**解决**：
- 检查模型路径配置：`EMBEDDING_MODEL`, `BGE_MODEL_PATH`
- 确保有足够的磁盘空间和内存
- 使用本地模型路径

### 3. Milvus 连接失败

**原因**：
- Milvus 服务未启动
- 连接配置错误

**解决**：
- 检查 Milvus 服务状态
- 验证配置：`MILVUS_HOST`, `MILVUS_PORT`

### 4. 向量维度不匹配

**原因**：
- Collection 已存在但维度不同
- 切换了 Embedding 模型

**解决**：
- 删除旧 Collection 重新创建
- 或使用 `scripts/init_milvus_collection.py` 初始化

## 性能测试

### 批量大小测试

测试不同批量大小的性能：

```python
batch_sizes = [16, 32, 64, 128]
for batch_size in batch_sizes:
    # 设置批量大小
    import os
    os.environ['EMBEDDING_BATCH_SIZE'] = str(batch_size)
    
    # 重新初始化
    from src.processing.ai.embedding.bge_embedder import get_embedder
    embedder = get_embedder()
    
    # 测试性能
    import time
    texts = ["测试文本"] * 100
    start = time.time()
    vectors = embedder.embed_batch(texts)
    elapsed = time.time() - start
    print(f"批量大小 {batch_size}: {elapsed:.2f}秒")
```

### GPU vs CPU 性能对比

```python
# CPU 测试
import os
os.environ['EMBEDDING_DEVICE'] = 'cpu'
embedder_cpu = get_embedder()

# GPU 测试（如果有GPU）
os.environ['EMBEDDING_DEVICE'] = 'cuda'
embedder_gpu = get_embedder()

# 性能对比...
```

## 测试检查清单

- [ ] Embedder 服务初始化成功
- [ ] 单个文本向量化正常
- [ ] 批量向量化正常
- [ ] 能找到未向量化的分块
- [ ] Milvus Collection 存在或可创建
- [ ] 单个分块向量化成功
- [ ] 数据库记录更新成功
- [ ] Milvus 向量插入成功
- [ ] 批量向量化成功
- [ ] Dagster scan_op 正常
- [ ] Dagster vectorize_op 正常
- [ ] Dagster validate_op 正常
- [ ] 完整作业流程正常

## 下一步

测试通过后，可以：

1. **启用定时调度**：
   - 在 Dagster UI 中启用 `hourly_vectorize_schedule` 或 `daily_vectorize_schedule`

2. **监控向量化进度**：
   - 查看 Dagster UI 中的作业执行历史
   - 检查数据库中的 `vectorized_at` 字段

3. **集成到 RAG 应用**：
   - 使用向量化后的分块进行检索
   - 实现 RAG 检索服务
