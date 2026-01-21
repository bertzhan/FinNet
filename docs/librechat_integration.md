# LibreChat 集成指南

本文档介绍如何将 FinNet RAG API 服务接入 LibreChat 的 Custom AI Endpoints。

## 概述

FinNet API 服务提供了 OpenAI 兼容的 `/v1/chat/completions` 接口，支持流式和非流式响应，可以直接作为 LibreChat 的自定义 AI 端点使用。

## 前置要求

1. FinNet API 服务已启动并运行
2. LibreChat 已安装并配置
3. 确保 FinNet API 服务可以从 LibreChat 访问（网络连通性）

## 配置步骤

### 1. 配置 FinNet API 服务

确保 FinNet API 服务正在运行，默认端口为 `8000`。可以通过以下方式启动：

```bash
# 方式1：直接运行
python -m src.api.main

# 方式2：使用 uvicorn
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

### 2. 配置 LibreChat

#### 2.1 创建 `librechat.yaml` 配置文件

在 LibreChat 的配置目录中创建或编辑 `librechat.yaml` 文件：

**标准配置示例**：

```yaml
endpoints:
  custom:
    - name: "FinNet-RAG"
      apiKey: "rag123456"  # 你的 API Key
      baseURL: "http://host.docker.internal:8000/v1"  # 注意：包含 /v1 路径
      models:
        default:
          - "finnet-rag"
        fetch: false  # 手动指定模型列表
      modelDisplayLabel: "FinNet RAG"
```

**不同环境的 baseURL 配置**：

- **本地开发（LibreChat 和 FinNet API 都在本地）**:
  ```yaml
  baseURL: "http://localhost:8000/v1"
  ```

- **Docker 环境（LibreChat 在 Docker，FinNet API 在宿主机）**:
  ```yaml
  baseURL: "http://host.docker.internal:8000/v1"
  ```

- **Docker 网络（都在 Docker Compose 中）**:
  ```yaml
  baseURL: "http://finnet-api:8000/v1"  # 使用服务名
  ```

- **生产环境**:
  ```yaml
  baseURL: "https://your-domain.com/v1"
  ```

**重要配置说明**：

- `name`: 在 LibreChat 界面中显示的名称
- `apiKey`: 
  - 设置具体的 API Key 值（如 `"rag123456"`）
  - 或使用 `"user_provided"` 让用户在 UI 中输入 API Key
- `baseURL`: **必须包含 `/v1` 路径**，这是 OpenAI 兼容 API 的基础路径
- `models.default`: 模型名称列表（使用 YAML 列表格式 `- "finnet-rag"`）
- `fetch`: 
  - `false` - 手动指定模型列表（推荐，更快）
  - `true` - 自动从 `/v1/models` 端点获取模型列表

#### 2.2 Docker Compose 配置（如果使用 Docker）

如果 LibreChat 和 FinNet API 都在 Docker 中运行，需要在 `docker-compose.yml` 中：

1. 确保 `librechat.yaml` 文件被挂载到容器中
2. 确保网络配置允许容器间通信

示例 `docker-compose.override.yml`：

```yaml
version: '3.8'

services:
  librechat:
    volumes:
      - ./librechat.yaml:/app/librechat.yaml
    environment:
      - FINNET_API_URL=http://finnet-api:8000
```

### 3. 配置 API Key 验证（可选）

FinNet API 支持可选的 API Key 验证。有两种配置方式：

#### 方式1: 不启用验证（默认，允许所有请求）

如果不在 `.env` 文件中设置 `LIBRECHAT_API_KEY`，则所有请求都会被接受（不验证 API Key）。

在 `librechat.yaml` 中：
```yaml
apiKey: "user_provided"  # 或任意值，不会被验证
```

#### 方式2: 启用 API Key 验证

**步骤1**: 在 FinNet API 的 `.env` 文件中配置密钥：

```bash
# LibreChat 集成配置
LIBRECHAT_ENABLED=true
LIBRECHAT_MODEL_NAME=finnet-rag
LIBRECHAT_API_KEY=your-secret-api-key-here  # 设置你的密钥
```

**步骤2**: 在 `librechat.yaml` 中配置相同的密钥：

```yaml
endpoints:
  custom:
    - name: "FinNet-RAG"
      apiKey: "your-secret-api-key-here"  # 必须与 LIBRECHAT_API_KEY 一致
      baseURL: "http://localhost:8000/v1"  # 注意：包含 /v1 路径
      models:
        default:
          - "finnet-rag"
        fetch: false
```

**或者**使用环境变量（推荐）：

在 `librechat.yaml` 中：
```yaml
apiKey: "${FINNET_API_KEY}"  # 从环境变量读取
```

在 LibreChat 的 `.env` 文件中：
```bash
FINNET_API_KEY=your-secret-api-key-here
```

**注意**: 
- 如果启用了验证，请求头必须包含 `Authorization: Bearer <api_key>`
- API Key 不匹配会返回 401 错误
- 建议在生产环境中启用 API Key 验证以提高安全性

## 验证配置

### 1. 测试 FinNet API 端点

使用 curl 测试 API 是否正常工作：

```bash
# 测试非流式响应
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "finnet-rag",
    "messages": [
      {"role": "user", "content": "平安银行2023年第三季度的营业收入是多少？"}
    ],
    "temperature": 0.7,
    "max_tokens": 1000,
    "stream": false
  }'

