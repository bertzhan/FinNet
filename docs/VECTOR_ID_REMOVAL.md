# vector_id 字段移除说明

**日期**: 2026-01-28  
**变更**: 移除 `vector_id` 字段，改用 `vectorized_at` 判断是否已向量化

---

## 📝 变更原因

1. **Milvus Schema V2**: 使用 `chunk_id` 作为主键，不再需要单独的 `vector_id`
2. **数据冗余**: `vector_id` 现在就是 `chunk_id`，完全重复
3. **简化逻辑**: 使用 `vectorized_at` 时间戳更直观地表示向量化状态

---

## 🔄 变更内容

### 之前（使用 vector_id）
```python
# 判断是否已向量化
if chunk.vector_id is None:
    # 未向量化
else:
    # 已向量化

# 更新向量化状态
chunk.vector_id = chunk.id  # 存储 chunk_id
chunk.embedding_model = "openai/text-embedding-3-large"
chunk.vectorized_at = datetime.now()
```

### 之后（使用 vectorized_at）
```python
# 判断是否已向量化
if chunk.vectorized_at is None:
    # 未向量化
else:
    # 已向量化

# 更新向量化状态
chunk.embedding_model = "openai/text-embedding-3-large"
chunk.vectorized_at = datetime.now()
# 不再需要设置 vector_id
```

---

## 📋 修改的文件

### 1. `src/storage/metadata/crud.py`
- ✅ 新增 `update_chunk_embedding()` 函数（替代 `update_chunk_vector_id()`）
- ✅ `update_chunk_vector_id()` 标记为已废弃，保留以向后兼容
- ✅ `create_document_chunk()` 中的 `vector_id` 参数标记为已废弃

### 2. `src/processing/ai/embedding/vectorizer.py`
- ✅ 检查已向量化：`chunk.vector_id` → `chunk.vectorized_at`
- ✅ 更新向量化状态：调用 `update_chunk_embedding()` 而不是 `update_chunk_vector_id()`

### 3. `src/processing/compute/dagster/jobs/vectorize_jobs.py`
- ✅ 扫描未向量化分块：`vector_id IS NULL` → `vectorized_at IS NULL`
- ✅ 更新文档字符串和日志信息

### 4. `scripts/check_vectorized_chunks.py`
- ✅ 所有统计查询：`vector_id IS NOT NULL` → `vectorized_at IS NOT NULL`
- ✅ 更新注释和提示信息

---

## 🔍 查询变更对照表

| 操作 | 旧查询 | 新查询 |
|------|--------|--------|
| 检查是否已向量化 | `chunk.vector_id is not None` | `chunk.vectorized_at is not None` |
| 扫描未向量化分块 | `vector_id IS NULL` | `vectorized_at IS NULL` |
| 统计已向量化数量 | `COUNT(vector_id)` | `COUNT(vectorized_at)` |
| 按模型统计 | `WHERE vector_id IS NOT NULL` | `WHERE vectorized_at IS NOT NULL` |

---

## ✅ 优势

1. **逻辑更清晰**: `vectorized_at` 明确表示"什么时候向量化的"
2. **减少冗余**: 不再存储重复的 `chunk_id`
3. **语义更准确**: 时间戳比 ID 更能表达状态
4. **简化代码**: 不需要维护 `vector_id` 字段

---

## ⚠️ 注意事项

### 数据库迁移

如果现有数据库中有 `vector_id` 字段的数据，需要迁移：

```sql
-- 将已向量化的记录的 vectorized_at 设置为当前时间
UPDATE document_chunks 
SET vectorized_at = NOW() 
WHERE vector_id IS NOT NULL AND vectorized_at IS NULL;

-- 可选：清空 vector_id 字段（如果不再需要）
-- UPDATE document_chunks SET vector_id = NULL;
```

### 向后兼容

- `update_chunk_vector_id()` 函数保留但标记为已废弃
- `create_document_chunk()` 的 `vector_id` 参数保留但不再使用
- 现有代码可以继续工作，但建议逐步迁移到新 API

---

## 📊 字段对比

| 字段 | 类型 | 用途 | 是否必需 |
|------|------|------|---------|
| `chunk.id` | UUID | 分块唯一标识（主键） | ✅ 必需 |
| ~~`vector_id`~~ | String | ~~向量 ID~~ | ❌ 已移除 |
| `vectorized_at` | DateTime | 向量化时间戳（状态标记） | ✅ 必需 |
| `embedding_model` | String | 使用的向量化模型 | ✅ 推荐保留 |

---

## 🔄 迁移步骤

### 1. 代码已更新 ✅
所有相关代码已修改完成。

### 2. 数据库迁移（可选）
如果现有数据库有数据，运行迁移脚本：

```sql
-- 迁移现有数据
UPDATE document_chunks 
SET vectorized_at = COALESCE(vectorized_at, NOW())
WHERE vector_id IS NOT NULL AND vectorized_at IS NULL;
```

### 3. 验证
```bash
# 检查统计（应该使用 vectorized_at）
python scripts/check_vectorized_chunks.py

# 运行向量化作业测试
# 在 Dagster UI 中运行 vectorize_documents_job
```

---

## 📚 相关文档

- `docs/MILVUS_SCHEMA_MIGRATION.md` - Milvus Schema 迁移指南
- `SCHEMA_CHANGE_SUMMARY.md` - Schema 变更总结
- `MILVUS_SCHEMA_V2.md` - Schema V2 快速参考

---

**状态**: ✅ 代码修改完成，等待数据库迁移和测试
