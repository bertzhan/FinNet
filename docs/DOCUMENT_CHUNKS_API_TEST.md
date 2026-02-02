# 文档Chunks查询接口测试指南

## 接口说明

### 接口路径
```
GET /api/v1/document/{document_id}/chunks
```

### 功能描述
根据document_id获取该文档的所有chunk列表，返回JSON格式，包含：
- `chunk_id`: Chunk ID（UUID字符串）
- `title`: Chunk标题
- `parent_chunk_id`: 父Chunk ID（UUID字符串），如果为None则表示顶级chunk

### 响应格式
```json
{
    "document_id": "123e4567-e89b-12d3-a456-426614174000",
    "chunks": [
        {
            "chunk_id": "223e4567-e89b-12d3-a456-426614174001",
            "title": "第一章 公司基本情况",
            "parent_chunk_id": null
        },
        {
            "chunk_id": "323e4567-e89b-12d3-a456-426614174002",
            "title": "1.1 公司简介",
            "parent_chunk_id": "223e4567-e89b-12d3-a456-426614174001"
        }
    ],
    "total": 2
}
```

## 测试方法

### 方法1: 使用测试脚本（推荐）

#### 1. 获取测试用的document_id

```bash
# 从数据库获取一些document_id
python examples/get_document_id_for_test.py --limit 5
```

这会显示最近的一些文档及其ID，并推荐一个有chunks的文档用于测试。

#### 2. 运行测试脚本

**方式A: 直接使用document_id**
```bash
python examples/test_document_chunks.py --document-id <document_id>
```

**方式B: 通过查询参数获取document_id后测试**
```bash
python examples/test_document_chunks.py \
    --stock-code 000001 \
    --year 2024 \
    --quarter 3 \
    --doc-type quarterly_reports
```

**方式C: 使用默认参数（自动查询并测试）**
```bash
python examples/test_document_chunks.py
```

### 方法2: 使用curl命令

```bash
# 替换 <document_id> 为实际的文档ID
curl -X GET "http://localhost:8000/api/v1/document/<document_id>/chunks" \
     -H "Content-Type: application/json"
```

### 方法3: 使用Python requests

```python
import requests

document_id = "123e4567-e89b-12d3-a456-426614174000"
url = f"http://localhost:8000/api/v1/document/{document_id}/chunks"

response = requests.get(url)
print(response.json())
```

## 测试场景

### 1. 正常情况测试
- 使用一个存在且有chunks的document_id
- 验证返回的chunks列表格式正确
- 验证chunk_id, title, parent_chunk_id字段都存在

### 2. 边界情况测试
- **文档不存在**: 使用一个不存在的document_id，应该返回404
- **文档没有chunks**: 使用一个存在但没有chunks的document_id，应该返回空列表
- **无效的document_id格式**: 使用非UUID格式的字符串，应该返回400

### 3. 错误处理测试
```bash
# 测试无效的UUID格式
curl -X GET "http://localhost:8000/api/v1/document/invalid-uuid/chunks"

# 测试不存在的document_id
curl -X GET "http://localhost:8000/api/v1/document/00000000-0000-0000-0000-000000000000/chunks"
```

## 预期结果

### 成功响应（200）
- 返回JSON格式的chunks列表
- 每个chunk包含chunk_id, title, parent_chunk_id字段
- total字段显示chunks总数

### 错误响应

**404 - 文档不存在**
```json
{
    "detail": "文档不存在: document_id=..."
}
```

**400 - 无效的UUID格式**
```json
{
    "detail": "无效的document_id格式: ..."
}
```

## 测试检查清单

- [ ] API服务正在运行（`http://localhost:8000/health`）
- [ ] 数据库中有文档记录
- [ ] 至少有一个文档有chunks数据
- [ ] 测试脚本可以正常运行
- [ ] 正常情况测试通过
- [ ] 错误情况测试通过（404, 400）
- [ ] 返回的JSON格式正确
- [ ] chunk_id, title, parent_chunk_id字段都存在

## 相关文件

- API路由: `src/api/routes/document.py`
- Schema定义: `src/api/schemas/document.py`
- CRUD操作: `src/storage/metadata/crud.py` (get_document_chunks函数)
- 测试脚本: `examples/test_document_chunks.py`
- 辅助脚本: `examples/get_document_id_for_test.py`
