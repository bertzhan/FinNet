#!/bin/bash

# Dagster 集成测试脚本
# 用于验证 Dagster 集成是否正常工作

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Dagster 集成测试${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 获取项目根目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

# 设置 PYTHONPATH
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# 测试1: 检查 Python 环境
echo -e "${BLUE}[1/6] 检查 Python 环境...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ 未找到 python3${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}✅ Python: $PYTHON_VERSION${NC}"
echo ""

# 测试2: 检查并安装项目依赖
echo -e "${BLUE}[2/6] 检查项目依赖...${NC}"
REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"
if [ -f "$REQUIREMENTS_FILE" ]; then
    echo -e "${BLUE}   发现 requirements.txt，检查依赖...${NC}"
    
    # 检查关键依赖
    MISSING_DEPS=()
    
    if ! python3 -c "import pydantic_settings" 2>/dev/null; then
        MISSING_DEPS+=("pydantic-settings")
    fi
    
    if ! python3 -c "import dagster" 2>/dev/null; then
        MISSING_DEPS+=("dagster")
        MISSING_DEPS+=("dagster-webserver")
    fi
    
    if ! python3 -c "import minio" 2>/dev/null; then
        MISSING_DEPS+=("minio")
    fi
    
    if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
        echo -e "${YELLOW}⚠️  缺少依赖: ${MISSING_DEPS[*]}${NC}"
        echo -e "${YELLOW}   正在安装...${NC}"
        pip3 install "${MISSING_DEPS[@]}"
        if [ $? -ne 0 ]; then
            echo -e "${RED}❌ 安装失败，请手动运行: pip install -r requirements.txt${NC}"
            exit 1
        fi
        echo -e "${GREEN}✅ 依赖安装成功${NC}"
    else
        echo -e "${GREEN}✅ 所有关键依赖已安装${NC}"
        if python3 -c "import dagster" 2>/dev/null; then
            DAGSTER_VERSION=$(python3 -c "import dagster; print(dagster.__version__)" 2>/dev/null)
            echo -e "${GREEN}   Dagster 版本: $DAGSTER_VERSION${NC}"
        fi
    fi
else
    echo -e "${YELLOW}⚠️  未找到 requirements.txt，尝试安装 Dagster...${NC}"
    if ! python3 -c "import dagster" 2>/dev/null; then
        pip3 install dagster dagster-webserver
    fi
fi
echo ""

# 测试3: 检查爬虫模块是否可以导入
echo -e "${BLUE}[3/6] 检查爬虫模块...${NC}"
IMPORT_ERROR=$(python3 -c "from src.ingestion.a_share import ReportCrawler, CninfoIPOProspectusCrawler; print('OK')" 2>&1)
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ 爬虫模块导入失败${NC}"
    echo "$IMPORT_ERROR"
    
    # 检查是否是依赖问题
    if echo "$IMPORT_ERROR" | grep -q "pydantic_settings"; then
        echo -e "${YELLOW}   检测到缺少 pydantic-settings，正在安装...${NC}"
        pip3 install pydantic-settings
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}   pydantic-settings 安装成功，重试导入...${NC}"
            python3 -c "from src.ingestion.a_share import ReportCrawler, CninfoIPOProspectusCrawler; print('OK')" 2>&1
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✅ 爬虫模块导入成功${NC}"
            else
                exit 1
            fi
        else
            exit 1
        fi
    else
        exit 1
    fi
else
    echo -e "${GREEN}✅ 爬虫模块导入成功${NC}"
fi
echo ""

# 测试4: 检查 Dagster Jobs 是否可以导入
echo -e "${BLUE}[4/6] 检查 Dagster Jobs 模块...${NC}"
if ! python3 -c "from src.processing.compute.dagster.jobs import crawl_a_share_reports_job, crawl_a_share_ipo_job; print('OK')" 2>/dev/null; then
    echo -e "${RED}❌ Dagster Jobs 导入失败${NC}"
    python3 -c "from src.processing.compute.dagster.jobs import crawl_a_share_reports_job" 2>&1
    exit 1
fi
echo -e "${GREEN}✅ Dagster Jobs 导入成功${NC}"
echo ""

# 测试5: 检查 Jobs 定义是否正确
echo -e "${BLUE}[5/6] 检查 Jobs 定义...${NC}"
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from src.processing.compute.dagster.jobs import (
    crawl_a_share_reports_job,
    crawl_a_share_ipo_job,
    daily_crawl_reports_schedule,
    daily_crawl_ipo_schedule,
)

# 检查 Jobs
assert crawl_a_share_reports_job is not None, "crawl_a_share_reports_job 未定义"
assert crawl_a_share_ipo_job is not None, "crawl_a_share_ipo_job 未定义"
assert daily_crawl_reports_schedule is not None, "daily_crawl_reports_schedule 未定义"
assert daily_crawl_ipo_schedule is not None, "daily_crawl_ipo_schedule 未定义"

print("✅ 所有 Jobs 和 Schedules 定义正确")
EOF

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Jobs 定义检查失败${NC}"
    exit 1
fi
echo ""

# 测试6: 检查 Dagster 是否可以加载模块
echo -e "${BLUE}[6/6] 检查 Dagster 模块加载...${NC}"
python3 << 'EOF'
import sys
sys.path.insert(0, '.')

try:
    # 尝试导入所有定义
    from src.processing.compute.dagster import (
        crawl_a_share_reports_job,
        crawl_a_share_ipo_job,
        daily_crawl_reports_schedule,
        daily_crawl_ipo_schedule,
        manual_trigger_reports_sensor,
        manual_trigger_ipo_sensor,
    )
    
    # 验证所有对象都存在
    assert crawl_a_share_reports_job is not None, "crawl_a_share_reports_job 未定义"
    assert crawl_a_share_ipo_job is not None, "crawl_a_share_ipo_job 未定义"
    assert daily_crawl_reports_schedule is not None, "daily_crawl_reports_schedule 未定义"
    assert daily_crawl_ipo_schedule is not None, "daily_crawl_ipo_schedule 未定义"
    assert manual_trigger_reports_sensor is not None, "manual_trigger_reports_sensor 未定义"
    assert manual_trigger_ipo_sensor is not None, "manual_trigger_ipo_sensor 未定义"
    
    # 尝试创建 Definitions（Dagster 会验证所有定义）
    from dagster import Definitions
    defs = Definitions(
        jobs=[crawl_a_share_reports_job, crawl_a_share_ipo_job],
        schedules=[daily_crawl_reports_schedule, daily_crawl_ipo_schedule],
        sensors=[manual_trigger_reports_sensor, manual_trigger_ipo_sensor],
    )
    
    print("✅ Dagster 模块加载成功")
    print(f"   Jobs: 2")
    print(f"   Schedules: 2")
    print(f"   Sensors: 2")
    print("   ✅ 所有定义验证通过")
except Exception as e:
    print(f"❌ Dagster 模块加载失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Dagster 模块加载失败${NC}"
    exit 1
fi
echo ""

# 总结
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ 所有测试通过！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}下一步：${NC}"
echo "1. 启动 Dagster UI: bash scripts/start_dagster.sh"
echo "2. 访问 http://localhost:3000"
echo "3. 手动触发任务进行测试"
echo ""
