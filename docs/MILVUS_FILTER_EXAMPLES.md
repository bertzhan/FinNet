# Milvus 过滤检索示例

**更新日期**: 2026-01-28  
**新增字段**: `company_name`, `doc_type`

---

## 📋 可用的过滤字段

Milvus Collection `financial_documents` 包含以下可用于过滤的字段：

| 字段名 | 类型 | 说明 | 示例值 |
|--------|------|------|--------|
| `chunk_id` | VARCHAR(36) | 分块 UUID（主键） | "abc-123-def-456" |
| `document_id` | VARCHAR(36) | 文档 UUID | "doc-789-xyz-012" |
| `stock_code` | VARCHAR(20) | 股票代码 | "000001", "600000" |
| `company_name` | VARCHAR(100) | 公司名称 | "平安银行", "招商银行" |
| `doc_type` | VARCHAR(50) | 文档类型 | "annual_reports", "quarterly_reports" |
| `year` | INT32 | 年份 | 2023, 2024 |
| `quarter` | INT32 | 季度 | 1, 2, 3, 4 |
| `embedding` | FLOAT_VECTOR | 向量（不用于过滤） | [0.1, 0.2, ...] |

---

## 🔍 过滤表达式语法

Milvus 使用类似 SQL 的表达式语法进行过滤。

### 基本运算符
- 相等：`==`
- 不等：`!=`
- 比较：`>`, `>=`, `<`, `<=`
- 逻辑：`and`, `or`, `not`
- 包含：`in`, `not in`

### 字符串匹配
- 完全匹配：`company_name == "平安银行"`
- 包含（部分匹配）：`company_name like "%平安%"`

---

## 📝 使用示例

### 1. 按公司名称过滤

```python
from src.storage.vector.milvus_client import get_milvus_client
from src.common.constants import MilvusCollection

client = get_milvus_client()

# 查询平安银行的文档
results = client.search_vectors(
    collection_name=MilvusCollection.DOCUMENTS,
    query_vectors=[query_embedding],
    top_k=10,
    expr='company_name == "平安银行"',
    output_fields=["chunk_id", "stock_code", "company_name", "doc_type", "year"]
)
```

### 2. 按文档类型过滤

```python
# 只查询年度报告
results = client.search_vectors(
    collection_name=MilvusCollection.DOCUMENTS,
    query_vectors=[query_embedding],
    top_k=10,
    expr='doc_type == "annual_reports"',
    output_fields=["chunk_id", "company_name", "doc_type", "year"]
)

# 查询年度报告或季度报告
results = client.search_vectors(
    collection_name=MilvusCollection.DOCUMENTS,
    query_vectors=[query_embedding],
    top_k=10,
    expr='doc_type in ["annual_reports", "quarterly_reports"]'
)
```

### 3. 组合过滤：公司 + 文档类型

```python
# 查询平安银行的年度报告
results = client.search_vectors(
    collection_name=MilvusCollection.DOCUMENTS,
    query_vectors=[query_embedding],
    top_k=10,
    expr='company_name == "平安银行" and doc_type == "annual_reports"'
)
```

### 4. 组合过滤：公司 + 年份 + 文档类型

```python
# 查询平安银行 2023 年的年度报告
results = client.search_vectors(
    collection_name=MilvusCollection.DOCUMENTS,
    query_vectors=[query_embedding],
    top_k=10,
    expr='company_name == "平安银行" and year == 2023 and doc_type == "annual_reports"'
)
```

### 5. 多公司查询

```python
# 查询多家银行的年度报告
results = client.search_vectors(
    collection_name=MilvusCollection.DOCUMENTS,
    query_vectors=[query_embedding],
    top_k=10,
    expr='company_name in ["平安银行", "招商银行", "工商银行"] and doc_type == "annual_reports"'
)
```

### 6. 模糊匹配公司名称

```python
# 查询所有包含"银行"的公司
results = client.search_vectors(
    collection_name=MilvusCollection.DOCUMENTS,
    query_vectors=[query_embedding],
    top_k=10,
    expr='company_name like "%银行%"'
)
```

### 7. 时间范围查询

```python
# 查询 2022-2024 年的报告
results = client.search_vectors(
    collection_name=MilvusCollection.DOCUMENTS,
    query_vectors=[query_embedding],
    top_k=10,
    expr='year >= 2022 and year <= 2024'
)
```

### 8. 复杂组合查询

```python
# 查询平安银行或招商银行的 2023 年年度报告或季度报告
results = client.search_vectors(
    collection_name=MilvusCollection.DOCUMENTS,
    query_vectors=[query_embedding],
    top_k=10,
    expr='''
        (company_name == "平安银行" or company_name == "招商银行") 
        and year == 2023 
        and doc_type in ["annual_reports", "quarterly_reports"]
    '''
)
```

### 9. 排除特定条件

