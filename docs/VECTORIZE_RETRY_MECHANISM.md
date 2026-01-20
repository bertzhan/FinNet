# 向量化失败重试机制说明

## 📋 概述

本文档说明向量化作业失败后的自动重试机制，以及系统如何确保所有分块最终都能成功向量化。

---

## 🔄 核心机制

### 1. 失败标记机制

**关键字段：`vector_id`**

- **成功向量化**：`vector_id` 会被更新为 Milvus 返回的向量 ID（非空字符串）
- **向量化失败**：`vector_id` 保持为 `NULL`，**不会被更新**

这意味着失败的分块在数据库中仍然标记为"未向量化"状态。

### 2. 扫描机制

**扫描条件：`vector_id IS NULL`**

每次向量化作业执行时，`scan_unvectorized_chunks_op` 会查询所有 `vector_id IS NULL` 的分块：

```python
# 来自 src/processing/compute/dagster/jobs/vectorize_jobs.py
query = session.query(DocumentChunk).join(
    Document, DocumentChunk.document_id == Document.id
)

if not force_revectorize:
    query = query.filter(DocumentChunk.vector_id.is_(None))
    logger.info("过滤条件: 只扫描未向量化的分块 (vector_id IS NULL)")
```

**扫描范围**：
- 新创建的分块（从未向量化）
- **之前向量化失败的分块**（`vector_id` 仍为 `NULL`）

### 3. 自动重试机制

**Dagster Schedule 定期执行**

系统配置了两个定时调度：

1. **每2小时执行**（`hourly_vectorize_schedule`）
   ```python
   cron_schedule="0 */2 * * *"  # 每2小时执行一次
   ```

2. **每天凌晨6点执行**（`daily_vectorize_schedule`）
   ```python
   cron_schedule="0 6 * * *"  # 每天凌晨6点执行
   ```

每次调度执行时，都会：
1. 扫描所有 `vector_id IS NULL` 的分块（包括之前失败的）
2. 尝试向量化这些分块
3. 成功的分块更新 `vector_id`，失败的分块保持 `vector_id = NULL`
4. 下次调度时，失败的分块会再次被扫描和处理

---

## 🔍 失败场景分析

### 场景1：API 调用失败

**原因**：
- API 服务不可用
- 网络超时
- API Key 无效
- 请求频率限制（429）

**处理**：
- `vector_id` 保持为 `NULL`
- 分块会在下次调度时自动重试

### 场景2：向量数量不匹配

**原因**：
- API 返回的向量数量与输入文本数量不一致
- 批量处理时部分文本处理失败

**处理**：
- 整个批次标记为失败
- `vector_id` 保持为 `NULL`
- 所有分块会在下次调度时重试

### 场景3：Milvus 插入失败

**原因**：
- Milvus 服务不可用
- 向量维度不匹配
- 数据库连接失败

**处理**：
- `vector_id` 保持为 `NULL`
- 分块会在下次调度时重试

### 场景4：数据库更新失败

**原因**：
- PostgreSQL 连接失败
- 事务提交失败
- 分块记录不存在

**处理**：
- `vector_id` 保持为 `NULL`（如果更新失败）
- 分块会在下次调度时重试

---

## 📊 重试流程示例

```
时间线：
T0: 分块创建，vector_id = NULL
T1: 向量化作业执行，API 调用失败
     → vector_id 保持 NULL
T2: 2小时后，向量化作业再次执行
     → 扫描到该分块（vector_id IS NULL）
     → 重试向量化，成功
     → vector_id 更新为 "12345"
T3: 后续作业不再扫描该分块（vector_id 不为 NULL）
```

---

## ⚙️ 配置说明

### 扫描配置

在 Dagster 作业配置中：

```yaml
ops:
  scan_unvectorized_chunks_op:
    config:
      batch_size: 32        # 每批处理32个分块
      limit: 1000            # 每次最多处理1000个分块
      force_revectorize: false  # 不强制重新向量化
```

### 调度配置

```python
# 每2小时执行
@schedule(
    job=vectorize_documents_job,
    cron_schedule="0 */2 * * *",
    default_status=DefaultScheduleStatus.STOPPED,  # 默认停止，需手动启用
)
```

---

## ✅ 优势

1. **自动恢复**：临时故障（网络、服务重启）会自动恢复
2. **无需人工干预**：失败的分块会自动重试，无需手动处理
3. **数据一致性**：只有成功向量化的分块才会更新 `vector_id`
4. **幂等性**：多次执行不会产生重复数据

---

## ⚠️ 注意事项

### 1. 无限重试

**当前机制**：失败的分块会**无限重试**，直到成功。

**潜在问题**：
- 如果分块本身有问题（如文本格式错误），会一直重试
- 可能浪费计算资源

**建议改进**：
- 添加重试次数限制（如最多重试 5 次）
- 记录失败原因，便于排查问题
- 对于持续失败的分块，可以考虑隔离或标记

### 2. 批量失败

如果整个批次失败，所有分块都会重试。

**示例**：
- 批次包含 32 个分块
- API 返回向量数量不匹配（返回 1 个，期望 32 个）
- 整个批次标记为失败，32 个分块都会重试

### 3. 调度频率

**当前配置**：每2小时执行一次

**考虑因素**：
- 如果失败分块很多，可能需要更频繁的调度
- 如果失败分块很少，可以减少调度频率以节省资源

---

## 🔧 如何查看失败的分块

### 方法1：查询数据库

```sql
-- 查看未向量化的分块数量
SELECT COUNT(*) 
FROM document_chunks 
WHERE vector_id IS NULL;

-- 查看未向量化的分块详情
SELECT 
    dc.id AS chunk_id,
    dc.chunk_index,
    d.stock_code,
    d.company_name,
    d.year,
    d.quarter
FROM document_chunks dc
JOIN documents d ON dc.document_id = d.id
WHERE dc.vector_id IS NULL
LIMIT 100;
```

### 方法2：使用脚本

```bash
# 使用检查脚本
python scripts/check_chunks_stats.py
```

### 方法3：查看 Dagster UI

在 Dagster UI 中查看向量化作业的执行历史：
- 查看 `failed_count` 统计
- 查看 `failed_chunks` 列表（最多显示10个）

---

## 🚀 未来改进建议

### 1. 添加重试次数限制

```python
# 在 DocumentChunk 模型中添加字段
vectorize_retry_count = Column(Integer, default=0)
vectorize_last_error = Column(Text)  # 记录最后一次失败原因
```

### 2. 失败原因记录

记录每次失败的具体原因，便于排查：
- API 错误信息
- 向量数量不匹配详情
- Milvus 错误信息

### 3. 智能重试策略

- **指数退避**：失败次数越多，重试间隔越长
- **分类处理**：根据失败原因采用不同的重试策略
- **告警机制**：连续失败超过阈值时发送告警

### 4. 失败分块隔离

对于持续失败的分块（如重试超过5次），可以考虑：
- 标记为"需要人工处理"
- 移动到隔离区
- 记录详细错误信息

---

## 📝 总结

**当前机制**：
- ✅ 自动重试失败的分块
- ✅ 基于 `vector_id IS NULL` 的简单判断
- ✅ 定期调度确保最终一致性

**改进方向**：
- 🔄 添加重试次数限制
- 📝 记录失败原因
- 🚨 添加告警机制
- 🔍 提供更详细的失败分析工具
