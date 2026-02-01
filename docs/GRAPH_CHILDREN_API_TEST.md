# 图检索子节点查询接口测试指南

## 接口说明

### 接口路径
```
POST /api/v1/retrieval/graph/children
```

### 功能描述
根据给定的 `chunk_id`，查询该 chunk 的所有直接子节点（children），返回包含 `chunk_id` 和 `title` 的列表。

### 请求格式

**请求体**
```json
{
  "chunk_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `chunk_id` | string | 是 | 父分块 ID（UUID 格式） |

### 响应格式

**成功响应（200）**
```json
{
  "children": [
    {
      "chunk_id": "123e4567-e89b-12d3-a456-426614174001",
      "title": "第一章 公司基本情况"
    },
    {
      "chunk_id": "123e4567-e89b-12d3-a456-426614174002",
      "title": "第二章 财务数据"
    }
  ],
  "total": 2,
  "metadata": {
    "parent_chunk_id": "123e4567-e89b-12d3-a456-426614174000",
    "query_time": 0.012
  }
}
```

**响应字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `children` | array | 子节点列表 |
| `children[].chunk_id` | string | 子分块 ID |
| `children[].title` | string | 子分块标题（可能为 null） |
| `total` | integer | 子节点总数 |
| `metadata` | object | 元数据 |
| `metadata.parent_chunk_id` | string | 父分块 ID |
| `metadata.query_time` | float | 查询耗时（秒） |

## 测试方法

### 方法1: 使用测试脚本（推荐）

#### 1. 直接测试方法（不依赖API服务）

```bash
# 测试 GraphRetriever.get_children() 方法
python examples/test_graph_children_simple.py <chunk_id>
```

**示例**
```bash
python examples/test_graph_children_simple.py 123e4567-e89b-12d3-a456-426614174000
```

#### 2. 通过API接口测试（需要API服务运行）

```bash
# 测试完整的API接口
python examples/test_graph_children.py <chunk_id>

# 或从文档获取chunk_id后测试
python examples/test_graph_children.py <chunk_id> <document_id>
```

### 方法2: 使用curl命令

```bash
# 替换 <chunk_id> 为实际的chunk ID
curl -X POST "http://localhost:8000/api/v1/retrieval/graph/children" \
     -H "Content-Type: application/json" \
     -d '{
       "chunk_id": "123e4567-e89b-12d3-a456-426614174000"
     }'
```

### 方法3: 使用Python requests

```python
import requests

url = "http://localhost:8000/api/v1/retrieval/graph/children"
payload = {
    "chunk_id": "123e4567-e89b-12d3-a456-426614174000"
}

response = requests.post(url, json=payload)
print(response.json())
```

## 获取测试用的chunk_id

### 方法1: 通过文档chunks接口获取

```bash
# 1. 获取文档的chunks列表
curl -X GET "http://localhost:8000/api/v1/document/<document_id>/chunks"

# 2. 从返回的chunks中选择一个有子节点的chunk_id
# 查找 parent_chunk_id 不为 null 的chunk，其parent_chunk_id就是我们要测试的chunk_id
```

### 方法2: 从数据库查询

```sql
-- 查询有子节点的chunk（parent_chunk_id不为null的chunk的parent_chunk_id）
SELECT DISTINCT parent_chunk_id 
FROM document_chunks 
WHERE parent_chunk_id IS NOT NULL 
LIMIT 1;
```

### 方法3: 使用测试脚本自动获取

```bash
# 脚本会自动从文档获取chunk_id
python examples/test_graph_children.py <document_id>
```

## 测试场景

### 1. 正常情况测试
- 使用一个存在且有子节点的 `chunk_id`
- 验证返回的 `children` 列表格式正确
- 验证 `chunk_id` 和 `title` 字段都存在
- 验证 `total` 字段等于 `children` 数组长度

### 2. 边界情况测试
- **chunk没有子节点**: 使用一个存在但没有子节点的 `chunk_id`，应该返回空列表
- **chunk不存在**: 使用一个不存在的 `chunk_id`，应该返回空列表（不会报错）
- **无效的chunk_id格式**: 使用非UUID格式的字符串，应该返回400错误

### 3. 错误处理测试

```bash
# 测试无效的UUID格式
curl -X POST "http://localhost:8000/api/v1/retrieval/graph/children" \
     -H "Content-Type: application/json" \
     -d '{"chunk_id": "invalid-uuid"}'

# 测试不存在的chunk_id
curl -X POST "http://localhost:8000/api/v1/retrieval/graph/children" \
     -H "Content-Type: application/json" \
     -d '{"chunk_id": "00000000-0000-0000-0000-000000000000"}'
```

## 预期结果

### 成功响应（200）
- 返回JSON格式的子节点列表
- 每个子节点包含 `chunk_id` 和 `title` 字段
- `total` 字段显示子节点总数
- `metadata` 包含查询元数据

### 错误响应

**400 - 无效的UUID格式**
```json
{
  "detail": "查询子节点过程中发生错误: ..."
}
```

**500 - 服务器错误**
```json
{
  "detail": "查询子节点过程中发生错误: ..."
}
```

## 测试检查清单

- [ ] API服务正在运行（`http://localhost:8000/health`）
- [ ] Neo4j 图数据库正在运行
- [ ] 数据库中有chunk记录
- [ ] 至少有一个chunk有子节点（HAS_CHILD关系）
- [ ] 测试脚本可以正常运行
- [ ] 正常情况测试通过
- [ ] 边界情况测试通过（空列表、无效格式）
- [ ] 返回的JSON格式正确
- [ ] `chunk_id` 和 `title` 字段都存在

## 相关文件

- API路由: `src/api/routes/retrieval.py` (get_chunk_children函数)
- Schema定义: `src/api/schemas/retrieval.py` (ChunkChildrenRequest, ChunkChildrenResponse)
- 图检索器: `src/application/rag/graph_retriever.py` (get_children方法)
- 测试脚本: 
  - `examples/test_graph_children.py` (API接口测试)
  - `examples/test_graph_children_simple.py` (直接方法测试)

## 注意事项

1. **只查询直接子节点**: 此接口只返回直接子节点（一层），不包括子节点的子节点
2. **空列表不是错误**: 如果chunk没有子节点，返回空列表是正常情况，不是错误
3. **Neo4j关系**: 确保Neo4j中存在 `HAS_CHILD` 关系，否则查询结果为空
4. **chunk_id格式**: 必须是有效的UUID格式字符串
