# 数据库迁移：删除 vector_id 字段

**日期**: 2026-01-28  
**变更**: 从 `document_chunks` 表中删除 `vector_id` 字段

---

## 📝 变更说明

### 删除原因
1. **Milvus Schema V2**: 使用 `chunk_id` 作为主键，不再需要单独的 `vector_id`
2. **数据冗余**: `vector_id` 现在就是 `chunk_id`，完全重复
3. **已改用 `vectorized_at`**: 使用时间戳字段判断是否已向量化

### 保留字段
- ✅ `embedding_model`: 记录使用的向量化模型（仍在使用）
- ✅ `vectorized_at`: 向量化时间戳（用于判断是否已向量化）

---

## 🔄 数据库迁移 SQL

### 方案 A：直接删除（推荐，如果数据已迁移）

```sql
-- 1. 确认所有已向量化的记录都有 vectorized_at
SELECT 
    COUNT(*) as total,
    COUNT(vector_id) as has_vector_id,
    COUNT(vectorized_at) as has_vectorized_at
FROM document_chunks
WHERE vector_id IS NOT NULL;

-- 2. 如果 has_vectorized_at < has_vector_id，先迁移数据
UPDATE document_chunks 
SET vectorized_at = COALESCE(vectorized_at, NOW())
WHERE vector_id IS NOT NULL AND vectorized_at IS NULL;

-- 3. 删除 vector_id 列
ALTER TABLE document_chunks DROP COLUMN vector_id;
```

### 方案 B：先迁移数据再删除（安全）

```sql
-- 1. 为所有有 vector_id 但没有 vectorized_at 的记录设置时间戳
UPDATE document_chunks 
SET vectorized_at = COALESCE(vectorized_at, NOW())
WHERE vector_id IS NOT NULL AND vectorized_at IS NULL;

-- 2. 验证迁移结果
SELECT 
    COUNT(*) as total,
    COUNT(vector_id) as has_vector_id,
    COUNT(vectorized_at) as has_vectorized_at,
    COUNT(CASE WHEN vector_id IS NOT NULL AND vectorized_at IS NULL THEN 1 END) as missing_timestamp
FROM document_chunks;

-- 3. 如果 missing_timestamp = 0，可以安全删除
ALTER TABLE document_chunks DROP COLUMN vector_id;
```

---

## ✅ 迁移前检查清单

- [ ] 确认代码已更新（不再使用 `vector_id`）
- [ ] 备份数据库
- [ ] 检查现有数据状态
- [ ] 迁移数据（设置 `vectorized_at`）
- [ ] 验证迁移结果
- [ ] 删除 `vector_id` 列

---

## 🔍 验证查询

### 迁移前检查
```sql
-- 检查有多少记录需要迁移
SELECT 
    COUNT(*) as total_chunks,
    COUNT(vector_id) as chunks_with_vector_id,
    COUNT(vectorized_at) as chunks_with_vectorized_at,
    COUNT(CASE WHEN vector_id IS NOT NULL AND vectorized_at IS NULL THEN 1 END) as need_migration
FROM document_chunks;
```

### 迁移后验证
```sql
-- 验证 vector_id 已删除
SELECT column_name 
FROM information_schema.columns 
WHERE table_name = 'document_chunks' 
  AND column_name = 'vector_id';
-- 应该返回 0 行

-- 验证向量化状态统计
SELECT 
    COUNT(*) as total,
    COUNT(vectorized_at) as vectorized,
    COUNT(*) - COUNT(vectorized_at) as unvectorized
FROM document_chunks;
```

---

## ⚠️ 注意事项

1. **备份数据库**: 删除列是不可逆操作，务必先备份
2. **测试环境**: 先在测试环境验证迁移脚本
3. **停机时间**: 如果数据量大，可能需要短暂停机
4. **代码部署**: 确保代码已更新，不再使用 `vector_id` 字段

---

## 📊 影响范围

### 已更新的代码
- ✅ `src/storage/metadata/models.py` - 已删除字段定义
- ✅ `src/storage/metadata/crud.py` - 已移除相关参数
- ✅ `src/processing/ai/embedding/vectorizer.py` - 已改用 `vectorized_at`
- ✅ `src/processing/compute/dagster/jobs/vectorize_jobs.py` - 已改用 `vectorized_at`
- ✅ `scripts/check_vectorized_chunks.py` - 已改用 `vectorized_at`

### 数据库变更
- ❌ 删除列：`document_chunks.vector_id`
- ✅ 保留列：`document_chunks.embedding_model`
- ✅ 保留列：`document_chunks.vectorized_at`

---

## 🚀 执行步骤

### 1. 准备阶段
```bash
# 备份数据库
pg_dump -h localhost -U finnet -d finnet > backup_$(date +%Y%m%d_%H%M%S).sql
```

### 2. 迁移数据
```sql
-- 连接数据库
psql -h localhost -U finnet -d finnet

-- 执行迁移
UPDATE document_chunks 
SET vectorized_at = COALESCE(vectorized_at, NOW())
WHERE vector_id IS NOT NULL AND vectorized_at IS NULL;
```

### 3. 验证
```sql
-- 检查迁移结果
SELECT 
    COUNT(*) as total,
    COUNT(vector_id) as has_vector_id,
    COUNT(vectorized_at) as has_vectorized_at
FROM document_chunks;
```

### 4. 删除列
```sql
-- 删除 vector_id 列
ALTER TABLE document_chunks DROP COLUMN vector_id;
```

### 5. 最终验证
```bash
# 运行检查脚本
python scripts/check_vectorized_chunks.py

# 运行向量化作业测试
# 在 Dagster UI 中运行 doc_vectorize_job
```

---

## 📚 相关文档

- `docs/VECTOR_ID_REMOVAL.md` - vector_id 移除说明
- `docs/MILVUS_SCHEMA_MIGRATION.md` - Milvus Schema 迁移指南
- `SCHEMA_CHANGE_SUMMARY.md` - Schema 变更总结

---

**状态**: ✅ 代码已更新，等待数据库迁移执行
