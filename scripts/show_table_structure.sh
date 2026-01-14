#!/bin/bash
# 显示 PostgreSQL 表的详细结构

POSTGRES_HOST=${POSTGRES_HOST:-localhost}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
POSTGRES_DB=${POSTGRES_DB:-finnet}
POSTGRES_USER=${POSTGRES_USER:-finnet}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-finnet123456}

export PGPASSWORD=$POSTGRES_PASSWORD

TABLE_NAME=${1:-documents}

echo "=========================================="
echo "表结构: $TABLE_NAME"
echo "=========================================="

psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "\d $TABLE_NAME"

echo ""
echo "=========================================="
echo "表数据示例（前5条）"
echo "=========================================="

psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT * FROM $TABLE_NAME LIMIT 5;"

unset PGPASSWORD
