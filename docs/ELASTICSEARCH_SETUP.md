# Elasticsearch 设置指南

## 概述

Elasticsearch 用于全文检索和结构化查询，支持中文分词。本文档说明如何设置和配置 Elasticsearch。

## 快速开始

### 1. 启动 Elasticsearch 服务

```bash
# 启动 Elasticsearch 容器
docker-compose up -d elasticsearch

# 检查服务状态
docker-compose ps elasticsearch

# 查看日志
docker-compose logs -f elasticsearch
```

**注意**：如果在 Apple Silicon (M1/M2/M3) Mac 上运行，Docker Compose 配置中已设置 `platform: linux/amd64` 以通过 Rosetta 2 模拟运行。这可能会稍微影响性能，但可以确保兼容性。

### 2. 验证 Elasticsearch 运行

```bash
# 检查集群健康状态
curl http://localhost:9200/_cluster/health

# 应该返回类似以下内容：
# {"cluster_name":"docker-cluster","status":"green",...}
```

### 3. 安装 IK 中文分词器插件

Elasticsearch 默认不支持中文分词，需要安装 IK 分词器插件：

```bash
# 使用提供的脚本自动安装
./scripts/install_elasticsearch_ik.sh

# 或手动安装
docker exec -it finnet-elasticsearch \
    bin/elasticsearch-plugin install \
    https://github.com/medcl/elasticsearch-analysis-ik/releases/download/v8.11.0/elasticsearch-analysis-ik-8.11.0.zip

# 重启容器
docker restart finnet-elasticsearch
```

### 4. 验证 IK 分词器

```bash
# 查看已安装的插件
curl http://localhost:9200/_cat/plugins

# 测试中文分词
curl -X POST "http://localhost:9200/_analyze" -H 'Content-Type: application/json' -d'
{
  "analyzer": "ik_max_word",
  "text": "金融数据湖平台"
}'
```

## 配置说明

### 环境变量配置

在 `.env` 文件中配置以下变量：

```bash
# Elasticsearch 配置
ELASTICSEARCH_HOSTS=http://localhost:9200
ELASTICSEARCH_USER=elastic          # 如果启用了安全认证
ELASTICSEARCH_PASSWORD=elastic123456  # 如果启用了安全认证
ELASTICSEARCH_INDEX_PREFIX=finnet
ELASTICSEARCH_USE_SSL=false
ELASTICSEARCH_VERIFY_CERTS=true
```

### Docker Compose 配置

Elasticsearch 服务配置在 `docker-compose.yml` 中：

- **端口**：
  - `9200`: HTTP API 端口
  - `9300`: 节点间通信端口（单节点模式下不使用）

- **内存配置**：
  - 默认：512MB（`ES_JAVA_OPTS: -Xms512m -Xmx512m`）
  - 可根据需要调整

- **安全配置**：
  - 开发环境：禁用安全特性（`xpack.security.enabled: false`）
  - 生产环境：建议启用安全认证

## 索引结构

### 分块索引（chunks）

索引名称：`finnet_chunks`

字段映射：
- `id`: keyword（分块ID）
- `document_id`: keyword（文档ID）
- `chunk_index`: integer（分块索引）
- `chunk_text`: text（分块文本，使用 IK 分词器）
- `title`: text（标题，使用 IK 分词器）
- `title_level`: integer（标题层级）
- `chunk_size`: integer（分块大小）
- `is_table`: boolean（是否是表格）
- `stock_code`: keyword（股票代码）
- `company_name`: keyword（公司名称）
- `market`: keyword（市场：a_share/hk_stock/us_stock）
- `doc_type`: keyword（文档类型）
- `year`: integer（年份）
- `quarter`: integer（季度）
- `publish_date`: date（发布日期）
- `created_at`: date（创建时间）

## 使用方式

### 1. 通过 Dagster Job 自动索引

```bash
# 在 Dagster UI 中触发 elasticsearch_index_job
# 或使用命令行
dagster job execute -j elasticsearch_index_job
```

### 2. 手动索引文档

```python
from src.storage.elasticsearch import get_elasticsearch_client

client = get_elasticsearch_client()

# 索引单个文档
doc = {
    "id": "chunk-123",
    "document_id": "doc-456",
    "chunk_text": "这是分块文本内容",
    "stock_code": "000001",
    "market": "a_share"
}
client.index_document("chunks", doc, document_id="chunk-123")

# 批量索引
docs = [doc1, doc2, ...]
client.bulk_index_documents("chunks", docs)
```

### 3. 搜索文档

```python
from src.storage.elasticsearch import get_elasticsearch_client

client = get_elasticsearch_client()

# 全文搜索
query = {
    "bool": {
        "must": [
            {"match": {"chunk_text": "财务报告"}},
            {"term": {"stock_code": "000001"}}
        ]
    }
}
results = client.search("chunks", query, size=20)
```

## 常见问题

### 1. IK 分词器安装失败

**问题**：插件安装失败或版本不匹配

**解决**：
- 确保 Elasticsearch 版本与 IK 插件版本匹配
- 检查网络连接（需要从 GitHub 下载）
- 查看容器日志：`docker logs finnet-elasticsearch`

### 2. 内存不足

**问题**：Elasticsearch 启动失败，提示内存不足

**解决**：
- 调整 `docker-compose.yml` 中的 `ES_JAVA_OPTS`
- 确保系统有足够内存（建议至少 2GB）

### 3. 连接失败

**问题**：无法连接到 Elasticsearch

**解决**：
- 检查容器是否运行：`docker ps | grep elasticsearch`
- 检查端口是否被占用：`lsof -i :9200`
- 查看容器日志：`docker logs finnet-elasticsearch`

### 4. 中文分词不工作

**问题**：搜索中文内容时无法正确分词

**解决**：
- 确保已安装 IK 分词器插件
- 检查索引 mapping 中是否配置了 IK 分词器
- 重新创建索引（如果索引已存在，需要删除后重建）

## 生产环境建议

1. **启用安全认证**：
   ```yaml
   xpack.security.enabled: "true"
   ```

2. **调整内存配置**：
   ```yaml
   ES_JAVA_OPTS: -Xms2g -Xmx2g
   ```

3. **配置持久化存储**：
   - 确保 `elasticsearch_data` volume 有足够的空间
   - 定期备份数据

4. **监控和告警**：
   - 使用 Kibana 进行监控
   - 配置健康检查告警

5. **集群模式**（可选）：
   - 对于生产环境，建议使用多节点集群
   - 配置主节点和数据节点

## 相关文档

- [Elasticsearch 官方文档](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
- [IK 分词器 GitHub](https://github.com/medcl/elasticsearch-analysis-ik)
- [plan.md 中的 Elasticsearch 设计](../plan.md#415-全文搜索引擎elasticsearch)
