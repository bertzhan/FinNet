# -*- coding: utf-8 -*-
"""
Neo4j 图结构迁移脚本

将图结构从两层（Document -> Chunk）迁移到三层（Company -> Document -> Chunk）

使用方法:
    # 查看当前数据统计
    python scripts/migrate_neo4j_graph.py --stats
    
    # 试运行（不实际执行）
    python scripts/migrate_neo4j_graph.py --dry-run
    
    # 执行迁移（方案1：清空重建）
    python scripts/migrate_neo4j_graph.py --clear-rebuild
    
    # 执行迁移（方案2：数据迁移，保留现有数据）
    python scripts/migrate_neo4j_graph.py --migrate-data
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
    print("📊 Neo4j 当前数据统计")
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
    
    # 判断是否需要迁移
    if company_nodes == 0 and document_nodes > 0:
        print("⚠️  检测到旧图结构（缺少 Company 节点），需要迁移")
        return True
    elif company_nodes > 0:
        print("✅ 图结构已是最新版本（包含 Company 节点）")
        return False
    else:
        print("ℹ️  数据库为空，无需迁移")
        return False


def migrate_data(dry_run: bool = False):
    """
    方案2：数据迁移（保留现有数据）
    从现有 Document 节点提取 stock_code，创建 Company 节点和关系
    
    Args:
        dry_run: 是否试运行
    """
    client = get_neo4j_client()
    
    print("\n" + "="*60)
    print("🔄 方案2：数据迁移（保留现有数据）")
    print("="*60)
    
    if dry_run:
        print("⚠️  试运行模式：不会实际执行操作")
        print("")
    
    # 1. 查询所有 Document 节点，提取唯一的 stock_code
    print("步骤 1/3: 查询所有 Document 节点...")
    query_docs = """
    MATCH (d:Document)
    RETURN DISTINCT d.stock_code as stock_code, d.company_name as company_name
    """
    
    if not dry_run:
        results = client.execute_query(query_docs)
        companies = {}
        for record in results:
            stock_code = record.get('stock_code')
            company_name = record.get('company_name')
            if stock_code:
                companies[stock_code] = company_name or stock_code
        
        print(f"  找到 {len(companies)} 个唯一的股票代码")
        
        # 2. 创建 Company 节点
        print("\n步骤 2/3: 创建 Company 节点...")
        created_companies = 0
        for stock_code, company_name in companies.items():
            query_create = """
            MERGE (c:Company {code: $code})
            ON CREATE SET c.name = $name
            ON MATCH SET c.name = $name
            RETURN c
            """
            try:
                client.execute_write(query_create, parameters={
                    "code": stock_code,
                    "name": company_name
                })
                created_companies += 1
            except Exception as e:
                logger.error(f"创建 Company 节点失败: {stock_code}, {e}")
        
        print(f"  创建/更新 {created_companies} 个 Company 节点")
        
        # 3. 创建 Company -> Document 关系
        print("\n步骤 3/3: 创建 Company -> Document 关系...")
        query_create_rels = """
        MATCH (c:Company), (d:Document {stock_code: c.code})
        MERGE (c)-[r:HAS_DOCUMENT]->(d)
        RETURN count(r) as created
        """
        
        try:
            results = client.execute_write(query_create_rels)
            created_rels = results[0].get('created', 0) if results else 0
            print(f"  创建 {created_rels} 个 HAS_DOCUMENT 关系")
        except Exception as e:
            logger.error(f"创建关系失败: {e}")
            print(f"  ❌ 创建关系失败: {e}")
    else:
        print("  [试运行] 将查询所有 Document 节点")
        print("  [试运行] 将创建 Company 节点")
        print("  [试运行] 将创建 Company -> Document 关系")
    
    print("\n✅ 数据迁移完成！")
    print("="*60 + "\n")


def clear_rebuild(dry_run: bool = False):
    """
    方案1：清空重建（简单快速）
    删除所有数据，然后重新构建图
    
    Args:
        dry_run: 是否试运行
    """
    from src.processing.graph.graph_builder import GraphBuilder
    from src.storage.metadata.postgres_client import get_postgres_client
    from src.storage.metadata.models import Document
    
    print("\n" + "="*60)
    print("🗑️  方案1：清空重建")
    print("="*60)
    
    if dry_run:
        print("⚠️  试运行模式：不会实际执行操作")
        print("")
    
    # 1. 清空 Neo4j
    print("步骤 1/3: 清空 Neo4j 数据库...")
    if not dry_run:
        client = get_neo4j_client()
        result = client.reset_schema()
        if result.get('success'):
            print(f"  ✅ 已删除 {result.get('nodes_deleted', 0):,} 个节点")
            print(f"  ✅ 已删除 {result.get('relationships_deleted', 0):,} 个关系")
        else:
            print(f"  ❌ 清空失败: {result.get('error_message')}")
            return False
    else:
        print("  [试运行] 将清空所有 Neo4j 数据")
    
    # 2. 查询需要重建的文档
    print("\n步骤 2/3: 查询需要重建的文档...")
    if not dry_run:
        pg_client = get_postgres_client()
        with pg_client.get_session() as session:
            documents = session.query(Document).all()
            document_ids = [doc.id for doc in documents]
            print(f"  找到 {len(document_ids)} 个文档需要重建")
    else:
        print("  [试运行] 将查询所有文档")
    
    # 3. 重新构建图
    print("\n步骤 3/3: 重新构建图结构...")
    if not dry_run and document_ids:
        builder = GraphBuilder()
        result = builder.build_document_chunk_graph(document_ids, batch_size=50)
        
        print(f"  ✅ 公司节点: {result.get('companies_processed', 0):,}")
        print(f"  ✅ 文档节点: {result.get('documents_processed', 0):,}")
        print(f"  ✅ 分块节点: {result.get('chunks_created', 0):,}")
        print(f"  ✅ HAS_DOCUMENT 关系: {result.get('has_document_edges_created', 0):,}")
        print(f"  ✅ BELONGS_TO 关系: {result.get('belongs_to_edges_created', 0):,}")
        print(f"  ✅ HAS_CHILD 关系: {result.get('has_child_edges_created', 0):,}")
    else:
        print("  [试运行] 将重新构建图结构")
    
    print("\n✅ 清空重建完成！")
    print("="*60 + "\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Neo4j 图结构迁移工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 查看当前数据统计
  python scripts/migrate_neo4j_graph.py --stats
  
  # 试运行（不实际执行）
  python scripts/migrate_neo4j_graph.py --clear-rebuild --dry-run
  
  # 方案1：清空重建（推荐，简单快速）
  python scripts/migrate_neo4j_graph.py --clear-rebuild
  
  # 方案2：数据迁移（保留现有数据）
  python scripts/migrate_neo4j_graph.py --migrate-data
        """
    )
    
    parser.add_argument(
        "--stats",
        action="store_true",
        help="显示数据统计"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="试运行模式（不实际执行）"
    )
    
    parser.add_argument(
        "--clear-rebuild",
        action="store_true",
        help="方案1：清空重建（简单快速）"
    )
    
    parser.add_argument(
        "--migrate-data",
        action="store_true",
        help="方案2：数据迁移（保留现有数据）"
    )
    
    args = parser.parse_args()
    
    # 如果没有参数，显示帮助
    if not any([args.stats, args.clear_rebuild, args.migrate_data]):
        parser.print_help()
        return
    
    try:
        # 显示统计
        if args.stats:
            show_stats()
            return
        
        # 检查是否需要迁移
        needs_migration = show_stats()
        
        if not needs_migration:
            print("✅ 无需迁移，图结构已是最新版本")
            return
        
        # 确认操作
        if not args.dry_run:
            print("\n⚠️  警告：此操作将修改 Neo4j 数据库！")
            confirm = input("是否继续？(yes/no): ")
            if confirm.lower() != "yes":
                print("操作已取消")
                return
        
        # 执行迁移
        if args.clear_rebuild:
            clear_rebuild(dry_run=args.dry_run)
        elif args.migrate_data:
            migrate_data(dry_run=args.dry_run)
        else:
            print("\n请选择迁移方案：")
            print("  --clear-rebuild  : 清空重建（推荐）")
            print("  --migrate-data   : 数据迁移（保留数据）")
            print("\n或使用 --dry-run 查看将执行的操作")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  操作已取消")
        sys.exit(1)
    except Exception as e:
        logger.error(f"迁移失败: {e}", exc_info=True)
        print(f"\n❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
