# CIK UNIQUE 约束问题说明

## 问题描述

在运行 `sync_us_companies_job` 时，部分公司处理失败：

```
处理公司失败: DNMXU (CIK: 0002081125)
处理公司失败: DNMXW (CIK: 0002081125)
处理公司失败: APXTU (CIK: 0002079253)
处理公司失败: APXTW (CIK: 0002079253)
...
```

## 根本原因

### CIK (Central Index Key) 的特性

CIK 是 SEC 分配给**公司**的唯一标识符，而非证券级别的标识符。

同一家公司可能发行多种证券类型：

| 证券类型 | 后缀 | 示例 | 说明 |
|---------|------|------|------|
| 普通股 (Common Stock) | 无 | DNMX | 公司的普通股票 |
| 单位 (Units) | U | DNMXU | 股票+认股权证的组合 |
| 认股权证 (Warrants) | W | DNMXW | 购买普通股的权利 |
| 优先股 (Preferred) | -P | DNMX-P | 优先股 |
| 权利 (Rights) | -R | DNMX-R | 认购权 |

**关键点**：所有这些证券都属于**同一家公司**，因此共享**同一个 CIK**。

### 数据库约束冲突

原始 schema 中，`cik` 字段有 `UNIQUE` 约束：

```sql
cik VARCHAR(10) NOT NULL UNIQUE
```

这导致：
1. 插入 `DNMX` (CIK: 0002081125) ✅ 成功
2. 插入 `DNMXU` (CIK: 0002081125) ❌ 失败（CIK 重复）
3. 插入 `DNMXW` (CIK: 0002081125) ❌ 失败（CIK 重复）

## 解决方案

### 1. 移除 CIK UNIQUE 约束

**原因**：
- `code` (Ticker) 是证券级别的唯一标识符（主键）
- `cik` 是公司级别的标识符，允许重复
- 保留 `cik` 索引用于查询性能

**修改**：
```sql
-- 原来
cik VARCHAR(10) NOT NULL UNIQUE

-- 修改后
cik VARCHAR(10) NOT NULL  -- 移除 UNIQUE，保留索引
```

### 2. 执行数据库迁移

**方案 A：使用 Python 脚本（推荐）**

```bash
python scripts/migrate_us_companies_db.py
# 输入 'yes' 确认更新
```

脚本会自动：
- ✅ 删除 `cik` 的 UNIQUE 约束
- ✅ 保留 `idx_us_cik` 索引（查询性能）
- ✅ 删除 `exchange` 字段
- ✅ 添加 `idx_us_active` 索引

**方案 B：使用 SQL 脚本**

```bash
psql -h localhost -U finnet -d finnet -f migrations/fix_us_companies_cik_unique.sql
```

### 3. 重新运行同步任务

修复后重新运行：

```bash
python src/ingestion/us_stock/jobs/sync_us_companies_job.py
```

现在所有证券都能成功插入：
- ✅ DNMX (CIK: 0002081125)
- ✅ DNMXU (CIK: 0002081125)
- ✅ DNMXW (CIK: 0002081125)

## 数据示例

修复后，数据库中会有类似记录：

```sql
SELECT code, name, cik FROM us_listed_companies WHERE cik = '0002081125';

 code  |        name         |    cik
-------|---------------------|------------
 DNMX  | Innovision Inc      | 0002081125
 DNMXU | Innovision Inc Unit | 0002081125
 DNMXW | Innovision Inc Wt   | 0002081125
```

## 查询多证券公司

查看哪些公司发行了多种证券：

```sql
SELECT
    cik,
    COUNT(*) as ticker_count,
    STRING_AGG(code, ', ' ORDER BY code) as tickers
FROM us_listed_companies
GROUP BY cik
HAVING COUNT(*) > 1
ORDER BY ticker_count DESC
LIMIT 10;
```

## 影响范围

### 已修改文件

1. ✅ `migrations/add_us_listed_companies.sql` - 创建表 schema（移除 UNIQUE）
2. ✅ `migrations/fix_us_companies_cik_unique.sql` - 修复现有表的迁移脚本
3. ✅ `src/storage/metadata/models.py` - SQLAlchemy 模型（移除 unique=True）
4. ✅ `src/ingestion/us_stock/jobs/sync_us_companies_job.py` - 改进错误日志
5. ✅ `scripts/migrate_us_companies_db.py` - 迁移脚本（新增 CIK 约束处理）
6. ✅ `src/ingestion/us_stock/README.md` - 文档更新

### 不影响的功能

- ✅ 按 CIK 查询公司（索引仍然存在）
- ✅ 按 Ticker 查询证券（主键唯一性）
- ✅ 财报爬取逻辑（使用 CIK 获取财报）

## 最佳实践

### 查询单只证券

```python
# 使用 Ticker（主键）
result = session.query(USListedCompany).filter_by(code='AAPL').first()
```

### 查询公司的所有证券

```python
# 使用 CIK（现在允许多条记录）
results = session.query(USListedCompany).filter_by(cik='0000320193').all()
# 可能返回：AAPL, AAPL-W, AAPL-U 等
```

### 过滤主要证券（排除衍生品）

```python
# 排除 Warrants, Units, Rights
results = session.query(USListedCompany).filter(
    USListedCompany.code.notlike('%U'),
    USListedCompany.code.notlike('%W'),
    USListedCompany.code.notlike('%-R')
).all()
```

## 参考资料

- [SEC Ticker Symbol Conventions](https://www.sec.gov/edgar/searchedgar/companysearch.html)
- [Understanding Stock Warrants](https://www.investopedia.com/terms/w/warrant.asp)
- [Understanding Units](https://www.investopedia.com/terms/u/unitholder.asp)
