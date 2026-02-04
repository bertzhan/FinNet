# 爬虫 Job 快速参考

## 快速使用

### 1. 按股票代码爬取（推荐用于测试和精确爬取）

```yaml
ops:
  crawl_a_share_reports_op:
    config:
      stock_codes: ["000001", "000002", "600000"]
```

### 2. 按行业爬取

```yaml
ops:
  crawl_a_share_reports_op:
    config:
      industry: "银行"
      limit: 10
```

### 3. 爬取前 N 家公司

```yaml
ops:
  crawl_a_share_reports_op:
    config:
      limit: 100
```

### 4. 爬取所有公司

```yaml
ops:
  crawl_a_share_reports_op:
    config: {}
```

## 参数说明

| 参数 | 类型 | 必需 | 默认值 | 说明 | 优先级 |
|------|------|------|--------|------|--------|
| `stock_codes` | list | 否 | None | 股票代码列表 | 1 (最高) |
| `industry` | str | 否 | None | 行业名称 | 2 |
| `limit` | int | 否 | None | 限制数量 | 3 |
| `year` | int | 否 | None | 指定年份 | - |
| `workers` | int | 否 | 4 | 并发数 | - |
| `enable_minio` | bool | 否 | true | 启用MinIO | - |
| `enable_postgres` | bool | 否 | true | 启用PostgreSQL | - |

## 常见场景

### 场景 1: 快速测试

```yaml
# 测试 2 家公司
stock_codes: ["000001", "000002"]
workers: 2
year: 2024
```

### 场景 2: 补爬特定公司

```yaml
# 补爬缺失的报告
stock_codes: ["600000", "600036", "601398"]
year: 2023
```

### 场景 3: 行业分析

```yaml
# 爬取银行业所有公司
industry: "银行"
year: 2024
```

### 场景 4: 重点公司监控

```yaml
# 监控重点公司（不指定年份，爬取当前季度和上一季度）
stock_codes:
  - "000001"  # 平安银行
  - "000002"  # 万科A
  - "600000"  # 浦发银行
  - "600036"  # 招商银行
  - "601398"  # 工商银行
```

## 完整配置示例

```yaml
ops:
  crawl_a_share_reports_op:
    config:
      # 基础配置
      output_root: "downloads"
      workers: 4
      enable_minio: true
      enable_postgres: true

      # 时间范围
      # year: 2024  # 可选，不指定则爬取当前季度和上一季度

      # 过滤条件（选择其一）
      stock_codes: ["000001", "000002"]
      # industry: "银行"
      # limit: 100
```

## 注意事项

1. **stock_codes 优先级最高**: 指定后将忽略 industry 和 limit
2. **年份配置**:
   - `year: None` (或不设置): 爬取当前季度和上一季度
   - `year: 2024`: 爬取 2024 年的所有季度 (Q1-Q4)
3. **并发数建议**: workers=2~8，过大可能被目标网站限流
4. **股票代码格式**: 6位数字字符串，如 "000001"

## 错误处理

### 问题 1: 未找到股票代码

**错误信息**:
```
⚠️ 公司列表为空，未找到指定的股票代码: ['999999']
```

**解决方法**:
1. 检查股票代码是否正确
2. 运行 `update_listed_companies_job` 更新公司列表
3. 使用以下脚本查看可用的股票代码：

```python
from src.storage.metadata import get_postgres_client, crud

pg_client = get_postgres_client()
with pg_client.get_session() as session:
    companies = crud.get_all_listed_companies(session, limit=10)
    for company in companies:
        print(f"{company.code} - {company.name}")
```

### 问题 2: 公司列表为空

**错误信息**:
```
⚠️ 公司列表为空，请先运行 update_listed_companies_job 更新公司列表
```

**解决方法**:
在 Dagster UI 中运行 `update_listed_companies_job`

## 相关文档

- [详细使用说明](crawl_job_stock_codes_usage.md)
- [功能实现总结](CRAWL_STOCK_CODES_FEATURE.md)
