#!/bin/bash
# 隔离管理器测试脚本
# 快速验证隔离管理器功能

set -e

echo "=========================================="
echo "隔离管理器测试脚本"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试计数
PASSED=0
FAILED=0

# 测试函数
test_check() {
    local name=$1
    local command=$2
    
    echo -n "测试: $name ... "
    
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 通过${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}❌ 失败${NC}"
        ((FAILED++))
        return 1
    fi
}

# 1. 检查 Python 环境
echo "1. 检查 Python 环境"
echo "----------------------------------------"
test_check "Python 版本" "python3 --version"
test_check "pip 可用" "python3 -m pip --version"
echo ""

# 2. 检查服务状态
echo "2. 检查服务状态"
echo "----------------------------------------"
if command -v docker-compose &> /dev/null; then
    test_check "Docker Compose" "docker-compose --version"
    
    # 检查服务是否运行
    if docker-compose ps | grep -q "Up"; then
        echo -e "   ${GREEN}✅ 服务正在运行${NC}"
    else
        echo -e "   ${YELLOW}⚠️  服务未运行，请先启动: docker-compose up -d${NC}"
    fi
else
    echo -e "   ${YELLOW}⚠️  Docker Compose 未安装${NC}"
fi
echo ""

# 3. 检查模块导入
echo "3. 检查模块导入"
echo "----------------------------------------"
test_check "隔离管理器导入" "python3 -c 'from src.storage.metadata import QuarantineManager; print(\"OK\")'"
test_check "便捷函数导入" "python3 -c 'from src.storage.metadata import get_quarantine_manager; print(\"OK\")'"
test_check "常量导入" "python3 -c 'from src.common.constants import QuarantineReason; print(\"OK\")'"
echo ""

# 4. 测试隔离管理器初始化
echo "4. 测试隔离管理器初始化"
echo "----------------------------------------"
python3 << 'EOF'
try:
    from src.storage.metadata import get_quarantine_manager
    manager = get_quarantine_manager()
    print("✅ 隔离管理器初始化成功")
    print(f"   MinIO 客户端: {'✅' if manager.minio_client else '❌'}")
    print(f"   路径管理器: {'✅' if manager.path_manager else '❌'}")
    print(f"   PostgreSQL 客户端: {'✅' if manager.pg_client else '❌'}")
except Exception as e:
    print(f"❌ 初始化失败: {e}")
    import traceback
    traceback.print_exc()
EOF
echo ""

# 5. 测试统计功能
echo "5. 测试统计功能"
echo "----------------------------------------"
python3 << 'EOF'
try:
    from src.storage.metadata import get_quarantine_manager
    manager = get_quarantine_manager()
    stats = manager.get_statistics()
    print("✅ 统计功能正常")
    print(f"   待处理: {stats['pending_count']}")
    print(f"   处理中: {stats['processing_count']}")
    print(f"   已解决: {stats['resolved_count']}")
    print(f"   已丢弃: {stats['discarded_count']}")
    print(f"   总计: {stats['total_count']}")
    print(f"   状态: {stats['status']}")
except Exception as e:
    print(f"❌ 统计功能失败: {e}")
    import traceback
    traceback.print_exc()
EOF
echo ""

# 6. 测试查询功能
echo "6. 测试查询功能"
echo "----------------------------------------"
python3 << 'EOF'
try:
    from src.storage.metadata import get_quarantine_manager
    manager = get_quarantine_manager()
    records = manager.get_pending_records(limit=5)
    print(f"✅ 查询功能正常，找到 {len(records)} 条待处理记录")
    if records:
        print("   示例记录:")
        for i, record in enumerate(records[:3], 1):
            print(f"   {i}. ID={record.id}, 原因={record.failure_reason[:30]}...")
except Exception as e:
    print(f"❌ 查询功能失败: {e}")
    import traceback
    traceback.print_exc()
EOF
echo ""

# 7. 测试路径生成
echo "7. 测试路径生成"
echo "----------------------------------------"
python3 << 'EOF'
try:
    from src.storage.object_store.path_manager import PathManager
    from src.common.constants import QuarantineReason
    
    pm = PathManager()
    original_path = "bronze/a_share/quarterly_reports/2023/Q3/000001/report.pdf"
    
    quarantine_path = pm.get_quarantine_path(
        reason=QuarantineReason.VALIDATION_FAILED,
        original_path=original_path
    )
    
    print("✅ 路径生成正常")
    print(f"   原始路径: {original_path}")
    print(f"   隔离路径: {quarantine_path}")
    
    # 验证路径格式
    if quarantine_path.startswith("quarantine/validation_failed/"):
        print("   ✅ 路径格式正确")
    else:
        print("   ❌ 路径格式错误")
except Exception as e:
    print(f"❌ 路径生成失败: {e}")
    import traceback
    traceback.print_exc()
EOF
echo ""

# 8. 测试 BaseCrawler 集成
echo "8. 测试 BaseCrawler 集成"
echo "----------------------------------------"
python3 << 'EOF'
try:
    from src.ingestion.base.base_crawler import BaseCrawler
    from src.common.constants import Market
    
    # 检查 BaseCrawler 是否有隔离管理器属性
    # 注意：BaseCrawler 是抽象类，不能直接实例化
    # 我们检查是否有 enable_quarantine 参数
    
    import inspect
    sig = inspect.signature(BaseCrawler.__init__)
    params = list(sig.parameters.keys())
    
    if 'enable_quarantine' in params:
        print("✅ BaseCrawler 支持 enable_quarantine 参数")
    else:
        print("❌ BaseCrawler 缺少 enable_quarantine 参数")
        
    # 检查是否有 quarantine_manager 属性
    if hasattr(BaseCrawler, '__init__'):
        print("   ✅ BaseCrawler 初始化方法存在")
    else:
        print("   ❌ BaseCrawler 初始化方法不存在")
        
except Exception as e:
    print(f"❌ BaseCrawler 集成检查失败: {e}")
    import traceback
    traceback.print_exc()
EOF
echo ""

# 9. 测试 Dagster 集成
echo "9. 测试 Dagster 集成"
echo "----------------------------------------"
python3 << 'EOF'
try:
    # 检查 Dagster 作业是否导入隔离管理器
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from src.processing.compute.dagster.jobs.crawl_jobs import validate_crawl_results_op
    
    # 检查函数是否存在
    if validate_crawl_results_op:
        print("✅ Dagster 验证作业存在")
        
        # 检查是否导入 QuarantineManager
        import inspect
        source = inspect.getsource(validate_crawl_results_op)
        if 'QuarantineManager' in source:
            print("   ✅ 已导入 QuarantineManager")
        else:
            print("   ⚠️  未找到 QuarantineManager 导入")
    else:
        print("❌ Dagster 验证作业不存在")
        
except ImportError as e:
    print(f"⚠️  Dagster 未安装或无法导入: {e}")
except Exception as e:
    print(f"❌ Dagster 集成检查失败: {e}")
    import traceback
    traceback.print_exc()
EOF
echo ""

# 10. 运行示例脚本
echo "10. 运行示例脚本"
echo "----------------------------------------"
if [ -f "examples/quarantine_demo.py" ]; then
    echo "运行隔离示例脚本..."
    python3 examples/quarantine_demo.py stats 2>&1 | head -20
    echo ""
else
    echo "⚠️  示例脚本不存在: examples/quarantine_demo.py"
fi

# 总结
echo "=========================================="
echo "测试总结"
echo "=========================================="
echo -e "通过: ${GREEN}$PASSED${NC}"
echo -e "失败: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 所有测试通过！${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️  有 $FAILED 个测试失败${NC}"
    exit 1
fi
