# 重复向量问题分析报告

**日期**: 2026-01-28  
**问题**: Milvus 向量数量与 PostgreSQL 记录不一致

---

## 📊 数据对比

| 指标 | PostgreSQL | Milvus | 差异 |
|------|-----------|--------|------|
| **已向量化分块数** | 3,964 | - | - |
| **实际向量数** | - | 5,403 | +1,439 (36.3%) |
| **未向量化分块数** | 1,146 | - | - |
| **总分块数** | 5,110 | - | - |

---

## 🔍 问题分析

### 1. 初步假设
最初认为可能是：
- ❌ 孤立向量（Milvus 中有但 PostgreSQL 中没有对应 chunk_id）
- ❌ 元数据更新失败
- ❌ 历史测试数据残留

### 2. 实际原因 ✅
经过分析确认：**重复向量化时没有删除旧向量**

#### 问题流程
```
初始状态:
  Chunk ABC → Vector 1000 (在 Milvus 中)
  PostgreSQL: chunk_id=ABC, vector_id=1000

使用 force_revectorize=True 重新向量化:
  1. 生成新向量 → Vector 2000
  2. 插入 Milvus → 成功
  3. 更新 PostgreSQL: vector_id=2000 → 成功
  4. 删除旧向量 Vector 1000？ → ❌ 没有执行！

结果:
  Milvus: [Vector 1000, Vector 2000] ← 两个向量！
  PostgreSQL: chunk_id=ABC, vector_id=2000 ← 只记录新的
```

### 3. 验证方法
```python
# Milvus 中同一个 chunk_id 有多个向量
chunk_id: "abc-123"
Milvus vectors: [
    {id: 1000, chunk_id: "abc-123"},  # 旧向量（孤儿）
    {id: 2000, chunk_id: "abc-123"},  # 新向量
    {id: 3000, chunk_id: "abc-123"}   # 更新前的向量（孤儿）
]
PostgreSQL: {chunk_id: "abc-123", vector_id: 3000}  # 只记录最新的
```

---

## 💡 解决方案

### 🎉 根本解决方案（已实现）⭐

**方案 D: 使用 chunk_id 作为 Milvus 主键**

| 项目 | 说明 |
|------|------|
| **方法** | 修改 Milvus Schema，将 `chunk_id` 作为主键（替代自动生成的 `id`） |
| **原理** | 主键天然保证唯一性，重新插入相同 `chunk_id` 时自动覆盖（upsert） |
| **优点** | • 从根本上解决问题<br>• 无需手动删除<br>• 代码更简洁<br>• 性能更好 |
| **缺点** | • 需要重建 Collection<br>• 一次性迁移 |
| **耗时** | ~10-20 分钟 |
| **成本** | 免费（或重新向量化的 API 费用） |

**实施状态**: ✅ 已完成代码修改，详见 `docs/MILVUS_SCHEMA_MIGRATION.md`

---

### 临时解决方案对比

| 方案 | 优点 | 缺点 | 耗时 | 成本 |
|------|------|------|------|------|
| **A. 清理重复向量** | • 快速<br>• 无需 API 调用<br>• 保留现有数据 | • 治标不治本<br>• 需要 pymilvus | ~5分钟 | 免费 |
| **B. 完全重建** | • 彻底清理<br>• 确保无历史问题 | • 耗时长<br>• 产生 API 费用 | ~30-60分钟 | $$$ |
| **C. 修复代码** | • 防止未来问题 | • 不解决当前问题<br>• 仍需手动删除 | 代码修改 | 免费 |

### 推荐：方案 D（根本解决）
1. **实施 Schema 迁移**：按照 `docs/MILVUS_SCHEMA_MIGRATION.md` 操作
2. **验证结果**：确认不再产生重复向量

---

## 🛠️ 执行步骤

### Step 1: 安装依赖（如需要）
```bash
pip install pymilvus
```