# 测试流式响应
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "finnet-rag",
    "messages": [
      {"role": "user", "content": "平安银行2023年第三季度的营业收入是多少？"}
    ],
    "temperature": 0.7,
    "max_tokens": 1000,
    "stream": true
  }'
```

### 2. 在 LibreChat 中测试

1. 启动 LibreChat 服务
2. 在 LibreChat 界面左侧的端点选择栏中，应该能看到 "FinNet-RAG" 选项
3. 选择该端点，开始对话测试

## 功能特性

### 支持的 OpenAI API 参数

- `model`: 模型名称（必须为 `finnet-rag`）
- `messages`: 消息列表（支持 system, user, assistant）
- `temperature`: 温度参数（0.0-2.0，默认 0.7）
- `max_tokens`: 最大生成长度（默认 1000）
- `stream`: 是否流式返回（默认 false）

### RAG 功能

所有通过 LibreChat 发送的请求都会：
1. 提取最后一条用户消息作为查询问题
2. 通过 RAG Pipeline 检索相关文档
3. 基于检索到的上下文生成答案
4. 返回生成的答案（流式或非流式）

### 注意事项

1. **历史对话**: 当前实现是无状态的，每次查询都是独立的，不会考虑历史对话上下文
2. **系统消息**: 系统提示词已在 RAG Pipeline 中定义，LibreChat 发送的系统消息会被忽略
3. **过滤条件**: 当前不支持通过 LibreChat 传递过滤条件（如股票代码、年份等），所有查询都是全局检索

## 故障排查

### 问题1: LibreChat 无法连接到 FinNet API

**解决方案**:
- 检查 FinNet API 服务是否正在运行
- 检查 `baseURL` 配置是否正确
- 检查网络连接和防火墙设置
- 查看 FinNet API 日志确认请求是否到达

### 问题2: 模型列表为空或无法选择

**解决方案**:
- 确保 `baseURL` 包含 `/v1` 路径（如 `http://localhost:8000/v1`）
- 确保 `models.default` 使用正确的 YAML 列表格式：
  ```yaml
  models:
    default:
      - "finnet-rag"
  ```
- FinNet API 已实现 `/v1/models` 端点，可以设置 `fetch: true` 自动获取，或 `fetch: false` 手动指定
- 检查 `modelDisplayLabel` 是否正确

### 问题3: 流式响应不工作

**解决方案**:
- 确保 `stream: true` 在请求中
- 检查 FinNet API 日志确认流式响应是否正常生成
- 如果底层 LLM 不支持流式，系统会自动回退到模拟流式

### 问题4: API 密钥验证失败

**解决方案**:
- 如果启用了 `LIBRECHAT_API_KEY`，确保 LibreChat 配置中的 `apiKey` 与 FinNet API 配置一致
- 检查 Authorization 头格式：`Bearer <api-key>`
- 注意：`/v1/models` 端点不需要 API key，但 `/v1/chat/completions` 需要

### 问题5: baseURL 配置错误

**解决方案**:
- **重要**：`baseURL` 必须包含 `/v1` 路径
- 正确格式：`http://localhost:8000/v1` 或 `http://host.docker.internal:8000/v1`
- 错误格式：`http://localhost:8000`（缺少 `/v1`）
- LibreChat 会在 `baseURL` 后面直接拼接端点路径（如 `/chat/completions`），所以需要包含 `/v1`

## API 端点

### `/v1/models` - 模型列表

返回可用的模型列表（OpenAI 兼容格式）：

**请求示例**:
```bash
# 无需 API key（模型列表是公开信息）
curl http://localhost:8000/v1/models

# 或带 API key（也可以）
curl -H "Authorization: Bearer rag123456" http://localhost:8000/v1/models
```

**响应示例**:
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

### `/v1/chat/completions` - 聊天完成

执行 RAG 查询并返回答案。

## API 响应格式

### 非流式响应示例

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "finnet-rag",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "根据2023年第三季度报告，平安银行营业收入为XXX亿元..."
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 200,
    "total_tokens": 300
  }
}
```

### 流式响应示例（SSE 格式）

```
data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1234567890,"model":"finnet-rag","choices":[{"index":0,"delta":{"role":"assistant","content":"根据"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1234567890,"model":"finnet-rag","choices":[{"index":0,"delta":{"content":"2023年"},"finish_reason":null}]}

data: [DONE]
```

## 参考资源

- [LibreChat Custom Endpoints 文档](https://www.librechat.ai/docs/quick_start/custom_endpoints)
- [OpenAI API 文档](https://platform.openai.com/docs/api-reference/chat)
- [FinNet API 文档](../api/README.md)

## 更新日志

- 2025-01-XX: 初始版本，支持基本的 OpenAI 兼容接口和流式响应