```python
# 查询非年度报告的文档
results = client.search_vectors(
    collection_name=MilvusCollection.DOCUMENTS,
    query_vectors=[query_embedding],
    top_k=10,
    expr='doc_type != "annual_reports"'
)
```

---

## 🎯 RAG 应用中的使用

### 在 RAG Retriever 中使用过滤

```python
from src.application.rag.retriever import Retriever

retriever = Retriever()

# 查询平安银行的相关信息
results = retriever.retrieve(
    query="平安银行的营业收入情况",
    top_k=5,
    filters={
        "company_name": "平安银行",
        "doc_type": "annual_reports"
    }
)
```

### 动态构建过滤条件

```python
def build_filter_expr(company_name=None, doc_type=None, year=None, stock_code=None):
    """动态构建过滤表达式"""
    conditions = []
    
    if company_name:
        conditions.append(f'company_name == "{company_name}"')
    
    if doc_type:
        if isinstance(doc_type, list):
            doc_types_str = ', '.join([f'"{dt}"' for dt in doc_type])
            conditions.append(f'doc_type in [{doc_types_str}]')
        else:
            conditions.append(f'doc_type == "{doc_type}"')
    
    if year:
        if isinstance(year, list):
            conditions.append(f'year in {year}')
        else:
            conditions.append(f'year == {year}')
    
    if stock_code:
        conditions.append(f'stock_code == "{stock_code}"')
    
    # 组合所有条件
    if conditions:
        return ' and '.join(conditions)
    return None

# 使用示例
expr = build_filter_expr(
    company_name="平安银行",
    doc_type=["annual_reports", "quarterly_reports"],
    year=[2022, 2023]
)
# 结果: 'company_name == "平安银行" and doc_type in ["annual_reports", "quarterly_reports"] and year in [2022, 2023]'

results = client.search_vectors(
    collection_name=MilvusCollection.DOCUMENTS,
    query_vectors=[query_embedding],
    top_k=10,
    expr=expr
)
```

---

## 📊 常用文档类型值

根据系统设计，`doc_type` 字段可能的值包括：

| 值 | 说明 | 中文名称 |
|----|------|---------|
| `annual_reports` | 年度报告 | 年报 |
| `quarterly_reports` | 季度报告 | 季报 |
| `interim_reports` | 中期报告 | 中报 |
| `ipo_prospectus` | 首次公开发行招股说明书 | IPO 招股书 |

---

## ⚠️ 注意事项

### 1. 字符串字段必须使用引号
```python
# ✅ 正确
expr = 'company_name == "平安银行"'

# ❌ 错误
expr = 'company_name == 平安银行'
```

### 2. 列表中的字符串也需要引号
```python
# ✅ 正确
expr = 'company_name in ["平安银行", "招商银行"]'

# ❌ 错误
expr = 'company_name in [平安银行, 招商银行]'
```

### 3. 数字字段不需要引号
```python
# ✅ 正确
expr = 'year == 2023'
expr = 'year in [2022, 2023]'

# ❌ 错误（但通常也能工作）
expr = 'year == "2023"'
```

### 4. 模糊匹配性能较低
```python
# 模糊匹配会扫描所有记录，性能较低
expr = 'company_name like "%银行%"'

# 如果可能，优先使用精确匹配
expr = 'company_name in ["平安银行", "招商银行", "工商银行"]'
```

### 5. 主键字段可以用于精确查找
```python
# 使用 chunk_id 进行精确查找（最快）
expr = 'chunk_id == "abc-123-def-456"'
```

---

## 🔧 调试技巧

### 1. 测试过滤表达式

```python
from pymilvus import Collection
from src.common.constants import MilvusCollection

collection = Collection(MilvusCollection.DOCUMENTS)

# 测试过滤条件（不进行向量搜索）
results = collection.query(
    expr='company_name == "平安银行"',
    output_fields=["chunk_id", "company_name", "doc_type", "year"],
    limit=10
)

print(f"找到 {len(results)} 条记录")
for result in results:
    print(result)
```

### 2. 统计每个公司的文档数量

```python
# 查询所有唯一的公司名称
collection = Collection(MilvusCollection.DOCUMENTS)
collection.load()

# 获取所有记录（限制数量以避免内存问题）
results = collection.query(
    expr="chunk_id != ''",  # 匹配所有记录
    output_fields=["company_name"],
    limit=10000
)

# 统计
from collections import Counter
company_counts = Counter([r["company_name"] for r in results])
print("公司文档统计:")
for company, count in company_counts.most_common(10):
    print(f"  {company}: {count}")
```

---

## 📚 参考资料

- [Milvus Boolean 表达式文档](https://milvus.io/docs/boolean.md)
- [Milvus 搜索参数文档](https://milvus.io/docs/search.md)
- 项目内部文档：
  - `docs/MILVUS_SCHEMA_MIGRATION.md` - Schema 设计
  - `src/application/rag/retriever.py` - RAG 检索实现

---

**提示**: 合理使用过滤条件可以大幅提升检索的准确性和相关性！
