# 隔离管理器测试和验证指南

**创建时间**: 2025-01-13  
**目的**: 验证隔离管理器功能是否正确实现

---

## 📋 测试概览

### 测试类型

1. **单元测试** - 测试隔离管理器各个方法
2. **集成测试** - 测试与 BaseCrawler 和 Dagster 的集成
3. **端到端测试** - 测试完整的数据流程
4. **手动测试** - 通过示例脚本和 UI 验证

---

## 🧪 测试方案

### 1. 单元测试

#### 1.1 测试隔离管理器核心方法

**文件**: `tests/unit/test_quarantine_manager.py`

**测试用例**：

```python
# 测试 quarantine_document()
- 测试正常隔离流程
- 测试文件不存在时的处理
- 测试数据库连接失败时的处理
- 测试隔离路径生成

# 测试 get_pending_records()
- 测试查询待处理记录
- 测试按失败阶段过滤
- 测试限制返回数量

# 测试 resolve_record()
- 测试 restore 操作
- 测试 re_crawl 操作
- 测试 discard 操作
- 测试无效操作的处理

# 测试 get_statistics()
- 测试统计信息准确性
- 测试告警阈值判断
```

#### 1.2 测试隔离路径生成

**验证点**：
- 路径格式符合 plan.md 规范
- 不同失败阶段生成不同路径
- 原始路径正确保留

#### 1.3 测试文件操作

**验证点**：
- MinIO 文件复制成功
- 文件元数据正确设置
- 文件不存在时的错误处理

---

### 2. 集成测试

#### 2.1 BaseCrawler 集成测试

**测试场景**：

```python
# 场景1：文件大小验证失败
- 创建一个 < 1KB 的文件
- 运行爬虫
- 验证是否自动隔离

# 场景2：文件不存在验证失败
- 模拟文件下载失败
- 验证是否隔离

# 场景3：验证通过
- 创建正常文件
- 验证不被隔离
```

#### 2.2 Dagster 作业集成测试

**测试场景**：

```python
# 场景1：爬取失败隔离
- 模拟爬取失败
- 验证是否隔离（ingestion_failed）

# 场景2：缺少MinIO路径隔离
- 模拟MinIO上传失败
- 验证是否隔离（validation_failed）

# 场景3：缺少数据库ID隔离
- 模拟数据库记录失败
- 验证是否隔离（validation_failed）
```

---

### 3. 端到端测试

#### 3.1 完整流程测试

**测试步骤**：

1. 启动服务（MinIO、PostgreSQL）
2. 运行爬虫任务
3. 触发验证失败
4. 验证隔离记录创建
5. 验证文件移动到隔离区
6. 验证文档状态更新
7. 测试处理隔离记录

---

## 🔧 测试脚本

### 脚本1：单元测试脚本

**文件**: `tests/unit/test_quarantine_manager.py`

```python
"""
隔离管理器单元测试
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.storage.metadata.quarantine_manager import QuarantineManager
from src.storage.metadata.models import QuarantineRecord
from src.common.constants import QuarantineReason

class TestQuarantineManager:
    """隔离管理器测试类"""
    
    def test_quarantine_document_success(self):
        """测试成功隔离文档"""
        # TODO: 实现测试
        pass
    
    def test_quarantine_document_file_not_exists(self):
        """测试文件不存在时的处理"""
        # TODO: 实现测试
        pass
    
    def test_get_pending_records(self):
        """测试查询待处理记录"""
        # TODO: 实现测试
        pass
    
    def test_resolve_record_restore(self):
        """测试恢复操作"""
        # TODO: 实现测试
        pass
    
    def test_get_statistics(self):
        """测试统计信息"""
        # TODO: 实现测试
        pass
```

### 脚本2：集成测试脚本

**文件**: `tests/integration/test_quarantine_integration.py`

```python
"""
隔离管理器集成测试
测试与 BaseCrawler 和 Dagster 的集成
"""

def test_basecrawler_auto_quarantine():
    """测试 BaseCrawler 自动隔离"""
    # TODO: 实现测试
    pass

def test_dagster_auto_quarantine():
    """测试 Dagster 作业自动隔离"""
    # TODO: 实现测试
    pass
```

### 脚本3：手动测试脚本

**文件**: `scripts/test_quarantine_manual.sh`

```bash
#!/bin/bash
# 隔离管理器手动测试脚本

echo "=== 隔离管理器手动测试 ==="

# 1. 检查服务状态
echo "1. 检查服务状态..."
docker-compose ps

# 2. 运行示例脚本
echo "2. 运行隔离示例..."
python examples/quarantine_demo.py

# 3. 查询隔离记录
echo "3. 查询隔离记录..."
python -c "
from src.storage.metadata import get_quarantine_manager
manager = get_quarantine_manager()
records = manager.get_pending_records(limit=10)
print(f'待处理记录数: {len(records)}')
"

# 4. 获取统计信息
echo "4. 获取统计信息..."
python -c "
from src.storage.metadata import get_quarantine_manager
manager = get_quarantine_manager()
stats = manager.get_statistics()
print(f'待处理: {stats[\"pending_count\"]}')
print(f'状态: {stats[\"status\"]}')
"
```

