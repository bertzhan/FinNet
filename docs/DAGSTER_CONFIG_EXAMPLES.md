# Dagster 爬虫配置示例

## 📝 配置说明

`crawl_a_share_reports_op` 的 `year` 和 `quarter` 参数是**可选的**。如果不提供，系统会自动计算当前季度和上一季度。

## ✅ 方式1：不提供 year/quarter（自动计算，推荐）

### 在 Dagster UI 中配置

```yaml
ops:
  crawl_a_share_reports_op:
    config:
      workers: 4
      # year 和 quarter 不提供，会自动计算当前和上一季度
```

### 通过配置文件

创建 `dagster_config.yaml`：

```yaml
ops:
  crawl_a_share_reports_op:
    config:
      company_list_path: "src/crawler/zh/company_list.csv"
      output_root: "./downloads"
      workers: 4
      enable_minio: true
      enable_postgres: true
      # year 和 quarter 不设置，自动计算
      # 注意：文档类型会根据季度自动判断（Q1/Q3=季度报告，Q2=半年报，Q4=年报）
```

### 自动计算逻辑

- 如果当前是 2025年1月（Q1），会爬取：
  - 2024年Q4（上一季度）
  - 2025年Q1（当前季度）

## ✅ 方式2：指定 year 和 quarter

### 爬取指定季度

```yaml
ops:
  crawl_a_share_reports_op:
    config:
      workers: 4
      year: 2023
      quarter: 3  # Q3（自动判断为季度报告）
```

### 爬取年报

```yaml
ops:
  crawl_a_share_reports_op:
    config:
      workers: 4
      year: 2023
      quarter: 4  # Q4（自动判断为年报）
```

## 🔍 完整配置示例

### 示例1：最小配置（使用所有默认值）

```yaml
ops:
  crawl_a_share_reports_op:
    config:
      # 所有参数都使用默认值
      # 自动计算季度，爬取所有公司
```

### 示例2：完整配置

```yaml
ops:
  crawl_a_share_reports_op:
    config:
      company_list_path: "src/crawler/zh/company_list.csv"
      output_root: "./downloads/bronze"
      workers: 6
      old_pdf_dir: "./old_pdfs"  # 可选：检查旧PDF避免重复下载
      enable_minio: true
      enable_postgres: true
      year: 2023
      quarter: 3
      # 文档类型会根据季度自动判断：
      #   Q1, Q3: 季度报告 (quarterly_report)
      #   Q2: 半年报 (interim_report)
      #   Q4: 年报 (annual_report)
```

### 示例3：测试配置（少量数据）

```yaml
ops:
  crawl_a_share_reports_op:
    config:
      company_list_path: "src/crawler/zh/company_list.csv"
      output_root: "./downloads/test"
      workers: 2
      year: 2023
      quarter: 3
      enable_minio: true
      enable_postgres: true
```

## 🐛 常见问题

### Q1: 爬取失败，是否需要提供 year/quarter？

**A**: 不需要。`year` 和 `quarter` 是可选的。如果不提供，会自动计算。

### Q2: 如何知道爬取的是哪个季度？

**A**: 查看 Dagster UI 中的日志，会显示：
```
自动计算季度: 2024Q4, 2025Q1
```

### Q3: 如何只爬取一个季度？

**A**: 明确指定 `year` 和 `quarter`：
```yaml
year: 2023
quarter: 3
```

### Q4: 爬取失败的可能原因

1. **公司列表文件不存在**
   - 检查：`src/crawler/zh/company_list.csv` 是否存在
   - 解决：确保文件存在且格式正确（code,name 列）

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
| `company_list_path` | str | 否 | `src/crawler/zh/company_list.csv` | 公司列表CSV文件路径 |
| `output_root` | str | 否 | `downloads/` | 输出根目录 |
| `workers` | int | 否 | 4 | 并行进程数（1-16） |
| `old_pdf_dir` | str | 否 | None | 旧PDF目录（检查重复） |
| `enable_minio` | bool | 否 | True | 是否启用MinIO上传 |
| `enable_postgres` | bool | 否 | True | 是否启用PostgreSQL记录 |
| `year` | int | 否 | None | 年份（None=自动计算） |
| `quarter` | int | 否 | None | 季度1-4（None=自动计算） |
| | | | | **注意**：文档类型会根据季度自动判断：Q1/Q3=季度报告，Q2=半年报，Q4=年报 |

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
     crawl_a_share_reports_op:
       config:
         year: 2023
         quarter: 3
   ```
3. 点击 "Launch"

---

*最后更新: 2025-01-13*
