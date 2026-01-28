# -*- coding: utf-8 -*-
"""
图构建服务
基于 DocumentChunk 表的信息构建 Neo4j 图结构
"""

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.storage.graph.neo4j_client import get_neo4j_client, Neo4jClient
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import Document, DocumentChunk
from src.common.logger import LoggerMixin


class GraphBuilder(LoggerMixin):
    """
    图构建服务
    负责将 DocumentChunk 数据转换为 Neo4j 图结构
    """

    def __init__(self, neo4j_client: Optional[Neo4jClient] = None):
        """
        初始化图构建服务

        Args:
            neo4j_client: Neo4j 客户端（默认自动创建）
        """
        self.neo4j_client = neo4j_client or get_neo4j_client()
        self.pg_client = get_postgres_client()
        
        # 确保约束和索引存在
        self.neo4j_client.create_constraints_and_indexes()

    def build_document_chunk_graph(
        self,
        document_ids: List[uuid.UUID],
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """
        为指定文档构建图结构

        Args:
            document_ids: 文档 ID 列表
            batch_size: 每批处理的文档数量

        Returns:
            构建结果统计

        Example:
            >>> builder = GraphBuilder()
            >>> result = builder.build_document_chunk_graph([uuid.UUID("...")])
            >>> print(result['documents_processed'], result['chunks_created'])
        """
        self.logger.info(f"开始构建图结构，文档数量: {len(document_ids)}")

        total_companies = 0
        total_documents = 0
        total_chunks = 0
        total_company_document_edges = 0
        total_contains_edges = 0
        total_parent_edges = 0
        failed_documents = []
        successful_document_ids = []  # 记录成功构建图的文档ID

        # 分批处理文档
        for i in range(0, len(document_ids), batch_size):
            batch_doc_ids = document_ids[i:i + batch_size]
            self.logger.info(f"处理批次 {i//batch_size + 1}/{(len(document_ids) + batch_size - 1)//batch_size}")

            try:
                with self.pg_client.get_session() as session:
                    # 查询文档信息
                    documents = session.query(Document).filter(
                        Document.id.in_(batch_doc_ids)
                    ).all()

                    # 查询分块信息（不依赖向量化状态）
                    chunks = session.query(DocumentChunk).filter(
                        DocumentChunk.document_id.in_(batch_doc_ids)
                    ).all()

                    # 1. 构建 Company 节点（根节点）
                    company_nodes = []
                    company_codes = set()
                    for doc in documents:
                        if doc.stock_code not in company_codes:
                            company_props = {
                                'code': doc.stock_code,  # 使用 code 作为主键
                                'name': doc.company_name,
                            }
                            company_nodes.append(company_props)
                            company_codes.add(doc.stock_code)

                    # 批量创建 Company 节点
                    if company_nodes:
                        # 使用自定义查询创建 Company 节点（因为主键是 code 而不是 id）
                        for company in company_nodes:
                            query = """
                            MERGE (c:Company {code: $code})
                            ON CREATE SET c.name = $name
                            ON MATCH SET c.name = $name
                            RETURN c
                            """
                            self.neo4j_client.execute_write(query, parameters=company)
                        total_companies += len(company_nodes)
                        self.logger.debug(f"创建/更新 {len(company_nodes)} 个 Company 节点")

                    # 2. 构建文档节点
                    document_nodes = []
                    for doc in documents:
                        node_props = {
                            'id': str(doc.id),
                            'stock_code': doc.stock_code,
                            'company_name': doc.company_name,
                            'market': doc.market,
                            'doc_type': doc.doc_type,
                            'year': doc.year,
                            'quarter': doc.quarter if doc.quarter else None,
                        }
                        document_nodes.append(node_props)

                    # 批量创建文档节点
                    if document_nodes:
                        created = self.neo4j_client.batch_merge_nodes(
                            'Document',
                            document_nodes,
                            batch_size=50
                        )
                        total_documents += created

                    # 3. 创建 Company -> Document 关系
                    company_document_relationships = []
                    for doc in documents:
                        rel = {
                            'from_label': 'Company',
                            'from_id': doc.stock_code,  # Company 的主键是 code
                            'to_label': 'Document',
                            'to_id': str(doc.id),
                            'relationship_type': 'HAS_DOCUMENT',
                        }
                        company_document_relationships.append(rel)

                    # 批量创建 Company -> Document 关系
                    if company_document_relationships:
                        created = self.neo4j_client.batch_create_relationships(
                            company_document_relationships,
                            batch_size=100
                        )
                        total_company_document_edges += created
                        self.logger.debug(f"创建 {created} 个 Company -> Document 关系")

                    # 构建分块节点
                    chunk_nodes = []
                    for chunk in chunks:
                        node_props = {
                            'id': str(chunk.id),
                            'document_id': str(chunk.document_id),
                            'chunk_index': chunk.chunk_index,
                            'chunk_text': chunk.chunk_text,  # 存储分块文本内容
                            'title': chunk.title if chunk.title else None,
                            'title_level': chunk.title_level if chunk.title_level else None,
                            'chunk_size': chunk.chunk_size,
                            'is_table': chunk.is_table if chunk.is_table else False,
                        }
                        chunk_nodes.append(node_props)

                    # 批量创建分块节点
                    if chunk_nodes:
                        created = self.neo4j_client.batch_merge_nodes(
                            'Chunk',
                            chunk_nodes,
                            batch_size=100
                        )
                        total_chunks += created

                    # 构建 BELONGS_TO 边（只有顶级分块才直接连接到文档）
                    belongs_to_relationships = []
                    for chunk in chunks:
                        # 只有当分块没有父分块时（parent_chunk_id 为 None），才直接连接到文档
                        if chunk.parent_chunk_id is None:
                            rel = {
                                'from_label': 'Chunk',
                                'from_id': str(chunk.id),
                                'to_label': 'Document',
                                'to_id': str(chunk.document_id),
                                'relationship_type': 'BELONGS_TO',
                            }
                            belongs_to_relationships.append(rel)

                    # 批量创建 BELONGS_TO 边
                    if belongs_to_relationships:
                        created = self.neo4j_client.batch_create_relationships(
                            belongs_to_relationships,
                            batch_size=100
                        )
                        total_contains_edges += created

                    # 构建 HAS_CHILD 边（父分块有子分块）
                    parent_relationships = []
                    for chunk in chunks:
                        if chunk.parent_chunk_id:
                            rel = {
                                'from_label': 'Chunk',
                                'from_id': str(chunk.parent_chunk_id),
                                'to_label': 'Chunk',
                                'to_id': str(chunk.id),
                                'relationship_type': 'HAS_CHILD',
                            }
                            parent_relationships.append(rel)

                    # 批量创建 HAS_PARENT 边
                    if parent_relationships:
                        created = self.neo4j_client.batch_create_relationships(
                            parent_relationships,
                            batch_size=100
                        )
                        total_parent_edges += created

                    # 批次成功处理，记录成功构建图的文档ID
                    # 只有当文档有分块且成功构建图时才记录
                    if chunks:
                        successful_doc_ids_in_batch = set(chunk.document_id for chunk in chunks)
                        successful_document_ids.extend(list(successful_doc_ids_in_batch))

            except Exception as e:
                self.logger.error(f"处理批次失败: {e}", exc_info=True)
                failed_documents.extend([str(doc_id) for doc_id in batch_doc_ids])

        # 更新成功构建图的文档的 graphed_at 字段
        if successful_document_ids:
            try:
                with self.pg_client.get_session() as session:
                    graphed_at = datetime.now()
                    # 去重文档ID
                    unique_doc_ids = list(set(successful_document_ids))
                    
                    # 批量更新文档的 graphed_at 字段
                    updated_count = session.query(Document).filter(
                        Document.id.in_(unique_doc_ids)
                    ).update(
                        {Document.graphed_at: graphed_at},
                        synchronize_session=False
                    )
                    session.commit()
                    self.logger.info(f"更新 {updated_count} 个文档的 graphed_at 字段")
            except Exception as e:
                self.logger.error(f"更新文档 graphed_at 字段失败: {e}", exc_info=True)

        result = {
            'success': len(failed_documents) == 0,
            'companies_processed': total_companies,
            'documents_processed': total_documents,
            'chunks_created': total_chunks,
            'has_document_edges_created': total_company_document_edges,
            'belongs_to_edges_created': total_contains_edges,
            'has_child_edges_created': total_parent_edges,
            'failed_documents': failed_documents,
        }

        self.logger.info(
            f"图构建完成: 公司={total_companies}, 文档={total_documents}, 分块={total_chunks}, "
            f"HAS_DOCUMENT边={total_company_document_edges}, BELONGS_TO边={total_contains_edges}, "
            f"HAS_CHILD边={total_parent_edges}, 失败={len(failed_documents)}"
        )

        return result

    def build_chunk_hierarchy(
        self,
        chunks: List[DocumentChunk]
    ) -> int:
        """
        构建分块层级关系

        Args:
            chunks: 分块列表

        Returns:
            创建的层级边数量
        """
        parent_relationships = []
        
        for chunk in chunks:
            if chunk.parent_chunk_id:
                rel = {
                    'from_label': 'Chunk',
                    'from_id': str(chunk.id),
                    'to_label': 'Chunk',
                    'to_id': str(chunk.parent_chunk_id),
                    'relationship_type': 'HAS_PARENT',
                }
                parent_relationships.append(rel)

        if parent_relationships:
            created = self.neo4j_client.batch_create_relationships(
                parent_relationships,
                batch_size=100
            )
            return created
        
        return 0

    def upsert_document_node(self, document: Document) -> Dict[str, Any]:
        """
        创建或更新 Document 节点

        Args:
            document: Document 对象

        Returns:
            创建的节点信息
        """
        node_props = {
            'id': str(document.id),
            'stock_code': document.stock_code,
            'company_name': document.company_name,
            'market': document.market,
            'doc_type': document.doc_type,
            'year': document.year,
            'quarter': document.quarter if document.quarter else None,
        }
        
        return self.neo4j_client.merge_node('Document', node_props)

    def upsert_chunk_node(self, chunk: DocumentChunk) -> Dict[str, Any]:
        """
        创建或更新 Chunk 节点

        Args:
            chunk: DocumentChunk 对象

        Returns:
            创建的节点信息
        """
        node_props = {
            'id': str(chunk.id),
            'document_id': str(chunk.document_id),
            'chunk_index': chunk.chunk_index,
            'chunk_text': chunk.chunk_text,  # 存储分块文本内容
            'title': chunk.title if chunk.title else None,
            'title_level': chunk.title_level if chunk.title_level else None,
            'chunk_size': chunk.chunk_size,
            'is_table': chunk.is_table if chunk.is_table else False,
        }
        
        return self.neo4j_client.merge_node('Chunk', node_props)

    def create_belongs_to_edge(
        self,
        chunk_id: uuid.UUID,
        document_id: uuid.UUID
    ) -> bool:
        """
        创建 BELONGS_TO 边（分块属于文档）

        Args:
            chunk_id: 分块 ID
            document_id: 文档 ID

        Returns:
            是否创建成功
        """
        return self.neo4j_client.create_relationship(
            from_label='Chunk',
            from_id=str(chunk_id),
            to_label='Document',
            to_id=str(document_id),
            relationship_type='BELONGS_TO'
        )

    def create_child_edge(
        self,
        parent_chunk_id: uuid.UUID,
        child_chunk_id: uuid.UUID
    ) -> bool:
        """
        创建 HAS_CHILD 边（父分块有子分块）

        Args:
            parent_chunk_id: 父分块 ID
            child_chunk_id: 子分块 ID

        Returns:
            是否创建成功
        """
        return self.neo4j_client.create_relationship(
            from_label='Chunk',
            from_id=str(parent_chunk_id),
            to_label='Chunk',
            to_id=str(child_chunk_id),
            relationship_type='HAS_CHILD'
        )

    def check_document_in_graph(self, document_id: uuid.UUID) -> bool:
        """
        检查文档是否已在图中

        Args:
            document_id: 文档 ID

        Returns:
            文档是否存在于图中
        """
        return self.neo4j_client.check_node_exists('Document', str(document_id))

    def get_graph_stats(self) -> Dict[str, Any]:
        """
        获取图统计信息

        Returns:
            统计信息字典
        """
        company_count = self.neo4j_client.get_node_count('Company')
        document_count = self.neo4j_client.get_node_count('Document')
        chunk_count = self.neo4j_client.get_node_count('Chunk')
        has_document_count = self.neo4j_client.get_relationship_count('HAS_DOCUMENT')
        belongs_to_count = self.neo4j_client.get_relationship_count('BELONGS_TO')
        has_child_count = self.neo4j_client.get_relationship_count('HAS_CHILD')

        return {
            'company_nodes': company_count,
            'document_nodes': document_count,
            'chunk_nodes': chunk_count,
            'has_document_edges': has_document_count,
            'belongs_to_edges': belongs_to_count,
            'has_child_edges': has_child_count,
            'total_nodes': company_count + document_count + chunk_count,
            'total_edges': has_document_count + belongs_to_count + has_child_count,
        }
