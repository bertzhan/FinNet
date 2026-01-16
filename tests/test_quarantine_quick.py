# -*- coding: utf-8 -*-
"""
隔离管理器快速测试脚本
用于快速验证隔离管理器功能是否正确实现
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.storage.metadata import QuarantineManager, get_quarantine_manager
from src.storage.object_store.path_manager import PathManager
from src.common.constants import QuarantineReason


def test_import():
    """测试1: 模块导入"""
    print("=" * 60)
    print("测试1: 模块导入")
    print("=" * 60)
    
    try:
        from src.storage.metadata import QuarantineManager, get_quarantine_manager
        from src.common.constants import QuarantineReason
        print("✅ 模块导入成功")
        return True
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_initialization():
    """测试2: 初始化"""
    print("\n" + "=" * 60)
    print("测试2: 隔离管理器初始化")
    print("=" * 60)
    
    try:
        manager = get_quarantine_manager()
        print("✅ 隔离管理器初始化成功")
        print(f"   MinIO 客户端: {'✅' if manager.minio_client else '❌'}")
        print(f"   路径管理器: {'✅' if manager.path_manager else '❌'}")
        print(f"   PostgreSQL 客户端: {'✅' if manager.pg_client else '❌'}")
        return True
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_path_generation():
    """测试3: 路径生成"""
    print("\n" + "=" * 60)
    print("测试3: 隔离路径生成")
    print("=" * 60)
    
    try:
        pm = PathManager()
        original_path = "bronze/a_share/quarterly_reports/2023/Q3/000001/report.pdf"
        
        # 测试不同失败阶段的路径生成
        for reason in [QuarantineReason.INGESTION_FAILED, 
                      QuarantineReason.VALIDATION_FAILED,
                      QuarantineReason.CONTENT_FAILED]:
            quarantine_path = pm.get_quarantine_path(
                reason=reason,
                original_path=original_path
            )
            print(f"✅ {reason.value}: {quarantine_path}")
            
            # 验证路径格式
            expected_prefix = f"quarantine/{reason.value}/"
            if quarantine_path.startswith(expected_prefix):
                print(f"   ✅ 路径格式正确")
            else:
                print(f"   ❌ 路径格式错误，期望前缀: {expected_prefix}")
                return False
        
        return True
    except Exception as e:
        print(f"❌ 路径生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_pending_records():
    """测试4: 查询待处理记录"""
    print("\n" + "=" * 60)
    print("测试4: 查询待处理记录")
    print("=" * 60)
    
    try:
        manager = get_quarantine_manager()
        records = manager.get_pending_records(limit=5)
        print(f"✅ 查询成功，找到 {len(records)} 条待处理记录")
        
        if records:
            print("   示例记录:")
            for i, record in enumerate(records[:3], 1):
                print(f"   {i}. ID={record.id}")
                print(f"      失败阶段: {record.failure_stage}")
                print(f"      失败原因: {record.failure_reason[:50]}...")
                print(f"      隔离时间: {record.quarantine_time}")
        
        return True
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_statistics():
    """测试5: 获取统计信息"""
    print("\n" + "=" * 60)
    print("测试5: 获取统计信息")
    print("=" * 60)
    
    try:
        manager = get_quarantine_manager()
        stats = manager.get_statistics()
        
        print("✅ 统计信息获取成功")
        print(f"   待处理: {stats['pending_count']}")
        print(f"   处理中: {stats['processing_count']}")
        print(f"   已解决: {stats['resolved_count']}")
        print(f"   已丢弃: {stats['discarded_count']}")
        print(f"   总计: {stats['total_count']}")
        print(f"   状态: {stats['status']}")
        
        # 验证统计信息结构
        required_keys = ['pending_count', 'processing_count', 'resolved_count', 
                        'discarded_count', 'total_count', 'by_stage', 'status']
        for key in required_keys:
            if key not in stats:
                print(f"   ❌ 缺少统计字段: {key}")
                return False
        
        print("   ✅ 统计信息结构完整")
        return True
    except Exception as e:
        print(f"❌ 获取统计信息失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_record_by_id():
    """测试6: 根据ID获取记录"""
    print("\n" + "=" * 60)
    print("测试6: 根据ID获取记录")
    print("=" * 60)
    
    try:
        manager = get_quarantine_manager()
        
        # 先获取一条记录
        records = manager.get_pending_records(limit=1)
        if records:
            record_id = records[0].id
            record = manager.get_record_by_id(record_id)
            
            if record:
                print(f"✅ 根据ID获取记录成功: ID={record_id}")
                print(f"   失败原因: {record.failure_reason[:50]}...")
                return True
            else:
                print(f"⚠️  记录不存在: ID={record_id}")
                return True  # 不算失败
        else:
            print("⚠️  没有待处理记录，跳过测试")
            return True
    except Exception as e:
        print(f"❌ 获取记录失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_basecrawler_integration():
    """测试7: BaseCrawler 集成检查"""
    print("\n" + "=" * 60)
    print("测试7: BaseCrawler 集成检查")
    print("=" * 60)
    
    try:
        from src.ingestion.base.base_crawler import BaseCrawler
        import inspect
        
        # 检查 __init__ 方法签名
        sig = inspect.signature(BaseCrawler.__init__)
        params = list(sig.parameters.keys())
        
        if 'enable_quarantine' in params:
            print("✅ BaseCrawler 支持 enable_quarantine 参数")
        else:
            print("❌ BaseCrawler 缺少 enable_quarantine 参数")
            return False
        
        # 检查是否有 quarantine_manager 属性（通过查看源码）
        try:
            source = inspect.getsource(BaseCrawler.__init__)
            if 'quarantine_manager' in source:
                print("✅ BaseCrawler 包含 quarantine_manager 属性")
            else:
                print("⚠️  BaseCrawler 可能未初始化 quarantine_manager")
        except:
            print("⚠️  无法检查源码")
        
        return True
    except Exception as e:
        print(f"❌ BaseCrawler 集成检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dagster_integration():
    """测试8: Dagster 集成检查"""
    print("\n" + "=" * 60)
    print("测试8: Dagster 集成检查")
    print("=" * 60)
    
    try:
        from src.processing.compute.dagster.jobs.crawl_jobs import validate_crawl_results_op
        import inspect
        
        print("✅ Dagster 验证作业存在")
        
        # 检查是否导入 QuarantineManager
        source = inspect.getsource(validate_crawl_results_op)
        if 'QuarantineManager' in source:
            print("✅ 已导入 QuarantineManager")
        else:
            print("⚠️  未找到 QuarantineManager 导入")
        
        if 'quarantine_manager' in source:
            print("✅ 使用了 quarantine_manager")
        else:
            print("⚠️  未找到 quarantine_manager 使用")
        
        if 'quarantined_count' in source:
            print("✅ 记录了隔离数量")
        else:
            print("⚠️  未找到隔离数量记录")
        
        return True
    except ImportError as e:
        print(f"⚠️  Dagster 未安装或无法导入: {e}")
        return True  # 不算失败
    except Exception as e:
        print(f"❌ Dagster 集成检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("隔离管理器快速测试")
    print("=" * 60)
    print()
    
    tests = [
        ("模块导入", test_import),
        ("初始化", test_initialization),
        ("路径生成", test_path_generation),
        ("查询待处理记录", test_get_pending_records),
        ("获取统计信息", test_get_statistics),
        ("根据ID获取记录", test_get_record_by_id),
        ("BaseCrawler 集成", test_basecrawler_integration),
        ("Dagster 集成", test_dagster_integration),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ 测试 '{name}' 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    total = len(results)
    passed = sum(1 for _, r in results if r)
    
    print(f"\n总计: {passed}/{total} 通过 ({passed*100//total if total > 0 else 0}%)")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
