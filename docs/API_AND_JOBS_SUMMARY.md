# FinNet API 接口和 Jobs 总结

**更新时间**: 2025-01-28

---

## 📋 API 接口总览

### 基础接口

| 接口路径 | 方法 | 说明 |
|---------|------|------|
| `/` | GET | 获取 API 基本信息 |
| `/health` | GET | 全局健康检查 |

---

## 🔍 检索接口 (Retrieval API)

**基础路径**: `/api/v1/retrieval`

| 接口路径 | 方法 | 说明 | 功能 |
|---------|------|------|------|
| `/api/v1/retrieval/vector` | POST | 向量检索 | 基于 Milvus 的语义相似度检索 |
| `/api/v1/retrieval/fulltext` | POST | 全文检索 | 基于 Elasticsearch 的关键词检索 |
| `/api/v1/retrieval/graph/children` | POST | 图检索-子节点查询 | 查询文档分块的子节点 |
| `/api/v1/retrieval/hybrid` | POST | 混合检索 | 结合向量检索和全文检索 |
| `/api/v1/retrieval/company-code-search` | POST | 公司代码搜索 | 根据公司名称搜索股票代码 |
| `/api/v1/retrieval/health` | GET | 检索服务健康检查 | 检查检索服务状态 |

### 检索接口详情

#### 1. 向量检索 (`/api/v1/retrieval/vector`)
- **功能**: 基于向量相似度的语义检索
- **输入**: 查询文本、过滤条件（股票代码、年份、季度等）、top_k
- **输出**: 检索结果列表，包含相似度分数
- **应用场景**: 理解用户意图，找到语义相关的文档

#### 2. 全文检索 (`/api/v1/retrieval/fulltext`)
- **功能**: 基于关键词的全文检索
- **输入**: 查询文本、过滤条件、top_k
- **输出**: 检索结果列表，包含 BM25 评分
- **应用场景**: 精确匹配关键词，查找特定内容

#### 3. 图检索-子节点查询 (`/api/v1/retrieval/graph/children`)
- **功能**: 查询文档分块的直接子节点
- **输入**: chunk_id
- **输出**: 子节点列表（chunk_id, title）
- **应用场景**: 浏览文档结构，查看章节关系

#### 4. 混合检索 (`/api/v1/retrieval/hybrid`)
- **功能**: 结合向量检索和全文检索
- **输入**: 查询文本、过滤条件、top_k、权重配置
- **输出**: 融合后的检索结果列表
- **应用场景**: 综合语义和关键词，获得最佳检索效果

#### 5. 公司代码搜索 (`/api/v1/retrieval/company-code-search`)
- **功能**: 根据公司名称搜索股票代码
- **输入**: 公司名称（支持模糊匹配）
- **输出**: 匹配的公司列表（包含股票代码、公司名称等）
- **应用场景**: 用户输入公司名称，系统返回匹配的股票代码

---

## 💬 问答接口 (QA API)

**基础路径**: `/api/v1/qa`

| 接口路径 | 方法 | 说明 | 功能 |
|---------|------|------|------|
| `/api/v1/qa/query` | POST | RAG 问答 | 基于检索增强生成的智能问答 |
| `/api/v1/qa/health` | GET | 问答服务健康检查 | 检查问答服务状态 |

### 问答接口详情

#### RAG 问答 (`/api/v1/qa/query`)
- **功能**: 基于 RAG 的智能问答
- **输入**: 问题、过滤条件（股票代码、年份、季度等）、top_k、温度参数
- **输出**: 答案、来源列表、元数据
- **应用场景**: 用户用自然语言提问，系统自动检索文档并生成答案

---

## 📄 文档接口 (Document API)

**基础路径**: `/api/v1/document`

| 接口路径 | 方法 | 说明 | 功能 |
|---------|------|------|------|
| `/api/v1/document/query` | POST | 查询文档ID | 根据股票代码、年份、季度、文档类型查询文档ID |
| `/api/v1/document/{document_id}/chunks` | GET | 获取文档分块列表 | 根据文档ID获取所有分块信息 |

### 文档接口详情

