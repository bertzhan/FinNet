#!/bin/bash

# Dagster 代码语法检查脚本
# 不依赖 Dagster 安装，只检查代码结构

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Dagster 代码语法检查${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 获取项目根目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

# 设置 PYTHONPATH
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# 测试1: 检查 Python 语法
echo -e "${BLUE}[1/4] 检查 Python 语法...${NC}"
python3 -m py_compile src/processing/compute/dagster/jobs/crawl_jobs.py 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ crawl_jobs.py 语法正确${NC}"
else
    echo -e "${RED}❌ crawl_jobs.py 语法错误${NC}"
    exit 1
fi

python3 -m py_compile src/processing/compute/dagster/jobs/__init__.py 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ jobs/__init__.py 语法正确${NC}"
else
    echo -e "${RED}❌ jobs/__init__.py 语法错误${NC}"
    exit 1
fi

python3 -m py_compile src/processing/compute/dagster/__init__.py 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ dagster/__init__.py 语法正确${NC}"
else
    echo -e "${RED}❌ dagster/__init__.py 语法错误${NC}"
    exit 1
fi
echo ""

# 测试2: 检查导入的模块是否存在
echo -e "${BLUE}[2/4] 检查导入的模块...${NC}"
python3 << 'EOF'
import sys
sys.path.insert(0, '.')

# 检查爬虫模块
try:
    from src.ingestion.a_share import ReportCrawler, CninfoIPOProspectusCrawler
    print("✅ 爬虫模块导入成功")
except ImportError as e:
    print(f"❌ 爬虫模块导入失败: {e}")
    sys.exit(1)

# 检查基础模块
try:
    from src.ingestion.base.base_crawler import CrawlTask, CrawlResult
    from src.common.constants import Market, DocType
    from src.common.config import common_config
    print("✅ 基础模块导入成功")
except ImportError as e:
    print(f"❌ 基础模块导入失败: {e}")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    exit 1
fi
echo ""

# 测试3: 检查代码结构（不实际导入Dagster）
echo -e "${BLUE}[3/4] 检查代码结构...${NC}"
python3 << 'EOF'
import sys
import ast
sys.path.insert(0, '.')

def check_file_structure(filepath):
    """检查文件结构"""
    with open(filepath, 'r', encoding='utf-8') as f:
        code = f.read()
    
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        print(f"❌ 语法错误: {e}")
        return False
    
    # 检查是否有必要的函数和类定义
    functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    
    print(f"   函数: {len(functions)} 个")
    print(f"   类: {len(classes)} 个")
    
    # 检查关键函数是否存在
    required_functions = [
        'crawl_a_share_reports_op',
        'crawl_a_share_ipo_op',
        'validate_crawl_results_op',
        'crawl_a_share_reports_job',
        'crawl_a_share_ipo_job',
    ]
    
    missing = [f for f in required_functions if f not in functions]
    if missing:
        print(f"⚠️  缺少函数: {missing}")
    else:
        print("✅ 所有关键函数都存在")
    
    return True

# 检查主文件
if check_file_structure('src/processing/compute/dagster/jobs/crawl_jobs.py'):
    print("✅ crawl_jobs.py 结构检查通过")
else:
    print("❌ crawl_jobs.py 结构检查失败")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    exit 1
fi
echo ""

# 测试4: 检查文件是否存在
echo -e "${BLUE}[4/4] 检查文件完整性...${NC}"
files=(
    "src/processing/compute/dagster/__init__.py"
    "src/processing/compute/dagster/jobs/__init__.py"
    "src/processing/compute/dagster/jobs/crawl_jobs.py"
    "scripts/start_dagster.sh"
    "docs/DAGSTER_INTEGRATION.md"
    "docs/DAGSTER_QUICKSTART.md"
)

all_exist=true
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅ $file${NC}"
    else
        echo -e "${RED}❌ $file 不存在${NC}"
        all_exist=false
    fi
done

if [ "$all_exist" = false ]; then
    exit 1
fi
echo ""

# 总结
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ 代码结构检查通过！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}注意：${NC}"
echo "由于网络限制，无法安装和测试 Dagster。"
echo "请手动安装 Dagster 后运行完整测试："
echo ""
echo "  1. pip install dagster dagster-webserver"
echo "  2. bash scripts/test_dagster_integration.sh"
echo "  3. bash scripts/start_dagster.sh"
echo ""
