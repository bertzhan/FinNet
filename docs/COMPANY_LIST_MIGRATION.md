# 上市公司列表表数据库迁移指南

## 概述

本文档说明如何将新创建的 `listed_companies` 表迁移到现有数据库中。

## 迁移方式

### 方式1：使用迁移脚本（推荐）

运行专门的迁移脚本：

```bash
python scripts/migrate_listed_companies_table.py
```

这个脚本会：
1. 检查数据库连接
2. 检查表是否已存在
3. 如果表不存在，创建新表
4. 如果表已存在，询问是否重新创建（会删除现有数据）
5. 验证表结构

### 方式2：使用数据库初始化脚本

运行完整的数据库初始化脚本（会创建所有表，包括新表）：

```bash
python scripts/init_database.py
```

这个脚本会：
- 检查所有必需的表
- 创建缺失的表（包括 `listed_companies`）
- 不会删除现有数据（使用 `checkfirst=True`）

### 方式3：手动创建表（使用 SQLAlchemy）

在 Python 中直接创建：

```python
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import ListedCompany

pg_client = get_postgres_client()

# 创建表（如果不存在）
ListedCompany.__table__.create(bind=pg_client.engine, checkfirst=True)
```

## 表结构

`listed_companies` 表的结构：

```sql
CREATE TABLE listed_companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT idx_code UNIQUE (code)
);

CREATE INDEX idx_code ON listed_companies(code);
```

字段说明：
- `id`: UUID 主键，自动生成
- `code`: 股票代码（如：000001），唯一索引
- `name`: 公司名称
- `created_at`: 创建时间
- `updated_at`: 更新时间（自动更新）

## 验证迁移

迁移完成后，可以验证表是否创建成功：

```python
from src.storage.metadata import get_postgres_client, crud

pg_client = get_postgres_client()

# 检查表是否存在
if pg_client.table_exists('listed_companies'):
    print("✅ 表已创建")
    
    # 获取记录数
    count = pg_client.get_table_count('listed_companies')
    print(f"当前记录数: {count} 家")
    
    # 查看表结构
    with pg_client.get_session() as session:
        companies = crud.get_all_listed_companies(session, limit=5)
        for company in companies:
            print(f"{company.code} - {company.name}")
else:
    print("❌ 表不存在")
```

## 常见问题

### 1. 表已存在

如果表已存在，迁移脚本会询问是否重新创建。选择：
- `yes`: 删除现有表并重新创建（会丢失所有数据）
- 其他: 保持现有表不变

### 2. 数据库连接失败

确保：
- PostgreSQL 服务正在运行
- 数据库配置正确（`.env` 文件或环境变量）
- 数据库用户有创建表的权限

### 3. 权限不足

如果遇到权限错误，确保数据库用户有：
- `CREATE TABLE` 权限
- `CREATE INDEX` 权限

## 迁移后的操作

迁移完成后，可以：

1. **运行更新作业**：
   ```bash
   python examples/test_company_list_job.py
   ```

2. **或使用 Dagster UI**：
   - 启动 UI: `bash scripts/start_dagster.sh`
   - 手动触发 `update_listed_companies_job`

3. **验证数据**：
   ```python
   from src.storage.metadata import get_postgres_client, crud
   
   pg_client = get_postgres_client()
   with pg_client.get_session() as session:
       count = len(crud.get_all_listed_companies(session))
       print(f"总记录数: {count} 家")
   ```

## 回滚

如果需要删除表（谨慎操作）：

```python
from src.storage.metadata.postgres_client import get_postgres_client
from sqlalchemy import text

pg_client = get_postgres_client()
with pg_client.get_session() as session:
    session.execute(text("DROP TABLE IF EXISTS listed_companies CASCADE"))
    session.commit()
```

⚠️ **警告**：删除表会永久丢失所有数据！

## 相关文件

- 迁移脚本：`scripts/migrate_listed_companies_table.py`
- 初始化脚本：`scripts/init_database.py`
- 模型定义：`src/storage/metadata/models.py` (ListedCompany)
- CRUD 操作：`src/storage/metadata/crud.py`
