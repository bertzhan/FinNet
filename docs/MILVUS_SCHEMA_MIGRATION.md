# Milvus Schema 迁移指南

**日期**: 2026-01-28  
**变更**: 将 `chunk_id` 设为主键，解决重复向量问题

---

## 📝 变更说明

### 旧 Schema
```python
fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),  # 自动生成的主键
    FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=36),
    FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=36),         # 普通字段
    FieldSchema(name="stock_code", dtype=DataType.VARCHAR, max_length=20),
    FieldSchema(name="year", dtype=DataType.INT32),
    FieldSchema(name="quarter", dtype=DataType.INT32),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension)
]
```

**问题**：
- 使用 `force_revectorize=True` 时，会插入新向量但不删除旧向量
- 同一个 `chunk_id` 可能有多个向量副本
- 导致 Milvus 向量数 > PostgreSQL 记录数

### 新 Schema ✨
```python
fields = [
    FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=36, is_primary=True),  # 主键
    FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=36),
    FieldSchema(name="stock_code", dtype=DataType.VARCHAR, max_length=20),
    FieldSchema(name="company_name", dtype=DataType.VARCHAR, max_length=100),  # 新增：公司名称
    FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=50),       # 新增：文档类型
    FieldSchema(name="year", dtype=DataType.INT32),
    FieldSchema(name="quarter", dtype=DataType.INT32),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension)
]
```

**优点**：
- ✅ `chunk_id` 作为主键，天然保证唯一性
- ✅ 重新插入相同 `chunk_id` 时自动覆盖（upsert 行为）
- ✅ 无需手动删除旧向量
- ✅ 从根本上解决重复向量问题
- ✅ Milvus 向量数始终等于已向量化的分块数
- ✅ 新增 `company_name` 和 `doc_type` 字段，支持更精确的过滤检索

---

## 🔧 迁移步骤

### 方案 A：删除并重建（推荐，简单快速）⭐

#### 1. 备份当前状态（可选）
```bash
# 记录当前向量数量
./scripts/check_milvus_direct.sh > milvus_backup_$(date +%Y%m%d).txt
python scripts/check_vectorized_chunks.py > postgres_backup_$(date +%Y%m%d).txt
```

#### 2. 删除旧 Collection
```bash
# 停止所有向量化作业
# 在 Dagster UI 中停止 doc_vectorize_job

# 删除 Milvus 中的所有 collections
./scripts/delete_milvus_collections.sh
```

#### 3. 清空 PostgreSQL 的向量化记录
```bash
psql -h localhost -U finnet -d finnet << 'EOF'
-- 清空 vector_id（标记为未向量化）
UPDATE document_chunks SET vector_id = NULL, embedding_model = NULL;

-- 验证
SELECT 
    COUNT(*) as total_chunks,
    COUNT(vector_id) as vectorized_chunks
FROM document_chunks;
-- 应该显示：vectorized_chunks = 0
EOF
```

#### 4. 重新运行向量化
代码会自动创建新的 Collection（使用新 Schema）：

```bash
# 方法1：通过 Dagster UI
# 访问 http://localhost:3000
# 运行 doc_vectorize_job

# 方法2：通过 Python 脚本
python scripts/init_milvus_collection.py  # 创建新 Collection（可选）
```

新 Collection 会自动使用新 Schema（chunk_id 作为主键）。

#### 5. 验证迁移结果
```bash
# 检查 Collection schema
python -c "
from src.storage.vector.milvus_client import get_milvus_client
from src.common.constants import MilvusCollection

client = get_milvus_client()
collection = client.get_collection(MilvusCollection.DOCUMENTS)
if collection:
    print('Schema fields:')
    for field in collection.schema.fields:
        primary = ' (PRIMARY KEY)' if field.is_primary else ''
        print(f'  - {field.name}: {field.dtype}{primary}')
"

# 检查向量数量
./scripts/check_milvus_direct.sh
python scripts/check_vectorized_chunks.py
```

---

### 方案 B：数据导出/导入（保留现有数据，较复杂）

**注意**：Milvus 不支持直接修改 Schema，必须重建 Collection。如果要保留数据，需要：

#### 1. 导出现有数据
```python
# scripts/export_milvus_data.py
from src.storage.vector.milvus_client import get_milvus_client
from src.common.constants import MilvusCollection
import json

client = get_milvus_client()
collection = client.get_collection(MilvusCollection.DOCUMENTS)

# 查询所有数据
all_data = []
offset = 0
batch_size = 1000

while True:
    results = collection.query(
        expr="id >= 0",
        output_fields=["id", "chunk_id", "document_id", "stock_code", "year", "quarter", "embedding"],
        limit=batch_size,
        offset=offset
    )
    if not results:
        break
    all_data.extend(results)
    offset += len(results)
    if len(results) < batch_size:
        break

# 保存到文件
with open("milvus_backup.json", "w") as f:
    json.dump(all_data, f)

print(f"导出 {len(all_data)} 条记录")
```

#### 2. 删除旧 Collection
```bash
./scripts/delete_milvus_collections.sh
```

#### 3. 创建新 Collection（自动使用新 Schema）
```bash
python scripts/init_milvus_collection.py
```

