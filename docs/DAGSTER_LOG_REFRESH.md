# Dagster 日志刷新问题解决方案

## 📋 问题描述

在 Dagster 作业执行过程中，后台的 `logger.info()` 信息不能立即刷新到 Dagster 前端 UI，需要等待一段时间或手动刷新页面才能看到最新日志。

## 🔍 原因分析

### 1. Python 日志缓冲机制

Python 的 `logging` 模块默认使用缓冲输出，日志不会立即刷新到标准输出。这导致：

- 日志在内存中缓冲
- 只有在缓冲区满或程序结束时才刷新
- Dagster 前端通过轮询获取日志，但缓冲区未刷新时无法获取新日志

### 2. Dagster 日志收集机制

Dagster 通过以下方式收集日志：

1. **`get_dagster_logger()`**：Dagster 提供的日志记录器，会自动将日志发送到 Dagster 后端
2. **标准输出捕获**：Dagster 会捕获 `stdout` 和 `stderr` 的输出
3. **轮询机制**：前端通过轮询后端 API 获取最新日志（通常每 1-2 秒轮询一次）

### 3. 日志缓冲的影响

- **缓冲延迟**：日志在 Python 的缓冲区中，未刷新到 `stdout`
- **前端轮询**：即使前端轮询，也获取不到未刷新的日志
- **批量刷新**：日志可能在作业结束时才批量刷新

## ✅ 解决方案

### 方案 1：使用 `get_dagster_logger()`（推荐）⭐

**最佳实践**：在 Dagster ops 中使用 `get_dagster_logger()`，而不是普通的 `logging.getLogger()`。

```python
from dagster import get_dagster_logger

@op
def my_op(context):
    # ✅ 正确：使用 Dagster 日志记录器
    logger = get_dagster_logger()
    logger.info("这条日志会立即显示在 Dagster UI")
    
    # ❌ 错误：使用普通日志记录器（可能不会立即显示）
    # import logging
    # logger = logging.getLogger(__name__)
    # logger.info("这条日志可能不会立即显示")
```

**优点**：
- Dagster 日志记录器会自动将日志发送到 Dagster 后端
- 日志会立即出现在前端 UI
- 不需要手动刷新缓冲区

### 方案 2：手动刷新标准输出

如果必须使用普通日志记录器，可以手动刷新 `stdout`：

```python
import sys
import logging

logger = logging.getLogger(__name__)

@op
def my_op(context):
    logger.info("这条日志")
    sys.stdout.flush()  # 手动刷新缓冲区
```

**缺点**：
- 需要每次日志后都调用 `flush()`
- 代码冗余
- 不推荐使用

### 方案 3：配置日志 Handler 无缓冲

在日志配置中设置 `StreamHandler` 为无缓冲模式：

```python
import sys
import logging

# 创建无缓冲的 StreamHandler
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
handler.stream.reconfigure(line_buffering=True)  # Python 3.7+

logger = logging.getLogger(__name__)
logger.addHandler(handler)
```

**注意**：这种方法可能影响性能，不推荐在生产环境使用。

### 方案 4：使用 `context.log`（Dagster 专用）

Dagster 提供了 `context.log` 方法，专门用于在 ops 中记录日志：

```python
@op
def my_op(context):
    # ✅ 使用 context.log（推荐）
    context.log.info("这条日志会立即显示")
    context.log.warning("警告日志")
    context.log.error("错误日志")
```

**优点**：
- 专门为 Dagster 设计
- 日志立即显示
- 与 Dagster 的日志系统完美集成

## 🎯 最佳实践

### 1. 在 Dagster Ops 中使用 `get_dagster_logger()`

```python
from dagster import op, get_dagster_logger

@op
def vectorize_chunks_op(context, scan_result: Dict) -> Dict:
    logger = get_dagster_logger()  # ✅ 使用 Dagster 日志记录器
    
    logger.info("开始向量化...")
    # 执行向量化
    logger.info("向量化完成")
    
    return result
```

### 2. 避免在 Dagster Ops 中使用普通日志记录器

