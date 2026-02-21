# get_hs_companies_job 测试指南

## 测试状态

当前测试环境限制：
- ❌ akshare 未安装（需要 `pip install akshare`）
- ❌ 数据库连接受限（需要数据库服务运行）
- ⚠️ 部分 Dagster 依赖缺失（sentence_transformers）

## 快速测试步骤

### 1. 安装依赖

```bash
# 安装 akshare
pip install akshare>=1.12.0

# 确保其他依赖已安装
pip install -r requirements.txt
```

### 2. 初始化数据库

```bash
# 创建 listed_companies 表
python scripts/migrate_listed_companies_table.py

# 或使用完整初始化脚本
python scripts/init_database.py
```

### 3. 运行测试

#### 方式1：完整功能测试（推荐）

```bash
python examples/test_update_listed_companies_job.py
```

这个脚本会：
- 从 akshare 获取数据
- 测试数据库更新操作
- 模拟完整作业执行
- 执行实际的 Dagster 作业

#### 方式2：简单验证测试

```bash
python examples/test_company_list_simple.py
```

#### 方式3：直接执行 Dagster 作业

```bash
python examples/test_company_list_job.py
```

## 测试内容

### 测试1: akshare 数据获取

验证从 akshare API 获取 A 股上市公司列表：

```python
import akshare as ak

stock_df = ak.stock_info_a_code_name()
print(f"获取到 {len(stock_df)} 家公司")
print(stock_df.head())
```

**预期结果**：
- 成功获取数据
- 数据包含 `code` 和 `name` 列
- 数据量 > 4000 家

### 测试2: 数据库更新操作

验证数据写入数据库：

```python
from src.storage.metadata import get_postgres_client, crud

pg_client = get_postgres_client()
with pg_client.get_session() as session:
    # 更新一条记录
    company = crud.upsert_listed_company(session, "000001", "平安银行")
    print(f"更新成功: {company.code} - {company.name}")
```

**预期结果**：
- 成功连接数据库
- 表已存在
- 数据成功写入

### 测试3: 完整作业执行

执行完整的 Dagster 作业：

```python
from dagster import execute_job, RunConfig
from src.processing.compute.dagster.jobs import get_hs_companies_job

config = RunConfig(
    ops={
        "get_hs_companies_op": {
            "config": {
                "clear_before_update": False,
                "basic_info_only": False
            }
        }
    }
)

result = execute_job(get_hs_companies_job, run_config=config)
print(f"执行成功: {result.success}")
```

**预期结果**：
- 作业执行成功
- 返回统计信息（total, inserted, updated）
- 数据库记录更新

## 验证结果

### 检查数据库记录

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

### 检查作业输出

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

## 使用 Dagster UI 测试

### 1. 启动 Dagster UI

```bash
bash scripts/start_dagster.sh
```

访问：http://localhost:3000

### 2. 查找作业

在 Jobs 列表中找到 `get_hs_companies_job`

### 3. 手动触发

1. 点击作业名称
2. 点击 "Launch Run"
3. 配置参数（可选）：
   ```yaml
   ops:
     get_hs_companies_op:
       config:
         clear_before_update: false
         basic_info_only: false
   ```
4. 点击 "Launch"

### 4. 查看结果

- 在 "Runs" 标签页查看运行历史
- 点击运行记录查看详细日志
- 查看输出结果

## 命令行测试

```bash
cd /Users/han/PycharmProjects/FinNet
export PYTHONPATH=".:$PYTHONPATH"

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
- 确认数据库已创建

### 3. 表不存在

**错误**：`relation "listed_companies" does not exist`

**解决**：
```bash
python scripts/migrate_listed_companies_table.py
```

### 4. 网络问题

**错误**：从 akshare 获取的数据为空

**解决**：
- 检查网络连接
- akshare 需要访问外部 API
- 可以稍后重试

### 5. Dagster 依赖缺失

**错误**：`No module named 'sentence_transformers'`

**解决**：
```bash
pip install sentence-transformers
```

注意：这个依赖是其他 Dagster 作业需要的，不影响 `get_hs_companies_job` 本身。

## 测试检查清单

- [ ] akshare 已安装
- [ ] 数据库服务运行正常
- [ ] listed_companies 表已创建
- [ ] 数据库连接正常
- [ ] 可以从 akshare 获取数据
- [ ] 数据可以写入数据库
- [ ] Dagster 作业可以执行
- [ ] 作业输出统计信息正确

## 预期测试结果

成功执行后应该看到：

```
✅ 获取 akshare 数据: ✅ 通过
✅ 数据库更新操作: ✅ 通过
✅ 完整作业模拟: ✅ 通过
✅ Dagster 作业执行: ✅ 通过

总计: 4/4 通过

🎉 所有测试通过！

📊 作业输出:
   总计: 5000 家
   新增: 50 家
   更新: 4950 家
   更新时间: 2026-01-27T17:30:00
```

## 相关文件

- 测试脚本：`examples/test_update_listed_companies_job.py`
- 作业定义：`src/processing/compute/dagster/jobs/company_list_jobs.py`
- 数据库模型：`src/storage/metadata/models.py`
- CRUD 操作：`src/storage/metadata/crud.py`
