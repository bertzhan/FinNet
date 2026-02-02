# 测试公司名称搜索接口

## 启动 API 服务

### 方式1: 使用启动脚本（推荐）

```bash
bash scripts/start_api.sh
```

### 方式2: 使用 uvicorn 直接启动

```bash
cd /Users/han/PycharmProjects/FinNet
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 方式3: 使用 Python 模块启动

```bash
cd /Users/han/PycharmProjects/FinNet
python -m src.api.main
```

## 验证服务启动

服务启动后，访问以下地址验证：

- 健康检查: http://localhost:8000/health
- API 文档: http://localhost:8000/docs
- 根路径: http://localhost:8000/

## 测试接口

### 方式1: 使用 Python 测试脚本

```bash
# 测试单个公司名称
python examples/test_company_name_search.py --company-name "平安银行"

# 测试多个公司名称（批量测试）
python examples/test_company_name_search.py --batch

# 自定义参数
python examples/test_company_name_search.py --company-name "平安银行"
```

### 方式2: 使用 cURL

```bash
curl -X POST "http://localhost:8000/api/v1/retrieval/company-code-search" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "平安银行"
  }' | python -m json.tool
```

### 方式3: 使用 Python requests

```python
import requests
import json

url = "http://localhost:8000/api/v1/retrieval/company-code-search"
payload = {
    "company_name": "平安银行"
}

response = requests.post(url, json=payload)
result = response.json()

print(f"公司名称: {result['company_name']}")
print(f"最可能的股票代码: {result['stock_code']}")
print(f"\n所有候选:")
for candidate in result['all_candidates']:
    print(f"  {candidate['stock_code']}: {candidate['votes']} 票 "
          f"(置信度: {candidate['confidence']:.1%})")
```

### 方式4: 在浏览器中测试

1. 访问 http://localhost:8000/docs
2. 找到 `/api/v1/retrieval/company-code-search` 接口
3. 点击 "Try it out"
4. 输入请求参数：
   ```json
   {
     "company_name": "平安银行"
   }
   ```
5. 点击 "Execute" 执行请求

## 测试用例

### 测试用例1: 完整公司名称

```bash
curl -X POST "http://localhost:8000/api/v1/retrieval/company-code-search" \
  -H "Content-Type: application/json" \
  -H "Content-Type: application/json" \
  -d '{"company_name": "平安银行"}'
```

### 测试用例2: 部分公司名称（模糊匹配）

```bash
curl -X POST "http://localhost:8000/api/v1/retrieval/company-code-search" \
  -H "Content-Type: application/json" \
  -H "Content-Type: application/json" \
  -d '{"company_name": "平安"}'
```

### 测试用例3: 其他公司

```bash
# 招商银行
curl -X POST "http://localhost:8000/api/v1/retrieval/company-code-search" \
  -H "Content-Type: application/json" \
  -H "Content-Type: application/json" \
  -d '{"company_name": "招商银行"}'

# 工商银行
curl -X POST "http://localhost:8000/api/v1/retrieval/company-code-search" \
  -H "Content-Type: application/json" \
  -H "Content-Type: application/json" \
  -d '{"company_name": "工商银行"}'
```

## 预期响应格式

**唯一匹配时：**
```json
{
  "stock_code": "000001",
  "message": null
}
```

**多个候选时（2-5个）：**
```json
{
  "stock_code": null,
  "message": "找到 3 个可能的公司，请选择：\n1. 平安银行 (000001) - 平安银行股份有限公司\n2. 平安证券 (002736) - 平安证券股份有限公司\n3. ..."
}
```

**候选过多时（>5个）：**
```json
{
  "stock_code": null,
  "message": "找到 15 个可能的公司，匹配结果过多，请进一步明确公司名称。"
}
```

**未找到时：**
```json
{
  "stock_code": null,
  "message": null
}
```

## 前置条件

### 1. Elasticsearch 服务运行

确保 Elasticsearch 服务正在运行：

```bash
# 检查 Elasticsearch 健康状态
curl http://localhost:9200/_cluster/health

# 应该返回类似：
# {"cluster_name":"docker-cluster","status":"green",...}
```

### 2. 创建 Elasticsearch 索引

索引会在首次调用接口时自动创建，但也可以手动创建：

```bash
# 方式1: 使用脚本创建索引
PYTHONPATH=/Users/han/PycharmProjects/FinNet python examples/create_elasticsearch_index.py

# 方式2: 检查索引状态
PYTHONPATH=/Users/han/PycharmProjects/FinNet python examples/create_elasticsearch_index.py --check
```

### 3. 索引数据到 Elasticsearch

**重要**: 创建索引后，需要将文档数据索引到 Elasticsearch 才能搜索。

```bash
# 方式1: 使用 Dagster Job（推荐）
dagster job execute -j elasticsearch_index_job

# 方式2: 使用测试脚本
PYTHONPATH=/Users/han/PycharmProjects/FinNet python examples/test_elasticsearch_job_simple.py
```

**注意**: 如果没有数据，接口会返回空结果，但不会报错。

## 故障排查

### 问题1: 索引不存在错误

**错误**: `index_not_found_exception: no such index [finnet_chunks]`

**解决方案**:
1. 索引会在首次调用时自动创建
2. 或手动创建索引：
   ```bash
   PYTHONPATH=/Users/han/PycharmProjects/FinNet python examples/create_elasticsearch_index.py
   ```

### 问题2: 连接被拒绝

**错误**: `Connection refused` 或 `Failed to connect`

**解决方案**:
1. 确认 API 服务正在运行
2. 检查端口 8000 是否被占用: `lsof -i :8000`
3. 检查防火墙设置

### 问题2: 未找到相关文档

**响应**: `stock_code` 为 `null`，`total_documents` 为 0

**可能原因**:
1. Elasticsearch 中没有索引数据
2. 公司名称不匹配（尝试使用部分名称）
3. Elasticsearch 服务未运行

**解决方案**:
1. 检查 Elasticsearch 服务: `curl http://localhost:9200/_cluster/health`
2. 检查索引是否存在: `curl http://localhost:9200/_cat/indices`
3. 运行索引作业以创建数据

### 问题3: 导入错误

**错误**: `ModuleNotFoundError` 或 `ImportError`

**解决方案**:
1. 确认已安装所有依赖: `pip install -r requirements.txt`
2. 检查 Python 环境是否正确
3. 确认项目根目录在 Python 路径中

## 相关文档

- [API 文档](./API_DOCUMENTATION.md)
- [Elasticsearch 设置指南](../ELASTICSEARCH_SETUP.md)