#### 查询文档ID (`/api/v1/document/query`)
- **功能**: 根据条件查询文档ID
- **输入**: stock_code, year, quarter, doc_type
- **输出**: document_id, found, message
- **应用场景**: 在检索前先确认文档是否存在

#### 获取文档分块列表 (`/api/v1/document/{document_id}/chunks`)
- **功能**: 获取文档的所有分块信息
- **输入**: document_id (路径参数)
- **输出**: 分块列表（chunk_id, title, title_level, parent_chunk_id）
- **应用场景**: 浏览文档结构，了解文档组织方式

---

## 🤖 OpenAI 兼容接口

**基础路径**: `/v1`

| 接口路径 | 方法 | 说明 | 功能 |
|---------|------|------|------|
| `/v1/chat/completions` | POST | 聊天完成 | OpenAI 兼容的聊天接口（支持流式） |
| `/v1/models` | GET | 模型列表 | 返回可用的模型列表 |

### OpenAI 兼容接口详情

#### 聊天完成 (`/v1/chat/completions`)
- **功能**: OpenAI 兼容的聊天接口
- **输入**: messages, model, stream 等 OpenAI 标准参数
- **输出**: 聊天回复（支持流式和非流式）
- **应用场景**: 集成 LibreChat 等第三方聊天工具

#### 模型列表 (`/v1/models`)
- **功能**: 返回可用的模型列表
- **输入**: 无
- **输出**: 模型列表
- **应用场景**: 客户端查询可用模型

---

## ⚙️ Dagster Jobs 总览

### 数据采集 Jobs

| Job 名称 | 说明 | 调度 | 传感器 |
|---------|------|------|--------|
| `crawl_a_share_reports_job` | A股定期报告爬取 | 每天执行 | `manual_trigger_reports_sensor` |
| `crawl_a_share_ipo_job` | A股IPO招股书爬取 | 每天执行 | `manual_trigger_ipo_sensor` |

### 数据处理 Jobs

| Job 名称 | 说明 | 调度 | 传感器 |
|---------|------|------|--------|
| `parse_pdf_job` | PDF 解析作业 | 每小时/每天 | `manual_trigger_parse_sensor` |
| `chunk_documents_job` | 文本分块作业 | 每小时/每天 | `manual_trigger_chunk_sensor` |
| `vectorize_documents_job` | 向量化作业 | 每2小时/每天 | `manual_trigger_vectorize_sensor` |

### 索引和构建 Jobs

| Job 名称 | 说明 | 调度 | 传感器 |
|---------|------|------|--------|
| `elasticsearch_index_job` | Elasticsearch 索引作业 | 每小时/每天 | `manual_trigger_elasticsearch_sensor` |
| `build_graph_job` | 图构建作业 | 每小时/每天 | `manual_trigger_graph_sensor` |

### 数据更新 Jobs

| Job 名称 | 说明 | 调度 | 传感器 |
|---------|------|------|--------|
| `update_listed_companies_job` | 上市公司列表更新作业 | 每天执行 | `manual_trigger_companies_sensor` |

---

## 📊 Jobs 详细说明

### 1. 数据采集 Jobs

#### `crawl_a_share_reports_job`
- **功能**: 爬取 A股定期报告（季报、年报）
- **数据源**: 巨潮资讯网（CNInfo）
- **输出**: PDF 文件存储到 MinIO
- **调度**: 每天执行一次
- **手动触发**: 通过 `manual_trigger_reports_sensor` 传感器

#### `crawl_a_share_ipo_job`
- **功能**: 爬取 A股 IPO 招股书
- **数据源**: 巨潮资讯网（CNInfo）
- **输出**: PDF 文件存储到 MinIO
- **调度**: 每天执行一次
- **手动触发**: 通过 `manual_trigger_ipo_sensor` 传感器

### 2. 数据处理 Jobs

#### `parse_pdf_job`
- **功能**: 解析 PDF 文档，提取文本和结构
- **输入**: 待解析的 PDF 文档
- **输出**: 解析后的文档存储到 PostgreSQL
- **调度**: 每小时或每天执行
- **手动触发**: 通过 `manual_trigger_parse_sensor` 传感器

