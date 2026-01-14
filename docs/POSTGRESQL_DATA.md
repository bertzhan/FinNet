# PostgreSQL 数据存储说明

本文档说明运行 Dagster op（如 `crawl_a_share_ipo_op`、`crawl_a_share_reports_op`）时会存入 PostgreSQL 的数据结构。

## 数据表：`documents`

运行 op 时，每个成功爬取的文档会在 `documents` 表中创建一条记录。

### 表结构

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `id` | Integer | 主键，自增 | `1` |
| `stock_code` | String(20) | 股票代码 | `"000001"` |
| `company_name` | String(200) | 公司名称 | `"平安银行"` |
| `market` | String(50) | 市场类型 | `"a_share"` |
| `doc_type` | String(50) | 文档类型 | `"ipo_prospectus"` 或 `"quarterly_reports"` |
| `year` | Integer | 年份 | `2023` |
| `quarter` | Integer | 季度 (1-4)，IPO 为 NULL | `3` 或 `NULL` |
| `minio_object_name` | String(500) | MinIO 对象路径（唯一） | `"bronze/a_share/ipo_prospectus/000001/000001.pdf"` |
| `file_size` | BigInteger | 文件大小（字节） | `1024000` |
| `file_hash` | String(64) | 文件哈希（MD5） | `"a1b2c3d4e5f6..."` |
| `status` | String(50) | 文档状态 | `"crawled"` |
| `created_at` | DateTime | 创建时间 | `2024-01-01 10:00:00` |
| `crawled_at` | DateTime | 爬取时间 | `2024-01-01 10:00:00` |
| `parsed_at` | DateTime | 解析时间（初始为 NULL） | `NULL` |
| `vectorized_at` | DateTime | 向量化时间（初始为 NULL） | `NULL` |
| `updated_at` | DateTime | 更新时间 | `2024-01-01 10:00:00` |
| `error_message` | Text | 错误信息（成功时为 NULL） | `NULL` |
| `retry_count` | Integer | 重试次数 | `0` |
| `extra_metadata` | JSON | 额外元数据（JSON 格式） | 见下方说明 |

### IPO 招股说明书数据示例

```json
{
  "id": 1,
  "stock_code": "000001",
  "company_name": "平安银行",
  "market": "a_share",
  "doc_type": "ipo_prospectus",
  "year": 2023,
  "quarter": null,
  "minio_object_name": "bronze/a_share/ipo_prospectus/000001/000001.pdf",
  "file_size": 2048000,
  "file_hash": "a1b2c3d4e5f6789012345678901234567890abcd",
  "status": "crawled",
  "created_at": "2024-01-01T10:00:00",
  "crawled_at": "2024-01-01T10:00:00",
  "parsed_at": null,
  "vectorized_at": null,
  "updated_at": "2024-01-01T10:00:00",
  "error_message": null,
  "retry_count": 0,
  "extra_metadata": {
    "publication_date": "01012023",
    "publication_year": "2023",
    "publication_date_iso": "2023-01-01T00:00:00",
    "doc_type": "ipo_prospectus"
  }
}
```

### 定期报告数据示例

```json
{
  "id": 2,
  "stock_code": "000001",
  "company_name": "平安银行",
  "market": "a_share",
  "doc_type": "quarterly_reports",
  "year": 2023,
  "quarter": 3,
  "minio_object_name": "bronze/a_share/quarterly_reports/2023/Q3/000001/000001_2023_Q3.pdf",
  "file_size": 3072000,
  "file_hash": "b2c3d4e5f6789012345678901234567890abcdef",
  "status": "crawled",
  "created_at": "2024-01-01T10:05:00",
  "crawled_at": "2024-01-01T10:05:00",
  "parsed_at": null,
  "vectorized_at": null,
  "updated_at": "2024-01-01T10:05:00",
  "error_message": null,
  "retry_count": 0,
  "extra_metadata": {
    "stock_code": "000001",
    "year": "2023",
    "quarter": "3"
  }
}
```

## extra_metadata 字段说明

`extra_metadata` 是一个 JSON 字段，存储额外的元数据信息。

### IPO 招股说明书的 extra_metadata

```json
{
  "publication_date": "01012023",           // 发布日期（DDMMYYYY 格式）
  "publication_year": "2023",              // 发布年份（YYYY 格式）
  "publication_date_iso": "2023-01-01T00:00:00",  // 发布日期（ISO 格式）
  "doc_type": "ipo_prospectus"             // 文档类型
}
```

### 定期报告的 extra_metadata

