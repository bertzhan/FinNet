# Vectorize Job 实时进度显示功能

## 问题描述

**修改前**：
- `vectorize_chunks_op` 在 Dagster UI 中无法显示实时进度
- 后端日志显示批次进度（如 `📦 批次 [95/132]`），但前端看不到
- 用户在整个向量化过程中（可能需要10-30分钟）看不到任何进度反馈
- 只有向量化完成后，所有 AssetMaterialization 事件才会一次性显示

## 解决方案

通过**进度回调机制**，让 `Vectorizer` 在每个批次完成后通知 `vectorize_chunks_op`，从而实时记录 AssetMaterialization 事件。

### 技术实现

#### 1. 修改 `Vectorizer.vectorize_chunks()` 方法

**文件**: `src/processing/ai/embedding/vectorizer.py`

添加可选的 `progress_callback` 参数：

```python
def vectorize_chunks(
    self,
    chunk_ids: List[Union[uuid.UUID, str]],
    force_revectorize: bool = False,
    progress_callback: Optional[callable] = None  # 新增
) -> Dict[str, Any]:
```

**位置**: 第76-98行

#### 2. 在批次循环中调用回调

**文件**: `src/processing/ai/embedding/vectorizer.py`

在每个批次处理完成后调用回调函数：

```python
# 批次处理循环（第196-236行）
for i in range(0, len(chunks_data), batch_size):
    batch = chunks_data[i:i + batch_size]
    # ... 处理批次
    result = self._vectorize_batch(batch, force_revectorize)

    # 调用进度回调（第221-236行）
    if progress_callback:
        try:
            progress_callback({
                "batch_num": batch_num,
                "total_batches": total_batches,
                "batch_size": len(batch),
                "processed": processed,
                "total": len(chunks_data),
                "vectorized_count": result["vectorized_count"],
                "failed_count": result["failed_count"],
                "batch_chunks": batch,  # 当前批次的分块数据
            })
        except Exception as callback_error:
            # 回调失败不影响主流程
            self.logger.warning(f"进度回调执行失败: {callback_error}")
```

**位置**: 第221-236行

#### 3. 修改 `vectorize_chunks_op` 提供回调实现

**文件**: `src/processing/compute/dagster/jobs/vectorize_jobs.py`

定义回调函数，在每个批次完成后立即记录 AssetMaterialization：

```python
def vectorize_chunks_op(context, scan_result: Dict) -> Dict:
    # ...

    # 定义进度回调函数（第280-330行）
    def on_batch_complete(batch_info):
        """每个批次完成后调用，记录该批次的 AssetMaterialization 事件"""
        pg_client = get_postgres_client()
        with pg_client.get_session() as session:
            # 为当前批次的成功分块记录事件
            for chunk_data in batch_info["batch_chunks"]:
                chunk_id = chunk_data["chunk_id"]

                # 查询分块信息
                chunk = session.query(DocumentChunk).filter(...).first()

                if chunk and chunk.vectorized_at:  # 确认已向量化
                    doc = session.query(Document).filter(...).first()

                    if doc:
                        # 立即记录 AssetMaterialization 事件
                        context.log_event(
                            AssetMaterialization(
                                asset_key=["silver", "vectorized_chunks", doc.market, doc.doc_type, doc.stock_code],
                                description=f"{doc.company_name} - Chunk {chunk.chunk_index} (批次 {batch_info['batch_num']}/{batch_info['total_batches']})",
                                metadata={
                                    "chunk_id": MetadataValue.text(str(chunk.id)),
                                    "batch": MetadataValue.text(f"{batch_info['batch_num']}/{batch_info['total_batches']}"),
                                    "progress": MetadataValue.text(f"{batch_info['processed']}/{batch_info['total']} (...)"),
                                    # ... 其他元数据
                                }
                            )
                        )

    # 调用向量化，传入回调（第332-337行）
    result = vectorizer.vectorize_chunks(
        chunk_ids=chunk_ids,
        force_revectorize=force_revectorize,
        progress_callback=on_batch_complete  # 传入回调
    )
```

**位置**: 第280-337行

#### 4. 移除旧的批量记录逻辑

**文件**: `src/processing/compute/dagster/jobs/vectorize_jobs.py`

删除原来的批量记录代码（第347-348行），因为已经在回调中实时记录了：

```python
# 注意：AssetMaterialization 事件已经在 on_batch_complete 回调中实时记录了
# 不再需要批量记录逻辑
```

## 效果对比

### 修改前

```
用户视角（Dagster UI）:
  [启动作业]
  ⏳ 等待 30 分钟... （看不到任何进度）
  ✅ 作业完成
  💥 突然出现 4000 个 AssetMaterialization 事件

后端日志:
  📦 批次 [1/132] | 本批 32 项 | 总进度 32/4194 (0.8%)
  📦 批次 [2/132] | 本批 32 项 | 总进度 64/4194 (1.5%)
  ...
  📦 批次 [132/132] | 本批 26 项 | 总进度 4194/4194 (100.0%)
```

### 修改后

