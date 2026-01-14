#!/bin/bash
# 列出 PostgreSQL 数据库中的所有表

# 从环境变量或使用默认值
POSTGRES_HOST=${POSTGRES_HOST:-localhost}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
POSTGRES_DB=${POSTGRES_DB:-finnet}
POSTGRES_USER=${POSTGRES_USER:-finnet}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-finnet123456}

echo "=========================================="
echo "PostgreSQL 数据库表列表"
echo "=========================================="
echo "数据库: $POSTGRES_DB"
echo "主机: $POSTGRES_HOST:$POSTGRES_PORT"
echo "用户: $POSTGRES_USER"
echo "=========================================="
echo ""

# 使用 PGPASSWORD 环境变量传递密码
export PGPASSWORD=$POSTGRES_PASSWORD

# 列出所有表
psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "\dt"

echo ""
echo "=========================================="
echo "表详细信息（包含行数）"
echo "=========================================="

# 获取表名列表并显示每个表的行数
psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -t -c "
SELECT 
    schemaname || '.' || tablename AS table_name,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY tablename;
"

echo ""
echo "=========================================="
echo "每个表的行数统计"
echo "=========================================="

# 获取每个表的行数
psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "
SELECT 
    schemaname || '.' || relname AS table_name,
    n_tup_ins - n_tup_del AS row_count
FROM pg_stat_user_tables
ORDER BY relname;
"

# 清除密码
unset PGPASSWORD
