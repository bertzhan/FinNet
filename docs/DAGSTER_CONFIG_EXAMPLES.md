# Dagster 爬虫配置示例

## 📝 配置说明

`crawl_hs_reports_op` 的 `year` 参数是**必需的**。爬取该年 Q1-Q4 所有季度。

## ✅ 基本配置

### 在 Dagster UI 中配置

```yaml
ops:
  crawl_hs_reports_op:
    config:
      year: 2024  # 必需
      workers: 4
```

### 通过配置文件

创建 `dagster_config.yaml`：

```yaml
ops:
  crawl_hs_reports_op:
    config:
      year: 2024  # 必需
      output_root: "./downloads"
      workers: 4
      # 公司列表从数据库读取（需先运行 get_hs_companies_job）
      # limit: 10  # 可选，限制公司数量
      # stock_codes: ["000001", "000002"]  # 可选，仅爬取指定代码
```

### 爬取逻辑

- 指定 `year` 后，会爬取该年 Q1、Q2、Q3、Q4 四个季度的报告
- 文档类型自动判断：Q1/Q3=季度报告，Q2=半年报，Q4=年报

## 🔍 完整配置示例

### 示例1：最小配置

```yaml
ops:
  crawl_hs_reports_op:
    config:
      year: 2024  # 必需，爬取该年 Q1-Q4
```

### 示例2：完整配置

```yaml
ops:
  crawl_hs_reports_op:
    config:
      year: 2023
      output_root: "./downloads/bronze"
      workers: 6
      # 文档类型会根据季度自动判断：Q1/Q3=季度报告，Q2=半年报，Q4=年报
```

### 示例3：测试配置（少量数据）

```yaml
ops:
  crawl_hs_reports_op:
    config:
      year: 2023
      output_root: "./downloads/test"
      workers: 2
      limit: 10  # 测试时限制公司数量
```

## 🐛 常见问题

### Q1: 爬取失败，是否需要提供 year？

**A**: 需要。`year` 是必需参数，会爬取该年 Q1-Q4 所有季度。

### Q2: 如何只爬取部分公司？

**A**: 使用 `limit` 或 `stock_codes` 参数：
```yaml
year: 2024
limit: 10  # 仅爬取前10家
# 或
stock_codes: ["000001", "000002"]  # 仅爬取指定代码
```

### Q4: 爬取失败的可能原因

1. **公司列表为空**
   - 检查：是否已运行 `get_hs_companies_job` 更新公司列表
   - 解决：在 Dagster UI 中先运行 `get_hs_companies_job`

2. **MinIO 连接失败**
   - 检查：MinIO 服务是否运行
   - 解决：`docker-compose ps minio` 或检查环境变量

3. **PostgreSQL 连接失败**
   - 检查：PostgreSQL 服务是否运行
   - 解决：`docker-compose ps postgres` 或检查环境变量

4. **输出目录权限问题**
   - 检查：输出目录是否可写
   - 解决：使用相对路径 `./downloads` 而不是 `/data/...`

## 📋 参数说明

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----|------|------|--------|------|
| `year` | int | 是 | - | 年份，爬取该年 Q1-Q4 |
| `output_root` | str | 否 | `downloads/` | 输出根目录 |
| `workers` | int | 否 | 4 | 并行进程数（1-16） |
| `limit` | int | 否 | None | 限制公司数量（测试用） |
| `stock_codes` | list | 否 | None | 指定股票代码列表 |
| | | | | **注意**：公司列表从数据库读取，需先运行 `get_hs_companies_job` |

## 🚀 快速测试

### 测试1：使用默认配置（自动计算季度）

在 Dagster UI 中：
1. 点击 `crawl_hs_reports_job`
2. 点击 "Launch Run"
3. 不修改配置，直接点击 "Launch"

### 测试2：指定季度

在 Dagster UI 中：
1. 点击 "Launch Run"
2. 在配置中添加：
   ```yaml
   ops:
     crawl_hs_reports_op:
       config:
         year: 2023
         quarter: 3
   ```
3. 点击 "Launch"

---

*最后更新: 2025-01-13*
