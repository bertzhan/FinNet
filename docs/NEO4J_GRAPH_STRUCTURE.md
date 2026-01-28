# Neo4j 图结构说明

**更新日期**: 2026-01-28  
**版本**: V2

---

## 📊 图结构层次

新的图结构采用三层层次结构：

```
Company (根节点)
  └── Document (文档节点)
      └── Chunk (分块节点)
          └── Chunk (子分块节点)
```

## 🏗️ 节点类型

### 1. Company 节点（根节点）

**标签**: `Company`  
**主键**: `code` (股票代码，如 "000001")

**属性**:
- `code`: String - 股票代码（主键，唯一）
- `name`: String - 公司名称

**约束**:
- `code` 唯一约束

**索引**:
- `name` 索引

### 2. Document 节点

**标签**: `Document`  
**主键**: `id` (UUID)

**属性**:
- `id`: UUID - 文档 ID（主键，唯一）
- `stock_code`: String - 股票代码
- `company_name`: String - 公司名称
- `market`: String - 市场（如 "a_share"）
- `doc_type`: String - 文档类型（如 "annual_reports"）
- `year`: Integer - 年份
- `quarter`: Integer - 季度（可选）

**约束**:
- `id` 唯一约束

**索引**:
- `stock_code` 索引
- `doc_type` 索引
- `year` 索引

### 3. Chunk 节点

**标签**: `Chunk`  
**主键**: `id` (UUID)

**属性**:
- `id`: UUID - 分块 ID（主键，唯一）
- `document_id`: UUID - 所属文档 ID
- `chunk_index`: Integer - 分块索引
- `chunk_text`: String - 分块文本内容
- `title`: String - 标题（可选）
- `title_level`: Integer - 标题级别（可选）
- `chunk_size`: Integer - 分块大小
- `is_table`: Boolean - 是否为表格

**约束**:
- `id` 唯一约束

**索引**:
- `document_id` 索引
- `title_level` 索引

---

## 🔗 关系类型

### 1. HAS_DOCUMENT

**方向**: `Company -[:HAS_DOCUMENT]-> Document`  
**说明**: 公司拥有文档

**示例**:
```cypher
MATCH (c:Company {code: "000001"})-[:HAS_DOCUMENT]->(d:Document)
RETURN d
```

### 2. BELONGS_TO

**方向**: `Chunk -[:BELONGS_TO]-> Document`  
**说明**: 分块属于文档（仅顶级分块，parent_chunk_id 为 None）

**示例**:
```cypher
MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document {id: "doc-uuid"})
RETURN c
```

### 3. HAS_CHILD

**方向**: `Chunk -[:HAS_CHILD]-> Chunk`  
**说明**: 父分块包含子分块

**示例**:
```cypher
MATCH (parent:Chunk)-[:HAS_CHILD]->(child:Chunk)
RETURN parent, child
```

---

## 📝 查询示例

### 查询公司的所有文档

```cypher
MATCH (c:Company {code: "000001"})-[:HAS_DOCUMENT]->(d:Document)
RETURN d
```

### 查询文档的所有分块

```cypher
MATCH (d:Document {id: "doc-uuid"})<-[:BELONGS_TO]-(c:Chunk)
RETURN c
ORDER BY c.chunk_index
```

### 查询分块的层级结构

```cypher
MATCH path = (parent:Chunk {id: "chunk-uuid"})-[:HAS_CHILD*]->(child:Chunk)
RETURN path
```

### 查询公司的完整图结构

```cypher
MATCH (company:Company {code: "000001"})
MATCH path = (company)-[:HAS_DOCUMENT]->(doc:Document)<-[:BELONGS_TO]-(chunk:Chunk)
RETURN company, doc, chunk
LIMIT 100
```

---

## 🔧 代码使用示例

### 创建 Company 节点

```python
from src.storage.graph.neo4j_client import get_neo4j_client

client = get_neo4j_client()
company = client.merge_node(
    "Company",
    {"code": "000001", "name": "平安银行"},
    primary_key="code"
)
```

### 创建 Company -> Document 关系

```python
client.create_relationship(
    from_label="Company",
    from_id="000001",  # Company 使用 code 作为主键
    to_label="Document",
    to_id="doc-uuid",
    relationship_type="HAS_DOCUMENT"
)
```

### 使用 GraphBuilder 构建图

```python
from src.processing.graph.graph_builder import GraphBuilder

builder = GraphBuilder()
result = builder.build_document_chunk_graph([document_id1, document_id2])

print(f"公司: {result['companies_processed']}")
print(f"文档: {result['documents_processed']}")
print(f"分块: {result['chunks_created']}")
```

---

## 📈 统计信息

使用 `GraphBuilder.get_graph_stats()` 获取图统计：

```python
stats = builder.get_graph_stats()
# 返回:
# {
#     'company_nodes': 100,
#     'document_nodes': 500,
#     'chunk_nodes': 10000,
#     'has_document_edges': 500,
#     'belongs_to_edges': 10000,
#     'has_child_edges': 2000,
#     'total_nodes': 10600,
#     'total_edges': 12500
# }
```

---

## 🔄 迁移说明

### 从旧结构迁移

如果已有旧数据，需要：

1. **清空旧数据**:
   ```bash
   python scripts/clear_neo4j.py --clear --confirm
   ```

2. **重新构建图**:
   使用 `GraphBuilder.build_document_chunk_graph()` 重新构建

### 新结构优势

- ✅ **层次清晰**: Company -> Document -> Chunk 三层结构
- ✅ **查询高效**: 可以通过公司代码快速定位所有文档
- ✅ **易于扩展**: 可以在 Company 节点上添加更多公司属性
- ✅ **关系明确**: 每个层级的关系类型清晰

---

## 📚 相关文件

- `src/storage/graph/neo4j_client.py` - Neo4j 客户端
- `src/processing/graph/graph_builder.py` - 图构建服务
- `src/processing/compute/dagster/jobs/graph_jobs.py` - Dagster 图构建作业
- `scripts/clear_neo4j.py` - 数据清理脚本
