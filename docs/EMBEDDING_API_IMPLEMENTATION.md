# Embedding API 实现总结

## 实现概述

已实现基于 OpenAI 兼容 API 的 Embedding 服务，支持用户自定义 URL、API Key 和 Model。

## 实现的功能

### 1. API Embedder (`src/processing/ai/embedding/api_embedder.py`)

- ✅ 支持 OpenAI 兼容的 API 接口
- ✅ 支持自定义 URL、API Key 和 Model
- ✅ 支持单个文本和批量向量化
- ✅ 自动重试机制
- ✅ 错误处理和日志记录

### 2. Embedder 工厂 (`src/processing/ai/embedding/embedder_factory.py`)

- ✅ 统一接口，自动根据配置选择模式
- ✅ 支持本地模型和 API 两种模式
- ✅ 支持运行时切换模式

### 3. 配置支持 (`src/common/config.py`)

- ✅ 添加 API 模式配置项
- ✅ 支持环境变量配置
- ✅ 支持自定义 URL、API Key、Model

### 4. Vectorizer 集成 (`src/processing/ai/embedding/vectorizer.py`)

- ✅ 自动根据配置选择 Embedder
- ✅ 支持本地模型和 API 模式无缝切换

## 文件清单

### 新建文件

1. `src/processing/ai/embedding/api_embedder.py` - API Embedder 实现
2. `src/processing/ai/embedding/embedder_factory.py` - Embedder 工厂
3. `examples/test_api_embedder.py` - API Embedder 测试脚本
4. `docs/EMBEDDING_API_CONFIG.md` - API 配置指南
5. `docs/EMBEDDING_QUICKSTART.md` - 快速开始指南

### 修改文件

1. `src/common/config.py` - 添加 API 配置项
2. `src/processing/ai/embedding/__init__.py` - 导出 API Embedder
3. `src/processing/ai/embedding/vectorizer.py` - 支持 API 模式
4. `env.example` - 添加 Embedding 配置示例

## 配置项说明

### 模式选择

```bash
EMBEDDING_MODE=api  # 或 local
```

### API 配置

```bash
# 必需配置
EMBEDDING_API_URL=https://api.openai.com/v1/embeddings
EMBEDDING_API_KEY=sk-your-api-key
EMBEDDING_API_MODEL=text-embedding-ada-002

# 可选配置
EMBEDDING_API_TIMEOUT=30
EMBEDDING_API_MAX_RETRIES=3
EMBEDDING_DIM=1536  # 根据模型设置
EMBEDDING_BATCH_SIZE=32
```

## 使用方式

### 方式1：使用工厂模式（推荐）

```python
from src.processing.ai.embedding.embedder_factory import get_embedder_by_mode

# 自动根据配置选择
embedder = get_embedder_by_mode()

# 或强制使用 API
embedder = get_embedder_by_mode(mode="api")
```

### 方式2：直接使用 API Embedder

```python
from src.processing.ai.embedding.api_embedder import get_api_embedder

# 使用配置
embedder = get_api_embedder()

# 或自定义配置
embedder = get_api_embedder(
    api_url="https://api.example.com/v1/embeddings",
    api_key="your-key",
    model="text-embedding-ada-002"
)
```

### 方式3：在 Vectorizer 中使用

Vectorizer 会自动根据配置选择模式：

```python
from src.processing.ai.embedding.vectorizer import get_vectorizer

# 如果 EMBEDDING_MODE=api，会自动使用 API
vectorizer = get_vectorizer()
result = vectorizer.vectorize_chunks(chunk_ids)
```

## API 请求格式

使用 OpenAI 兼容格式：

**请求**：
```json
POST /v1/embeddings
{
  "input": ["文本1", "文本2"],
  "model": "text-embedding-ada-002"
}
```

**响应**：
```json
{
  "data": [
    {
      "embedding": [0.1, 0.2, ...],
      "index": 0
    }
  ],
  "model": "text-embedding-ada-002"
}
```

## 支持的 API 服务

- ✅ OpenAI
- ✅ Azure OpenAI
- ✅ 其他 OpenAI 兼容服务（如本地部署的 API）

## 特性

1. **自动重试**：网络错误时自动重试（最多3次）
2. **批量处理**：支持批量向量化，提高效率
3. **错误处理**：完善的错误处理和日志记录
4. **灵活配置**：支持环境变量和代码配置
5. **统一接口**：与本地模型使用相同的接口

## 测试

```bash
# 测试 API Embedder
python examples/test_api_embedder.py

# 测试完整向量化流程（使用 API）
EMBEDDING_MODE=api python examples/test_vectorize_simple.py
```

## 注意事项

1. **API 成本**：使用 API 会产生费用
2. **数据隐私**：数据会发送到外部服务
3. **网络依赖**：需要稳定的网络连接
4. **速率限制**：注意 API 的速率限制
5. **向量维度**：确保 `EMBEDDING_DIM` 与模型匹配

## 下一步

1. 配置 API 信息（URL、Key、Model）
2. 运行测试验证功能
3. 在 Dagster 作业中使用
4. 监控 API 调用和成本