---

## ✅ 验证清单

### 功能验证

#### 1. 隔离功能验证

- [ ] **隔离文档**
  - [ ] 文件成功复制到隔离区
  - [ ] 隔离记录成功创建
  - [ ] 文档状态更新为 `quarantined`
  - [ ] 隔离路径格式正确

- [ ] **查询功能**
  - [ ] 可以查询待处理记录
  - [ ] 可以按失败阶段过滤
  - [ ] 可以限制返回数量

- [ ] **处理功能**
  - [ ] `restore` 操作：文件恢复到正常路径
  - [ ] `re_crawl` 操作：删除记录和文件
  - [ ] `discard` 操作：标记为已丢弃

- [ ] **统计功能**
  - [ ] 统计信息准确
  - [ ] 告警阈值正确判断

#### 2. BaseCrawler 集成验证

- [ ] **自动隔离**
  - [ ] 验证失败时自动调用隔离
  - [ ] 隔离记录正确创建
  - [ ] 日志记录完整

- [ ] **配置选项**
  - [ ] `enable_quarantine=False` 时跳过隔离
  - [ ] `enable_quarantine=True` 时正常隔离

#### 3. Dagster 集成验证

- [ ] **自动隔离**
  - [ ] 爬取失败时隔离（`ingestion_failed`）
  - [ ] 缺少MinIO路径时隔离（`validation_failed`）
  - [ ] 缺少数据库ID时隔离（`validation_failed`）

- [ ] **Asset 记录**
  - [ ] 隔离数量记录到 Dagster Asset
  - [ ] 可以在 Dagster UI 中查看

---

## 🧪 测试步骤

### 步骤1：准备测试环境

```bash
# 1. 启动服务
docker-compose up -d

# 2. 检查服务状态
docker-compose ps

# 3. 验证服务连接
python scripts/check_services.sh
```

### 步骤2：运行单元测试

```bash
# 运行隔离管理器单元测试
pytest tests/unit/test_quarantine_manager.py -v

# 或者使用 Python 直接运行
python -m pytest tests/unit/test_quarantine_manager.py -v
```

### 步骤3：运行集成测试

```bash
# 运行集成测试
pytest tests/integration/test_quarantine_integration.py -v
```

### 步骤4：手动测试

#### 4.1 测试隔离功能

```bash
# 运行隔离示例
python examples/quarantine_demo.py quarantine
```

**预期结果**：
- 隔离记录创建成功
- 文件复制到隔离区
- 日志显示隔离成功

#### 4.2 测试查询功能

```bash
# 查询待处理记录
python examples/quarantine_demo.py list
```

**预期结果**：
- 显示待处理记录列表
- 记录信息完整

#### 4.3 测试处理功能

```bash
# 处理隔离记录
python examples/quarantine_demo.py resolve
```

**预期结果**：
- 记录状态更新
- 文件操作成功（restore/re_crawl）
- 日志记录完整

#### 4.4 测试统计功能

```bash
# 获取统计信息
python examples/quarantine_demo.py stats
```

**预期结果**：
- 统计信息准确
- 告警状态正确

### 步骤5：测试 BaseCrawler 集成

```python
# 创建测试脚本 test_basecrawler_quarantine.py
from src.ingestion.a_share import ReportCrawler
from src.ingestion.base.base_crawler import CrawlTask
from src.common.constants import Market, DocType

# 创建爬虫（启用自动隔离）
crawler = ReportCrawler(enable_quarantine=True)

# 创建一个会验证失败的任务（文件太小）
# 需要模拟一个 < 1KB 的文件
task = CrawlTask(
    stock_code="000001",
    company_name="测试公司",
    market=Market.A_SHARE,
    doc_type=DocType.QUARTERLY_REPORT,
    year=2023,
    quarter=3
)

# 运行爬取（应该会触发隔离）
result = crawler.crawl(task)

# 验证是否隔离
from src.storage.metadata import get_quarantine_manager
manager = get_quarantine_manager()
if result.document_id:
    records = manager.get_pending_records()
    # 检查是否有对应的隔离记录
    print(f"隔离记录数: {len(records)}")
```

### 步骤6：测试 Dagster 集成

```bash
# 1. 启动 Dagster
bash scripts/start_dagster.sh

# 2. 访问 Dagster UI
# http://localhost:3000

# 3. 运行爬虫作业
# 在 UI 中手动触发 crawl_a_share_reports_job

# 4. 查看验证结果
# 检查 Asset Materialization 中的隔离数量

# 5. 查询隔离记录
python -c "
from src.storage.metadata import get_quarantine_manager
manager = get_quarantine_manager()
stats = manager.get_statistics()
print(f'隔离统计: {stats}')
"
```

---

## 🔍 验证点检查

### 1. 数据库验证

```sql
-- 查询隔离记录
SELECT * FROM quarantine_records 
WHERE status = 'pending' 
ORDER BY quarantine_time DESC 
LIMIT 10;

-- 查询文档状态
SELECT id, stock_code, status 
FROM documents 
WHERE status = 'quarantined' 
LIMIT 10;
```

