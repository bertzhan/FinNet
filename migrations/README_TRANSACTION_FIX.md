# PostgreSQL 事务处理修复说明

## 问题描述

运行 `sync_us_companies_job` 时遇到错误：

```
sqlalchemy.exc.InternalError: (psycopg2.errors.InFailedSqlTransaction)
current transaction is aborted, commands ignored until end of transaction block
```

## 根本原因

### PostgreSQL 事务特性

当 PostgreSQL 事务中的某个 SQL 语句失败时（例如违反约束）：
1. 整个事务进入 **失败状态** (aborted state)
2. 后续所有 SQL 操作都会被**拒绝执行**
3. 必须先 `ROLLBACK` 事务，才能继续执行新操作

### 代码问题

原始代码在异常处理中：
```python
except Exception as e:
    logger.error(...)
    continue  # ❌ 没有回滚事务！
```

**流程示例**：
1. 插入 `DNMX` (CIK: 0002081125) ✅ 成功
2. 插入 `DNMXU` (CIK: 0002081125) ❌ 失败（CIK UNIQUE 冲突）
3. **事务进入失败状态**
4. 插入 `TPZEF` ❌ 被拒绝："transaction is aborted"
5. 后续所有操作都失败 ❌

## 解决方案

### 方案 1：简单回滚（已采用）

在异常处理中添加 `session.rollback()`：

```python
except Exception as e:
    session.rollback()  # ✅ 回滚事务
    logger.error(...)
    continue
```

**优点**：简单直接
**缺点**：失败记录会导致前面的成功记录也被回滚（如果在批量提交中）

### 方案 2：使用 SAVEPOINT（最终采用）

使用 PostgreSQL SAVEPOINT 实现**细粒度事务控制**：

```python
try:
    # 创建保存点
    session.execute(text("SAVEPOINT upsert_company"))

    # 执行 SQL
    result = session.execute(upsert_sql, params)

    # 释放保存点
    session.execute(text("RELEASE SAVEPOINT upsert_company"))

except Exception as e:
    # 回滚到保存点（不影响其他记录）
    try:
        session.execute(text("ROLLBACK TO SAVEPOINT upsert_company"))
    except:
        session.rollback()

    logger.error(...)
    continue
```

**优点**：
- ✅ 单个记录失败不影响其他记录
- ✅ 批量提交仍然有效
- ✅ 性能更好

**工作原理**：
1. 每条记录前创建 SAVEPOINT
2. 如果成功，释放 SAVEPOINT
3. 如果失败，回滚到 SAVEPOINT（不回滚整个事务）
4. 继续处理下一条记录

## 修改内容

### 文件修改

**src/ingestion/us_stock/jobs/sync_us_companies_job.py**

1. **添加失败计数**：
   ```python
   companies_failed = 0
   ```

2. **添加 SAVEPOINT 保护**：
   ```python
   # 在每条记录前
   session.execute(text("SAVEPOINT upsert_company"))

   # 成功后
   session.execute(text("RELEASE SAVEPOINT upsert_company"))
   ```

3. **改进异常处理**：
   ```python
   except Exception as e:
       # 回滚到 SAVEPOINT
       try:
           session.execute(text("ROLLBACK TO SAVEPOINT upsert_company"))
       except:
           session.rollback()

       companies_failed += 1
       logger.error(...)  # 显示完整错误信息
   ```

4. **改进日志输出**：
   ```python
   logger.info(f"进度: {idx}/{total} (新增: {added}, 更新: {updated}, 失败: {failed})")
   ```

5. **返回失败统计**：
   ```python
   result = {
       'companies_failed': companies_failed,
       ...
   }
   ```

## 测试验证

### 执行前（有 CIK UNIQUE 约束）

```bash
python src/ingestion/us_stock/jobs/sync_us_companies_job.py
```

**预期行为**：
- ❌ DNMXU 失败但不阻塞后续记录
- ✅ TPZEF 成功插入
- ✅ 其他记录正常处理

### 执行后（移除 CIK UNIQUE 约束）

```bash
# 1. 先执行数据库迁移
python scripts/migrate_us_companies_db.py

# 2. 重新运行同步
python src/ingestion/us_stock/jobs/sync_us_companies_job.py
```

**预期结果**：
```
✅ 美股公司列表同步完成
  总公司数: 13000
  新增: 13000
  更新: 0
  失败: 0
  耗时: 45.0秒
```

## 最佳实践

### 1. 事务边界管理

**不推荐**（粗粒度）：
```python
# 整批数据共用一个事务
for item in items:
    process(item)
session.commit()  # 任何一个失败，全部回滚
```

**推荐**（细粒度）：
```python
# 每条记录使用 SAVEPOINT
for item in items:
    try:
        session.execute(text("SAVEPOINT sp"))
        process(item)
        session.execute(text("RELEASE SAVEPOINT sp"))
    except:
        session.execute(text("ROLLBACK TO SAVEPOINT sp"))

session.commit()  # 提交成功的记录
```

### 2. 批量提交策略

```python
# 每 100 条提交一次（减少事务开销）
if idx % 100 == 0:
    session.commit()
```

### 3. 错误日志

显示完整错误信息：
```python
logger.error(
    f"处理失败: {ticker} - {str(e)}",
    extra={
        "error_type": type(e).__name__,
        ...
    },
    exc_info=True  # 打印堆栈跟踪
)
```

## 相关资源

- [PostgreSQL SAVEPOINT 文档](https://www.postgresql.org/docs/current/sql-savepoint.html)
- [SQLAlchemy 事务管理](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html)
- [psycopg2 事务控制](https://www.psycopg.org/docs/usage.html#transactions-control)
