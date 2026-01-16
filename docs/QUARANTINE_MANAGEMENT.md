# 隔离区管理功能说明

## 📋 概述

隔离区（Quarantine）是数据质量保证体系的核心组件，用于**隔离和处理验证失败的数据**，防止问题数据进入后续处理流程。

按照 plan.md 7.6 设计，隔离区管理需要实现以下功能：

---

## 🎯 核心功能

### 1. 自动隔离验证失败的数据

当数据在以下阶段验证失败时，自动移动到隔离区：

| 失败阶段 | 触发时机 | 示例 |
|---------|---------|------|
| **采集阶段失败** (`ingestion_failed`) | 爬虫下载失败、超时、格式错误 | PDF 无法下载、响应超时 |
| **入湖验证失败** (`validation_failed`) | Bronze 层验证失败 | 文件大小异常、哈希校验失败、元数据缺失 |
| **内容验证失败** (`content_failed`) | Silver 层验证失败 | 编码错误、语言不匹配、内容为空 |

**隔离流程**：
```
验证失败 → 移动到隔离区 → 记录到数据库 → 发送告警
```

### 2. 隔离区路径管理

按照 plan.md 5.2 存储路径规范，隔离区路径格式：

```
quarantine/{failure_stage}/{original_path}
```

**示例**：
```
# 入湖验证失败
quarantine/validation_failed/bronze/a_share/quarterly_reports/2023/Q3/000001/bad.pdf

# 内容验证失败
quarantine/content_failed/silver/text_cleaned/a_share/quarterly_reports/2023/Q3/000001/empty.txt
```

### 3. 隔离记录数据库管理

在 PostgreSQL 中记录所有隔离数据的信息：

**`quarantine_records` 表结构**：

| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | Integer | 隔离记录ID |
| `document_id` | Integer | 关联的文档ID（可选） |
| `source_type` | String | 数据来源（a_share/hk_stock/us_stock） |
| `doc_type` | String | 文档类型 |
| `original_path` | String | 原始文件路径 |
| `quarantine_path` | String | 隔离区路径 |
| `failure_stage` | String | 失败阶段（ingestion_failed/validation_failed/content_failed） |
| `failure_reason` | String | 失败原因（简要描述） |
| `failure_details` | Text | 详细错误信息 |
| `status` | String | 状态（pending/processing/resolved/discarded） |
| `handler` | String | 处理人 |
| `resolution` | Text | 处理结果 |
| `quarantine_time` | DateTime | 进入隔离时间 |
| `resolution_time` | DateTime | 处理时间 |

### 4. 人工审核和处理

提供人工审核界面和API，支持：

- **查看待处理列表**：按状态、失败阶段、时间筛选
- **查看详细信息**：失败原因、错误详情、原始文件
- **处理决策**：
  - ✅ **修复后重新入库**：修复问题后，从隔离区移回正常路径
  - 🔄 **重新采集**：删除记录，重新触发爬取任务
  - ❌ **永久丢弃**：标记为已丢弃，记录原因
  - 📝 **规则优化**：根据失败原因优化验证规则

### 5. 监控和告警

- **隔离区监控**：统计待处理数量、各阶段失败率
- **告警触发**：待处理 > 100 条时发送告警
- **趋势分析**：分析失败原因趋势，识别系统性问题

---

## 🔧 需要实现的功能

### 优先级 1：核心隔离功能

#### 1.1 隔离管理器类

**文件**: `src/storage/metadata/quarantine_manager.py`

```python
class QuarantineManager:
    """隔离区管理器"""
    
    def quarantine_document(
        self,
        document_id: int,
        failure_stage: str,
        failure_reason: str,
        failure_details: str,
        original_path: str
    ) -> QuarantineRecord:
        """
        将文档移动到隔离区
        
        流程：
        1. 生成隔离区路径
        2. 从 MinIO 移动文件到隔离区
        3. 创建隔离记录
        4. 更新文档状态为 quarantined
        """
        pass
    
    def get_pending_records(
        self,
        limit: int = 100,
        failure_stage: Optional[str] = None
    ) -> List[QuarantineRecord]:
        """获取待处理的隔离记录"""
        pass
    
    def resolve_record(
        self,
        record_id: int,
        resolution: str,
        handler: str,
        action: str  # "restore", "re_crawl", "discard"
    ) -> QuarantineRecord:
        """处理隔离记录"""
        pass
```

#### 1.2 集成到 BaseCrawler

**文件**: `src/ingestion/base/base_crawler.py`

在 `crawl()` 方法中，当验证失败时自动调用隔离：

