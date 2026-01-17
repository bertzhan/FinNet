# Document 模型缺失字段修复

## 问题描述

数据库创建文档记录时出现错误：
```
psycopg2.errors.NotNullViolation: null value in column "created_at" of relation "documents" violates not-null constraint
```

导致所有爬取任务虽然成功上传到 MinIO，但无法创建数据库记录，最终被标记为"缺少数据库ID"并隔离。

## 根本原因

**模型与数据库表结构不匹配**：

`documents` 数据库表中有以下字段要求非空：
- `created_at` (timestamp, 非空, 无默认值)

但 `Document` 模型（src/storage/metadata/models.py）中缺失了该字段及其他相关字段：
- `created_at` ❌ 缺失
- `updated_at` ❌ 缺失
- `vectorized_at` ❌ 缺失
- `error_message` ❌ 缺失
- `retry_count` ❌ 缺失

## 修复方案

在 `Document` 模型中添加缺失的字段：

### 修改前
```python
class Document(Base):
    # ... 其他字段 ...

    # 状态和时间
    status = Column(String(50), nullable=False, default='pending', index=True)
    crawled_at = Column(DateTime)
    parsed_at = Column(DateTime)

    # 元数据
    extra_metadata = Column(JSON, default={})
```

### 修改后
```python
class Document(Base):
    # ... 其他字段 ...

    # 状态和时间
    status = Column(String(50), nullable=False, default='pending', index=True)
    created_at = Column(DateTime, nullable=False, default=func.now())  # ✅ 新增
    crawled_at = Column(DateTime)
    parsed_at = Column(DateTime)
    vectorized_at = Column(DateTime)  # ✅ 新增
    updated_at = Column(DateTime, onupdate=func.now())  # ✅ 新增

    # 错误和重试  # ✅ 新增
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)

    # 元数据
    extra_metadata = Column(JSON, default={})
```

## 修改文件

- `src/storage/metadata/models.py` (第41-54行)

## 验证结果

### 修复前
```
❌ 创建文档记录失败: null value in column "created_at" violates not-null constraint
```

### 修复后
```
✅ 成功创建文档记录: id=140
   - stock_code: 000001
   - doc_type: quarterly_reports
   - year: 2023, quarter: 3
   - created_at: 2026-01-16 10:55:01.239119
   - crawled_at: 2026-01-16 18:55:01.204594
   - document_id: 140
```

## 完整测试结果

```bash
测试爬取一个文档...
✅ MinIO 上传成功: bronze/a_share/quarterly_reports/2023/Q3/000001/000001_2023_Q3.pdf
✅ PostgreSQL 记录成功: id=140

结果:
  - success: True
  - minio_object_path: bronze/a_share/quarterly_reports/2023/Q3/000001/000001_2023_Q3.pdf
  - document_id: 140  # ✅ 不再是 None
  - error_message: None

✅ 测试通过！文档已创建，document_id=140
```

## 影响范围

此修复解决了以下问题：

1. ✅ 文档记录可以成功创建到数据库
2. ✅ `document_id` 不再为空
3. ✅ 验证步骤不再报告"缺少数据库ID"
4. ✅ 文件不会被错误地隔离
5. ✅ 爬取流程完整运行（MinIO + PostgreSQL）

## 相关问题

这个问题是导致以下警告的根本原因：
```
WARNING: 缺少数据库ID: 300552
INFO: ✅ 已隔离缺少数据库ID的文档: bronze/a_share/annual_reports/2023/300552/300552_2023_Q4.pdf
```

现在这些警告将不再出现，因为文档记录可以正常创建了。
