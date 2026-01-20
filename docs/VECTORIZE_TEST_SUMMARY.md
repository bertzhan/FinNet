# 向量化作业测试总结

## 当前状态

✅ **代码实现已完成**：
- BGE Embedder 服务 (`src/processing/ai/embedding/bge_embedder.py`)
- Vectorizer 服务 (`src/processing/ai/embedding/vectorizer.py`)
- Milvus 客户端 UUID 支持 (`src/storage/vector/milvus_client.py`)
- Dagster 向量化作业 (`src/processing/compute/dagster/jobs/vectorize_jobs.py`)
- 测试脚本和文档

⚠️ **测试环境问题**：
- torch 库权限问题（Anaconda 环境）
- pymilvus 可能未安装

## 需要手动执行的步骤

### 1. 安装依赖

```bash
# 安装向量化相关依赖
pip install pymilvus sentence-transformers

# 或使用 requirements.txt
pip install -r requirements.txt
```

### 2. 解决权限问题（如果遇到）

如果遇到 torch 权限问题，可以尝试：

```bash
# 方案1：重新安装 torch
pip uninstall torch
pip install torch

# 方案2：使用 conda
conda install pytorch -c pytorch

# 方案3：检查并修复文件权限
chmod 644 /Users/han/Anaconda3/anaconda3/lib/python3.12/site-packages/torch/_environment.py
```

### 3. 验证安装

```bash
# 验证依赖安装
python -c "import torch; print('✅ torch OK')"
python -c "import sentence_transformers; print('✅ sentence-transformers OK')"
python -c "import pymilvus; print('✅ pymilvus OK')"
```

### 4. 运行测试

#### 4.1 环境检查

```bash
python scripts/check_vectorize_environment.py
```

#### 4.2 简单测试

```bash
python examples/test_vectorize_simple.py
```

#### 4.3 快速测试（不依赖模型）

```bash
python tests/test_vectorize_quick.py
```

#### 4.4 完整测试

```bash
python tests/test_vectorize_job.py
```

### 5. 在 Dagster UI 中测试

1. **启动 Dagster UI**：
   ```bash
   dagster dev
   ```

2. **运行向量化作业**：
   - 在 UI 中找到 `vectorize_documents_job`
   - 点击 "Launch Run"
   - 配置参数（可选）：
     ```yaml
     ops:
       scan_unvectorized_chunks_op:
         config:
           batch_size: 10
           limit: 50
       vectorize_chunks_op:
         config:
           force_revectorize: false
     ```

3. **或使用传感器**：
   - 找到 `manual_trigger_vectorize_sensor`
   - 点击 "Tick" 触发

## 测试检查清单

- [ ] 依赖安装完成（pymilvus, sentence-transformers）
- [ ] torch 权限问题已解决
- [ ] Milvus 服务已启动
- [ ] PostgreSQL 数据库已连接
- [ ] 有未向量化的分块数据
- [ ] Embedder 初始化成功
- [ ] Vectorizer 初始化成功
- [ ] 单个分块向量化成功
- [ ] 批量向量化成功
- [ ] 数据库更新成功
- [ ] Milvus 向量存储成功
- [ ] Dagster 作业运行成功

## 预期测试结果

### 成功情况

```
✅ Embedder 初始化成功
   模型名称: bge-large-zh-v1.5
   向量维度: 1024

✅ 向量化成功
   文本长度: 50 字符
   向量维度: 1024

✅ 批量向量化成功
   输入文本数: 5
   输出向量数: 5

✅ Vectorizer 初始化成功

✅ 找到 10 个未向量化的分块

✅ 向量化完成
   成功数量: 10
   失败数量: 0

✅ 数据库更新验证
   已更新分块数: 10

✅ Milvus Collection 存在
   向量数量: 10
```

### 常见问题

1. **没有未向量化的分块**
   - 解决：先运行分块作业 `chunk_documents_job`

2. **Milvus 连接失败**
   - 解决：检查 Milvus 服务是否启动

3. **模型下载失败**
   - 解决：检查网络连接，或使用本地模型路径

4. **向量维度不匹配**
   - 解决：删除旧 Collection，让 Vectorizer 自动创建新的

## 代码文件位置

- **Embedder**: `src/processing/ai/embedding/bge_embedder.py`
- **Vectorizer**: `src/processing/ai/embedding/vectorizer.py`
- **Milvus 客户端**: `src/storage/vector/milvus_client.py`
- **Dagster 作业**: `src/processing/compute/dagster/jobs/vectorize_jobs.py`
- **测试脚本**: `examples/test_vectorize_simple.py`, `tests/test_vectorize_*.py`

## 下一步

测试通过后，可以：

1. **启用定时调度**：在 Dagster UI 中启用 `hourly_vectorize_schedule` 或 `daily_vectorize_schedule`

2. **监控向量化进度**：查看 Dagster UI 中的作业执行历史

3. **集成到 RAG 应用**：使用向量化后的分块进行检索

## 参考文档

- [向量化测试指南](VECTORIZE_TESTING_GUIDE.md)
- [向量化测试状态](VECTORIZE_TEST_STATUS.md)
