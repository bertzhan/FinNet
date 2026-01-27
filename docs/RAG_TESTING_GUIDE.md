# RAG 系统测试指南

## 快速开始

### 方式1: 运行集成测试脚本（推荐）

```bash
# 直接运行集成测试脚本
python test_rag_integration_simple.py
```

这个脚本会：
- ✅ 检查服务连接（PostgreSQL、Milvus、LLM）
- ✅ 测试 Retriever 初始化
- ✅ 测试基础检索功能
- ✅ 测试带过滤条件的检索
- ✅ 测试 ContextBuilder
- ✅ 测试 LLM Service
- ✅ 测试完整的 RAG Pipeline

### 方式2: 运行示例脚本

```bash
# 运行 RAG 查询示例
python examples/rag_query_demo.py
```

### 方式3: 使用 pytest（如果环境支持）

```bash
# 运行所有单元测试（跳过集成测试）
pytest tests/test_rag_retriever.py -v -m "not integration"
pytest tests/test_rag_context_builder.py -v
pytest tests/test_rag_pipeline.py -v -m "not integration"

# 运行集成测试（需要实际服务）
pytest tests/test_rag_retriever.py -v -m integration
pytest tests/integration/test_rag_e2e.py -v
```

### 方式4: 运行简单逻辑测试

```bash
# 运行不依赖外部服务的逻辑测试
python test_rag_simple.py
```

## 测试前准备

### 1. 检查服务状态

```bash
# 检查 PostgreSQL
psql -h localhost -U finnet -d finnet -c "SELECT COUNT(*) FROM document_chunks;"

# 检查 Milvus（需要安装 pymilvus）
python -c "from src.storage.vector.milvus_client import get_milvus_client; c = get_milvus_client(); print(c.list_collections())"
```

### 2. 配置环境变量

确保 `.env` 文件中配置了：

```bash
# LLM 配置（至少配置一种）
CLOUD_LLM_ENABLED=true
CLOUD_LLM_API_BASE=https://api.deepseek.com
CLOUD_LLM_API_KEY=your-api-key
CLOUD_LLM_MODEL=deepseek-chat

# 或使用本地 LLM
LOCAL_LLM_ENABLED=true
LOCAL_LLM_MODEL=qwen2.5:7b
LOCAL_LLM_API_BASE=http://localhost:11434
```

### 3. 确保有向量数据

```bash
# 检查 Milvus 中是否有向量数据
python -c "
from src.storage.vector.milvus_client import get_milvus_client
client = get_milvus_client()
stats = client.get_collection_stats('financial_documents')
print(f'向量数量: {stats.get(\"row_count\", 0)}')
"
```

## 常见问题

### 问题1: NumPy 版本兼容性错误

如果遇到 NumPy 版本兼容性问题：

```bash
# 降级 NumPy
pip install "numpy<2.0"
```

### 问题2: Milvus 连接失败

```bash
# 安装 pymilvus
pip install pymilvus

# 检查 Milvus 服务
docker ps | grep milvus
```

### 问题3: PostgreSQL 连接失败

```bash
# 检查 PostgreSQL 服务
docker ps | grep postgres

# 检查连接配置
python -c "from src.common.config import postgres_config; print(postgres_config.database_url)"
```

### 问题4: LLM API 调用失败

- 检查 API Key 是否正确
- 检查 API URL 是否正确
- 检查网络连接
- 查看日志获取详细错误信息

## 测试输出说明

### 成功示例

```
✅ PostgreSQL 连接成功，DocumentChunk 数量: 5509
✅ Milvus 连接成功，Collections: ['financial_documents']
✅ 云端 LLM 已启用: https://api.deepseek.com
✅ Retriever 初始化成功
✅ 检索成功，返回 3 个结果
✅ 上下文构建成功，长度: 1050 字符
✅ LLM 生成成功，回答长度: 150 字符
✅ RAG 查询成功
```

### 失败示例

```
❌ Milvus 连接失败: No module named 'pymilvus'
   提示: 请确保 Milvus 服务运行并安装 pymilvus: pip install pymilvus
```

## 性能测试

```bash
# 运行性能测试（需要实现）
python -c "
import time
from src.application.rag.rag_pipeline import RAGPipeline

pipeline = RAGPipeline()
start = time.time()
response = pipeline.query('什么是营业收入？', top_k=5)
elapsed = time.time() - start

print(f'查询时间: {elapsed:.2f}s')
print(f'检索数量: {len(response.sources)}')
print(f'生成时间: {response.metadata.get(\"generation_time\", 0):.2f}s')
"
```

## 调试技巧

### 1. 启用详细日志

```bash
# 设置日志级别
export LOG_LEVEL=DEBUG
python test_rag_integration_simple.py
```

### 2. 单独测试组件

```bash
# 只测试 Retriever
python -c "
from src.application.rag.retriever import Retriever
r = Retriever()
results = r.retrieve('营业收入', top_k=3)
print(f'找到 {len(results)} 个结果')
"

# 只测试 LLM Service
python -c "
from src.processing.ai.llm.llm_service import get_llm_service
s = get_llm_service()
answer = s.generate('你好', max_tokens=10)
print(answer)
"
```

### 3. 检查配置

```bash
# 查看当前配置
python -c "
from src.common.config import llm_config, milvus_config, postgres_config
print('LLM:', llm_config.CLOUD_LLM_ENABLED, llm_config.CLOUD_LLM_API_BASE)
print('Milvus:', milvus_config.MILVUS_HOST, milvus_config.MILVUS_PORT)
print('PostgreSQL:', postgres_config.POSTGRES_HOST, postgres_config.POSTGRES_PORT)
"
```
