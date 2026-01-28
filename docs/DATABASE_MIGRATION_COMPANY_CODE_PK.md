# 数据库迁移：将 code 设为主键

**日期**: 2026-01-28  
**变更**: 将 `listed_companies` 表的 `code` 字段设为主键，删除 `id` 字段

---

## 📝 变更说明

### 变更原因
1. **避免重复公司记录**: 主键约束确保每个股票代码只有一条记录
2. **简化查询**: 直接使用股票代码作为主键，无需 UUID
3. **符合业务逻辑**: 股票代码本身就是唯一标识符
4. **提高性能**: 主键查询比唯一索引查询更快

### 变更内容
- ✅ `code` 字段设为主键
- ❌ 删除 `id` (UUID) 字段
- ❌ 删除 `idx_code` 索引（主键自动有索引）

---

## 🔄 数据库迁移 SQL

### 方案 A：直接迁移（推荐）

```sql
-- 1. 检查是否有重复的 code
SELECT code, COUNT(*) as count
FROM listed_companies
GROUP BY code
HAVING COUNT(*) > 1;
-- 如果有重复，需要先清理

-- 2. 删除重复记录（保留最新的）
DELETE FROM listed_companies
WHERE id NOT IN (
    SELECT MAX(id)
    FROM listed_companies
    GROUP BY code
);

-- 3. 删除外键约束（如果有）
-- 检查是否有其他表引用 listed_companies.id
SELECT 
    tc.table_name, 
    kcu.column_name, 
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name 
FROM information_schema.table_constraints AS tc 
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY' 
  AND ccu.table_name = 'listed_companies'
  AND ccu.column_name = 'id';

-- 4. 删除旧的唯一索引（如果存在）
DROP INDEX IF EXISTS idx_code;

-- 5. 删除 id 列并设置 code 为主键
ALTER TABLE listed_companies 
DROP COLUMN id,
ADD PRIMARY KEY (code);
```

### 方案 B：安全迁移（分步执行）

```sql
-- 步骤 1: 备份数据
CREATE TABLE listed_companies_backup AS 
SELECT * FROM listed_companies;

-- 步骤 2: 检查数据完整性
SELECT 
    COUNT(*) as total,
    COUNT(DISTINCT code) as unique_codes,
    COUNT(*) - COUNT(DISTINCT code) as duplicates
FROM listed_companies;

-- 步骤 3: 如果有重复，清理数据
-- 保留 updated_at 最新的记录
DELETE FROM listed_companies
WHERE id IN (
    SELECT id
    FROM (
        SELECT id,
               ROW_NUMBER() OVER (PARTITION BY code ORDER BY updated_at DESC) as rn
        FROM listed_companies
    ) t
    WHERE rn > 1
);

-- 步骤 4: 删除索引
DROP INDEX IF EXISTS idx_code;

-- 步骤 5: 删除 id 列
ALTER TABLE listed_companies DROP COLUMN id;

-- 步骤 6: 设置 code 为主键
ALTER TABLE listed_companies ADD PRIMARY KEY (code);

-- 步骤 7: 验证
SELECT 
    COUNT(*) as total,
    COUNT(DISTINCT code) as unique_codes
FROM listed_companies;
-- 应该 total = unique_codes
```

---

## ✅ 迁移前检查清单

- [ ] 备份数据库
- [ ] 检查是否有重复的 `code` 值
- [ ] 检查是否有外键引用 `listed_companies.id`
- [ ] 确认代码已更新（不再使用 `id` 字段）
- [ ] 在测试环境验证迁移脚本

---

## 🔍 验证查询

### 迁移前检查
```sql
-- 检查重复的 code
SELECT code, COUNT(*) as count
FROM listed_companies
GROUP BY code
HAVING COUNT(*) > 1;

-- 检查数据总数
SELECT COUNT(*) as total FROM listed_companies;

-- 检查唯一 code 数量
SELECT COUNT(DISTINCT code) as unique_codes FROM listed_companies;
```

### 迁移后验证
```sql
-- 验证主键设置
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'listed_companies'
ORDER BY ordinal_position;

-- 验证主键约束
SELECT 
    constraint_name,
    constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'listed_companies'
  AND constraint_type = 'PRIMARY KEY';

-- 验证数据完整性
SELECT 
    COUNT(*) as total,
    COUNT(DISTINCT code) as unique_codes
FROM listed_companies;
-- 应该 total = unique_codes
```

---

## ⚠️ 注意事项

1. **备份数据库**: 删除列和修改主键是不可逆操作，务必先备份
2. **检查重复数据**: 如果有重复的 `code`，需要先清理
3. **检查外键**: 如果有其他表引用 `listed_companies.id`，需要先处理
4. **测试环境**: 先在测试环境验证迁移脚本
5. **停机时间**: 如果数据量大，可能需要短暂停机

---

## 📊 影响范围

### 已更新的代码
- ✅ `src/storage/metadata/models.py` - `code` 设为主键，删除 `id` 字段
- ✅ `src/storage/metadata/crud.py` - 代码已通过 `code` 查询，无需修改

### 数据库变更
- ❌ 删除列：`listed_companies.id`
- ✅ 主键变更：`listed_companies.code` → PRIMARY KEY
- ❌ 删除索引：`idx_code`（主键自动有索引）

---

## 🚀 执行步骤

### 1. 准备阶段
```bash
# 备份数据库
pg_dump -h localhost -U finnet -d finnet > backup_$(date +%Y%m%d_%H%M%S).sql
```

### 2. 检查数据
```sql
-- 连接数据库
psql -h localhost -U finnet -d finnet

-- 检查重复
SELECT code, COUNT(*) as count
FROM listed_companies
GROUP BY code
HAVING COUNT(*) > 1;
```

### 3. 执行迁移
```sql
-- 如果有重复，先清理
-- 然后执行主键迁移
ALTER TABLE listed_companies 
DROP COLUMN id,
ADD PRIMARY KEY (code);
```

### 4. 验证
```sql
-- 验证主键
SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'listed_companies'
  AND constraint_type = 'PRIMARY KEY';

-- 验证数据
SELECT COUNT(*) as total, COUNT(DISTINCT code) as unique_codes
FROM listed_companies;
```

### 5. 测试代码
```bash
# 测试查询功能
python -c "
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud

with get_postgres_client().get_session() as session:
    company = crud.get_listed_company_by_code(session, '000001')
    print(f'Company: {company.code} - {company.name}' if company else 'Not found')
"
```

---

## 📚 相关文档

- `src/storage/metadata/models.py` - ListedCompany 模型定义
- `src/storage/metadata/crud.py` - ListedCompany CRUD 操作

---

## 💡 优势

1. **避免重复**: 主键约束确保每个股票代码只有一条记录
2. **简化查询**: 直接使用 `code` 作为主键查询，无需 UUID
3. **提高性能**: 主键查询比唯一索引查询更快
4. **符合业务逻辑**: 股票代码本身就是唯一标识符

---

**状态**: ✅ 代码已更新，等待数据库迁移执行
