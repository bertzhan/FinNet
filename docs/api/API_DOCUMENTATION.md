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

### 3. 图检索

基于 Neo4j 知识图谱的检索。

**请求**

```http
POST /api/v1/retrieval/graph
Content-Type: application/json
```

**请求体（文档检索）**

```json
{
  "query": "000001",
  "query_type": "document",
  "filters": {
    "stock_code": "000001",
    "year": 2023,
    "doc_type": "annual_reports"
  },
  "top_k": 10
}
```

**请求体（层级遍历）**

```json
{
  "query": "document_id_123",
  "query_type": "hierarchy",
  "max_depth": 3,
  "top_k": 20
}
```

**请求体（Cypher 查询）**

```json
{
  "query_type": "cypher",
  "cypher_query": "MATCH (d:Document {stock_code: $stock_code}) RETURN d LIMIT 10",
  "cypher_parameters": {
    "stock_code": "000001"
  },
  "top_k": 10
}
```

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 否 | 查询文本或节点ID |
| `query_type` | string | 是 | 查询类型：document/chunk/hierarchy/cypher |
| `filters` | object | 否 | 过滤条件 |
| `max_depth` | integer | 否 | 最大遍历深度（1-10，用于层级查询） |
| `top_k` | integer | 否 | 返回数量（1-100，默认10） |
| `cypher_query` | string | 否 | 自定义 Cypher 查询（query_type=cypher 时必填） |
| `cypher_parameters` | object | 否 | Cypher 查询参数 |

**查询类型说明**

- `document`: 文档检索，根据文档ID或股票代码查找相关文档
- `chunk`: 分块检索，根据分块ID查找相关分块
- `hierarchy`: 层级遍历，根据文档/分块ID遍历其层级结构
- `cypher`: 自定义 Cypher 查询，支持复杂的图查询

**响应格式**: 同向量检索

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
    "fulltext": 0.3,
    "graph": 0.2
  }
}
```

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 是 | 查询文本 |
| `filters` | object | 否 | 过滤条件 |
| `top_k` | integer | 否 | 返回数量（1-100，默认10） |
| `hybrid_weights` | object | 否 | 混合检索权重（默认：vector=0.5, fulltext=0.3, graph=0.2） |
| `hybrid_weights.vector` | float | 否 | 向量检索权重（0.0-1.0） |
| `hybrid_weights.fulltext` | float | 否 | 全文检索权重（0.0-1.0） |
| `hybrid_weights.graph` | float | 否 | 图检索权重（0.0-1.0） |

**响应格式**: 同向量检索

**注意**: 如果某个检索方式失败，会自动降级到其他可用的检索方式。

### 5. 根据公司名称搜索股票代码

根据公司名称使用 Elasticsearch 模糊搜索排名前十的文档，然后根据这些文档的 `stock_code` 进行投票决定最可能的股票代码。

**请求**

```http
POST /api/v1/retrieval/company-name-search
Content-Type: application/json
```

**请求体**

```json
{
  "company_name": "平安银行",
  "top_k": 10
}
```

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `company_name` | string | 是 | 公司名称（1-200字符） |
| `top_k` | integer | 否 | 检索文档数量，用于投票（1-20，默认10） |

**响应**

```json
{
  "stock_code": "000001"
}
```

**响应字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `stock_code` | string/null | 股票代码（投票最多的，如果未找到则为 null） |

**工作原理**

1. 使用 Elasticsearch 在公司名称字段中进行模糊搜索（支持精确匹配、前缀匹配、通配符匹配）
2. 获取排名前 `top_k` 的文档
3. 从这些文档中提取 `stock_code`
4. 统计每个 `stock_code` 出现的次数（投票）
5. 返回投票最多的 `stock_code` 作为最终的股票代码

**示例**

```bash
# 搜索"平安银行"的股票代码
curl -X POST "http://localhost:8000/api/v1/retrieval/company-name-search" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "平安银行",
    "top_k": 10
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

# 3. 根据公司名称搜索股票代码
def company_name_search(company_name, top_k=10):
    url = f"{BASE_URL}/api/v1/retrieval/company-name-search"
    payload = {
        "company_name": company_name,
        "top_k": top_k
    }
    response = requests.post(url, json=payload)
    return response.json()

# 使用示例
result = company_name_search("平安银行", top_k=10)
print(f"公司名称: {result['company_name']}")
print(f"最可能的股票代码: {result['stock_code']}")
print(f"所有候选:")
for candidate in result['all_candidates']:
    print(f"  {candidate['stock_code']}: {candidate['votes']} 票 (置信度: {candidate['confidence']:.2%})")

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
curl -X POST "http://localhost:8000/api/v1/retrieval/company-name-search" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "平安银行",
    "top_k": 10
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

// 2. 根据公司名称搜索股票代码
async function companyNameSearch(companyName, topK = 10) {
  const response = await fetch(`${BASE_URL}/api/v1/retrieval/company-name-search`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      company_name: companyName,
      top_k: topK,
    }),
  });
  return await response.json();
}

// 使用示例
const searchResult = await companyNameSearch("平安银行", 10);
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
