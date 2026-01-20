# Embedding 快速开始指南

## 两种模式

### 模式1：本地模型（默认）

使用本地模型，数据不出网，适合敏感数据。

**配置**：
```bash
EMBEDDING_MODE=local
EMBEDDING_MODEL=bge-large-zh-v1.5
EMBEDDING_DEVICE=cpu
```

**使用**：
```python
from src.processing.ai.embedding.bge_embedder import get_embedder

embedder = get_embedder()
vector = embedder.embed_text("测试文本")
```

### 模式2：API 模式（推荐用于快速验证）

使用 OpenAI 兼容的 API，快速、无需下载模型。

**配置**：
```bash
EMBEDDING_MODE=api
EMBEDDING_API_URL=https://api.openai.com/v1/embeddings
EMBEDDING_API_KEY=sk-your-api-key
EMBEDDING_API_MODEL=text-embedding-ada-002
EMBEDDING_DIM=1536
```

**使用**：
```python
from src.processing.ai.embedding.api_embedder import get_api_embedder

embedder = get_api_embedder()
vector = embedder.embed_text("测试文本")
```

## 统一接口（推荐）

使用工厂模式，自动根据配置选择：

```python
from src.processing.ai.embedding.embedder_factory import get_embedder_by_mode

# 自动根据配置选择模式
embedder = get_embedder_by_mode()

# 或强制指定模式
embedder = get_embedder_by_mode(mode="api")  # 或 mode="local"

# 使用
vector = embedder.embed_text("测试文本")
vectors = embedder.embed_batch(["文本1", "文本2"])
```

## 快速测试

### 测试本地模型

```bash
conda activate finnet
python examples/test_embedder_only.py
```

### 测试 API 模式

```bash
# 1. 配置 .env 文件
EMBEDDING_MODE=api
EMBEDDING_API_URL=https://api.openai.com/v1/embeddings
EMBEDDING_API_KEY=your-key
EMBEDDING_API_MODEL=text-embedding-ada-002

# 2. 运行测试
python examples/test_api_embedder.py
```

## 在向量化作业中使用

Vectorizer 会自动根据配置选择模式：

```python
from src.processing.ai.embedding.vectorizer import get_vectorizer

# 如果 EMBEDDING_MODE=api，会自动使用 API
vectorizer = get_vectorizer()
result = vectorizer.vectorize_chunks(chunk_ids)
```

## 配置示例

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

### 自定义 API 服务

```bash
EMBEDDING_MODE=api
EMBEDDING_API_URL=https://api.example.com/v1/embeddings
EMBEDDING_API_KEY=your-key
EMBEDDING_API_MODEL=your-model
EMBEDDING_DIM=1536  # 根据实际模型设置
```

## 参考文档

- [API 配置指南](EMBEDDING_API_CONFIG.md) - 详细的 API 配置说明
- [安装指南](INSTALL_EMBEDDING_MODEL.md) - 本地模型安装说明