```python
# ❌ 不推荐
import logging
logger = logging.getLogger(__name__)

# ✅ 推荐
from dagster import get_dagster_logger
logger = get_dagster_logger()
```

### 3. 对于长时间运行的循环，定期记录进度

```python
@op
def process_batch_op(context, items: List) -> Dict:
    logger = get_dagster_logger()
    
    total = len(items)
    for i, item in enumerate(items):
        # 处理 item
        process_item(item)
        
        # 每处理 10% 记录一次进度
        if (i + 1) % (total // 10) == 0:
            logger.info(f"进度: {i + 1}/{total} ({(i+1)/total*100:.1f}%)")
    
    return {"processed": total}
```

### 4. 使用 `context.log_event()` 记录重要事件

```python
from dagster import AssetMaterialization, MetadataValue

@op
def my_op(context):
    logger = get_dagster_logger()
    
    # 记录普通日志
    logger.info("处理开始")
    
    # 记录重要事件（会在 Dagster UI 的 Assets 标签页显示）
    context.log_event(
        AssetMaterialization(
            asset_key=["my_asset"],
            description="处理完成",
            metadata={
                "count": MetadataValue.int(100),
                "status": MetadataValue.text("success")
            }
        )
    )
```

## 🔧 检查当前代码

### 检查是否使用了 `get_dagster_logger()`

```bash
# 检查 Dagster ops 中的日志使用情况
grep -r "get_dagster_logger" src/processing/compute/dagster/
grep -r "logging.getLogger" src/processing/compute/dagster/
```

### 检查日志配置

```bash
# 检查日志配置文件
cat config/logging.yaml
cat config/dagster.yaml
```

## 📊 日志刷新时间

| 方法 | 刷新延迟 | 推荐度 |
|------|---------|--------|
| `get_dagster_logger()` | 立即（< 1秒） | ⭐⭐⭐⭐⭐ |
| `context.log` | 立即（< 1秒） | ⭐⭐⭐⭐⭐ |
| `logging.getLogger()` + `sys.stdout.flush()` | 立即（但需要手动刷新） | ⭐⭐⭐ |
| `logging.getLogger()`（无缓冲配置） | 立即（但可能影响性能） | ⭐⭐ |
| `logging.getLogger()`（默认缓冲） | 延迟（可能数秒到数分钟） | ❌ |

## 💡 常见问题

### Q1: 为什么我的日志在作业完成后才显示？

**A**: 可能是因为使用了普通的 `logging.getLogger()` 而不是 `get_dagster_logger()`。Python 的日志缓冲机制导致日志在作业结束时才刷新。

### Q2: 我已经使用了 `get_dagster_logger()`，但日志还是不立即显示？

**A**: 检查以下几点：
1. 确认使用的是 `from dagster import get_dagster_logger`
2. 确认在 `@op` 装饰的函数中使用
3. 检查 Dagster UI 是否正常连接（查看浏览器控制台是否有错误）
4. 尝试刷新浏览器页面

### Q3: 可以在非 Dagster 代码中使用 `get_dagster_logger()` 吗？

**A**: 不建议。`get_dagster_logger()` 只能在 Dagster 的执行上下文中使用（即在 `@op` 或 `@asset` 装饰的函数中）。在非 Dagster 代码中，应该使用普通的 `logging.getLogger()`。

### Q4: 如何查看实时日志？

**A**: 
1. 在 Dagster UI 中打开运行详情页
2. 点击 "Logs" 标签页
3. 日志会自动刷新（通常每 1-2 秒）
4. 如果日志不更新，尝试刷新浏览器页面

## 📝 总结

**核心要点**：
1. ✅ 在 Dagster ops 中**始终使用 `get_dagster_logger()`**
2. ✅ 避免使用普通的 `logging.getLogger()`（除非在非 Dagster 代码中）
3. ✅ 对于重要事件，使用 `context.log_event()` 记录
4. ✅ 定期记录进度，避免长时间无日志输出

**快速修复**：
将所有 Dagster ops 中的 `logging.getLogger(__name__)` 替换为 `get_dagster_logger()`。

---

*最后更新: 2026-02-02*
