# Milvus 向量清理指南

## 🎯 问题诊断

### 症状
- Milvus 中的向量数量 > PostgreSQL 记录的已向量化数量
- 重新运行 `force_revectorize=True` 后向量数量继续增加

### 根本原因
当使用 `force_revectorize=True` 重新向量化时：
1. ✅ 新向量被插入 Milvus
2. ✅ PostgreSQL 的 `vector_id` 更新为新向量 ID
3. ❌ **旧向量没有被删除** ← 问题所在！

结果：同一个 `chunk_id` 在 Milvus 中有多个向量副本。

---

## 🔍 第一步：检查现状

### 1. 检查 PostgreSQL 元数据
```bash
cd /Users/han/PycharmProjects/FinNet
python scripts/check_vectorized_chunks.py
```

输出示例：
```
总分块数:          5,110
已向量化:          3,964 (77.6%)
未向量化:          1,146 (22.4%)
```

### 2. 检查 Milvus 实际向量数
```bash
./scripts/check_milvus_direct.sh
```

输出示例：
```
Collection: financial_documents
向量数量: 5,403
向量维度: 3072
```

### 3. 对比结果
- 如果 Milvus 向量数 > PostgreSQL 已向量化数 → **有重复向量**
- 差异数量 = 重复向量的数量（大约）

---

## 🧹 第二步：清理重复向量（推荐）

### 方案 A：使用清理脚本（推荐） ⭐

#### 1. 试运行（查看详情，不实际删除）
```bash
python scripts/clean_duplicate_vectors.py --dry-run --show-details
```

这会显示：
- 有多少重复向量
- 每个 chunk_id 有几个副本
- 哪些向量会被保留，哪些会被删除

#### 2. 执行清理
```bash
python scripts/clean_duplicate_vectors.py --force
```

会提示确认，输入 `yes` 后执行删除。

#### 3. 验证结果
```bash
# 检查 Milvus 向量数
./scripts/check_milvus_direct.sh

# 应该与 PostgreSQL 记录一致
python scripts/check_vectorized_chunks.py
```

**优点**：
- ✅ 快速（只删除重复部分）
- ✅ 保留已有向量，不需要重新向量化
- ✅ 不产生额外的 API 费用

---

### 方案 B：完全重建

#### 1. 删除 Milvus 中的所有向量
```bash
./scripts/delete_milvus_collections.sh
```

#### 2. 清空 PostgreSQL 的 vector_id
```bash
psql -h localhost -U finnet -d finnet << EOF
UPDATE document_chunks SET vector_id = NULL, embedding_model = NULL;
SELECT COUNT(*) as cleared_count FROM document_chunks WHERE vector_id IS NULL;
EOF
```

#### 3. 重新向量化
在 Dagster UI 中运行 `doc_vectorize_job`：
```bash
# 访问 http://localhost:3000
# 找到 doc_vectorize_job
# 点击 "Launch Run"
```

**优点**：
- ✅ 完全清理，确保没有历史问题

**缺点**：
- ❌ 耗时（需要重新向量化所有分块）
- ❌ 产生 API 费用（调用 OpenAI）

---

## 🔧 第三步：修复代码（防止未来再次出现）

### 问题代码位置
文件：`src/processing/ai/embedding/vectorizer.py`

### 当前行为（第 132-135 行）
```python
# 检查是否已向量化
if not force_revectorize and chunk.vector_id:
    self.logger.debug(f"分块已向量化，跳过: {chunk_id}")
    continue
```

### 修复方案
在上述代码后添加删除旧向量的逻辑：

```python
# 检查是否已向量化
if not force_revectorize and chunk.vector_id:
    self.logger.debug(f"分块已向量化，跳过: {chunk_id}")
    continue

# ✨ 新增：如果强制重新向量化，先删除旧向量
if force_revectorize and chunk.vector_id:
    try:
        self.milvus_client.delete_vectors(
            collection_name=MilvusCollection.DOCUMENTS,
            expr=f'chunk_id == "{str(chunk.id)}"'
        )
        self.logger.info(f"已删除旧向量: chunk_id={chunk.id}, old_vector_id={chunk.vector_id}")
    except Exception as e:
        self.logger.warning(f"删除旧向量失败: {e}")
```

### 测试修复
```bash
# 在 Dagster UI 中运行向量化作业，配置：
config:
  ops:
    scan_unvectorized_chunks_op:
      config:
        force_revectorize: true
        limit: 10  # 先测试少量数据
    doc_vectorize_op:
      config:
        force_revectorize: true
```

检查日志，应该看到 "已删除旧向量" 的消息。

---

## 📋 快速命令参考

```bash
# 检查状态
python scripts/check_vectorized_chunks.py        # PostgreSQL 统计
./scripts/check_milvus_direct.sh                # Milvus 统计

# 清理重复向量
python scripts/clean_duplicate_vectors.py --dry-run --show-details  # 试运行
python scripts/clean_duplicate_vectors.py --force                    # 执行删除

# 完全重建（谨慎）
./scripts/delete_milvus_collections.sh           # 删除所有 collections
psql -h localhost -U finnet -d finnet -c "UPDATE document_chunks SET vector_id = NULL;"

# 查看 Dagster 日志
# 访问 http://localhost:3000
```

---

## ❓ 常见问题

### Q1: 为什么会有重复向量？
**A**: 使用 `force_revectorize=True` 时，代码只插入新向量和更新 PostgreSQL，但没有删除 Milvus 中的旧向量。

### Q2: 如何确认清理成功？
**A**: 清理后，Milvus 向量数应该等于 PostgreSQL 中的已向量化数量：
```bash
# Milvus 向量数
./scripts/check_milvus_direct.sh | grep "向量数量"

# PostgreSQL 已向量化数
python scripts/check_vectorized_chunks.py | grep "已向量化"
```

### Q3: 清理会影响正在运行的服务吗？
**A**: 
- 清理脚本使用批量删除，影响较小
- 建议在低峰期或维护窗口执行
- RAG 查询可能在清理期间暂时查询到重复结果

### Q4: 清理失败怎么办？
**A**: 
1. 检查 Milvus 容器是否运行：`docker ps | grep milvus`
2. 检查网络连接：`telnet localhost 19530`
3. 查看错误日志
4. 如果持续失败，使用方案 B（完全重建）

### Q5: 需要安装 pymilvus 吗？
**A**: 
- `check_milvus_direct.sh` 不需要（自动处理）
- `clean_duplicate_vectors.py` 需要安装：
  ```bash
  pip install pymilvus
  ```

---

## 📊 预期结果

### 清理前
```
PostgreSQL: 3,964 个已向量化
Milvus:     5,403 个向量
差异:       +1,439 个（重复）
```

### 清理后
```
PostgreSQL: 3,964 个已向量化
Milvus:     3,964 个向量
差异:       0 个 ✓
```

---

## 🎯 总结

1. **问题根源**：`force_revectorize` 没有删除旧向量
2. **快速解决**：运行 `clean_duplicate_vectors.py --force`
3. **长期修复**：修改 `vectorizer.py` 代码
4. **验证方法**：对比 PostgreSQL 和 Milvus 的数量

如有问题，请查看详细日志或联系开发团队。