```python
# 在 BaseCrawler.crawl() 中
if not self.validate_result(result):
    # 自动隔离
    quarantine_manager.quarantine_document(
        document_id=result.document_id,
        failure_stage="validation_failed",
        failure_reason="文件验证失败",
        failure_details=error_message,
        original_path=result.minio_object_name
    )
```

#### 1.3 集成到 Dagster 作业

**文件**: `src/processing/compute/dagster/jobs/crawl_jobs.py`

在 `validate_crawl_results_op` 中，验证失败时自动隔离：

```python
@op
def validate_crawl_results_op(context, crawl_results: Dict) -> Dict:
    """验证爬取结果，失败数据自动隔离"""
    quarantine_manager = QuarantineManager()
    
    for result in failed_results:
        quarantine_manager.quarantine_document(
            document_id=result.document_id,
            failure_stage="validation_failed",
            failure_reason=result.reason,
            failure_details=result.error_message,
            original_path=result.minio_object_name
        )
```

### 优先级 2：人工审核功能

#### 2.1 隔离记录查询 API

**文件**: `src/api/routes/quarantine.py`

```python
@router.get("/quarantine/pending")
def get_pending_records(
    status: str = "pending",
    failure_stage: Optional[str] = None,
    limit: int = 100
):
    """获取待处理的隔离记录"""
    pass

@router.get("/quarantine/{record_id}")
def get_record_details(record_id: int):
    """获取隔离记录详情"""
    pass

@router.post("/quarantine/{record_id}/resolve")
def resolve_record(
    record_id: int,
    resolution: str,
    action: str  # restore, re_crawl, discard
):
    """处理隔离记录"""
    pass
```

#### 2.2 隔离区统计 Dashboard

**文件**: `src/api/routes/quarantine.py`

```python
@router.get("/quarantine/stats")
def get_quarantine_stats():
    """获取隔离区统计信息"""
    return {
        "pending_count": 50,
        "by_stage": {
            "ingestion_failed": 10,
            "validation_failed": 30,
            "content_failed": 10
        },
        "by_reason": {
            "文件大小异常": 15,
            "元数据缺失": 20,
            "编码错误": 15
        }
    }
```

### 优先级 3：监控和告警

#### 3.1 隔离区监控

**文件**: `src/service/quality/quarantine_monitor.py`

```python
class QuarantineMonitor:
    """隔离区监控服务"""
    
    def check_quarantine_status(self) -> Dict:
        """检查隔离区状态"""
        pending_count = self.get_pending_count()
        
        if pending_count > 100:
            self.send_alert(f"隔离区待处理数据过多: {pending_count} 条")
        
        return {
            "pending_count": pending_count,
            "alert_threshold": 100,
            "status": "warning" if pending_count > 100 else "ok"
        }
```

#### 3.2 Dagster Asset 监控

**文件**: `src/processing/compute/dagster/assets/quarantine_assets.py`

```python
@asset
def quarantine_stats(context) -> Dict:
    """隔离区统计 Asset（用于 Dagster UI 展示）"""
    monitor = QuarantineMonitor()
    stats = monitor.check_quarantine_status()
    
    yield AssetMaterialization(
        asset_key="quarantine_stats",
        metadata={
            "pending_count": MetadataValue.int(stats["pending_count"]),
            "status": MetadataValue.string(stats["status"])
        }
    )
    
    return stats
```

---

## 📊 数据流程

### 完整隔离流程

```
┌─────────────────┐
│   数据验证失败   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  生成隔离路径    │
│ quarantine/...   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  MinIO 移动文件  │
│  (或复制+删除)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  创建隔离记录    │
│  (PostgreSQL)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  更新文档状态    │
│  status=quarantined │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   发送告警      │
│  (如果超过阈值)  │
└─────────────────┘
```

### 处理流程

```
┌─────────────────┐
│  人工审核        │
│  (查看详情)     │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │         │
    ▼         ▼         ▼
┌────────┐ ┌────────┐ ┌────────┐
│ 修复后  │ │ 重新   │ │ 永久   │
│ 重新入库│ │ 采集   │ │ 丢弃   │
└────────┘ └────────┘ └────────┘
```

---

## 🔍 使用示例

### 示例 1：自动隔离验证失败的数据

