# Milvus Schema V2 - 快速参考

**版本**: V2  
**更新日期**: 2026-01-28

---

## 📊 Schema 结构

```python
Collection: financial_documents
Dimension: 3072 (OpenAI text-embedding-3-large)
Index Type: IVF_FLAT
Metric Type: L2
```

### 字段列表

| # | 字段名 | 类型 | 长度 | 主键 | 说明 |
|---|--------|------|------|------|------|
| 1 | `chunk_id` | VARCHAR | 36 | ✓ | 分块 UUID（主键，保证唯一性） |
| 2 | `document_id` | VARCHAR | 36 | | 文档 UUID |
| 3 | `stock_code` | VARCHAR | 20 | | 股票代码（如 000001） |
| 4 | `company_name` | VARCHAR | 100 | | 公司名称（如 平安银行）🆕 |
| 5 | `doc_type` | VARCHAR | 50 | | 文档类型（如 annual_reports）🆕 |
| 6 | `year` | INT32 | - | | 年份 |
| 7 | `quarter` | INT32 | - | | 季度 |
| 8 | `embedding` | FLOAT_VECTOR | 3072 | | 向量 |

---

## 🎯 主要特性

### 1. 主键设计 ⭐
- **主键**: `chunk_id`（UUID）
- **优势**: 自动 upsert，重新向量化时覆盖旧向量，不产生重复

### 2. 过滤能力 🔍
- **基础过滤**: `stock_code`, `year`, `quarter`
- **增强过滤**: `company_name`, `doc_type` 🆕
- **支持**: 精确匹配、范围查询、模糊匹配、组合条件

### 3. 检索性能 🚀
- **索引类型**: IVF_FLAT（倒排文件索引）
- **距离度量**: L2（欧氏距离）
- **查询优化**: 支持表达式过滤 + 向量相似度

---

## 📝 使用示例

### 插入向量

```python
from src.storage.vector.milvus_client import get_milvus_client
from src.common.constants import MilvusCollection

client = get_milvus_client()

client.insert_vectors(
    collection_name=MilvusCollection.DOCUMENTS,
    embeddings=[[0.1] * 3072],
    document_ids=["doc-uuid"],
    chunk_ids=["chunk-uuid"],
    stock_codes=["000001"],
    company_names=["平安银行"],      # 🆕
    doc_types=["annual_reports"],    # 🆕
    years=[2023],
    quarters=[4]
)
```

### 检索向量

```python
# 基础检索
results = client.search_vectors(
    collection_name=MilvusCollection.DOCUMENTS,
    query_vectors=[query_embedding],
    top_k=10
)

# 按公司名称过滤 🆕
results = client.search_vectors(
    collection_name=MilvusCollection.DOCUMENTS,
    query_vectors=[query_embedding],
    top_k=10,
    expr='company_name == "平安银行"'
)

# 按文档类型过滤 🆕
results = client.search_vectors(
    collection_name=MilvusCollection.DOCUMENTS,
    query_vectors=[query_embedding],
    top_k=10,
    expr='doc_type == "annual_reports"'
)

# 组合过滤 🆕
results = client.search_vectors(
    collection_name=MilvusCollection.DOCUMENTS,
    query_vectors=[query_embedding],
    top_k=10,
    expr='company_name == "平安银行" and doc_type == "annual_reports" and year == 2023'
)
```

---

## 🔄 V1 → V2 变更

| 项目 | V1 | V2 | 影响 |
|------|----|----|------|
| 主键 | 自动生成 INT64 | `chunk_id` (VARCHAR) | ✅ 解决重复向量 |
| 过滤字段 | 3 个 | 5 个 | ✅ 更精确的检索 |
| Upsert | ❌ 需手动删除 | ✅ 自动覆盖 | ✅ 简化代码 |
| 字段总数 | 7 个 | 9 个 | +2 个过滤字段 |

---

## 📚 文档类型值

| 值 | 说明 |
|----|------|
| `annual_reports` | 年度报告 |
| `quarterly_reports` | 季度报告 |
| `interim_reports` | 中期报告 |
| `ipo_prospectus` | IPO 招股说明书 |

---

## 🚀 性能优化建议

### 1. 过滤表达式优化
```python
# ✅ 推荐：精确匹配
expr = 'company_name == "平安银行"'

# ⚠️ 慎用：模糊匹配（性能较低）
expr = 'company_name like "%银行%"'
```

### 2. 组合过滤顺序
```python
# ✅ 推荐：高选择性条件在前
expr = 'stock_code == "000001" and year == 2023 and doc_type == "annual_reports"'

# 相对较慢：低选择性条件在前
expr = 'doc_type == "annual_reports" and stock_code == "000001" and year == 2023'
```

### 3. 批量插入
```python
# ✅ 推荐：批量插入（100-1000条）
client.insert_vectors(..., chunk_ids=chunk_ids_batch)

# ❌ 避免：单条插入
for chunk_id in chunk_ids:
    client.insert_vectors(..., chunk_ids=[chunk_id])
```

---

## ⚠️ 注意事项

1. **主键唯一性**: `chunk_id` 必须全局唯一
2. **字符串长度**: 注意字段长度限制（company_name: 100, doc_type: 50）
3. **过滤语法**: 字符串值必须使用双引号 `"value"`
4. **迁移必需**: V2 Schema 不兼容 V1，需要重建 Collection

---

## 📖 相关文档

- **迁移指南**: `docs/MILVUS_SCHEMA_MIGRATION.md`
- **过滤示例**: `docs/MILVUS_FILTER_EXAMPLES.md`
- **变更总结**: `SCHEMA_CHANGE_SUMMARY.md`
- **状态报告**: `VECTOR_STATUS_SUMMARY.md`

---

## 🎉 优势总结

✅ **无重复向量**: 主键保证，自动 upsert  
✅ **精确检索**: 公司名称 + 文档类型过滤  
✅ **代码简化**: 无需手动删除旧向量  
✅ **性能提升**: 减少冗余数据  
✅ **易于维护**: 数据一致性保证  

---

**版本**: V2  
**状态**: ✅ 已实现，等待部署  
**更新**: 2026-01-28