#### 4. 导入数据
```python
# scripts/import_milvus_data.py
from src.storage.vector.milvus_client import get_milvus_client
from src.common.constants import MilvusCollection
import json

# 读取备份数据
with open("milvus_backup.json", "r") as f:
    all_data = json.load(f)

client = get_milvus_client()

# 按 chunk_id 去重（保留最新的）
unique_data = {}
for item in all_data:
    chunk_id = item["chunk_id"]
    if chunk_id not in unique_data:
        unique_data[chunk_id] = item
    else:
        # 保留 id 更大的（更新的）
        if item["id"] > unique_data[chunk_id]["id"]:
            unique_data[chunk_id] = item

# 准备数据
chunk_ids = []
document_ids = []
stock_codes = []
years = []
quarters = []
embeddings = []

for item in unique_data.values():
    chunk_ids.append(item["chunk_id"])
    document_ids.append(item["document_id"])
    stock_codes.append(item["stock_code"])
    years.append(item["year"])
    quarters.append(item["quarter"])
    embeddings.append(item["embedding"])

# 批量插入
batch_size = 100
for i in range(0, len(chunk_ids), batch_size):
    client.insert_vectors(
        collection_name=MilvusCollection.DOCUMENTS,
        embeddings=embeddings[i:i+batch_size],
        document_ids=document_ids[i:i+batch_size],
        chunk_ids=chunk_ids[i:i+batch_size],
        stock_codes=stock_codes[i:i+batch_size],
        years=years[i:i+batch_size],
        quarters=quarters[i:i+batch_size]
    )
    print(f"已导入 {min(i+batch_size, len(chunk_ids))}/{len(chunk_ids)}")

print("导入完成")
```

---

## ✅ 验证清单

迁移完成后，验证以下内容：

- [ ] Milvus Collection 使用新 Schema（chunk_id 是主键）
- [ ] 向量数量正确（无重复）
- [ ] PostgreSQL 和 Milvus 数据一致
- [ ] RAG 查询正常工作
- [ ] 重新向量化（force_revectorize=True）不产生重复

### 验证命令
```bash
# 1. 检查 Schema
python -c "
from src.storage.vector.milvus_client import get_milvus_client
from src.common.constants import MilvusCollection
client = get_milvus_client()
collection = client.get_collection(MilvusCollection.DOCUMENTS)
for field in collection.schema.fields:
    if field.is_primary:
        print(f'✓ 主键: {field.name}')
"

# 2. 检查向量数量
./scripts/check_milvus_direct.sh
python scripts/check_vectorized_chunks.py

# 3. 测试向量化
# 在 Dagster UI 中运行 doc_vectorize_job
# 配置 force_revectorize=true 并运行少量数据测试

# 4. 测试 RAG 查询
python test_rag_simple.py
```

---

## 🔄 回滚方案

如果迁移出现问题，可以回滚：

```bash
# 1. 停止向量化作业

# 2. 删除新 Collection
./scripts/delete_milvus_collections.sh

# 3. 恢复旧代码（git checkout）
git checkout HEAD~1 src/storage/vector/milvus_client.py
git checkout HEAD~1 src/processing/ai/embedding/vectorizer.py

# 4. 如果有数据备份，使用方案 B 的导入脚本恢复

# 5. 重新运行向量化作业
```

---

## 📊 预期效果

### 迁移前
```
PostgreSQL: 3,964 个已向量化
Milvus:     5,403 个向量
问题:       1,439 个重复向量
```

### 迁移后
```
PostgreSQL: 3,964 个已向量化
Milvus:     3,964 个向量
状态:       ✓ 完全一致，无重复
```

### 未来运行 force_revectorize
```
迁移前: 每次都会增加重复向量
迁移后: 自动覆盖，不会产生重复 ✓
```

---

## 💡 技术细节

### Upsert 行为说明

在新 Schema 中，当插入相同 `chunk_id` 的向量时：

```python
# 第一次插入
client.insert_vectors(
    chunk_ids=["abc-123"],
    embeddings=[[0.1] * 3072],
    ...
)
# Result: Milvus 中有 1 个向量 (chunk_id=abc-123)

# 第二次插入（相同 chunk_id）
client.insert_vectors(
    chunk_ids=["abc-123"],  # 相同的主键
    embeddings=[[0.2] * 3072],  # 新的向量
    ...
)
# Result: Milvus 中仍然只有 1 个向量 (chunk_id=abc-123)
#         旧向量被覆盖，不会产生重复
```

### PostgreSQL 字段说明

`document_chunks.vector_id` 字段的新含义：
- **之前**: 存储 Milvus 自动生成的整数 ID（如 1000, 2000）
- **现在**: 存储 chunk_id（UUID 字符串）
- **用途**: 标记该分块是否已向量化（`vector_id IS NOT NULL`）

虽然 `vector_id` 和 `chunk.id` 现在值相同，但保留这个字段：
1. 向后兼容现有代码
2. 明确标记"已向量化"状态
3. 便于查询和统计

---

## 📚 相关文档

- `DUPLICATE_VECTORS_ANALYSIS.md` - 重复向量问题分析
- `VECTOR_STATUS_SUMMARY.md` - 向量化状态总结
- `scripts/VECTOR_CLEANUP_GUIDE.md` - 清理操作指南

---

**迁移完成后，请更新本文档的验证清单并保存记录。**