```json
{
  "stock_code": "000001",                  // 股票代码
  "year": "2023",                          // 年份
  "quarter": "3"                           // 季度
}
```

## 数据流程

### 1. IPO Op (`crawl_a_share_ipo_op`)

```
1. 爬取 IPO 招股说明书
   ↓
2. 下载文件到本地临时目录
   ↓
3. 计算文件哈希（MD5）
   ↓
4. 上传到 MinIO（Bronze 层）
   ↓
5. 读取 metadata 文件（包含发布日期信息）
   ↓
6. 存入 PostgreSQL documents 表
   - stock_code: 股票代码
   - company_name: 公司名称
   - market: "a_share"
   - doc_type: "ipo_prospectus"
   - year: 从 metadata 获取的发布年份
   - quarter: NULL（IPO 不需要季度）
   - minio_object_name: MinIO 路径
   - file_size: 文件大小
   - file_hash: MD5 哈希
   - status: "crawled"
   - crawled_at: 当前时间
   - extra_metadata: 包含 publication_date 等信息
```

### 2. Reports Op (`crawl_a_share_reports_op`)

```
1. 爬取定期报告（年报/季报）
   ↓
2. 下载文件到本地临时目录
   ↓
3. 计算文件哈希（MD5）
   ↓
4. 上传到 MinIO（Bronze 层）
   ↓
5. 存入 PostgreSQL documents 表
   - stock_code: 股票代码
   - company_name: 公司名称
   - market: "a_share"
   - doc_type: "quarterly_reports" 或 "annual_reports"
   - year: 报告年份
   - quarter: 季度 (1-4)
   - minio_object_name: MinIO 路径
   - file_size: 文件大小
   - file_hash: MD5 哈希
   - status: "crawled"
   - crawled_at: 当前时间
   - extra_metadata: 包含 stock_code, year, quarter
```

## 唯一性约束

`documents` 表有以下唯一性约束：

1. **`minio_object_name`** - 唯一索引，确保同一文件路径不会重复记录
2. **`(stock_code, year, quarter, doc_type)`** - 唯一约束，确保同一公司的同一文档不会重复

## 去重逻辑

在存入 PostgreSQL 前，代码会检查：

1. **按 MinIO 路径检查**：如果 `minio_object_name` 已存在，则返回现有记录的 ID，不创建新记录
2. **按业务键检查**：如果 `(stock_code, year, quarter, doc_type)` 已存在，则返回现有记录的 ID

这样可以避免重复爬取和存储相同文档。

## 查询示例

### 查询所有 IPO 招股说明书

```sql
SELECT * FROM documents 
WHERE doc_type = 'ipo_prospectus' 
ORDER BY crawled_at DESC;
```

### 查询特定股票的季度报告

```sql
SELECT * FROM documents 
WHERE stock_code = '000001' 
  AND doc_type = 'quarterly_reports'
  AND year = 2023
ORDER BY quarter;
```

### 查询包含发布日期信息的 IPO 文档

```sql
SELECT 
  id,
  stock_code,
  company_name,
  year,
  extra_metadata->>'publication_date' as publication_date,
  extra_metadata->>'publication_date_iso' as publication_date_iso
FROM documents 
WHERE doc_type = 'ipo_prospectus'
  AND extra_metadata->>'publication_date' IS NOT NULL;
```

### 统计各状态的文档数量

```sql
SELECT status, COUNT(*) as count
FROM documents
GROUP BY status;
```

## 相关表

除了 `documents` 表，系统还包含以下相关表（运行 op 时不会直接写入）：

- **`document_chunks`** - 文档分块表（解析后写入）
- **`crawl_tasks`** - 爬取任务表（可选，记录任务执行情况）
- **`parse_tasks`** - 解析任务表（解析阶段写入）
- **`validation_logs`** - 验证日志表（验证阶段写入）
- **`embedding_tasks`** - 向量化任务表（向量化阶段写入）
- **`quarantine_records`** - 隔离记录表（失败数据隔离时写入）

## 注意事项

1. **IPO 的 year 字段**：IPO 文档的 `year` 从 metadata 文件中的 `publication_year` 获取，如果无法获取则使用当前年份
2. **IPO 的 quarter 字段**：IPO 文档的 `quarter` 始终为 `NULL`
3. **文件哈希**：使用 MD5 算法计算文件哈希，用于去重和完整性校验
4. **状态管理**：初始状态为 `"crawled"`，后续处理阶段会更新为 `"parsed"`、`"vectorized"` 等
5. **时间戳**：`created_at` 和 `crawled_at` 在创建时设置为当前时间，`parsed_at` 和 `vectorized_at` 初始为 `NULL`
