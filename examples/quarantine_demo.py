# -*- coding: utf-8 -*-
"""
隔离区管理使用示例
演示如何使用 QuarantineManager 进行数据隔离和管理
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.storage.metadata import QuarantineManager, get_quarantine_manager
from src.common.constants import QuarantineReason


def demo_quarantine_document():
    """示例1：隔离验证失败的文档"""
    print("=" * 60)
    print("示例1：隔离验证失败的文档")
    print("=" * 60)
    
    manager = QuarantineManager()
    
    # 模拟一个验证失败的文档
    record = manager.quarantine_document(
        document_id=123,  # 可选，如果文档还未入库则为 None
        source_type="a_share",
        doc_type="quarterly_report",
        original_path="bronze/a_share/quarterly_reports/2023/Q3/000001/report.pdf",
        failure_stage="validation_failed",
        failure_reason="文件大小异常（小于1KB）",
        failure_details="文件大小: 512 bytes，小于最小阈值 1024 bytes",
        extra_metadata={
            "validation_rule": "min_file_size",
            "threshold": 1024,
            "actual_size": 512
        }
    )
    
    print(f"✅ 隔离记录已创建:")
    print(f"  - ID: {record.id}")
    print(f"  - 隔离路径: {record.quarantine_path}")
    print(f"  - 失败原因: {record.failure_reason}")
    print(f"  - 状态: {record.status}")
    print()


def demo_get_pending_records():
    """示例2：查询待处理的隔离记录"""
    print("=" * 60)
    print("示例2：查询待处理的隔离记录")
    print("=" * 60)
    
    manager = get_quarantine_manager()
    
    # 查询所有待处理记录
    records = manager.get_pending_records(limit=10)
    print(f"待处理记录数: {len(records)}")
    
    for record in records:
        print(f"  - ID: {record.id}")
        print(f"    失败阶段: {record.failure_stage}")
        print(f"    失败原因: {record.failure_reason}")
        print(f"    隔离时间: {record.quarantine_time}")
        print()
    
    # 按失败阶段过滤
    validation_failed = manager.get_pending_records(
        limit=10,
        failure_stage="validation_failed"
    )
    print(f"入湖验证失败记录数: {len(validation_failed)}")
    print()


def demo_resolve_record():
    """示例3：处理隔离记录"""
    print("=" * 60)
    print("示例3：处理隔离记录")
    print("=" * 60)
    
    manager = get_quarantine_manager()
    
    # 先获取一条待处理记录
    records = manager.get_pending_records(limit=1)
    if not records:
        print("⚠️ 没有待处理的隔离记录")
        return
    
    record = records[0]
    print(f"处理记录 ID: {record.id}")
    print(f"失败原因: {record.failure_reason}")
    print()
    
    # 方式1：修复后重新入库
    print("方式1：修复后重新入库")
    try:
        resolved = manager.resolve_record(
            record_id=record.id,
            resolution="文件已修复，重新验证通过",
            handler="admin",
            action="restore"
        )
        print(f"✅ 记录已处理: status={resolved.status}")
    except Exception as e:
        print(f"❌ 处理失败: {e}")
    
    print()
    
    # 方式2：重新采集（需要先有一条新的待处理记录）
    records = manager.get_pending_records(limit=1)
    if records:
        record = records[0]
        print("方式2：重新采集")
        try:
            resolved = manager.resolve_record(
                record_id=record.id,
                resolution="删除记录，重新触发爬取",
                handler="admin",
                action="re_crawl"
            )
            print(f"✅ 记录已处理: status={resolved.status}")
        except Exception as e:
            print(f"❌ 处理失败: {e}")
    
    print()
    
    # 方式3：永久丢弃
    records = manager.get_pending_records(limit=1)
    if records:
        record = records[0]
        print("方式3：永久丢弃")
        try:
            resolved = manager.resolve_record(
                record_id=record.id,
                resolution="数据源错误，无法修复",
                handler="admin",
                action="discard"
            )
            print(f"✅ 记录已处理: status={resolved.status}")
        except Exception as e:
            print(f"❌ 处理失败: {e}")
    
    print()


def demo_get_statistics():
    """示例4：获取隔离区统计信息"""
    print("=" * 60)
    print("示例4：获取隔离区统计信息")
    print("=" * 60)
    
    manager = get_quarantine_manager()
    
    stats = manager.get_statistics()
    
    print(f"📊 隔离区统计:")
    print(f"  - 待处理: {stats['pending_count']}")
    print(f"  - 处理中: {stats['processing_count']}")
    print(f"  - 已解决: {stats['resolved_count']}")
    print(f"  - 已丢弃: {stats['discarded_count']}")
    print(f"  - 总计: {stats['total_count']}")
    print()
    print(f"📈 按失败阶段统计:")
    for stage, count in stats['by_stage'].items():
        print(f"  - {stage}: {count}")
    print()
    print(f"⚠️ 状态: {stats['status']}")
    if stats['pending_count'] > stats['alert_threshold']:
        print(f"  ⚠️ 警告：待处理记录超过阈值 ({stats['alert_threshold']})")
    print()


def demo_get_record_details():
    """示例5：获取隔离记录详情"""
    print("=" * 60)
    print("示例5：获取隔离记录详情")
    print("=" * 60)
    
    manager = get_quarantine_manager()
    
    # 先获取一条记录
    records = manager.get_pending_records(limit=1)
    if not records:
        print("⚠️ 没有待处理的隔离记录")
        return
    
    record_id = records[0].id
    
    # 根据ID获取详情
    record = manager.get_record_by_id(record_id)
    if record:
        print(f"📋 隔离记录详情:")
        print(f"  - ID: {record.id}")
        print(f"  - 文档ID: {record.document_id}")
        print(f"  - 数据来源: {record.source_type}")
        print(f"  - 文档类型: {record.doc_type}")
        print(f"  - 原始路径: {record.original_path}")
        print(f"  - 隔离路径: {record.quarantine_path}")
        print(f"  - 失败阶段: {record.failure_stage}")
        print(f"  - 失败原因: {record.failure_reason}")
        print(f"  - 详细错误: {record.failure_details}")
        print(f"  - 状态: {record.status}")
        print(f"  - 处理人: {record.handler}")
        print(f"  - 处理结果: {record.resolution}")
        print(f"  - 隔离时间: {record.quarantine_time}")
        print(f"  - 处理时间: {record.resolution_time}")
        print(f"  - 元数据: {record.extra_metadata}")
    else:
        print(f"❌ 记录不存在: id={record_id}")
    
    print()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    else:
        mode = "all"
    
    if mode == "quarantine" or mode == "all":
        demo_quarantine_document()
    
    if mode == "list" or mode == "all":
        demo_get_pending_records()
    
    if mode == "resolve" or mode == "all":
        demo_resolve_record()
    
    if mode == "stats" or mode == "all":
        demo_get_statistics()
    
    if mode == "details" or mode == "all":
        demo_get_record_details()
    
    print("=" * 60)
    print("示例运行完成")
    print("=" * 60)
