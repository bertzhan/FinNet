-- 扩大港股公司表字段长度
-- 解决 akshare 返回的数据超过字段长度限制的问题
-- 执行时间: 2026-02-05

-- 扩大传真字段长度（可能包含多个号码）
ALTER TABLE hk_listed_companies ALTER COLUMN fax TYPE VARCHAR(100);

-- 扩大邮箱字段长度（可能包含多个邮箱）
ALTER TABLE hk_listed_companies ALTER COLUMN email TYPE VARCHAR(200);

-- 扩大公司秘书字段长度
ALTER TABLE hk_listed_companies ALTER COLUMN secretary TYPE VARCHAR(100);

-- 扩大董事长字段长度（可能有联席董事长）
ALTER TABLE hk_listed_companies ALTER COLUMN chairman TYPE VARCHAR(100);
