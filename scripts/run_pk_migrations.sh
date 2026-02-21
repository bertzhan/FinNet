#!/usr/bin/env bash
# 执行主键迁移：code -> org_id
# 顺序：listed_companies -> hk_listed_companies -> us_listed_companies

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MIGRATIONS_DIR="$PROJECT_ROOT/migrations"

# 从环境变量或默认值获取数据库连接
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-finnet}"
POSTGRES_USER="${POSTGRES_USER:-finnet}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-finnet123456}"

export PGPASSWORD="$POSTGRES_PASSWORD"

echo "=========================================="
echo "执行主键迁移: code -> org_id"
echo "=========================================="
echo "数据库: $POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB"
echo ""

for name in listed_companies hk_listed_companies us_listed_companies; do
    file="$MIGRATIONS_DIR/change_${name}_pk_to_org_id.sql"
    if [[ -f "$file" ]]; then
        echo ">>> 执行: $file"
        psql -v ON_ERROR_STOP=1 -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$file" || {
            echo "❌ 迁移失败: $file"
            exit 1
        }
        echo "✓ 完成: $name"
        echo ""
    else
        echo "⚠ 跳过（文件不存在）: $file"
    fi
done

echo "=========================================="
echo "✅ 主键迁移全部完成"
echo "=========================================="
