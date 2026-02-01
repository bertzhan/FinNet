# -*- coding: utf-8 -*-
"""
图检索器
基于 Neo4j 进行图检索，从 PostgreSQL 获取分块文本和元数据
"""

import uuid
import json
from typing import List, Dict, Any, Optional

from src.storage.graph.neo4j_client import get_neo4j_client, Neo4jClient
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import DocumentChunk, Document
from src.common.logger import get_logger, LoggerMixin
from src.application.rag.retriever import RetrievalResult

# #region agent log
DEBUG_LOG_PATH = "/Users/han/PycharmProjects/FinNet/.cursor/debug.log"
# #endregion


class GraphRetriever(LoggerMixin):
    """
    图检索器
    基于 Neo4j 进行图检索，从 PostgreSQL 获取完整的分块信息
    """

    def __init__(
        self,
        neo4j_client: Optional[Neo4jClient] = None,
        pg_client=None
    ):
        """
        初始化图检索器

        Args:
            neo4j_client: Neo4j 客户端（默认自动创建）
            pg_client: PostgreSQL 客户端（默认自动创建）
        """
        self.neo4j_client = neo4j_client or get_neo4j_client()
        self.pg_client = pg_client or get_postgres_client()

    def retrieve(
        self,
        query: Optional[str] = None,
        query_type: str = "document",
        filters: Optional[Dict[str, Any]] = None,
        max_depth: Optional[int] = None,
        top_k: int = 10,
        cypher_query: Optional[str] = None,
        cypher_parameters: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """
        检索相关文档分块（图检索）

        Args:
            query: 查询文本或节点ID（用于 document/chunk/hierarchy 查询类型）
            query_type: 查询类型（"document", "chunk", "hierarchy", "cypher"）
            filters: 过滤条件
                - stock_code: 股票代码
                - year: 年份
                - quarter: 季度
                - doc_type: 文档类型（字符串或列表）
                - market: 市场
            max_depth: 最大遍历深度（用于层级查询）
            top_k: 返回数量
            cypher_query: 自定义 Cypher 查询（当 query_type 为 "cypher" 时必填）
            cypher_parameters: Cypher 查询参数

        Returns:
            检索结果列表

        Example:
            >>> retriever = GraphRetriever()
            >>> results = retriever.retrieve(
            ...     query="000001",
            ...     query_type="document",
            ...     filters={"stock_code": "000001", "year": 2023},
            ...     top_k=10
            ... )
        """
        # #region agent log
        try:
            with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "graph_retriever.py:retrieve:entry", "message": "GraphRetriever.retrieve called", "data": {"query": query, "query_type": query_type, "filters": filters, "top_k": top_k}, "timestamp": int(__import__("time").time() * 1000)}) + "\n")
        except: pass
        # #endregion
        try:
            if query_type == "cypher":
                # 自定义 Cypher 查询
                if not cypher_query:
                    self.logger.error("cypher_query 不能为空")
                    return []
                chunk_ids = self._execute_cypher_query(cypher_query, cypher_parameters or {}, top_k)
            elif query_type == "document":
                # 文档检索：通过文档节点查找所有相关分块
                chunk_ids = self._retrieve_by_document(query, filters, top_k)
            elif query_type == "chunk":
                # 分块检索：查找特定分块
                chunk_ids = self._retrieve_by_chunk(query, filters, top_k)
            elif query_type == "hierarchy":
                # 层级遍历：通过 HAS_CHILD 关系遍历分块层级
                chunk_ids = self._retrieve_by_hierarchy(query, max_depth or 3, top_k)
            else:
                self.logger.error(f"不支持的查询类型: {query_type}")
                return []

            # #region agent log
            try:
                with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "B", "location": "graph_retriever.py:retrieve:after_neo4j", "message": "Neo4j query returned chunk_ids", "data": {"chunk_ids_count": len(chunk_ids) if chunk_ids else 0, "chunk_ids_sample": chunk_ids[:5] if chunk_ids else []}, "timestamp": int(__import__("time").time() * 1000)}) + "\n")
            except: pass
            # #endregion

            if not chunk_ids:
                self.logger.warning("图检索结果为空")
                return []

            # 从 PostgreSQL 获取分块详细信息
            self.logger.debug(f"从 PostgreSQL 获取 {len(chunk_ids)} 个分块信息")
            retrieval_results = self._fetch_chunks_from_db(chunk_ids)

            # #region agent log
            try:
                with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "C", "location": "graph_retriever.py:retrieve:after_pg", "message": "PostgreSQL fetch completed", "data": {"results_count": len(retrieval_results)}, "timestamp": int(__import__("time").time() * 1000)}) + "\n")
            except: pass
            # #endregion

            self.logger.info(
                f"图检索完成: query_type={query_type}, "
                f"返回 {len(retrieval_results)} 个结果"
            )
            return retrieval_results

        except Exception as e:
            # #region agent log
            try:
                with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "D", "location": "graph_retriever.py:retrieve:exception", "message": "Exception in retrieve", "data": {"error": str(e), "error_type": type(e).__name__}, "timestamp": int(__import__("time").time() * 1000)}) + "\n")
            except: pass
            # #endregion
            self.logger.error(f"图检索失败: {e}", exc_info=True)
            return []

    def _retrieve_by_document(
        self,
        query: Optional[str],
        filters: Optional[Dict[str, Any]],
        top_k: int
    ) -> List[str]:
        """
        通过文档节点查找所有相关分块

        Args:
            query: 查询文本（可以是股票代码、文档ID等）
            filters: 过滤条件
            top_k: 返回数量

        Returns:
            分块ID列表
        """
        # #region agent log
        try:
            with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "E", "location": "graph_retriever.py:_retrieve_by_document:entry", "message": "_retrieve_by_document called", "data": {"query": query, "filters": filters, "top_k": top_k}, "timestamp": int(__import__("time").time() * 1000)}) + "\n")
        except: pass
        # #endregion
        # 构建 Cypher 查询
        cypher = """
        MATCH (d:Document)<-[:BELONGS_TO]-(c:Chunk)
        WHERE 1=1
        """
        parameters = {}
        conditions = []

        # 添加过滤条件
        if filters:
            if filters.get("stock_code"):
                conditions.append("d.stock_code = $stock_code")
                parameters["stock_code"] = filters["stock_code"]

            if filters.get("year"):
                conditions.append("d.year = $year")
                parameters["year"] = filters["year"]

            if filters.get("quarter"):
                conditions.append("d.quarter = $quarter")
                parameters["quarter"] = filters["quarter"]

            if filters.get("doc_type"):
                doc_type = filters["doc_type"]
                if isinstance(doc_type, list):
                    conditions.append("d.doc_type IN $doc_type")
                    parameters["doc_type"] = doc_type
                else:
                    conditions.append("d.doc_type = $doc_type")
                    parameters["doc_type"] = doc_type

            if filters.get("market"):
                conditions.append("d.market = $market")
                parameters["market"] = filters["market"]

        # 如果提供了 query，可以用于匹配股票代码或文档ID
        if query:
            # 尝试作为股票代码匹配
            conditions.append("(d.stock_code = $query OR d.id = $query)")
            parameters["query"] = query

        if conditions:
            cypher += " AND " + " AND ".join(conditions)

        cypher += f" RETURN c.id as chunk_id LIMIT {top_k}"

        # #region agent log
        try:
            with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "F", "location": "graph_retriever.py:_retrieve_by_document:before_query", "message": "Cypher query built", "data": {"cypher": cypher, "parameters": parameters}, "timestamp": int(__import__("time").time() * 1000)}) + "\n")
        except: pass
        # #endregion

        try:
            results = self.neo4j_client.execute_query(cypher, parameters)
            # #region agent log
            try:
                with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "G", "location": "graph_retriever.py:_retrieve_by_document:after_query", "message": "Neo4j query executed", "data": {"results_count": len(results), "results_sample": results[:3] if results else []}, "timestamp": int(__import__("time").time() * 1000)}) + "\n")
            except: pass
            # #endregion
            chunk_ids = [str(record.get("chunk_id", "")) for record in results if record.get("chunk_id")]
            # #region agent log
            try:
                with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "H", "location": "graph_retriever.py:_retrieve_by_document:after_extract", "message": "chunk_ids extracted", "data": {"chunk_ids_count": len(chunk_ids), "chunk_ids_sample": chunk_ids[:5]}, "timestamp": int(__import__("time").time() * 1000)}) + "\n")
            except: pass
            # #endregion
            return chunk_ids
        except Exception as e:
            # #region agent log
            try:
                with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "I", "location": "graph_retriever.py:_retrieve_by_document:exception", "message": "Exception in _retrieve_by_document", "data": {"error": str(e), "error_type": type(e).__name__}, "timestamp": int(__import__("time").time() * 1000)}) + "\n")
            except: pass
            # #endregion
            self.logger.error(f"文档检索失败: {e}", exc_info=True)
            return []

    def _retrieve_by_chunk(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        top_k: int
    ) -> List[str]:
        """
        分块检索：查找特定分块

        Args:
            query: 分块ID
            filters: 过滤条件（可选）
            top_k: 返回数量

        Returns:
            分块ID列表
        """
        if not query:
            return []

        cypher = """
        MATCH (c:Chunk {id: $chunk_id})
        """
        parameters = {"chunk_id": query}

        # 如果指定了 top_k > 1，可以查找相关分块（例如同一文档的其他分块）
        if top_k > 1:
            cypher = """
            MATCH (c:Chunk {id: $chunk_id})-[:BELONGS_TO]->(d:Document)<-[:BELONGS_TO]-(related:Chunk)
            WHERE c.id <> related.id
            """
            if filters:
                # 可以添加额外的过滤条件
                pass

        cypher += f" RETURN c.id as chunk_id LIMIT {top_k}"

        try:
            results = self.neo4j_client.execute_query(cypher, parameters)
            chunk_ids = [str(record.get("chunk_id", "")) for record in results if record.get("chunk_id")]
            return chunk_ids
        except Exception as e:
            self.logger.error(f"分块检索失败: {e}", exc_info=True)
            return []

    def _retrieve_by_hierarchy(
        self,
        query: str,
        max_depth: int,
        top_k: int
    ) -> List[str]:
        """
        层级遍历：通过 HAS_CHILD 关系遍历分块层级

        Args:
            query: 起始分块ID
            max_depth: 最大遍历深度
            top_k: 返回数量

        Returns:
            分块ID列表
        """
        if not query:
            return []

        # 使用可变长度路径查询
        cypher = f"""
        MATCH path = (c:Chunk {{id: $chunk_id}})-[:HAS_CHILD*1..{max_depth}]->(child:Chunk)
        RETURN DISTINCT child.id as chunk_id
        ORDER BY length(path)
        LIMIT {top_k}
        """

        parameters = {"chunk_id": query}

        try:
            results = self.neo4j_client.execute_query(cypher, parameters)
            chunk_ids = [str(record.get("chunk_id", "")) for record in results if record.get("chunk_id")]
            return chunk_ids
        except Exception as e:
            self.logger.error(f"层级遍历失败: {e}", exc_info=True)
            return []

    def get_children(self, chunk_id: str) -> List[Dict[str, Any]]:
        """
        获取给定 chunk_id 的所有直接子节点（children）

        Args:
            chunk_id: 父分块 ID

        Returns:
            子节点列表，每个元素包含 chunk_id 和 title
            格式: [{"chunk_id": "...", "title": "..."}, ...]

        Example:
            >>> retriever = GraphRetriever()
            >>> children = retriever.get_children("chunk-uuid-123")
            >>> print(children)
            [{"chunk_id": "child-uuid-1", "title": "第一章"}, ...]
        """
        if not chunk_id:
            self.logger.warning("chunk_id 为空")
            return []

        # 查询直接子节点（只查询一层，不使用递归）
        # 使用 COALESCE 处理 NULL 值，确保排序正确
        # 注意：不使用 DISTINCT，因为每个关系应该只对应一个子节点
        cypher = """
        MATCH (parent:Chunk {id: $chunk_id})-[:HAS_CHILD]->(child:Chunk)
        RETURN child.id as chunk_id, child.title as title, child.chunk_index as chunk_index
        ORDER BY COALESCE(child.chunk_index, 999999) ASC
        """

        parameters = {"chunk_id": chunk_id}

        try:
            results = self.neo4j_client.execute_query(cypher, parameters)
            children = []
            for record in results:
                chunk_id_str = str(record.get("chunk_id", ""))
                title = record.get("title")
                chunk_index = record.get("chunk_index")
                if chunk_id_str:
                    children.append({
                        "chunk_id": chunk_id_str,
                        "title": title if title else None
                    })
            
            self.logger.info(
                f"查询子节点完成: parent_chunk_id={chunk_id}, "
                f"找到 {len(children)} 个子节点"
            )
            
            # 如果结果数量较少，记录详细信息用于调试
            if len(children) <= 5:
                for i, child in enumerate(children, 1):
                    self.logger.debug(
                        f"  子节点 {i}: chunk_id={child['chunk_id']}, "
                        f"title={child.get('title', 'N/A')}"
                    )
            
            return children
        except Exception as e:
            self.logger.error(f"查询子节点失败: {e}", exc_info=True)
            return []

    def _execute_cypher_query(
        self,
        cypher_query: str,
        parameters: Dict[str, Any],
        top_k: int
    ) -> List[str]:
        """
        执行自定义 Cypher 查询

        Args:
            cypher_query: Cypher 查询语句
            parameters: 查询参数
            top_k: 返回数量限制

        Returns:
            分块ID列表
        """
        try:
            # 如果查询中没有 LIMIT，添加一个
            if "LIMIT" not in cypher_query.upper():
                cypher_query += f" LIMIT {top_k}"

            results = self.neo4j_client.execute_query(cypher_query, parameters)

            # 尝试从结果中提取 chunk_id
            chunk_ids = []
            for record in results:
                # 尝试不同的字段名
                chunk_id = (
                    record.get("chunk_id") or
                    record.get("c.id") or
                    record.get("id") or
                    (record.get("c", {}).get("id") if isinstance(record.get("c"), dict) else None)
                )
                if chunk_id:
                    chunk_ids.append(str(chunk_id))

            return chunk_ids
        except Exception as e:
            self.logger.error(f"执行 Cypher 查询失败: {e}", exc_info=True)
            return []

    def _fetch_chunks_from_db(
        self,
        chunk_ids: List[str]
    ) -> List[RetrievalResult]:
        """
        从 PostgreSQL 获取分块文本和元数据

        Args:
            chunk_ids: 分块 ID 列表（字符串格式）

        Returns:
            检索结果列表
        """
        # #region agent log
        try:
            with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "J", "location": "graph_retriever.py:_fetch_chunks_from_db:entry", "message": "_fetch_chunks_from_db called", "data": {"chunk_ids_count": len(chunk_ids), "chunk_ids_sample": chunk_ids[:5]}, "timestamp": int(__import__("time").time() * 1000)}) + "\n")
        except: pass
        # #endregion
        if not chunk_ids:
            return []

        # 转换为 UUID
        chunk_uuids = []
        for chunk_id in chunk_ids:
            try:
                chunk_uuids.append(uuid.UUID(chunk_id))
            except ValueError:
                self.logger.warning(f"无效的 chunk_id: {chunk_id}")
                continue

        # #region agent log
        try:
            with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "K", "location": "graph_retriever.py:_fetch_chunks_from_db:after_uuid", "message": "UUIDs converted", "data": {"chunk_uuids_count": len(chunk_uuids)}, "timestamp": int(__import__("time").time() * 1000)}) + "\n")
        except: pass
        # #endregion

        if not chunk_uuids:
            return []

        # 从 PostgreSQL 查询
        results = []
        try:
            with self.pg_client.get_session() as session:
                # 查询分块和文档信息（JOIN）
                chunks = session.query(DocumentChunk, Document).join(
                    Document, DocumentChunk.document_id == Document.id
                ).filter(
                    DocumentChunk.id.in_(chunk_uuids)
                ).all()

                # #region agent log
                try:
                    with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                        f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "L", "location": "graph_retriever.py:_fetch_chunks_from_db:after_query", "message": "PostgreSQL query executed", "data": {"chunks_count": len(chunks)}, "timestamp": int(__import__("time").time() * 1000)}) + "\n")
                except: pass
                # #endregion

                # 构建结果
                for chunk, doc in chunks:
                    chunk_id_str = str(chunk.id)

                    # 图检索默认分数为 1.0（因为是基于关系的检索，不是相似度检索）
                    # 可以根据需要调整
                    score = 1.0

                    # 构建元数据
                    metadata = {
                        "stock_code": doc.stock_code,
                        "company_name": doc.company_name,
                        "market": doc.market,
                        "doc_type": doc.doc_type,
                        "year": doc.year,
                        "quarter": doc.quarter,
                        "chunk_index": chunk.chunk_index,
                    }

                    result = RetrievalResult(
                        chunk_id=chunk_id_str,
                        document_id=str(chunk.document_id),
                        chunk_text=chunk.chunk_text or "",
                        title=chunk.title,
                        title_level=chunk.title_level,
                        score=score,
                        metadata=metadata
                    )
                    results.append(result)

                # 按原始顺序排序（保持 Neo4j 返回的顺序）
                results.sort(
                    key=lambda r: chunk_ids.index(r.chunk_id)
                    if r.chunk_id in chunk_ids
                    else 999
                )

        except Exception as e:
            # #region agent log
            try:
                with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "M", "location": "graph_retriever.py:_fetch_chunks_from_db:exception", "message": "Exception in _fetch_chunks_from_db", "data": {"error": str(e), "error_type": type(e).__name__}, "timestamp": int(__import__("time").time() * 1000)}) + "\n")
            except: pass
            # #endregion
            self.logger.error(
                f"从 PostgreSQL 获取分块失败: {e}",
                exc_info=True
            )
            return []

        return results
