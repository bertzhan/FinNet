# FinNet API 文档

## 目录

- [概述](#概述)
- [基础信息](#基础信息)
- [认证](#认证)
- [基础接口](#基础接口)
- [问答接口 (QA)](#问答接口-qa)
- [OpenAI 兼容接口](#openai-兼容接口)
- [检索接口 (Retrieval)](#检索接口-retrieval)
- [错误处理](#错误处理)
- [示例代码](#示例代码)

---

## 概述

FinNet API 是一个基于 FastAPI 构建的 RESTful API 服务，提供以下核心功能：

- **问答服务 (QA)**: 基于 RAG (Retrieval-Augmented Generation) 的智能问答
- **检索服务 (Retrieval)**: 支持向量检索、全文检索、图检索和混合检索
- **OpenAI 兼容接口**: 兼容 OpenAI API 格式，支持 LibreChat 等客户端集成

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

## 认证

### API Key 认证（OpenAI 兼容接口）

部分接口（如 OpenAI 兼容接口）需要 API Key 认证。API Key 通过 HTTP Header 传递：

```
Authorization: Bearer <your_api_key>
```

**注意**: 如果未配置 API Key，则无需认证即可访问。

---

## 基础接口

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

---

## 问答接口 (QA)

### 1. 问答查询

基于 RAG 的智能问答接口，支持语义检索和 LLM 生成。

**请求**

```http
POST /api/v1/qa/query
Content-Type: application/json
```

**请求体**

```json
{
  "question": "平安银行2023年第三季度的营业收入是多少？",
  "filters": {
    "stock_code": "000001",
    "year": 2023,
    "quarter": 3,
    "doc_type": "quarterly_reports"
  },
  "top_k": 5,
  "temperature": 0.7,
  "max_tokens": 1000
}
```

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `question` | string | 是 | 用户问题（1-1000字符） |
| `filters` | object | 否 | 过滤条件 |
| `filters.stock_code` | string | 否 | 股票代码 |
| `filters.year` | integer | 否 | 年份 |
| `filters.quarter` | integer | 否 | 季度（1-4） |
| `filters.doc_type` | string | 否 | 文档类型 |
| `filters.market` | string | 否 | 市场（a_share/hk_stock/us_stock） |
| `top_k` | integer | 否 | 检索数量（1-20，默认5） |
| `temperature` | float | 否 | LLM 温度参数（0.0-2.0，默认0.7） |
| `max_tokens` | integer | 否 | 最大生成长度（1-4000，默认1000） |

**响应**

```json
{
  "answer": "根据2023年第三季度报告，平安银行营业收入为XXX亿元...",
  "sources": [
    {
      "chunk_id": "123e4567-e89b-12d3-a456-426614174000",
      "document_id": "123e4567-e89b-12d3-a456-426614174001",
      "title": "一、公司基本情况",
      "stock_code": "000001",
      "company_name": "平安银行",
      "doc_type": "quarterly_reports",
      "year": 2023,
      "quarter": 3,
      "score": 0.95,
      "snippet": "营业收入为XXX亿元..."
    }
  ],
  "metadata": {
    "retrieval_count": 5,
    "generation_time": 1.2,
    "model": "deepseek-chat"
  }
}
```

**响应字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `answer` | string | 生成的答案 |
| `sources` | array | 引用来源列表 |
| `sources[].chunk_id` | string | 分块ID |
| `sources[].document_id` | string | 文档ID |
| `sources[].title` | string | 标题 |
| `sources[].stock_code` | string | 股票代码 |
| `sources[].company_name` | string | 公司名称 |
| `sources[].doc_type` | string | 文档类型 |
| `sources[].year` | integer | 年份 |
| `sources[].quarter` | integer | 季度 |
| `sources[].score` | float | 相似度分数（0-1） |
| `sources[].snippet` | string | 相关文本片段 |
| `metadata` | object | 元数据 |
| `metadata.retrieval_count` | integer | 检索数量 |
| `metadata.generation_time` | float | 生成耗时（秒） |
| `metadata.model` | string | 使用的模型 |

### 2. 健康检查

检查 QA 服务健康状态。

**请求**

```http
GET /api/v1/qa/health
```

**响应**

```json
{
  "status": "healthy",
  "message": "QA service is running",
  "components": {
    "retriever": "ok",
    "context_builder": "ok",
    "llm_service": "ok"
  }
}
```

**状态值**

- `healthy`: 所有组件正常
- `degraded`: 部分组件异常，但服务可用
- `unhealthy`: 服务不可用

---

## OpenAI 兼容接口

### 1. Chat Completions

OpenAI 兼容的聊天完成接口，支持流式和非流式响应。

**请求**

```http
POST /v1/chat/completions
Content-Type: application/json
Authorization: Bearer <your_api_key>
```

**请求体（非流式）**

```json
{
  "model": "finnet-rag",
  "messages": [
    {
      "role": "user",
      "content": "平安银行2023年第三季度的营业收入是多少？"
    }
  ],
  "temperature": 0.7,
  "max_tokens": 1000,
  "stream": false
}
```

**请求体（流式）**

```json
{
  "model": "finnet-rag",
  "messages": [
    {
      "role": "user",
      "content": "平安银行2023年第三季度的营业收入是多少？"
    }
  ],
  "temperature": 0.7,
  "max_tokens": 1000,
  "stream": true
}
```

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `model` | string | 是 | 模型名称（如 "finnet-rag"） |
| `messages` | array | 是 | 消息列表（至少1条） |
| `messages[].role` | string | 是 | 角色（system/user/assistant） |
| `messages[].content` | string | 是 | 消息内容 |
| `temperature` | float | 否 | 温度参数（0.0-2.0，默认0.7） |
| `max_tokens` | integer | 否 | 最大生成长度（1-4000，默认1000） |
| `stream` | boolean | 否 | 是否流式返回（默认false） |
| `top_p` | float | 否 | Top-p 采样（0.0-1.0） |
| `frequency_penalty` | float | 否 | 频率惩罚（-2.0-2.0） |
| `presence_penalty` | float | 否 | 存在惩罚（-2.0-2.0） |
| `stop` | string/array | 否 | 停止序列 |
| `user` | string | 否 | 用户ID |

**响应（非流式）**

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "finnet-rag",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "根据2023年第三季度报告..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 200,
    "total_tokens": 300
  }
}
```

**响应（流式）**

流式响应使用 Server-Sent Events (SSE) 格式：

```
data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1234567890,"model":"finnet-rag","choices":[{"index":0,"delta":{"role":"assistant","content":"根据"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1234567890,"model":"finnet-rag","choices":[{"index":0,"delta":{"content":"2023年"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1234567890,"model":"finnet-rag","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

### 2. 模型列表

获取可用模型列表。

**请求**

```http
GET /v1/models
```

**响应**

```json
{
  "object": "list",
  "data": [
    {
      "id": "finnet-rag",
      "object": "model",
      "created": 1677610602,
      "owned_by": "finnet"
    }
  ]
}
```

**注意**: 此接口无需 API Key 认证。

---

## 检索接口 (Retrieval)

### 1. 向量检索

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
    "doc_type": "quarterly_reports"
  },
  "top_k": 5
}
```

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 是 | 查询文本（1-2000字符） |
| `filters` | object | 否 | 过滤条件（同 QA 接口） |
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
        "market": "a_share",
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

### 2. 全文检索

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
    "doc_type": "ipo_prospectus"
  },
  "top_k": 10
}
```

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 是 | 查询文本（支持关键词搜索） |
| `filters` | object | 否 | 过滤条件 |
| `top_k` | integer | 否 | 返回数量（1-100，默认5） |

**响应格式**: 同向量检索

### 3. 图检索 - 查询子节点

基于 Neo4j 知识图谱，查询指定 chunk 的所有直接子节点（children）。

**请求**

```http
POST /api/v1/retrieval/graph/children
Content-Type: application/json
```

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

### 4. 混合检索

结合向量检索、全文检索和图检索的混合检索，使用 RRF (Reciprocal Rank Fusion) 算法融合结果。

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

### 5. 根据公司名称搜索股票代码（company-code-search）

根据公司名称使用 PostgreSQL listed_companies 表进行精确和模糊匹配搜索，返回匹配的股票代码。

**请求**

```http
POST /api/v1/retrieval/company-code-search
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

**响应**

```json
{
  "stock_code": "000001",
  "message": null
}
```

**响应字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `stock_code` | string/null | 股票代码（如果唯一匹配则返回，否则为 null） |
| `message` | string/null | 提示信息（如果有多个候选或未找到，包含候选列表或提示） |

**工作原理**

使用 PostgreSQL 数据库中的 `listed_companies` 表进行搜索，搜索策略（按优先级）：
1. 精确匹配简称（name）
2. 精确匹配全称（full_name）
3. 简称包含查询词
4. 全称包含查询词
5. 查询词包含简称（用户输入全称的情况）
6. 曾用名匹配

如果找到唯一匹配，返回对应的股票代码；如果找到多个候选（2-5个），返回提示信息；如果候选过多（>5个），提示用户进一步明确。

**示例**

```bash
# 搜索"平安银行"的股票代码
curl -X POST "http://localhost:8000/api/v1/retrieval/company-code-search" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "平安银行"
  }'
```

### 6. 健康检查

检查检索服务健康状态。

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

---

## 错误处理

### 错误响应格式

所有错误响应遵循以下格式：

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
| 401 | 未授权（API Key 无效） |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

### 常见错误

#### 400 Bad Request

```json
{
  "detail": "无效的文档类型: invalid_type。支持的文档类型: annual_reports, quarterly_reports, ..."
}
```

#### 401 Unauthorized

```json
{
  "detail": {
    "error": {
      "message": "Invalid API key",
      "type": "invalid_request_error",
      "code": "invalid_api_key"
    }
  }
}
```

#### 500 Internal Server Error

```json
{
  "detail": "查询过程中发生错误: <错误详情>"
}
```

---

## 示例代码

### Python (requests)

```python
import requests

# 基础配置
BASE_URL = "http://localhost:8000"
API_KEY = "your_api_key_here"

# 1. 问答查询
def qa_query(question, filters=None):
    url = f"{BASE_URL}/api/v1/qa/query"
    payload = {
        "question": question,
        "filters": filters or {},
        "top_k": 5,
        "temperature": 0.7
    }
    response = requests.post(url, json=payload)
    return response.json()

# 使用示例
result = qa_query(
    question="平安银行2023年第三季度的营业收入是多少？",
    filters={
        "stock_code": "000001",
        "year": 2023,
        "quarter": 3
    }
)
print(result["answer"])

# 2. 向量检索
def vector_retrieval(query, filters=None, top_k=5):
    url = f"{BASE_URL}/api/v1/retrieval/vector"
    payload = {
        "query": query,
        "filters": filters or {},
        "top_k": top_k
    }
    response = requests.post(url, json=payload)
    return response.json()

# 使用示例
results = vector_retrieval(
    query="平安银行营业收入",
    filters={"stock_code": "000001", "year": 2023},
    top_k=10
)
for result in results["results"]:
    print(f"Score: {result['score']}, Text: {result['chunk_text'][:100]}...")

# 3. 根据公司名称搜索股票代码（company-code-search）
def company_code_search(company_name):
    url = f"{BASE_URL}/api/v1/retrieval/company-code-search"
    payload = {
        "company_name": company_name
    }
    response = requests.post(url, json=payload)
    return response.json()

# 使用示例
result = company_code_search("平安银行")
print(f"股票代码: {result['stock_code']}")
if result.get('message'):
    print(f"提示信息: {result['message']}")

# 4. OpenAI 兼容接口（非流式）
def chat_completion(messages, model="finnet-rag", stream=False):
    url = f"{BASE_URL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

# 使用示例
messages = [
    {"role": "user", "content": "平安银行2023年第三季度的营业收入是多少？"}
]
result = chat_completion(messages)
print(result["choices"][0]["message"]["content"])

# 4. OpenAI 兼容接口（流式）
def chat_completion_stream(messages, model="finnet-rag"):
    url = f"{BASE_URL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": messages,
        "stream": True
    }
    response = requests.post(url, json=payload, headers=headers, stream=True)
    
    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith('data: '):
                data_str = line_str[6:]  # 移除 "data: " 前缀
                if data_str == '[DONE]':
                    break
                import json
                data = json.loads(data_str)
                if 'choices' in data and len(data['choices']) > 0:
                    delta = data['choices'][0].get('delta', {})
                    content = delta.get('content', '')
                    if content:
                        print(content, end='', flush=True)
    print()  # 换行

# 使用示例
messages = [
    {"role": "user", "content": "平安银行2023年第三季度的营业收入是多少？"}
]
chat_completion_stream(messages)
```

### cURL

```bash
# 1. 问答查询
curl -X POST "http://localhost:8000/api/v1/qa/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "平安银行2023年第三季度的营业收入是多少？",
    "filters": {
      "stock_code": "000001",
      "year": 2023,
      "quarter": 3
    },
    "top_k": 5
  }'

# 2. 向量检索
curl -X POST "http://localhost:8000/api/v1/retrieval/vector" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "平安银行营业收入",
    "filters": {
      "stock_code": "000001",
      "year": 2023
    },
    "top_k": 10
  }'

# 3. OpenAI 兼容接口（非流式）
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_api_key_here" \
  -d '{
    "model": "finnet-rag",
    "messages": [
      {
        "role": "user",
        "content": "平安银行2023年第三季度的营业收入是多少？"
      }
    ],
    "stream": false
  }'

# 4. OpenAI 兼容接口（流式）
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_api_key_here" \
  -d '{
    "model": "finnet-rag",
    "messages": [
      {
        "role": "user",
        "content": "平安银行2023年第三季度的营业收入是多少？"
      }
    ],
    "stream": true
  }' \
  --no-buffer

# 5. 根据公司名称搜索股票代码
curl -X POST "http://localhost:8000/api/v1/retrieval/company-code-search" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "平安银行"
  }'

# 6. 健康检查
curl "http://localhost:8000/health"
curl "http://localhost:8000/api/v1/qa/health"
curl "http://localhost:8000/api/v1/retrieval/health"
```

### JavaScript (fetch)

```javascript
const BASE_URL = "http://localhost:8000";
const API_KEY = "your_api_key_here";

// 1. 问答查询
async function qaQuery(question, filters = {}) {
  const response = await fetch(`${BASE_URL}/api/v1/qa/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      question,
      filters,
      top_k: 5,
      temperature: 0.7,
    }),
  });
  return await response.json();
}

// 使用示例
const result = await qaQuery(
  "平安银行2023年第三季度的营业收入是多少？",
  {
    stock_code: "000001",
    year: 2023,
    quarter: 3,
  }
);
console.log(result.answer);

// 2. 根据公司名称搜索股票代码（company-code-search）
async function companyCodeSearch(companyName) {
  const response = await fetch(`${BASE_URL}/api/v1/retrieval/company-code-search`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      company_name: companyName,
    }),
  });
  return await response.json();
}

// 使用示例
const searchResult = await companyCodeSearch("平安银行");
console.log(`股票代码: ${searchResult.stock_code}`);
if (searchResult.message) {
  console.log(`提示信息: ${searchResult.message}`);
}
console.log(`公司名称: ${searchResult.company_name}`);
console.log(`最可能的股票代码: ${searchResult.stock_code}`);
searchResult.all_candidates.forEach((candidate) => {
  console.log(`${candidate.stock_code}: ${candidate.votes} 票 (置信度: ${(candidate.confidence * 100).toFixed(1)}%)`);
});

// 3. OpenAI 兼容接口（流式）
async function chatCompletionStream(messages) {
  const response = await fetch(`${BASE_URL}/v1/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${API_KEY}`,
    },
    body: JSON.stringify({
      model: "finnet-rag",
      messages,
      stream: true,
    }),
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split("\n");

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = line.slice(6);
        if (data === "[DONE]") return;

        try {
          const json = JSON.parse(data);
          const content = json.choices?.[0]?.delta?.content;
          if (content) {
            process.stdout.write(content);
          }
        } catch (e) {
          // 忽略解析错误
        }
      }
    }
  }
}

// 使用示例
await chatCompletionStream([
  { role: "user", content: "平安银行2023年第三季度的营业收入是多少？" },
]);
```

---

## 文档类型说明

支持的文档类型（`doc_type`）包括：

- `annual_reports`: 年报
- `quarterly_reports`: 季报
- `interim_reports`: 半年报
- `ipo_prospectus`: 招股书
- `announcements`: 公告
- 其他文档类型（根据实际数据）

---

## 更新日志

### v1.0.0 (2025-01-XX)

- 初始版本发布
- 支持问答接口 (QA)
- 支持 OpenAI 兼容接口
- 支持向量检索、全文检索、图检索和混合检索

---

## 支持与反馈

如有问题或建议，请联系开发团队或提交 Issue。