### Step 2: 试运行（查看将要删除什么）
```bash
cd /Users/han/PycharmProjects/FinNet
python scripts/clean_duplicate_vectors.py --dry-run --show-details
```

### Step 3: 执行清理
```bash
python scripts/clean_duplicate_vectors.py --force
# 输入 'yes' 确认
```

### Step 4: 验证结果
```bash
# 检查 Milvus 向量数（应该是 3,964）
./scripts/check_milvus_direct.sh

# 检查 PostgreSQL 统计
python scripts/check_vectorized_chunks.py
```

### Step 5: 修复代码（可选但推荐）
编辑 `src/processing/ai/embedding/vectorizer.py`，添加删除旧向量的逻辑。

详见：`scripts/VECTOR_CLEANUP_GUIDE.md`

---

## 📈 预期效果

### 清理前
```
PostgreSQL 记录: 3,964 个已向量化
Milvus 实际数量: 5,403 个向量
状态: ❌ 不一致 (+1,439 个重复)
```

### 清理后
```
PostgreSQL 记录: 3,964 个已向量化
Milvus 实际数量: 3,964 个向量
状态: ✅ 一致
```

---

## 🔧 代码修复建议

### 位置
文件: `src/processing/ai/embedding/vectorizer.py`  
行数: ~133-135 附近

### 当前代码
```python
# 检查是否已向量化
if not force_revectorize and chunk.vector_id:
    self.logger.debug(f"分块已向量化，跳过: {chunk_id}")
    continue
```

### 修复后的代码
```python
# 检查是否已向量化
if not force_revectorize and chunk.vector_id:
    self.logger.debug(f"分块已向量化，跳过: {chunk_id}")
    continue

# 如果强制重新向量化且已有向量，先删除旧向量
if force_revectorize and chunk.vector_id:
    try:
        # 构建删除表达式：删除该 chunk_id 的所有向量
        expr = f'chunk_id == "{str(chunk.id)}"'
        self.milvus_client.delete_vectors(
            collection_name=MilvusCollection.DOCUMENTS,
            expr=expr
        )
        self.logger.info(
            f"✓ 已删除旧向量: chunk_id={chunk.id}, "
            f"old_vector_id={chunk.vector_id}"
        )
    except Exception as e:
        self.logger.warning(
            f"删除旧向量失败: chunk_id={chunk.id}, error={e}"
        )
        # 继续处理，即使删除失败也要插入新向量
```

### 修复效果
修复后，`force_revectorize=True` 时会：
1. ✅ 删除 Milvus 中的旧向量
2. ✅ 插入新向量
3. ✅ 更新 PostgreSQL 记录

不会再产生重复向量。

---

## 📚 相关文档

- `VECTOR_STATUS_SUMMARY.md` - 详细的状态分析报告
- `scripts/VECTOR_CLEANUP_GUIDE.md` - 清理操作完整指南
- `scripts/check_vectorized_chunks.py` - PostgreSQL 统计脚本
- `scripts/check_milvus_direct.sh` - Milvus 统计脚本
- `scripts/clean_duplicate_vectors.py` - 重复向量清理脚本

---

## ✅ 检查清单

清理完成后，验证以下项目：

- [ ] Milvus 向量数 = PostgreSQL 已向量化数
- [ ] 没有重复的 chunk_id（运行清理脚本的 dry-run 模式验证）
- [ ] RAG 查询正常工作
- [ ] 代码已修复（可选）
- [ ] 文档已更新

---

## 📞 支持

如遇到问题：
1. 查看日志文件
2. 检查 Docker 容器状态：`docker ps`
3. 查看详细指南：`scripts/VECTOR_CLEANUP_GUIDE.md`
4. 联系开发团队

---

**报告生成**: 2026-01-28  
**分析工具**: `check_vectorized_chunks.py`, `check_milvus_direct.sh`  
**清理工具**: `clean_duplicate_vectors.py`
