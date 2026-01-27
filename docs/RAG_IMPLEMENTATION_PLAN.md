# RAG 系统实施计划

**创建时间**: 2025-01-15  
**状态**: 📋 规划中

---

## 📋 目录

1. [系统架构设计](#系统架构设计)
2. [模块划分](#模块划分)
3. [技术选型](#技术选型)
4. [实施步骤](#实施步骤)
5. [接口设计](#接口设计)
6. [测试计划](#测试计划)

---

## 🏗️ 系统架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户请求层                                │
│                    (FastAPI REST API)                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      RAG Pipeline 层                           │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │  问题理解        │  │  检索增强        │  │  答案生成    │  │
│  │  (Query          │  │  (Retrieval)     │  │  (Generation)│  │
│  │   Understanding) │  │                  │  │              │  │
│  └──────────────────┘  └──────────────────┘  └──────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Retriever   │    │   Embedder   │    │  LLM Service │
│  (向量检索)   │    │  (查询向量化) │    │  (答案生成)   │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                    │
       ▼                   ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Milvus     │    │  Embedding   │    │  Qwen/API    │
│  (向量库)     │    │  Model/API   │    │  (LLM)       │
└──────────────┘    └──────────────┘    └──────────────┘
       │
       ▼
┌──────────────┐
│  PostgreSQL  │
│  (元数据)     │
└──────────────┘
```

### 数据流程

```
用户问题
   ↓
1. 查询向量化 (Embedder)
   ↓
2. 向量检索 (Milvus)
   ├─→ 获取 Top-K 相关分块
   └─→ 过滤条件（股票代码、年份、文档类型等）
   ↓
3. 获取分块文本 (PostgreSQL)
   ├─→ chunk_text
   ├─→ title, title_level
   └─→ document 元数据
   ↓
4. 构建上下文 (Context Builder)
   ├─→ 合并相关分块
   ├─→ 添加元数据信息
   └─→ 格式化 Prompt
   ↓
5. LLM 生成答案 (LLM Service)
   ├─→ 输入：问题 + 上下文
   └─→ 输出：答案 + 引用来源
   ↓
6. 返回结果 (API Response)
   ├─→ answer: 生成的答案
   ├─→ sources: 引用来源列表
   └─→ metadata: 元数据
```

---

## 📦 模块划分

### 1. RAG 检索器 (`application/rag/retriever.py`)

**职责**：基于 Milvus 进行向量检索

**核心功能**：
- `retrieve()` - 检索相关文档分块
- `retrieve_with_filters()` - 带过滤条件的检索
- `rerank()` - 结果重排序

**输入**：
- `query`: 用户问题（文本）
- `top_k`: 返回数量（默认 5）
- `filters`: 过滤条件（股票代码、年份、文档类型等）

**输出**：
- `List[RetrievalResult]` - 检索结果列表

**数据结构**：
```python
@dataclass
class RetrievalResult:
    chunk_id: str
    document_id: str
    chunk_text: str
    title: Optional[str]
    title_level: Optional[int]
    score: float  # 相似度分数
    metadata: Dict[str, Any]  # 文档元数据（股票代码、公司名称等）
```

### 2. 上下文构建器 (`application/rag/context_builder.py`)

**职责**：将检索结果构建为 LLM 可用的上下文

**核心功能**：
- `build_context()` - 构建上下文
- `format_chunks()` - 格式化分块文本
- `add_metadata()` - 添加元数据信息

**输入**：
- `retrieval_results: List[RetrievalResult]`
- `max_length: int` - 最大上下文长度（默认 4000 tokens）

**输出**：
- `str` - 格式化后的上下文文本

**格式示例**：
```
文档1: 平安银行 2023年第三季度报告
标题: 一、公司基本情况
内容: [分块文本内容]

文档2: 平安银行 2023年第三季度报告
标题: 二、主要财务数据
内容: [分块文本内容]

...
```

### 3. RAG Pipeline (`application/rag/rag_pipeline.py`)

**职责**：整合检索、上下文构建、LLM 生成

**核心功能**：
- `query()` - 执行 RAG 查询
- `query_with_streaming()` - 流式返回（可选）

**输入**：
- `question: str` - 用户问题
- `filters: Optional[Dict]` - 过滤条件
- `top_k: int` - 检索数量
- `temperature: float` - LLM 温度参数

**输出**：
- `RAGResponse` - RAG 响应

**数据结构**：
```python
@dataclass
class RAGResponse:
    answer: str  # 生成的答案
    sources: List[Source]  # 引用来源
    metadata: Dict[str, Any]  # 元数据（检索数量、生成时间等）

@dataclass
class Source:
    chunk_id: str
    document_id: str
    title: Optional[str]
    stock_code: str
    company_name: str
    doc_type: str
    year: int
    quarter: Optional[int]
    score: float
    snippet: str  # 相关文本片段
```

### 4. LLM 服务 (`processing/ai/llm/llm_service.py`)

**职责**：提供统一的 LLM 调用接口

**核心功能**：
- `generate()` - 生成文本
- `generate_stream()` - 流式生成（可选）
- `chat()` - 对话接口

**支持模式**：
- 本地 LLM（Qwen via Ollama/vLLM）
- 云端 API（OpenAI/DeepSeek/通义千问等）

**输入**：
- `prompt: str` - 提示词
- `system_prompt: Optional[str]` - 系统提示词
- `temperature: float` - 温度参数
- `max_tokens: int` - 最大生成长度

**输出**：
- `str` - 生成的文本

### 5. API 路由 (`api/routes/qa.py`)

**职责**：提供 REST API 接口

**核心接口**：
- `POST /api/v1/qa/query` - 问答接口
- `POST /api/v1/qa/query/stream` - 流式问答接口（可选）
- `GET /api/v1/qa/health` - 健康检查

**请求格式**：
```json
{
  "question": "平安银行2023年第三季度的营业收入是多少？",
  "filters": {
    "stock_code": "000001",
    "year": 2023,
    "quarter": 3
  },
  "top_k": 5,
  "temperature": 0.7
}
```

**响应格式**：
```json
{
  "answer": "根据2023年第三季度报告，平安银行营业收入为XXX亿元...",
  "sources": [
    {
      "chunk_id": "xxx",
      "title": "一、公司基本情况",
      "stock_code": "000001",
      "company_name": "平安银行",
      "doc_type": "quarterly_report",
      "year": 2023,
      "quarter": 3,
      "score": 0.95,
      "snippet": "营业收入为XXX亿元..."
    }
  ],
  "metadata": {
    "retrieval_count": 5,
    "generation_time": 1.2,
    "model": "qwen2.5:7b"
  }
}
```

### 6. API Schemas (`api/schemas/qa.py`)

**职责**：定义 API 请求/响应模型

**模型**：
- `QueryRequest` - 查询请求
- `QueryResponse` - 查询响应
- `Source` - 来源信息
- `FilterParams` - 过滤参数

---

## 🔧 技术选型

### 1. 向量检索

**已实现**：Milvus 客户端 (`src/storage/vector/milvus_client.py`)

**使用方式**：
- Collection: `financial_documents`（已在 vectorizer 中创建）
- 向量维度：1024（BGE-large-zh-v1.5）
- 距离度量：L2
- 索引类型：IVF_FLAT

### 2. 查询向量化

**已实现**：Embedder 工厂 (`src/processing/ai/embedding/embedder_factory.py`)

**使用方式**：
```python
from src.processing.ai.embedding.embedder_factory import get_embedder_by_mode

embedder = get_embedder_by_mode()  # 自动选择本地或API
query_vector = embedder.embed_text("用户问题")
```

### 3. LLM 服务

**方案选择**：

| 方案 | 优点 | 缺点 | 推荐度 |
|-----|------|------|--------|
| **云端 API**（OpenAI/DeepSeek） | 快速实现、效果好 | 成本、数据隐私 | ⭐⭐⭐⭐⭐ 优先 |
| **本地 Ollama** | 免费、数据不出网 | 需要GPU、效果一般 | ⭐⭐⭐⭐ |
| **本地 vLLM** | 效果好、数据不出网 | 需要GPU、部署复杂 | ⭐⭐⭐ |

**实施策略**：
1. **第一阶段**：使用云端 API（DeepSeek/OpenAI）快速验证
2. **第二阶段**：部署本地 LLM（Ollama/Qwen）作为备选

### 4. Prompt 工程

**系统提示词模板**：
```
你是一个专业的金融数据分析助手，擅长分析上市公司财报和公告。

请基于以下文档内容回答用户问题：
{context}

用户问题：{question}

要求：
1. 答案要准确、专业
2. 如果文档中没有相关信息，请明确说明
3. 引用具体的文档来源
4. 使用中文回答
```

---

## 📅 实施步骤

### 阶段1：基础检索器（1-2天）

**目标**：实现基础的向量检索功能

**任务**：
- [ ] 实现 `Retriever` 类
  - [ ] `retrieve()` 方法
  - [ ] `retrieve_with_filters()` 方法
  - [ ] 从 PostgreSQL 获取分块文本
- [ ] 编写单元测试
- [ ] 编写使用示例

**验收标准**：
- 能够根据问题检索到相关分块
- 支持过滤条件（股票代码、年份等）
- 返回结果包含完整的分块信息和元数据

### 阶段2：上下文构建器（0.5-1天）

**目标**：将检索结果构建为 LLM 可用的上下文

**任务**：
- [ ] 实现 `ContextBuilder` 类
  - [ ] `build_context()` 方法
  - [ ] `format_chunks()` 方法
  - [ ] Token 长度控制
- [ ] 编写单元测试

**验收标准**：
- 能够将多个分块合并为格式化的上下文
- 支持 Token 长度限制
- 包含文档元数据信息

### 阶段3：LLM 服务（1-2天）

**目标**：实现统一的 LLM 调用接口

**任务**：
- [ ] 实现 `LLMService` 类
  - [ ] 支持云端 API（OpenAI/DeepSeek）
  - [ ] 支持本地 LLM（Ollama）
  - [ ] 统一的 `generate()` 接口
- [ ] 配置管理（LLMConfig）
- [ ] 错误处理和重试
- [ ] 编写单元测试

**验收标准**：
- 能够调用云端 API 生成答案
- 能够调用本地 LLM（如果配置）
- 支持 Prompt 模板
- 错误处理完善

### 阶段4：RAG Pipeline（1-2天）

**目标**：整合检索、上下文构建、LLM 生成

**任务**：
- [ ] 实现 `RAGPipeline` 类
  - [ ] `query()` 方法
  - [ ] 整合 Retriever、ContextBuilder、LLMService
  - [ ] 结果格式化
- [ ] Prompt 工程优化
- [ ] 编写集成测试

**验收标准**：
- 能够端到端执行 RAG 查询
- 返回格式化的答案和来源
- 支持过滤条件
- 错误处理完善

### 阶段5：API 接口（1天）

**目标**：提供 REST API 接口

**任务**：
- [ ] 实现 API Schemas (`api/schemas/qa.py`)
- [ ] 实现 API 路由 (`api/routes/qa.py`)
- [ ] 集成到 FastAPI 应用
- [ ] API 文档（Swagger）

**验收标准**：
- 提供 `/api/v1/qa/query` 接口
- 请求/响应格式正确
- API 文档完整
- 错误处理完善

### 阶段6：测试和优化（1-2天）

**目标**：端到端测试和性能优化

**任务**：
- [ ] 端到端测试
- [ ] 性能测试（响应时间、并发）
- [ ] Prompt 优化
- [ ] 结果质量评估
- [ ] 文档完善

**验收标准**：
- 所有功能测试通过
- 响应时间 < 3秒（云端API）
- 答案质量满足要求
- 文档完整

---

## 🔌 接口设计

### Retriever 接口

```python
class Retriever:
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """
        检索相关文档分块
        
        Args:
            query: 用户问题
            top_k: 返回数量
            filters: 过滤条件
                - stock_code: 股票代码
                - year: 年份
                - quarter: 季度
                - doc_type: 文档类型
                - market: 市场
        
        Returns:
            检索结果列表
        """
        pass
```

### RAG Pipeline 接口

```python
class RAGPipeline:
    def query(
        self,
        question: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> RAGResponse:
        """
        执行 RAG 查询
        
        Args:
            question: 用户问题
            filters: 过滤条件
            top_k: 检索数量
            temperature: LLM 温度参数
            max_tokens: 最大生成长度
        
        Returns:
            RAG 响应
        """
        pass
```

### LLM Service 接口

```python
class LLMService:
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """
        生成文本
        
        Args:
            prompt: 提示词
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大生成长度
        
        Returns:
            生成的文本
        """
        pass
```

---

## 🧪 测试计划

### 单元测试

1. **Retriever 测试**
   - 测试向量检索功能
   - 测试过滤条件
   - 测试边界情况（空结果、无效查询等）

2. **ContextBuilder 测试**
   - 测试上下文构建
   - 测试 Token 长度限制
   - 测试格式化

3. **LLMService 测试**
   - 测试云端 API 调用
   - 测试本地 LLM 调用
   - 测试错误处理

4. **RAGPipeline 测试**
   - 测试端到端流程
   - 测试各种查询场景

### 集成测试

1. **端到端测试**
   - 真实问题测试
   - 不同过滤条件测试
   - 性能测试

2. **API 测试**
   - API 接口测试
   - 错误处理测试
   - 并发测试

### 测试用例示例

```python
def test_retriever_basic():
    """测试基础检索功能"""
    retriever = Retriever()
    results = retriever.retrieve("平安银行营业收入", top_k=5)
    assert len(results) > 0
    assert results[0].score > 0

def test_retriever_with_filters():
    """测试带过滤条件的检索"""
    retriever = Retriever()
    results = retriever.retrieve(
        "营业收入",
        top_k=5,
        filters={"stock_code": "000001", "year": 2023}
    )
    assert all(r.metadata["stock_code"] == "000001" for r in results)

def test_rag_pipeline():
    """测试 RAG Pipeline"""
    pipeline = RAGPipeline()
    response = pipeline.query("平安银行2023年第三季度的营业收入是多少？")
    assert response.answer is not None
    assert len(response.sources) > 0
```

---

## 📊 性能指标

### 目标指标

| 指标 | 目标值 | 说明 |
|-----|-------|------|
| 检索响应时间 | < 200ms | Milvus 检索 |
| LLM 生成时间 | < 3s | 云端 API |
| 端到端响应时间 | < 3.5s | 完整流程 |
| 并发支持 | > 10 QPS | 同时处理请求数 |
| 答案准确率 | > 80% | 人工评估 |

### 优化策略

1. **检索优化**
   - 使用 Milvus 索引优化
   - 批量查询
   - 结果缓存

2. **LLM 优化**
   - Prompt 长度优化
   - 流式生成（可选）
   - 结果缓存

3. **系统优化**
   - 连接池
   - 异步处理
   - 负载均衡

---

## 📝 配置说明

### 环境变量

```bash
# LLM 配置
LLM_MODE=api  # api 或 local
LLM_API_URL=https://api.deepseek.com/v1/chat/completions
LLM_API_KEY=your-api-key
LLM_MODEL=deepseek-chat

# 本地 LLM（可选）
LOCAL_LLM_ENABLED=false
LOCAL_LLM_API_BASE=http://localhost:11434  # Ollama
LOCAL_LLM_MODEL=qwen2.5:7b

# RAG 配置
RAG_TOP_K=5
RAG_MAX_CONTEXT_LENGTH=4000
RAG_TEMPERATURE=0.7
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install openai  # 如果使用 OpenAI API
# 或
pip install ollama  # 如果使用本地 Ollama
```

### 2. 配置环境变量

```bash
cp env.example .env
# 编辑 .env，配置 LLM API
```

### 3. 运行测试

```bash
# 运行单元测试
pytest tests/test_rag_retriever.py
pytest tests/test_rag_pipeline.py

# 运行集成测试
pytest tests/integration/test_rag_e2e.py
```

### 4. 启动 API 服务

```bash
# 启动 FastAPI 服务
uvicorn src.api.main:app --reload --port 8000
```

### 5. 测试 API

```bash
curl -X POST http://localhost:8000/api/v1/qa/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "平安银行2023年第三季度的营业收入是多少？",
    "filters": {
      "stock_code": "000001",
      "year": 2023,
      "quarter": 3
    }
  }'
```

---

## 📚 参考文档

- [Milvus 检索文档](https://milvus.io/docs/v2.3.x/search.md)
- [OpenAI API 文档](https://platform.openai.com/docs/api-reference)
- [DeepSeek API 文档](https://platform.deepseek.com/api-docs/)
- [Ollama 文档](https://github.com/ollama/ollama)

---

## ✅ 检查清单

### 开发前准备
- [ ] 确认 Milvus 服务运行正常
- [ ] 确认 PostgreSQL 数据库连接正常
- [ ] 确认已有向量化的文档分块数据
- [ ] 配置 LLM API Key（或本地 LLM）

### 开发进度
- [ ] 阶段1：基础检索器
- [ ] 阶段2：上下文构建器
- [ ] 阶段3：LLM 服务
- [ ] 阶段4：RAG Pipeline
- [ ] 阶段5：API 接口
- [ ] 阶段6：测试和优化

### 文档
- [ ] API 文档
- [ ] 使用示例
- [ ] 配置说明
- [ ] 故障排查指南

---

**预计总时间**：5-7 天  
**优先级**：⭐⭐⭐⭐⭐（核心功能）