### 2. MinIO 验证

```python
from src.storage.object_store.minio_client import MinIOClient

client = MinIOClient()

# 列出隔离区文件
files = client.list_files(prefix="quarantine/", max_results=20)
for f in files:
    print(f"隔离文件: {f['name']}, 大小: {f['size']}")
```

### 3. 日志验证

```bash
# 查看隔离相关日志
grep -i "quarantine\|隔离" logs/*.log | tail -20
```

---

## 📊 测试数据准备

### 创建测试文件

```python
# 创建测试文件脚本 create_test_files.py
import os
from pathlib import Path

# 创建测试目录
test_dir = Path("test_data")
test_dir.mkdir(exist_ok=True)

# 1. 创建正常文件（> 1KB）
normal_file = test_dir / "normal.pdf"
with open(normal_file, "wb") as f:
    f.write(b"%PDF-1.4\n" + b"x" * 2000)  # 2KB

# 2. 创建小文件（< 1KB，会验证失败）
small_file = test_dir / "small.pdf"
with open(small_file, "wb") as f:
    f.write(b"%PDF-1.4\n" + b"x" * 500)  # 500B

# 3. 创建空文件（会验证失败）
empty_file = test_dir / "empty.pdf"
with open(empty_file, "wb") as f:
    f.write(b"")

print("测试文件创建完成")
```

---

## 🐛 常见问题排查

### 问题1：隔离记录未创建

**检查点**：
- PostgreSQL 连接是否正常
- 数据库表是否存在
- 日志中是否有错误信息

**解决方法**：
```bash
# 检查数据库连接
python scripts/check_database.py

# 检查表结构
python scripts/show_table_structure.sh quarantine_records
```

### 问题2：文件未复制到隔离区

**检查点**：
- MinIO 连接是否正常
- 原始文件是否存在
- 隔离路径是否正确

**解决方法**：
```bash
# 检查 MinIO 连接
python scripts/check_minio_config.py

# 检查文件是否存在
python scripts/check_minio_files.py
```

### 问题3：文档状态未更新

**检查点**：
- 文档ID是否正确
- 数据库事务是否提交
- 日志中是否有错误

**解决方法**：
```python
# 手动检查文档状态
from src.storage.metadata import get_postgres_client, crud

with get_postgres_client().get_session() as session:
    doc = crud.get_document_by_id(session, document_id)
    print(f"文档状态: {doc.status}")
```

---

## 📈 性能测试

### 测试批量隔离

```python
# 测试批量隔离性能
import time
from src.storage.metadata import QuarantineManager

manager = QuarantineManager()

start_time = time.time()

# 批量隔离100个文档
for i in range(100):
    manager.quarantine_document(
        document_id=None,
        source_type="a_share",
        doc_type="quarterly_report",
        original_path=f"bronze/a_share/test_{i}.pdf",
        failure_stage="validation_failed",
        failure_reason="测试隔离"
    )

elapsed = time.time() - start_time
print(f"批量隔离100个文档耗时: {elapsed:.2f}秒")
print(f"平均每个: {elapsed/100:.3f}秒")
```

---

## ✅ 测试报告模板

### 测试结果记录

```markdown
## 隔离管理器测试报告

**测试时间**: 2025-01-13
**测试人员**: [姓名]

### 单元测试
- [ ] quarantine_document() - ✅/❌
- [ ] get_pending_records() - ✅/❌
- [ ] resolve_record() - ✅/❌
- [ ] get_statistics() - ✅/❌

### 集成测试
- [ ] BaseCrawler 集成 - ✅/❌
- [ ] Dagster 集成 - ✅/❌

### 端到端测试
- [ ] 完整流程测试 - ✅/❌

### 问题记录
1. [问题描述]
2. [问题描述]

### 结论
[测试结论]
```

---

## 🎯 快速验证清单

### 5分钟快速验证

```bash
# 1. 检查服务
docker-compose ps

# 2. 运行示例
python examples/quarantine_demo.py stats

# 3. 检查数据库
python -c "
from src.storage.metadata import get_quarantine_manager
m = get_quarantine_manager()
print('隔离管理器初始化:', '✅' if m else '❌')
stats = m.get_statistics()
print(f'统计信息: {stats}')
"

# 4. 检查代码
python -c "
from src.storage.metadata import QuarantineManager
print('导入成功:', '✅')
"
```

---

## 📝 总结

### 测试重点

1. **功能正确性**：隔离、查询、处理功能正常
2. **集成正确性**：与 BaseCrawler 和 Dagster 正确集成
3. **数据一致性**：数据库、MinIO、日志数据一致
4. **错误处理**：异常情况正确处理

### 验证方法

1. **自动化测试**：单元测试和集成测试
2. **手动测试**：示例脚本和 UI 操作
3. **数据验证**：数据库和 MinIO 检查
4. **日志检查**：错误和警告日志

---

*最后更新: 2025-01-13*
