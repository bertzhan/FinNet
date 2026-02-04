# 爬虫 Job 按股票代码过滤使用说明

## 功能说明

爬虫 job 现已支持通过 `stock_codes` 参数按指定的股票代码列表进行爬取。此功能优先级高于 `limit` 和 `industry` 参数。

## 适用的 Jobs

- `crawl_a_share_reports_job` - A股定期报告爬虫
- `crawl_a_share_ipo_job` - A股IPO招股说明书爬虫

## 配置参数

### `stock_codes` 参数

- **类型**: `list` (字符串列表)
- **必需**: 否 (可选)
- **默认值**: `None`
- **说明**: 指定要爬取的股票代码列表
- **优先级**: 当设置此参数时，将忽略 `limit` 和 `industry` 参数

## 使用示例

### 1. 在 Dagster Launchpad 中使用

#### 爬取指定股票代码的定期报告

```yaml
ops:
  crawl_a_share_reports_op:
    config:
      workers: 4
      enable_minio: true
      enable_postgres: true
      year: 2024  # 指定年份，将爬取该年的所有季度
      stock_codes:
        - "000001"  # 平安银行
        - "000002"  # 万科A
        - "600000"  # 浦发银行
```

#### 爬取指定股票代码的 IPO 招股说明书

```yaml
ops:
  crawl_a_share_ipo_op:
    config:
      workers: 4
      enable_minio: true
      enable_postgres: true
      stock_codes:
        - "688001"  # 华兴源创
        - "688002"  # 睿创微纳
```

### 2. 参数优先级说明

配置参数的优先级从高到低：

1. **`stock_codes`** - 指定股票代码列表（最高优先级）
2. **`industry`** - 按行业过滤
3. **`limit`** - 限制公司数量

**示例：**

```yaml
# 示例 1: 使用 stock_codes（优先级最高）
stock_codes: ["000001", "000002"]
limit: 10        # 将被忽略
industry: "银行"  # 将被忽略
# 结果：只爬取 000001 和 000002

# 示例 2: 使用 industry + limit
industry: "银行"
limit: 5
# 结果：爬取银行行业的前 5 家公司

# 示例 3: 只使用 limit
limit: 10
# 结果：爬取数据库中的前 10 家公司

# 示例 4: 不指定任何过滤条件
# 结果：爬取数据库中的所有公司
```

### 3. 完整配置示例

#### 定期报告爬虫 - 按股票代码

```yaml
ops:
  crawl_a_share_reports_op:
    config:
      # 基础配置
      output_root: "downloads"
      workers: 4
      enable_minio: true
      enable_postgres: true

      # 年份配置
      # None = 自动计算当前季度和上一季度
      # 指定年份 = 爬取该年的所有季度（Q1-Q4）
      year: 2024

      # 过滤配置 - 按股票代码列表
      stock_codes:
        - "000001"  # 平安银行
        - "000002"  # 万科A
        - "600000"  # 浦发银行
        - "600036"  # 招商银行
```

#### IPO 招股说明书爬虫 - 按股票代码

```yaml
ops:
  crawl_a_share_ipo_op:
    config:
      # 基础配置
      output_root: "downloads"
      workers: 4
      enable_minio: true
      enable_postgres: true

      # 过滤配置 - 按股票代码列表
      stock_codes:
        - "688001"
        - "688002"
        - "688003"
```

## 错误处理

### 股票代码不存在

如果指定的股票代码在数据库中不存在，job 将返回错误：

```
⚠️ 公司列表为空，未找到指定的股票代码: ['999999']
```

**解决方法：**
1. 检查股票代码是否正确
2. 确保已运行 `update_listed_companies_job` 更新公司列表
3. 验证股票代码是否在数据库中存在

### 部分股票代码不存在

如果指定的股票代码列表中，部分代码存在、部分不存在，job 将：
- 爬取找到的股票代码对应的公司
- 在日志中记录实际找到的公司数量

```
按股票代码过滤: 指定 5 个代码，找到 3 家公司
从数据库加载了 3 家公司（按股票代码: ['000001', '000002', '999999', '888888', '600000']）
```

## 注意事项

1. **股票代码格式**: 股票代码必须是字符串，且与数据库中存储的格式一致（通常是 6 位数字）
2. **大小写**: 股票代码通常不区分大小写，但建议使用数据库中的标准格式
3. **性能**: 当指定少量股票代码时，爬虫性能最优
4. **并发**: `workers` 参数控制并发爬取的进程数，建议设置为 2-8

## 查看可用的股票代码

如需查看数据库中可用的股票代码列表，可以使用以下脚本：

```python
from src.storage.metadata import get_postgres_client, crud

pg_client = get_postgres_client()
with pg_client.get_session() as session:
    # 获取所有公司
    companies = crud.get_all_listed_companies(session, limit=10)
    for company in companies:
        print(f"{company.code} - {company.name}")

    # 按行业过滤
    companies = crud.get_all_listed_companies(session, industry="银行", limit=10)
    for company in companies:
        print(f"{company.code} - {company.name}")
```

## 常见使用场景

### 场景 1: 测试爬虫功能

爬取少量公司数据用于测试：

```yaml
stock_codes: ["000001", "000002"]
workers: 2
```

### 场景 2: 补爬特定公司

补爬某些公司缺失的报告：

```yaml
stock_codes: ["600000", "600036", "601398"]
year: 2023  # 爬取 2023 年的所有季度报告
```

### 场景 3: 重点公司监控

只爬取重点关注的公司：

```yaml
stock_codes:
  - "000001"  # 平安银行
  - "000002"  # 万科A
  - "600000"  # 浦发银行
  - "600036"  # 招商银行
  - "601398"  # 工商银行
  - "601988"  # 中国银行
# 不设置 year，自动爬取当前季度和上一季度
```

## 技术实现

### 代码路径

- 配置 Schema: `src/processing/compute/dagster/jobs/crawl_jobs.py` - `REPORT_CRAWL_CONFIG_SCHEMA`
- 辅助函数: `load_company_list_from_db()`
- Op 函数: `crawl_a_share_reports_op()`, `crawl_a_share_ipo_op()`

### 数据库查询

当指定 `stock_codes` 参数时，使用以下 SQL 查询：

```sql
SELECT * FROM listed_companies
WHERE code IN ('000001', '000002', '600000')
```

### 优先级逻辑

```python
if stock_codes:
    # 按股票代码列表过滤
    companies = query(ListedCompany).filter(code.in_(stock_codes)).all()
elif industry:
    # 按行业过滤
    companies = get_all_listed_companies(industry=industry)
elif limit:
    # 限制数量
    companies = get_all_listed_companies(limit=limit)
else:
    # 获取所有公司
    companies = get_all_listed_companies()
```
