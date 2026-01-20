# Embedding API 配置指南

## 概述

现在支持两种 Embedding 模式：
1. **本地模型模式**（local）：使用 sentence-transformers 加载本地模型
2. **API 模式**（api）：使用 OpenAI 兼容的 API 接口

## 配置方式

### 方式1：环境变量配置（推荐）

在 `.env` 文件中配置：

```bash
# 选择模式：local 或 api
EMBEDDING_MODE=api

# API 配置
EMBEDDING_API_URL=https://api.openai.com/v1/embeddings
EMBEDDING_API_KEY=sk-your-api-key-here
EMBEDDING_API_MODEL=text-embedding-ada-002

# API 可选配置
EMBEDDING_API_TIMEOUT=30  # 超时时间（秒）
EMBEDDING_API_MAX_RETRIES=3  # 最大重试次数
EMBEDDING_BATCH_SIZE=32  # 批量大小
EMBEDDING_DIM=1536  # 向量维度（根据模型设置，如 ada-002 是 1536）
```

### 方式2：代码中配置

```python
from src.processing.ai.embedding.api_embedder import get_api_embedder

# 使用自定义配置
embedder = get_api_embedder(
    api_url="https://api.openai.com/v1/embeddings",
    api_key="sk-your-api-key",
    model="text-embedding-ada-002"
)

# 使用
vector = embedder.embed_text("测试文本")
```

### 方式3：使用工厂模式（自动切换）

```python
from src.processing.ai.embedding.embedder_factory import get_embedder_by_mode

# 根据配置自动选择模式
embedder = get_embedder_by_mode()

# 或强制使用 API 模式
embedder = get_embedder_by_mode(mode="api")

# 或使用自定义 API 配置
embedder = get_embedder_by_mode(
    mode="api",
    api_url="https://api.example.com/v1/embeddings",
    api_key="your-key",
    model="text-embedding-ada-002"
)
```

## 支持的 API 服务

### OpenAI

```bash
EMBEDDING_MODE=api
EMBEDDING_API_URL=https://api.openai.com/v1/embeddings
EMBEDDING_API_KEY=sk-...
EMBEDDING_API_MODEL=text-embedding-ada-002
EMBEDDING_DIM=1536
```

### Azure OpenAI

```bash
EMBEDDING_MODE=api
EMBEDDING_API_URL=https://your-resource.openai.azure.com/openai/deployments/your-deployment/embeddings?api-version=2023-05-15
EMBEDDING_API_KEY=your-azure-key
EMBEDDING_API_MODEL=text-embedding-ada-002
EMBEDDING_DIM=1536
```

### 其他 OpenAI 兼容服务

```bash
EMBEDDING_MODE=api
EMBEDDING_API_URL=https://api.example.com/v1/embeddings
EMBEDDING_API_KEY=your-key
EMBEDDING_API_MODEL=your-model-name
EMBEDDING_DIM=1536  # 根据实际模型设置
```

## API 请求格式

API Embedder 使用 OpenAI 兼容的请求格式：

```json
{
  "input": ["文本1", "文本2"],
  "model": "text-embedding-ada-002"
}
```

响应格式（OpenAI 标准）：

```json
{
  "data": [
    {
      "embedding": [0.1, 0.2, ...],
      "index": 0
    },
    {
      "embedding": [0.3, 0.4, ...],
      "index": 1
    }
  ],
  "model": "text-embedding-ada-002",
  "usage": {
    "prompt_tokens": 10,
    "total_tokens": 10
  }
}
```

## 使用示例

### 示例1：基本使用

```python
from src.processing.ai.embedding.api_embedder import get_api_embedder

# 初始化（使用配置）
embedder = get_api_embedder()

# 单个文本向量化
vector = embedder.embed_text("这是一个测试文本")
print(f"向量维度: {len(vector)}")

# 批量向量化
texts = ["文本1", "文本2", "文本3"]
vectors = embedder.embed_batch(texts)
print(f"批量向量化: {len(vectors)} 个向量")
```

### 示例2：在 Vectorizer 中使用

Vectorizer 会自动根据配置选择模式：

```python
from src.processing.ai.embedding.vectorizer import get_vectorizer

# 如果 EMBEDDING_MODE=api，会自动使用 API 模式
vectorizer = get_vectorizer()

# 向量化分块
result = vectorizer.vectorize_chunks(chunk_ids)
```

### 示例3：切换模式

```python
from src.processing.ai.embedding.embedder_factory import get_embedder_by_mode

# 使用本地模型
local_embedder = get_embedder_by_mode(mode="local")

# 使用 API
api_embedder = get_embedder_by_mode(mode="api")
```

## 配置检查清单

- [ ] `EMBEDDING_MODE` 设置为 `api`
- [ ] `EMBEDDING_API_URL` 已配置（完整的 API 地址）
- [ ] `EMBEDDING_API_KEY` 已配置（有效的 API Key）
- [ ] `EMBEDDING_API_MODEL` 已配置（模型名称）
- [ ] `EMBEDDING_DIM` 已配置（与模型维度匹配）

## 常见问题

### Q1: API 调用失败

**检查**：
1. API URL 是否正确
2. API Key 是否有效
3. 网络连接是否正常
4. API 服务是否可用

**调试**：
```python
from src.processing.ai.embedding.api_embedder import APIEmbedder

try:
    embedder = APIEmbedder()
    vector = embedder.embed_text("test")
except Exception as e:
    print(f"错误: {e}")
```

### Q2: 向量维度不匹配

**解决**：
- 确保 `EMBEDDING_DIM` 配置与模型实际维度匹配
- API Embedder 会在首次调用时自动检测维度

### Q3: 批量请求失败

**解决**：
- 减小 `EMBEDDING_BATCH_SIZE`
- 检查 API 的速率限制
- 增加 `EMBEDDING_API_TIMEOUT`

### Q4: 如何切换回本地模型？

**解决**：
```bash
# 在 .env 文件中
EMBEDDING_MODE=local
```

## 测试

运行 API Embedder 测试：

```bash
python examples/test_api_embedder.py
```

## 性能对比

| 模式 | 速度 | 成本 | 数据隐私 | 适用场景 |
|------|------|------|----------|----------|
| 本地模型 | 慢（CPU） | 无 | 高 | 敏感数据、离线环境 |
| API | 快 | 有 | 低 | 快速验证、生产环境 |

## 注意事项

1. **API 成本**：使用 API 会产生费用，注意控制调用量
2. **数据隐私**：API 模式下数据会发送到外部服务
3. **网络依赖**：需要稳定的网络连接
4. **速率限制**：注意 API 的速率限制，适当调整批量大小