```python
from src.storage.metadata.quarantine_manager import QuarantineManager
from src.common.constants import QuarantineReason

# 创建隔离管理器
quarantine_mgr = QuarantineManager()

# 验证失败时自动隔离
if validation_failed:
    record = quarantine_mgr.quarantine_document(
        document_id=doc.id,
        failure_stage="validation_failed",
        failure_reason="文件大小异常（小于1KB）",
        failure_details="文件大小: 512 bytes，小于最小阈值 1024 bytes",
        original_path="bronze/a_share/quarterly_reports/2023/Q3/000001/report.pdf"
    )
    print(f"已隔离: {record.quarantine_path}")
```

### 示例 2：查询待处理的隔离记录

```python
# 查询所有待处理的记录
pending = quarantine_mgr.get_pending_records(limit=50)

for record in pending:
    print(f"ID: {record.id}")
    print(f"失败原因: {record.failure_reason}")
    print(f"隔离路径: {record.quarantine_path}")
    print(f"进入时间: {record.quarantine_time}")
```

### 示例 3：处理隔离记录

```python
# 方式1：修复后重新入库
quarantine_mgr.resolve_record(
    record_id=123,
    resolution="文件已修复，重新验证通过",
    handler="admin",
    action="restore"  # 从隔离区移回正常路径
)

# 方式2：重新采集
quarantine_mgr.resolve_record(
    record_id=124,
    resolution="删除记录，重新触发爬取",
    handler="admin",
    action="re_crawl"  # 删除隔离记录，触发重新爬取
)

# 方式3：永久丢弃
quarantine_mgr.resolve_record(
    record_id=125,
    resolution="数据源错误，无法修复",
    handler="admin",
    action="discard"  # 标记为已丢弃
)
```

---

## 📝 实现清单

### 核心功能（必须实现）

- [x] `src/storage/metadata/quarantine_manager.py` - 隔离管理器类 ✅
- [ ] 集成到 `BaseCrawler.crawl()` - 自动隔离验证失败数据
- [ ] 集成到 `validate_crawl_results_op` - Dagster 作业中自动隔离
- [x] MinIO 文件复制功能（从正常路径复制到隔离区）✅

### 人工审核功能（重要）

- [ ] `src/api/routes/quarantine.py` - 隔离记录查询和处理 API
- [ ] 隔离记录详情页面（可选，Web UI）
- [ ] 批量处理功能（批量恢复/丢弃）

### 监控和告警（可选）

- [ ] `src/service/quality/quarantine_monitor.py` - 隔离区监控服务
- [ ] Dagster Asset 监控（`quarantine_stats`）
- [ ] 告警通知（邮件/钉钉/企业微信）

---

## 🎯 总结

隔离区管理的核心价值：

1. **数据质量保证**：防止问题数据污染后续处理流程
2. **问题追踪**：记录所有失败数据，便于分析和优化
3. **人工介入**：提供审核和处理机制，确保数据完整性
4. **系统优化**：通过失败原因分析，持续优化验证规则

**当前状态**：
- ✅ 数据库表结构已定义（`QuarantineRecord`）
- ✅ CRUD 操作已实现（`crud.create_quarantine_record`）
- ✅ 路径管理已实现（`PathManager.get_quarantine_path`）
- ✅ 隔离管理器类已实现（`QuarantineManager`）
- ⏰ 自动隔离逻辑待集成（BaseCrawler、Dagster）
- ⏰ 人工审核功能待实现（API 路由）

## 🚀 快速开始

### 基本使用

```python
from src.storage.metadata import QuarantineManager

# 创建隔离管理器
manager = QuarantineManager()

# 隔离验证失败的文档
record = manager.quarantine_document(
    document_id=123,
    source_type="a_share",
    doc_type="quarterly_report",
    original_path="bronze/a_share/quarterly_reports/2023/Q3/000001/report.pdf",
    failure_stage="validation_failed",
    failure_reason="文件大小异常（小于1KB）",
    failure_details="文件大小: 512 bytes，小于最小阈值 1024 bytes"
)

# 查询待处理记录
pending = manager.get_pending_records(limit=50)

# 处理记录
manager.resolve_record(
    record_id=record.id,
    resolution="文件已修复",
    handler="admin",
    action="restore"  # restore, re_crawl, discard
)

# 获取统计信息
stats = manager.get_statistics()
print(f"待处理: {stats['pending_count']}")
```

### 运行示例

```bash
# 运行所有示例
python examples/quarantine_demo.py

# 运行特定示例
python examples/quarantine_demo.py quarantine  # 隔离文档
python examples/quarantine_demo.py list       # 查询记录
python examples/quarantine_demo.py resolve    # 处理记录
python examples/quarantine_demo.py stats      # 统计信息
```

---

*最后更新: 2025-01-13*