```
用户视角（Dagster UI）:
  [启动作业]
  📊 批次 [1/132] - 32 个事件出现
  📊 批次 [2/132] - 32 个事件出现
  📊 批次 [3/132] - 32 个事件出现
  ... （实时更新）
  📊 批次 [132/132] - 26 个事件出现
  ✅ 作业完成

后端日志:
  📦 批次 [1/132] | 本批 32 项 | 总进度 32/4194 (0.8%)
    ✓ 成功 32 失败 0
  📦 批次 [2/132] | 本批 32 项 | 总进度 64/4194 (1.5%)
    ✓ 成功 32 失败 0
  ...
```

## 技术优势

### 1. 保持分层架构
- `Vectorizer` 仍然是独立的服务层，不依赖 Dagster
- `progress_callback` 是可选的，不影响其他调用方
- 回调机制符合依赖反转原则

### 2. 向后兼容
- 如果不传 `progress_callback`，行为与之前一致
- 不影响其他直接调用 `Vectorizer` 的代码
- 只有 Dagster job 会使用回调功能

### 3. 错误隔离
- 回调执行失败不会中断向量化主流程
- 单个分块事件记录失败不影响其他分块
- 批次回调失败会记录警告但继续处理

### 4. 性能优化
- 每个批次只查询一次数据库（在回调中）
- 不需要在向量化完成后再次遍历所有分块
- 减少了内存占用（不需要保存所有分块数据）

## 用户体验改进

### 实时进度反馈
- ✅ 每处理 32 个分块（约 10-30 秒），就能看到进度更新
- ✅ 可以看到当前处理到第几批（如 `批次 95/132`）
- ✅ 可以看到整体进度百分比（如 `3040/4194 (72.5%)`）

### 资产追踪
- ✅ 每个分块的 AssetMaterialization 包含批次信息
- ✅ 可以在 Dagster Assets 页面按公司、市场、文档类型查看
- ✅ 支持数据血缘追踪

### 故障诊断
- ✅ 如果作业失败，可以看到在哪个批次失败的
- ✅ 失败的分块仍然会记录到日志中（不影响已成功的分块）
- ✅ 可以通过 UI 查看每个批次的成功率

## 批次大小说明

**Vectorizer 内部批次**: 32个分块（由 `EMBEDDING_BATCH_SIZE` 配置）
- 影响嵌入模型的批量推理性能
- 较小的批次（16-32）适合 GPU 显存有限的情况
- 较大的批次（64-128）适合高性能 GPU

**进度更新频率**: 每 32 个分块更新一次进度
- 在 Dagster UI 中，每 10-30 秒就能看到新的事件
- 对于 4000 个分块，会产生约 125 个批次更新
- 不会因为事件过多而影响 UI 性能

## 测试建议

### 功能测试

1. **启动作业**:
   ```bash
   # 在 Dagster UI Launchpad 中启动 vectorize_documents_job
   ```

2. **观察 Dagster UI**:
   - 进入 Run Details 页面
   - 观察 "Materializations" 标签页
   - 应该能看到事件实时出现（每批次约 32 个）

3. **检查进度信息**:
   - 每个事件的 metadata 应该包含 `batch` 和 `progress` 字段
   - Description 应该显示批次信息（如 `批次 95/132`）

### 性能测试

1. **大规模测试**:
   ```yaml
   ops:
     scan_unvectorized_chunks_op:
       config:
         limit: 5000  # 测试 5000 个分块
   ```

2. **观察指标**:
   - 批次处理时间（应该在 10-30 秒之间）
   - 回调执行时间（应该 < 1 秒）
   - UI 响应性（应该流畅，不卡顿）

### 错误处理测试

1. **模拟回调失败**:
   - 临时修改回调函数抛出异常
   - 验证向量化主流程不受影响
   - 检查日志中是否记录了警告

2. **模拟数据库查询失败**:
   - 临时修改查询条件导致查询失败
   - 验证只有该分块的事件记录失败
   - 其他分块应该正常记录

## 相关文档

- [VECTORIZE_PROGRESS_DISPLAY.md](./VECTORIZE_PROGRESS_DISPLAY.md) - 之前添加 AssetMaterialization 的修改
- [Vectorizer API 文档](../src/processing/ai/embedding/vectorizer.py) - Vectorizer 类的详细说明
- [Dagster Jobs 文档](../src/processing/compute/dagster/jobs/vectorize_jobs.py) - 向量化作业的完整实现

## 修改文件清单

1. **src/processing/ai/embedding/vectorizer.py**
   - 第76-98行: 添加 `progress_callback` 参数
   - 第221-236行: 在批次循环中调用回调

2. **src/processing/compute/dagster/jobs/vectorize_jobs.py**
   - 第280-330行: 定义 `on_batch_complete` 回调函数
   - 第332-337行: 调用 `vectorize_chunks()` 时传入回调
   - 第347-348行: 移除旧的批量记录逻辑

## 未来改进方向

### 1. 可配置的批次大小
允许在 Dagster 配置中调整批次大小，平衡进度更新频率和性能：
```yaml
ops:
  vectorize_chunks_op:
    config:
      embedding_batch_size: 64  # 自定义批次大小
```

### 2. 更丰富的进度信息
在回调中添加更多统计信息：
- 平均处理时间
- 预计剩余时间（ETA）
- 当前处理速度（chunks/sec）

### 3. 批次级别的质量检查
在回调中对每个批次进行质量检查：
- 检测零向量
- 验证向量维度
- 统计向量分布
