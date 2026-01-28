# -*- coding: utf-8 -*-
"""
清空 Neo4j 数据库脚本

使用方法:
    # 查看当前数据量（不删除）
    python scripts/clear_neo4j.py --stats
    
    # 清空所有数据（需要确认）
    python scripts/clear_neo4j.py --clear --confirm
    
    # 删除特定标签的节点
    python scripts/clear_neo4j.py --clear --label Document --confirm
    
    # 删除特定股票代码的数据
    python scripts/clear_neo4j.py --clear --stock-code 000002 --confirm
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.storage.graph.neo4j_client import get_neo4j_client
from src.common.logger import get_logger

logger = get_logger(__name__)


def show_stats():
    """显示当前数据统计"""
    client = get_neo4j_client()
    
    # 统计节点
    total_nodes = client.get_node_count()
    company_nodes = client.get_node_count("Company")
    document_nodes = client.get_node_count("Document")
    chunk_nodes = client.get_node_count("Chunk")
    
    # 统计关系
    total_rels = client.get_relationship_count()
    has_document_rels = client.get_relationship_count("HAS_DOCUMENT")
    belongs_to_rels = client.get_relationship_count("BELONGS_TO")
    has_child_rels = client.get_relationship_count("HAS_CHILD")
    
    print("\n" + "="*60)
    print("📊 Neo4j 数据统计")
    print("="*60)
    print(f"节点总数: {total_nodes:,}")
    print(f"  - Company 节点: {company_nodes:,}")
    print(f"  - Document 节点: {document_nodes:,}")
    print(f"  - Chunk 节点: {chunk_nodes:,}")
    print(f"\n关系总数: {total_rels:,}")
    print(f"  - HAS_DOCUMENT 关系: {has_document_rels:,}")
    print(f"  - BELONGS_TO 关系: {belongs_to_rels:,}")
    print(f"  - HAS_CHILD 关系: {has_child_rels:,}")
    print("="*60 + "\n")
    
    return {
        'total_nodes': total_nodes,
        'company_nodes': company_nodes,
        'document_nodes': document_nodes,
        'chunk_nodes': chunk_nodes,
        'total_rels': total_rels,
        'has_document_rels': has_document_rels,
        'belongs_to_rels': belongs_to_rels,
        'has_child_rels': has_child_rels
    }


def clear_all(confirm: bool = False):
    """
    清空 Neo4j 数据库中的所有数据
    
    Args:
        confirm: 是否确认删除（安全措施）
    """
    if not confirm:
        logger.error("⚠️  请使用 --confirm 参数以确认删除操作")
        print("\n❌ 删除操作需要确认！请添加 --confirm 参数")
        return False
    
    client = get_neo4j_client()
    
    # 先查看当前数据量
    stats = show_stats()
    
    if stats['total_nodes'] == 0:
        print("✅ 数据库已经是空的，无需删除")
        return True
    
    # 确认删除
    print("\n⚠️  警告：此操作将删除所有数据，且不可恢复！")
    print(f"即将删除: {stats['total_nodes']:,} 个节点, {stats['total_rels']:,} 个关系")
    
    # 删除所有数据
    logger.info("开始清空 Neo4j 数据库...")
    result = client.reset_schema()
    
    if result.get('success'):
        print(f"\n✅ 删除完成！")
        print(f"   - 节点: {result.get('nodes_deleted', 0):,}")
        print(f"   - 关系: {result.get('relationships_deleted', 0):,}")
        print(f"   - 约束: {result.get('constraints_deleted', 0):,}")
        print(f"   - 索引: {result.get('indexes_deleted', 0):,}")
        logger.info(f"清空完成: {result}")
        return True
    else:
        print(f"\n❌ 删除失败: {result.get('error_message', '未知错误')}")
        logger.error(f"删除失败: {result}")
        return False


def clear_by_label(label: str, confirm: bool = False):
    """
    删除特定标签的所有节点
    
    Args:
        label: 节点标签（如 "Document", "Chunk"）
        confirm: 是否确认删除
    """
    if not confirm:
        logger.error("⚠️  请使用 --confirm 参数以确认删除操作")
        print("\n❌ 删除操作需要确认！请添加 --confirm 参数")
        return False
    
    client = get_neo4j_client()
    
    # 先统计
    count = client.get_node_count(label)
    if count == 0:
        print(f"✅ 标签 '{label}' 没有节点，无需删除")
        return True
    
    print(f"\n⚠️  警告：即将删除 {count:,} 个 '{label}' 节点及其所有关系")
    
    # 删除节点（DETACH DELETE 会同时删除关系）
    query = f"MATCH (n:{label}) DETACH DELETE n RETURN count(n) as deleted"
    
    try:
        results = client.execute_write(query)
        deleted = results[0].get('deleted', 0) if results else 0
        print(f"\n✅ 删除完成！已删除 {deleted:,} 个 '{label}' 节点")
        logger.info(f"删除 {label} 节点完成: {deleted}")
        return True
    except Exception as e:
        print(f"\n❌ 删除失败: {e}")
        logger.error(f"删除 {label} 节点失败: {e}")
        return False


def clear_by_stock_code(stock_code: str, confirm: bool = False):
    """
    删除特定股票代码的所有数据
    
    Args:
        stock_code: 股票代码（如 "000002"）
        confirm: 是否确认删除
    """
    if not confirm:
        logger.error("⚠️  请使用 --confirm 参数以确认删除操作")
        print("\n❌ 删除操作需要确认！请添加 --confirm 参数")
        return False
    
    client = get_neo4j_client()
    
    # 先统计
    query_count = """
        MATCH (d:Document {stock_code: $code})
        OPTIONAL MATCH (d)-[*]->(c:Chunk)
        RETURN count(DISTINCT d) as doc_count, count(DISTINCT c) as chunk_count
    """
    results = client.execute_query(query_count, parameters={"code": stock_code})
    
    if results:
        doc_count = results[0].get('doc_count', 0)
        chunk_count = results[0].get('chunk_count', 0)
        
        if doc_count == 0:
            print(f"✅ 股票代码 '{stock_code}' 没有数据，无需删除")
            return True
        
        print(f"\n⚠️  警告：即将删除股票代码 '{stock_code}' 的数据")
        print(f"   - Document 节点: {doc_count:,}")
        print(f"   - Chunk 节点: {chunk_count:,}")
    
    # 删除（先删除 Document，会自动删除相关的 Chunk 和关系）
    query_delete = """
        MATCH (d:Document {stock_code: $code})
        DETACH DELETE d
        RETURN count(d) as deleted
    """
    
    try:
        results = client.execute_write(query_delete, parameters={"code": stock_code})
        deleted = results[0].get('deleted', 0) if results else 0
        print(f"\n✅ 删除完成！已删除股票代码 '{stock_code}' 的 {deleted:,} 个文档及其相关数据")
        logger.info(f"删除股票代码 {stock_code} 完成: {deleted}")
        return True
    except Exception as e:
        print(f"\n❌ 删除失败: {e}")
        logger.error(f"删除股票代码 {stock_code} 失败: {e}")
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Neo4j 数据管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 查看数据统计
  python scripts/clear_neo4j.py --stats
  
  # 清空所有数据
  python scripts/clear_neo4j.py --clear --confirm
  
  # 删除特定标签的节点
  python scripts/clear_neo4j.py --clear --label Document --confirm
  
  # 删除特定股票代码的数据
  python scripts/clear_neo4j.py --clear --stock-code 000002 --confirm
        """
    )
    
    parser.add_argument(
        "--stats",
        action="store_true",
        help="显示数据统计（不删除）"
    )
    
    parser.add_argument(
        "--clear",
        action="store_true",
        help="执行删除操作"
    )
    
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="确认删除操作（必须与 --clear 一起使用）"
    )
    
    parser.add_argument(
        "--label",
        type=str,
        help="删除特定标签的节点（如 Document, Chunk）"
    )
    
    parser.add_argument(
        "--stock-code",
        type=str,
        help="删除特定股票代码的数据（如 000002）"
    )
    
    args = parser.parse_args()
    
    # 如果没有参数，显示帮助
    if not args.stats and not args.clear:
        parser.print_help()
        return
    
    # 显示统计
    if args.stats:
        show_stats()
        return
    
    # 执行删除操作
    if args.clear:
        if args.label:
            clear_by_label(args.label, confirm=args.confirm)
        elif args.stock_code:
            clear_by_stock_code(args.stock_code, confirm=args.confirm)
        else:
            clear_all(confirm=args.confirm)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  操作已取消")
        sys.exit(1)
    except Exception as e:
        logger.error(f"脚本执行失败: {e}", exc_info=True)
        print(f"\n❌ 错误: {e}")
        sys.exit(1)
