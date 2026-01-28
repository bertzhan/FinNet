# 向量化状态总结报告

**生成时间**: 2026-01-28

## 🔍 检测结果对比

### 1️⃣ PostgreSQL 元数据统计
（基于 `document_chunks` 表的 `vector_id` 字段）

- **总分块数**: 5,110
- **已向量化**: 3,964 (77.6%)
- **未向量化**: 1,146 (22.4%)

#### 按分块类型
- **文本分块**: 2,710 个
  - 已向量化: 2,162 (79.8%)
  - 未向量化: 548 (20.2%)

- **表格分块**: 2,400 个
  - 已向量化: 1,802 (75.1%)
  - 未向量化: 598 (24.9%)

#### 按文档类型
| 文档类型 | 总数 | 已向量化 | 百分比 |
|---------|------|---------|--------|
| annual_reports | 2,319 | 1,609 | 69.4% |
| quarterly_reports | 376 | 312 | 83.0% |
| interim_reports | 2,415 | 2,043 | 84.6% |

#### Embedding 模型
- `openai/text-embedding-3-large`: 3,964 个向量

---

### 2️⃣ Milvus 实际向量数量
（直接查询 Milvus 向量数据库）

- **Collection**: `financial_documents`
- **向量数量**: **5,403**
- **向量维度**: 3072

---

## ⚠️ 发现的问题

### 数据不一致
- **PostgreSQL 记录**: 3,964 个已向量化
- **Milvus 实际存储**: 5,403 个向量
- **差异**: **+1,439 个向量** (Milvus 中多了 36.3%)

### 根本原因：重复向量
经过分析，确认问题是：**Milvus 中存在重复向量**

当运行 `force_revectorize=True` 时：
1. ✅ **新向量被插入** Milvus
2. ✅ **PostgreSQL 的 `vector_id` 被更新** 为新向量的 ID
3. ❌ **旧向量没有被删除** - 仍然保留在 Milvus 中

这导致：
- 同一个 `chunk_id` 在 Milvus 中有多个向量副本
- PostgreSQL 只记录最新的 `vector_id`
- 旧的向量成为"孤儿向量"（PostgreSQL 中没有指向它们的记录）

### 示例
```
Chunk ID: abc-123
PostgreSQL vector_id: 5000 (最新)
Milvus 中的向量: [5000, 3000, 1000]  ← 有 3 个副本！
```

---

## 🔧 关于 `force_revectorize` 参数

### 当前实现逻辑
在 `vectorize_jobs.py` 和 `vectorizer.py` 中：

#### 1. 扫描阶段 (`scan_unvectorized_chunks_op`)
```python
if not force_revectorize:
    query = query.filter(DocumentChunk.vector_id.is_(None))
else:
    # 扫描所有分块（包括已向量化的）
    pass
```

#### 2. 向量化阶段 (`vectorizer.py`)
```python
if not force_revectorize and chunk.vector_id:
    # 跳过已向量化的分块
    continue
```

### 问题诊断
如果设置了 `force_revectorize=True` 但没有检测到所有向量，可能是因为：

1. **配置不完整**: 需要在两个 op 中都设置 `force_revectorize: true`
   ```yaml
   config:
     ops:
       scan_unvectorized_chunks_op:
         config:
           force_revectorize: true  # ← 必需
       vectorize_chunks_op:
         config:
           force_revectorize: true  # ← 必需
   ```

2. **旧向量未删除**: 当前代码中，`force_revectorize` 时不会删除 Milvus 中的旧向量
   ```python
   # vectorizer.py line 452-454
   if force_revectorize and chunk.vector_id:
       # TODO: 从Milvus删除旧向量（当前未实现）
       pass
   ```

---

## 🎉 根本解决方案（已实现）

### 方案：使用 chunk_id 作为 Milvus 主键 ⭐⭐⭐

**变更内容**：
- 修改 Milvus Collection Schema，将 `chunk_id` 设为主键（原来是自动生成的 `id`）
- Milvus 会自动执行 upsert 行为：相同 `chunk_id` 的向量会被覆盖，不会产生重复

**优点**：
- ✅ 从根本上解决重复向量问题
- ✅ 无需手动删除旧向量
- ✅ `force_revectorize` 自动覆盖，代码更简洁
- ✅ 保证 Milvus 向量数 = PostgreSQL 已向量化数

**实施步骤**：
1. 删除旧 Collection 和 PostgreSQL 向量化记录
2. 重新运行向量化作业（自动使用新 Schema）
3. 验证结果

详细迁移指南：`docs/MILVUS_SCHEMA_MIGRATION.md`

---

## 📝 临时解决方案（如果不想重建）

