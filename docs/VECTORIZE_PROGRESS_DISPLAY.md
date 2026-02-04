# Vectorize Job 进度显示功能

## 问题描述
`vectorize_documents_job` 在 Dagster UI 中没有显示进度信息，只有日志输出，用户无法直观地看到向量化的进度。

## 解决方案
参考 `crawl_jobs.py` 的实现，在 `vectorize_jobs.py` 中添加了 `AssetMaterialization` 事件记录功能。

### 修改内容

#### 1. 导入必要的模块
```python
from dagster import (
    # ... 其他导入
    AssetMaterialization,
    MetadataValue,
)
```

#### 2. 在 `vectorize_chunks_op` 中记录每个成功向量化的分块
位置：`src/processing/compute/dagster/jobs/vectorize_jobs.py:283-331`

为每个成功向量化的分块记录 `AssetMaterialization` 事件，包含以下元数据：
- `chunk_id`: 分块 ID
- `document_id`: 文档 ID
- `stock_code`: 股票代码
- `company_name`: 公司名称
- `year`: 年份
- `quarter`: 季度
- `chunk_index`: 分块索引
- `vectorized_at`: 向量化时间

资产键格式：`["silver", "vectorized_chunks", market, doc_type, stock_code]`

#### 3. 在 `validate_vectorize_results_op` 中记录汇总信息
位置：`src/processing/compute/dagster/jobs/vectorize_jobs.py:474-487`

记录整体向量化质量指标，包含以下元数据：
- `total`: 总分块数
- `vectorized`: 成功向量化数量
- `failed`: 失败数量
- `success_rate`: 成功率
- `validation_passed`: 验证是否通过

资产键格式：`["quality_metrics", "vectorize_validation"]`

## 效果

### 在 Dagster UI 中的显示

1. **Run Details 页面**
   - 显示每个成功向量化的分块作为独立的资产物化事件
   - 可以查看每个分块的详细元数据（公司、季度、分块索引等）

2. **Assets 页面**
   - 在 `silver/vectorized_chunks` 下按 market、doc_type、stock_code 组织
   - 显示每个公司的向量化进度

3. **质量指标**
   - 在 `quality_metrics/vectorize_validation` 中显示汇总统计
   - 成功率、失败数量等关键指标

### 用户体验改进
- ✅ 实时看到向量化进度（已处理多少个分块）
- ✅ 查看每个分块的详细信息
- ✅ 追踪资产血缘关系
- ✅ 监控质量指标和成功率

## 测试建议

1. 运行 `vectorize_documents_job` 作业
2. 在 Dagster UI 中查看 Run Details
3. 检查是否显示 AssetMaterialization 事件
4. 查看 Assets 页面，确认资产已正确组织

## 相关文件
- `src/processing/compute/dagster/jobs/vectorize_jobs.py`
- `src/processing/compute/dagster/jobs/crawl_jobs.py` (参考实现)
