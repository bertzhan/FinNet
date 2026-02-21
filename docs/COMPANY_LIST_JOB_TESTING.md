# 上市公司列表更新作业测试指南

## 概述

本文档介绍如何测试 `get_hs_companies_job` 作业，该作业使用 akshare 获取 A 股上市公司列表并更新到数据库。

## 前置条件

### 1. 安装依赖

```bash
# 安装 akshare
pip install akshare>=1.12.0

# 确保其他依赖已安装
pip install -r requirements.txt
```

### 2. 初始化数据库

确保数据库表已创建：

```bash
python scripts/init_database.py
```

这会创建 `listed_companies` 表。

### 3. 配置环境变量

确保 PostgreSQL 数据库配置正确（在 `.env` 文件或环境变量中）：

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=finnet
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
```

## 测试方式

### 方式1：使用简单测试脚本（推荐用于快速验证）

```bash
python examples/test_company_list_simple.py
```

这个脚本会测试：
- akshare 导入
- 数据获取
- 数据库模型
- CRUD 操作
- Dagster Op 定义
- 数据库连接

### 方式2：使用完整测试脚本（需要完整 Dagster 环境）

```bash
python examples/test_company_list_job.py
```

这个脚本会：
- 执行完整的 Dagster 作业
- 验证数据库记录
- 测试查询功能

### 方式3：通过 Dagster UI 测试（推荐用于生产环境）

1. **启动 Dagster UI**：
   ```bash
   bash scripts/start_dagster.sh
   ```

2. **访问 UI**：
   打开浏览器访问：http://localhost:3000

3. **查找作业**：
   - 在 Jobs 列表中查找 `get_hs_companies_job`
   - 点击作业名称进入详情页

4. **手动触发**：
   - 点击右上角 "Launch Run" 按钮
   - 配置参数（可选）：
     ```yaml
     ops:
       get_hs_companies_op:
         config:
           clear_before_update: false  # false=upsert策略, true=清空后重新导入
           basic_info_only: false      # false=获取详情, true=仅 code/name
     ```
   - 点击 "Launch" 执行

5. **查看结果**：
   - 在 "Runs" 标签页查看运行历史
   - 点击运行记录查看详细日志
   - 查看输出结果（total, inserted, updated）

### 方式4：通过命令行测试

```bash
cd /Users/han/PycharmProjects/FinNet
export PYTHONPATH=".:$PYTHONPATH"

# 执行更新作业
dagster job execute \
  -j get_hs_companies_job \
  -m src.processing.compute.dagster \
  --config '{
    "ops": {
      "get_hs_companies_op": {
        "config": {
          "clear_before_update": false,
          "basic_info_only": false
        }
      }
    }
  }'
```

## 验证结果

### 1. 检查数据库记录

```python
from src.storage.metadata import get_postgres_client, crud

pg_client = get_postgres_client()
with pg_client.get_session() as session:
    # 获取总数
    companies = crud.get_all_listed_companies(session)
    print(f"总记录数: {len(companies)} 家")
    
    # 查看前10条
    for company in companies[:10]:
        print(f"{company.code} - {company.name}")
```

### 2. 检查作业输出

作业执行后会返回：
```python
{
    "success": True,
    "total": 5000,      # 从 akshare 获取的总数
    "inserted": 100,    # 新增的公司数
    "updated": 4900,    # 更新的公司数
    "updated_at": "2026-01-27T17:30:00"
}
```

## 常见问题

### 1. akshare 导入失败

**错误**：`ModuleNotFoundError: No module named 'akshare'`

**解决**：
```bash
pip install akshare>=1.12.0
```

### 2. 数据库连接失败

**错误**：`connection to server at "localhost" failed`

**解决**：
- 确保 PostgreSQL 服务正在运行
- 检查 `.env` 文件中的数据库配置
- 确认数据库已创建：`createdb finnet`

### 3. 表不存在

**错误**：`relation "listed_companies" does not exist`

**解决**：
```bash
python scripts/init_database.py
```

### 4. 网络问题导致数据获取失败

**错误**：从 akshare 获取的数据为空

**解决**：
- 检查网络连接
- akshare 可能需要访问外部 API，确保网络畅通
- 可以稍后重试

## 定时调度

作业默认配置了每日定时更新（凌晨1点），但默认是停止状态。要启用定时调度：

1. 在 Dagster UI 中进入 Schedules 页面
2. 找到 `daily_update_companies_schedule`
3. 点击 "Start" 启用

或者通过代码启用：
```python
from dagster import DagsterInstance

instance = DagsterInstance.get()
instance.start_schedule("daily_update_companies_schedule")
```

## 手动触发传感器

也可以通过传感器手动触发：

1. 在 Dagster UI 中进入 Sensors 页面
2. 找到 `manual_trigger_companies_sensor`
3. 点击 "Start" 启用
4. 点击 "Trigger" 手动触发

## 测试检查清单

- [ ] akshare 已安装
- [ ] 数据库表已创建
- [ ] 数据库连接正常
- [ ] 作业可以成功执行
- [ ] 数据正确写入数据库
- [ ] 更新统计信息正确
- [ ] 可以查询到更新后的数据

## 示例输出

成功执行后的输出示例：

```
✅ Job 执行完成
   成功: True
   运行ID: abc123-def456-ghi789

📊 更新结果:
   总计: 5000 家
   新增: 50 家
   更新: 4950 家
   更新时间: 2026-01-27T17:30:00
```

## 相关文件

- 作业定义：`src/processing/compute/dagster/jobs/company_list_jobs.py`
- 数据库模型：`src/storage/metadata/models.py` (ListedCompany)
- CRUD 操作：`src/storage/metadata/crud.py`
- 测试脚本：`examples/test_company_list_*.py`