### 选项 1: 清理重复向量
使用新创建的脚本清理重复向量，保留最新的向量：

```bash
# 1. 先试运行，查看详情（不会实际删除）
python scripts/clean_duplicate_vectors.py --dry-run --show-details

# 2. 确认无误后，执行实际删除
python scripts/clean_duplicate_vectors.py --force
```

**优点**：
- ✅ 保留已有的向量，不需要重新向量化
- ✅ 快速，只删除重复的部分
- ✅ 保持 PostgreSQL 和 Milvus 数据一致性

**预期结果**：
- 删除 ~1,439 个重复向量
- Milvus 向量数从 5,403 降至 ~3,964
- 与 PostgreSQL 记录一致

---

### 选项 2: 完全重建（彻底清理）
删除所有 collections 并重新向量化：

```bash
# 1. 删除 Milvus 中的所有数据
./scripts/delete_milvus_collections.sh

# 2. 清空 PostgreSQL 中的 vector_id
psql -h localhost -U finnet -d finnet -c "UPDATE document_chunks SET vector_id = NULL, embedding_model = NULL;"

# 3. 重新运行向量化作业（在 Dagster UI 中）
# 访问 http://localhost:3000
# 执行 vectorize_documents_job
```

**优点**：
- ✅ 完全清理，确保没有历史遗留问题
- ✅ 重新生成所有向量

**缺点**：
- ❌ 需要重新向量化所有分块（耗时）
- ❌ 需要调用 OpenAI API（产生费用）

---

### 选项 3: 修复代码后重新向量化
修复 `vectorizer.py` 的逻辑，实现 `force_revectorize` 时自动删除旧向量：

**在 `vectorizer.py` 的 `vectorize_chunks` 方法中添加：**
```python
# 在 line 133 附近，检查是否已向量化时
if not force_revectorize and chunk.vector_id:
    self.logger.debug(f"分块已向量化，跳过: {chunk_id}")
    continue

# 添加：如果 force_revectorize=True 且已有向量，先删除旧向量
if force_revectorize and chunk.vector_id:
    try:
        self.milvus_client.delete_vectors(
            collection_name=MilvusCollection.DOCUMENTS,
            expr=f'chunk_id == "{str(chunk.id)}"'
        )
        self.logger.debug(f"已删除旧向量: chunk_id={chunk.id}")
    except Exception as e:
        self.logger.warning(f"删除旧向量失败: {e}")
```

---

### 选项 4: 完成剩余的向量化
目前还有 **1,146 个分块** (22.4%) 未向量化，完成这些后再清理重复：

```bash
# 在 Dagster UI 中执行 vectorize_documents_job
# 或使用命令行
dagster job execute -j vectorize_documents_job
```

---

## 📊 检测和清理脚本

### 1. 检查向量化状态

#### 检查 PostgreSQL 元数据
```bash
python scripts/check_vectorized_chunks.py
```
输出：
- 总分块数、已向量化数量、未向量化数量
- 按文档类型、市场、分块类型的统计
- Embedding 模型信息

#### 检查 Milvus 实际向量数量
```bash
./scripts/check_milvus_direct.sh
```
输出：
- Collection 列表
- 每个 Collection 的向量数量和维度
- 总向量数

---

### 2. 清理重复向量

#### 检测重复向量（试运行）
```bash
python scripts/clean_duplicate_vectors.py --dry-run --show-details
```
输出：
- 重复向量的数量
- 每个 chunk_id 的重复情况
- 将要删除哪些向量（不会实际删除）

#### 执行清理
```bash
python scripts/clean_duplicate_vectors.py --force
```
会提示确认后执行删除。

---

### 3. 其他工具

#### 删除整个 Collection
```bash
./scripts/delete_milvus_collections.sh
```
⚠️ 谨慎使用！会删除所有向量数据。

---

## 🎯 总结

1. **根本原因**：重复向量化时没有删除旧向量
2. **当前状态**：
   - Milvus 中有 5,403 个向量
   - PostgreSQL 记录 3,964 个已向量化
   - 差异：~1,439 个重复向量
   - 还有 1,146 个分块未向量化
3. **推荐解决方案**：使用 `clean_duplicate_vectors.py` 清理重复向量
4. **长期修复**：修改 `vectorizer.py` 代码，在 `force_revectorize` 时自动删除旧向量

---

## 🔧 安装依赖

部分脚本需要 `pymilvus` 库：

```bash
# 安装 pymilvus
pip install pymilvus

# 或添加到 requirements.txt
echo "pymilvus>=2.3.0" >> requirements.txt
pip install -r requirements.txt
```

如果不想安装 `pymilvus`，可以使用 `check_milvus_direct.sh` 脚本（已自动处理 pymilvus）。
