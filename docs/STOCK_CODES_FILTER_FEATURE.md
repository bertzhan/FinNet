# Stock Codes 过滤参数功能

## 概述
为所有 Dagster 作业（除 `update_listed_companies_job` 外）添加了 `stock_codes` 参数，允许用户按股票代码列表过滤要处理的文档。

## 修改的文件

### 1. parse_jobs.py
- **配置参数位置**: `PARSE_CONFIG_SCHEMA` (第71-75行)
- **参数说明**: 按股票代码列表过滤待解析的文档
- **过滤逻辑**: 在扫描待解析文档时，根据 `stock_codes` 过滤 `Document` 表（第201-205行）
- **示例**: `stock_codes: ['000001', '000002']` - 只解析平安银行和万科A的文档

### 2. chunk_jobs.py
- **配置参数位置**: `CHUNK_CONFIG_SCHEMA` (第58-62行)
- **参数说明**: 按股票代码列表过滤待分块的文档
- **过滤逻辑**: 在扫描已解析文档时，通过 JOIN Document 表进行过滤（第121-124行）
- **示例**: `stock_codes: ['000001']` - 只对平安银行的已解析文档进行分块

### 3. vectorize_jobs.py
- **配置参数位置**: `VECTORIZE_CONFIG_SCHEMA` (第55-59行)
- **参数说明**: 按股票代码列表过滤待向量化的文档分块
- **过滤逻辑**: 在扫描待向量化分块时，通过 JOIN Document 表进行过滤（第137-140行）
- **示例**: `stock_codes: ['000001', '000002']` - 只向量化这两家公司的分块

### 4. graph_jobs.py
- **配置参数位置**: `GRAPH_CONFIG_SCHEMA` (第54-58行)
- **参数说明**: 按股票代码列表过滤待建图的文档
- **过滤逻辑**: 在多个查询中应用过滤（第117-132行、144-145行）
- **示例**: `stock_codes: ['000001']` - 只为平安银行构建知识图谱

### 5. elasticsearch_jobs.py
- **配置参数位置**: `ELASTICSEARCH_CONFIG_SCHEMA` (第53-57行)
- **参数说明**: 按股票代码列表过滤待索引到 Elasticsearch 的分块
- **过滤逻辑**: 在扫描待索引分块时，通过 JOIN Document 表进行过滤（第124-127行）
- **示例**: `stock_codes: ['000001', '000002']` - 只索引这两家公司的分块

## 参数说明

### 字段定义
```python
"stock_codes": Field(
    list,
    is_required=False,
    description="按股票代码列表过滤（None = 不过滤，指定后将只处理这些股票代码的文档）。例如: ['000001', '000002']"
)
```

### 参数特性
- **类型**: `list` (字符串列表)
- **必填**: 否 (is_required=False)
- **默认值**: `None` (不过滤)
- **过滤优先级**: 在 `market`、`doc_type`、`industry` 之后，`limit` 之前应用

## 使用场景

### 1. 测试特定公司
```yaml
ops:
  scan_pending_documents_op:
    config:
      stock_codes: ['000001']  # 只处理平安银行
      limit: 10
```

### 2. 批量处理多家公司
```yaml
ops:
  scan_unvectorized_chunks_op:
    config:
      stock_codes: ['000001', '000002', '000333']  # 平安银行、万科A、美的集团
      batch_size: 32
```

### 3. 组合过滤
```yaml
ops:
  scan_chunked_documents_for_graph_op:
    config:
      market: "a_share"
      doc_type: "annual_report"
      stock_codes: ['000001', '000002']  # 只处理A股年报中的这两家公司
      limit: 100
```

## 过滤逻辑

### SQL 查询示例
```python
# parse_jobs.py 中的过滤（Python 列表过滤）
if stock_codes_filter:
    documents = [d for d in documents if d.stock_code in stock_codes_filter]

# chunk_jobs.py 中的过滤（SQLAlchemy 查询）
if stock_codes_filter:
    query = query.filter(Document.stock_code.in_(stock_codes_filter))

# vectorize_jobs.py 中的过滤（SQLAlchemy 查询）
if stock_codes_filter:
    query = query.filter(Document.stock_code.in_(stock_codes_filter))

# graph_jobs.py 中的过滤（SQLAlchemy 查询）
if stock_codes_filter:
    query = query.filter(Document.stock_code.in_(stock_codes_filter))

# elasticsearch_jobs.py 中的过滤（SQLAlchemy 查询）
if stock_codes_filter:
    query = query.filter(Document.stock_code.in_(stock_codes_filter))
```

## 与其他过滤参数的关系

### 过滤顺序（从宽到窄）
1. `market` - 市场过滤（a_share/hk_stock/us_stock）
2. `doc_type` - 文档类型过滤（quarterly_report/annual_report/ipo_prospectus）
3. `industry` - 行业过滤（仅 parse_jobs.py）
4. **`stock_codes`** - 股票代码过滤（新增）
5. `limit` - 数量限制

### 参数组合示例
```yaml
# 示例1: 只使用 stock_codes
stock_codes: ['000001', '000002']

# 示例2: stock_codes + market
market: "a_share"
stock_codes: ['000001', '000002']

# 示例3: stock_codes + doc_type
doc_type: "annual_report"
stock_codes: ['000001']

# 示例4: 全部组合
market: "a_share"
doc_type: "annual_report"
stock_codes: ['000001', '000002']
limit: 100
```

## 日志输出

### 配置日志
```
配置: batch_size=32, limit=100, market=a_share, doc_type=annual_report, stock_codes=['000001', '000002'], force_reparse=False
```

### 过滤日志
```
按股票代码过滤: ['000001', '000002']
股票代码过滤后: 15 个文档
```

## 注意事项

1. **参数验证**: 确保 `stock_codes` 中的代码在 `listed_companies` 表中存在
2. **性能考虑**:
   - 少量股票代码（< 10）: 使用 `IN` 查询性能良好
   - 大量股票代码（> 100）: 可能需要优化查询或分批处理
3. **与 limit 的关系**:
   - `stock_codes` 过滤后再应用 `limit`
   - 如果指定了 `stock_codes`，建议不设置 `limit` 或设置较大的值
4. **错误处理**: 如果指定的股票代码都不存在，作业会处理 0 个文档（不会报错）

## 测试建议

### 1. 单元测试
```bash
# 测试单个股票代码
pytest tests/test_parse_jobs_stock_codes.py -k test_single_stock_code

# 测试多个股票代码
pytest tests/test_parse_jobs_stock_codes.py -k test_multiple_stock_codes
```

### 2. 集成测试
```bash
# 在 Dagster UI 中手动触发作业
# 配置 stock_codes: ['000001']
# 验证只处理了指定公司的文档
```

## 兼容性

- **向后兼容**: 是（参数为可选，默认值为 None）
- **Dagster 版本**: 适用于所有支持 Field 的 Dagster 版本
- **数据库**: 使用标准 SQLAlchemy `IN` 查询，兼容 PostgreSQL

## 相关文档
- [CRAWL_STOCK_CODES_FEATURE.md](./CRAWL_STOCK_CODES_FEATURE.md) - crawl_jobs.py 的 stock_codes 参数（参考实现）
- [DAGSTER_UI_TROUBLESHOOTING.md](./DAGSTER_UI_TROUBLESHOOTING.md) - Dagster UI 故障排查