#### `chunk_documents_job`
- **功能**: 将解析后的文档进行智能分块
- **输入**: 已解析的文档
- **输出**: 文档分块存储到 PostgreSQL
- **调度**: 每小时或每天执行
- **手动触发**: 通过 `manual_trigger_chunk_sensor` 传感器

#### `vectorize_documents_job`
- **功能**: 生成文档分块的向量嵌入
- **输入**: 未向量化的文档分块
- **输出**: 向量存储到 Milvus
- **调度**: 每2小时或每天执行
- **手动触发**: 通过 `manual_trigger_vectorize_sensor` 传感器

### 3. 索引和构建 Jobs

#### `elasticsearch_index_job`
- **功能**: 将文档分块索引到 Elasticsearch
- **输入**: 已分块的文档
- **输出**: Elasticsearch 索引
- **调度**: 每小时或每天执行
- **手动触发**: 通过 `manual_trigger_elasticsearch_sensor` 传感器

#### `build_graph_job`
- **功能**: 构建文档知识图谱
- **输入**: 已分块的文档
- **输出**: Neo4j 图数据库节点和关系
- **调度**: 每小时或每天执行
- **手动触发**: 通过 `manual_trigger_graph_sensor` 传感器

### 4. 数据更新 Jobs

#### `update_listed_companies_job`
- **功能**: 更新上市公司列表
- **数据源**: akshare
- **输出**: 更新 PostgreSQL 中的上市公司信息
- **调度**: 每天执行一次
- **手动触发**: 通过 `manual_trigger_companies_sensor` 传感器

---

## 🔄 数据处理 Pipeline

```
1. 数据采集 (Crawl Jobs)
   ├─ crawl_a_share_reports_job → PDF 文件
   └─ crawl_a_share_ipo_job → PDF 文件
   
2. 文档解析 (Parse Job)
   └─ parse_pdf_job → 结构化文本
   
3. 文档分块 (Chunk Job)
   └─ chunk_documents_job → 文档分块
   
4. 向量化 (Vectorize Job) [并行]
   └─ vectorize_documents_job → 向量嵌入
   
5. 全文索引 (Elasticsearch Job) [并行]
   └─ elasticsearch_index_job → Elasticsearch 索引
   
6. 图构建 (Graph Job) [并行]
   └─ build_graph_job → Neo4j 图数据库
   
7. 数据更新 (Company List Job) [独立]
   └─ update_listed_companies_job → 上市公司列表
```

---

## 📈 统计信息

### API 接口统计
- **总接口数**: 13 个
- **检索接口**: 6 个
- **问答接口**: 2 个
- **文档接口**: 2 个
- **OpenAI 兼容接口**: 2 个
- **基础接口**: 2 个

### Jobs 统计
- **总 Jobs 数**: 8 个
- **数据采集 Jobs**: 2 个
- **数据处理 Jobs**: 3 个
- **索引和构建 Jobs**: 2 个
- **数据更新 Jobs**: 1 个

### 调度统计
- **定时调度**: 13 个
- **手动传感器**: 8 个

---

## 🎯 使用场景

### API 接口使用场景

1. **智能问答**: 通过 `/api/v1/qa/query` 实现自然语言问答
2. **文档检索**: 通过检索接口查找相关文档
3. **文档浏览**: 通过文档接口查看文档结构
4. **第三方集成**: 通过 OpenAI 兼容接口集成聊天工具

### Jobs 使用场景

1. **数据采集**: 自动爬取最新的金融文档
2. **数据处理**: 自动解析、分块、向量化文档
3. **索引更新**: 自动更新全文索引和图数据库
4. **数据维护**: 自动更新上市公司列表

---

## 📝 相关文档

- [API 文档](api/API_DOCUMENTATION.md) - 完整的 API 文档
- [Dagster 集成文档](DAGSTER_INTEGRATION.md) - Dagster 集成说明
- [RAG 测试指南](RAG_TESTING_GUIDE.md) - RAG 功能测试指南
- [Elasticsearch 集成总结](ELASTICSEARCH_INTEGRATION_SUMMARY.md) - Elasticsearch 集成说明

---

**最后更新**: 2025-01-28
