# Milvus Schema 改动总结

**日期**: 2026-01-28  
**提出者**: 用户建议  
**实施状态**: ✅ 代码已修改，等待迁移部署

---

## 🎯 核心改动

### 1. 将 `chunk_id` 设为 Milvus Collection 主键

**之前**：
```python
FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True)
FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=36)
```

**之后**：
```python
FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=36, is_primary=True)
```

### 2. 新增过滤字段：`company_name` 和 `doc_type`

**新增字段**：
```python
FieldSchema(name="company_name", dtype=DataType.VARCHAR, max_length=100)  # 公司名称
FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=50)       # 文档类型
```

**用途**：支持更精确的向量检索过滤
- `company_name`: 按公司名称过滤（如 "平安银行"）
- `doc_type`: 按文档类型过滤（如 "annual_reports"）

---

## 💡 为什么要改？

### 问题描述
当使用 `force_revectorize=True` 重新向量化时：
1. 新向量被插入 Milvus
2. PostgreSQL 的 `vector_id` 被更新
3. ❌ **旧向量没有被删除** → 产生重复

结果：
- Milvus: 5,403 个向量
- PostgreSQL: 3,964 个已向量化记录
- 差异: 1,439 个重复向量 (36.3%)

### 解决方案
使用 `chunk_id` 作为主键后：
- 主键天然保证唯一性
- 重新插入相同 `chunk_id` 时**自动覆盖**（upsert 行为）
- ✅ 不会产生重复向量

---

## 📝 修改的文件

### 1. `src/storage/vector/milvus_client.py`
**变更**：
- 修改 `create_collection()`: 将 `chunk_id` 设为主键
- 修改 `insert_vectors()`: 调整数据顺序和返回值
- 更新文档字符串

**影响**：
- ✅ 新建的 Collection 自动使用新 Schema
- ✅ 插入操作自动执行 upsert

### 2. `src/processing/ai/embedding/vectorizer.py`
**变更**：
- 更新注释：说明不需要手动删除旧向量
- 移除无用代码（第 451-454 行）

**影响**：
- ✅ 代码更简洁
- ✅ `force_revectorize` 自动覆盖

### 3. 新增文档
- `docs/MILVUS_SCHEMA_MIGRATION.md` - 详细的迁移指南
- `scripts/migrate_milvus_schema.sh` - 自动化迁移脚本
- `SCHEMA_CHANGE_SUMMARY.md` - 本文档

### 4. 更新文档
- `VECTOR_STATUS_SUMMARY.md` - 添加根本解决方案说明
- `DUPLICATE_VECTORS_ANALYSIS.md` - 更新解决方案对比

---

## 🚀 部署步骤

### 选项 A: 简单重建（推荐）

```bash
# 1. 删除旧数据
./scripts/migrate_milvus_schema.sh

# 2. 重新向量化
# 在 Dagster UI 运行 vectorize_documents_job
```

### 选项 B: 保留数据迁移

详见：`docs/MILVUS_SCHEMA_MIGRATION.md`

---

## ✅ 验证清单

部署后验证：

- [ ] Collection Schema 正确（chunk_id 是主键）
  ```bash
  python -c "from src.storage.vector.milvus_client import get_milvus_client; \
             from src.common.constants import MilvusCollection; \
             client = get_milvus_client(); \
             collection = client.get_collection(MilvusCollection.DOCUMENTS); \
             for field in collection.schema.fields: \
                 if field.is_primary: print(f'主键: {field.name}')"
  ```

- [ ] 向量数量正确（无重复）
  ```bash
  ./scripts/check_milvus_direct.sh
  python scripts/check_vectorized_chunks.py
  ```

- [ ] `force_revectorize` 测试
  ```bash
  # 在 Dagster UI 中运行向量化作业
  # 配置 force_revectorize=true
  # 运行两次，检查向量数量是否保持不变
  ```

- [ ] RAG 查询正常
  ```bash
  python test_rag_simple.py
  ```

---

## 📊 预期效果

### 数据一致性
| 指标 | 迁移前 | 迁移后 |
|------|--------|--------|
| Milvus 向量数 | 5,403 | 3,964 |
| PostgreSQL 已向量化 | 3,964 | 3,964 |
| 重复向量 | 1,439 (36.3%) | 0 (0%) ✓ |

