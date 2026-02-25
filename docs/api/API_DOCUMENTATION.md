# FinNet API 文档

## 目录

- [概述](#概述)
- [基础信息](#基础信息)
- [检索接口 (Retrieval)](#检索接口-retrieval)
- [文档接口 (Document)](#文档接口-document)
- [错误处理](#错误处理)
- [示例代码](#示例代码)

---

## 概述

FinNet API 是一个基于 FastAPI 构建的 RESTful API 服务，提供以下核心功能：

- **检索服务 (Retrieval)**: 支持向量检索、全文检索、图检索和混合检索
- **文档服务 (Document)**: 文档查询、Chunk 列表、公司名称搜索等

---

## 基础信息

### 基础 URL

```
http://localhost:8000
```

### API 版本

当前版本: `v1.0.0`

### 内容类型

所有请求和响应均使用 `application/json` 格式。

### 交互式文档

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## 检索接口 (Retrieval)

前缀: `/api/v1/retrieval`

### 1. 根路径

获取 API 基本信息。

**请求**

```http
GET /
```

**响应**

```json
{
  "message": "FinNet API",
  "version": "1.0.0",
  "docs": "/docs"
}
```

### 2. 全局健康检查

检查 API 服务健康状态。

**请求**

```http
GET /health
```

**响应**

```json
{
  "status": "ok"
}
```

### 3. 向量检索

基于语义相似度的向量检索。

**请求**

```http
POST /api/v1/retrieval/vector
Content-Type: application/json
```

**请求体**

```json
{
  "query": "平安银行2023年第三季度的营业收入",
  "filters": {
    "stock_code": "000001",
    "year": 2023,
    "quarter": 3,
    "doc_type": "quarterly_reports",
    "market": "hs_stock"
  },
  "top_k": 5
}
```

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 是 | 查询文本（1-2000字符） |
| `filters` | object | 否 | 过滤条件 |
| `filters.stock_code` | string | 否 | 股票代码 |
| `filters.year` | integer | 否 | 年份 |
| `filters.quarter` | integer | 否 | 季度（1-4） |
| `filters.doc_type` | string/array | 否 | 文档类型 |
| `filters.market` | string | 否 | 市场（hs_stock/hk_stock/us_stock） |
| `top_k` | integer | 否 | 返回数量（1-100，默认5） |

**响应**

```json
{
  "results": [
    {
      "chunk_id": "123e4567-e89b-12d3-a456-426614174000",
      "document_id": "123e4567-e89b-12d3-a456-426614174001",
      "chunk_text": "2023年第三季度，公司实现营业收入XXX亿元...",
      "title": "一、公司基本情况",
      "title_level": 1,
      "score": 0.95,
      "metadata": {
        "stock_code": "000001",
        "company_name": "平安银行",
        "doc_type": "quarterly_reports",
        "year": 2023,
        "quarter": 3,
        "market": "hs_stock",
        "chunk_index": 0
      }
    }
  ],
  "total": 1,
  "metadata": {
    "retrieval_type": "vector",
    "query": "平安银行2023年第三季度的营业收入",
    "retrieval_time": 0.123,
    "top_k": 5,
    "requested_top_k": 5
  }
}
```

### 4. 全文检索

基于 Elasticsearch 的全文检索。

**请求**

```http
POST /api/v1/retrieval/fulltext
Content-Type: application/json
```

**请求体**

```json
{
  "query": "营业收入 净利润",
  "filters": {
    "stock_code": "000001",
    "year": 2023,
    "quarter": 3,
    "doc_type": "quarterly_reports"
  },
  "top_k": 10
}
```

**请求参数**: 同向量检索

**响应格式**: 同向量检索

### 5. 图检索 - 查询子节点

基于 Neo4j 知识图谱，查询指定 chunk 的所有直接子节点（children）。

**请求**

```http
POST /api/v1/retrieval/graph/children
Content-Type: application/json
```

**请求体**

```json
{
  "chunk_id": "123e4567-e89b-12d3-a456-426614174000",
  "recursive": true,
  "max_depth": null
}
```

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `chunk_id` | string | 是 | 父分块 ID（UUID 格式） |
| `recursive` | boolean | 否 | 是否递归查询所有子节点（默认 true） |
| `max_depth` | integer | 否 | 最大递归深度（recursive=true 时有效，null 表示不限制） |

**响应**

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
    "query_time": 0.012,
    "recursive": true,
    "max_depth": null
  }
}
```

### 6. 混合检索

结合向量检索和全文检索，使用 RRF (Reciprocal Rank Fusion) 算法融合结果。

**请求**

```http
POST /api/v1/retrieval/hybrid
Content-Type: application/json
```

**请求体**

```json
{
  "query": "平安银行营业收入",
  "filters": {
    "year": 2023,
    "doc_type": ["annual_reports", "quarterly_reports"]
  },
  "top_k": 10,
  "hybrid_weights": {
    "vector": 0.5,
    "fulltext": 0.5
  }
}
```

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 是 | 查询文本 |
| `filters` | object | 否 | 过滤条件 |
| `top_k` | integer | 否 | 返回数量（1-100，默认10） |
| `hybrid_weights` | object | 否 | 混合检索权重（默认：vector=0.5, fulltext=0.5） |
| `hybrid_weights.vector` | float | 否 | 向量检索权重（0.0-1.0） |
| `hybrid_weights.fulltext` | float | 否 | 全文检索权重（0.0-1.0） |

**响应格式**: 同向量检索

**注意**: 如果某个检索方式失败，会自动降级到其他可用的检索方式。

### 7. 检索服务健康检查

**请求**

```http
GET /api/v1/retrieval/health
```

**响应**

```json
{
  "status": "healthy",
  "message": "Retrieval service is running",
  "components": {
    "vector_retriever": "ok",
    "fulltext_retriever": "ok",
    "graph_retriever": "ok"
  }
}
```

**状态值**: `healthy` | `degraded` | `unhealthy`

---

## 文档接口 (Document)

前缀: `/api/v1/document`

### 1. 文档查询

根据 stock_code、year、quarter、doc_type 查询 document_id。

**请求**

```http
POST /api/v1/document/query
Content-Type: application/json
```

**请求体**

```json
{
  "stock_code": "000001",
  "year": 2023,
  "quarter": 3,
  "doc_type": "quarterly_reports"
}
```

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `stock_code` | string | 是 | 股票代码 |
| `year` | integer | 是 | 年份（2000-2100） |
| `quarter` | integer | 否 | 季度（1-4），为 null 时查询年度文档 |
| `doc_type` | string | 是 | 文档类型 |

**响应（找到）**

```json
{
  "document_id": "123e4567-e89b-12d3-a456-426614174000",
  "found": true,
  "message": null
}
```

**响应（未找到）**

```json
{
  "document_id": null,
  "found": false,
  "message": "未找到匹配的文档"
}
```

### 2. 获取文档 Chunk 列表

根据 document_id 获取该文档的所有 chunk 列表。

**请求**

```http
GET /api/v1/document/{document_id}/chunks
```

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `document_id` | string | 文档 ID（UUID 格式） |

**响应**

```json
{
  "document_id": "123e4567-e89b-12d3-a456-426614174000",
  "chunks": [
    {
      "chunk_id": "223e4567-e89b-12d3-a456-426614174001",
      "title": "第一章 公司基本情况",
      "title_level": 1,
      "parent_chunk_id": null
    },
    {
      "chunk_id": "323e4567-e89b-12d3-a456-426614174002",
      "title": "1.1 公司简介",
      "title_level": 2,
      "parent_chunk_id": "223e4567-e89b-12d3-a456-426614174001"
    }
  ],
  "total": 2
}
```

### 3. 根据公司名称搜索股票代码

使用 PostgreSQL listed_companies 表进行精确和模糊匹配搜索。

**请求**

```http
POST /api/v1/document/company-code-search
Content-Type: application/json
```

**请求体**

```json
{
  "company_name": "平安银行"
}
```

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `company_name` | string | 是 | 公司名称（1-200字符） |

**响应（唯一匹配）**

```json
{
  "stock_code": "000001",
  "message": null
}
```

**响应（多个候选）**

```json
{
  "stock_code": null,
  "message": "找到 3 个可能的公司，请选择：\n1. 平安银行 (000001) - 平安银行股份有限公司\n2. ..."
}
```

**搜索策略（按优先级）**:
1. 精确匹配简称（name）
2. 精确匹配全称（full_name）
3. 简称包含查询词
4. 全称包含查询词
5. 查询词包含简称
6. 曾用名匹配

### 4. 根据 Chunk ID 查询分块详情

**请求**

```http
POST /api/v1/document/chunk-by-id
Content-Type: application/json
```

**请求体**

```json
{
  "chunk_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

**响应**

```json
{
  "chunk_id": "123e4567-e89b-12d3-a456-426614174000",
  "document_id": "123e4567-e89b-12d3-a456-426614174001",
  "chunk_text": "2023年第三季度，公司实现营业收入XXX亿元...",
  "title": "一、公司基本情况",
  "title_level": 1,
  "parent_chunk_id": "123e4567-e89b-12d3-a456-426614174002",
  "is_table": false
}
```

---

## 错误处理

### 错误响应格式

```json
{
  "detail": "错误描述信息"
}
```

### HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

### 常见错误示例

**400 Bad Request**

```json
{
  "detail": "无效的文档类型: invalid_type。支持的文档类型: annual_reports, quarterly_reports, ..."
}
```

**404 Not Found**

```json
{
  "detail": "文档不存在: document_id"
}
```

**500 Internal Server Error**

```json
{
  "detail": "向量检索过程中发生错误: <错误详情>"
}
```

---

## 示例代码

### cURL

```bash
# 1. 向量检索
curl -X POST "http://localhost:8000/api/v1/retrieval/vector" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "平安银行营业收入",
    "filters": {"stock_code": "000001", "year": 2023},
    "top_k": 10
  }'

# 2. 文档查询
curl -X POST "http://localhost:8000/api/v1/document/query" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_code": "000001",
    "year": 2023,
    "quarter": 3,
    "doc_type": "quarterly_reports"
  }'

# 3. 根据公司名称搜索股票代码
curl -X POST "http://localhost:8000/api/v1/document/company-code-search" \
  -H "Content-Type: application/json" \
  -d '{"company_name": "平安银行"}'

# 4. 获取文档 Chunk 列表
curl "http://localhost:8000/api/v1/document/123e4567-e89b-12d3-a456-426614174000/chunks"

# 5. 健康检查
curl "http://localhost:8000/health"
curl "http://localhost:8000/api/v1/retrieval/health"
```

### Python (requests)

```python
import requests

BASE_URL = "http://localhost:8000"

# 向量检索
def vector_retrieval(query, filters=None, top_k=5):
    response = requests.post(
        f"{BASE_URL}/api/v1/retrieval/vector",
        json={
            "query": query,
            "filters": filters or {},
            "top_k": top_k
        }
    )
    return response.json()

# 公司名称搜索
def company_code_search(company_name):
    response = requests.post(
        f"{BASE_URL}/api/v1/document/company-code-search",
        json={"company_name": company_name}
    )
    return response.json()

# 使用示例
results = vector_retrieval("平安银行营业收入", {"stock_code": "000001"}, top_k=10)
stock_info = company_code_search("平安银行")
```

---

## 文档类型说明

支持的文档类型（`doc_type`）包括：

| 类型 | 说明 |
|------|------|
| `annual_reports` | 年报 |
| `quarterly_reports` | 季报 |
| `interim_reports` | 半年报 |
| `ipo_prospectus` | 招股书 |
| `announcements` | 公告 |
| `10k` | 美股年报 |
| `10q` | 美股季报 |
| `earnings_calls` | 财报电话会 |
| 其他 | 根据实际数据 |

---

## 更新日志

### v1.0.0

- 检索接口：向量、全文、图、混合检索
- 文档接口：文档查询、Chunk 列表、公司名称搜索、Chunk 详情