### 行为变化
| 操作 | 迁移前 | 迁移后 |
|------|--------|--------|
| 首次向量化 | 插入新向量 | 插入新向量 |
| force_revectorize | 插入新向量（产生重复） | 覆盖旧向量（无重复）✓ |
| 数据清理 | 需要手动脚本清理 | 自动维护，无需清理 ✓ |

---

## 🔧 技术细节

### Upsert 行为示例

```python
from src.storage.vector.milvus_client import get_milvus_client
from src.common.constants import MilvusCollection

client = get_milvus_client()

# 第一次插入
client.insert_vectors(
    collection_name=MilvusCollection.DOCUMENTS,
    chunk_ids=["abc-123-def"],
    embeddings=[[0.1] * 3072],
    document_ids=["doc-001"],
    stock_codes=["000001"],
    years=[2023],
    quarters=[3]
)
# Result: 1 个向量

# 再次插入相同 chunk_id（force_revectorize）
client.insert_vectors(
    collection_name=MilvusCollection.DOCUMENTS,
    chunk_ids=["abc-123-def"],  # 相同主键
    embeddings=[[0.2] * 3072],  # 新向量
    document_ids=["doc-001"],
    stock_codes=["000001"],
    years=[2023],
    quarters=[3]
)
# Result: 仍然是 1 个向量（旧的被覆盖）✓
```

### PostgreSQL 兼容性

`document_chunks.vector_id` 字段：
- **之前**: 存储 Milvus 自动生成的 INT64 ID
- **现在**: 存储 chunk_id（UUID 字符串）
- **用途**: 标记是否已向量化（`vector_id IS NOT NULL`）

虽然 `vector_id` 和 `chunk.id` 值相同，但保留此字段以：
- 向后兼容现有代码
- 明确标记"已向量化"状态
- 便于查询统计

---

## 🎉 优势总结

1. **根本性解决**：从数据库层面保证唯一性
2. **自动化**：无需手动删除旧向量
3. **性能提升**：减少冗余数据，查询更快
4. **代码简化**：移除复杂的删除逻辑
5. **维护性**：未来无需清理重复向量

---

## 📚 相关文档

- **迁移指南**: `docs/MILVUS_SCHEMA_MIGRATION.md`
- **问题分析**: `DUPLICATE_VECTORS_ANALYSIS.md`
- **状态报告**: `VECTOR_STATUS_SUMMARY.md`
- **清理指南**: `scripts/VECTOR_CLEANUP_GUIDE.md`

---

## 👏 致谢

感谢用户提出的宝贵建议！这是一个非常聪明的解决方案，从根本上解决了重复向量的问题。

---

---

## 📋 完整 Schema 对比

### 旧 Schema
```python
fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
    FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=36),
    FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=36),
    FieldSchema(name="stock_code", dtype=DataType.VARCHAR, max_length=20),
    FieldSchema(name="year", dtype=DataType.INT32),
    FieldSchema(name="quarter", dtype=DataType.INT32),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension)
]
```

### 新 Schema ✨
```python
fields = [
    FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=36, is_primary=True),     # 主键
    FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=36),
    FieldSchema(name="stock_code", dtype=DataType.VARCHAR, max_length=20),
    FieldSchema(name="company_name", dtype=DataType.VARCHAR, max_length=100),  # 🆕 新增
    FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=50),       # 🆕 新增
    FieldSchema(name="year", dtype=DataType.INT32),
    FieldSchema(name="quarter", dtype=DataType.INT32),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension)
]
```

### 变更总结
| 项目 | 旧值 | 新值 | 说明 |
|------|------|------|------|
| 主键 | `id` (INT64, auto_id) | `chunk_id` (VARCHAR) | 保证唯一性，支持 upsert |
| 字段数 | 7 个 | 9 个 | +2 个过滤字段 |
| 过滤能力 | 基础（股票代码、年份） | 增强（公司名称、文档类型） | 更精确的检索 |

---

**更新记录**:
- 2026-01-28: 完成代码修改和文档编写
- 2026-01-28: 新增 `company_name` 和 `doc_type` 字段
- 待定: 生产环境迁移部署
