# -*- coding: utf-8 -*-
"""
Neo4j 图数据库客户端
提供图数据库的连接、节点和边的创建、查询等操作
"""

import json
from typing import Optional, List, Dict, Any
from neo4j import GraphDatabase, Driver, Session
from neo4j.exceptions import ServiceUnavailable, AuthError

from src.common.config import neo4j_config
from src.common.logger import get_logger, LoggerMixin

# #region agent log
DEBUG_LOG_PATH = "/Users/han/PycharmProjects/FinNet/.cursor/debug.log"
# #endregion


class Neo4jClient(LoggerMixin):
    """
    Neo4j 客户端封装
    提供图数据库的所有操作
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None
    ):
        """
        初始化 Neo4j 客户端

        Args:
            uri: Neo4j 连接 URI（默认从配置读取）
            user: 用户名（默认从配置读取）
            password: 密码（默认从配置读取）
            database: 数据库名称（默认从配置读取）
        """
        self.uri = uri or neo4j_config.NEO4J_URI
        self.user = user or neo4j_config.NEO4J_USER
        self.password = password or neo4j_config.NEO4J_PASSWORD
        self.database = database or neo4j_config.NEO4J_DATABASE

        # 连接到 Neo4j
        self._connect()

    def _connect(self) -> None:
        """连接到 Neo4j"""
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
            # 验证连接
            self.driver.verify_connectivity()
            self.logger.info(f"Neo4j 连接成功: {self.uri}, database={self.database}")
        except ServiceUnavailable as e:
            self.logger.error(f"Neo4j 服务不可用: {e}")
            raise
        except AuthError as e:
            self.logger.error(f"Neo4j 认证失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Neo4j 连接失败: {e}")
            raise

    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        执行 Cypher 查询

        Args:
            query: Cypher 查询语句
            parameters: 查询参数
            database: 数据库名称（默认使用配置的数据库）

        Returns:
            查询结果列表

        Example:
            >>> client = Neo4jClient()
            >>> results = client.execute_query(
            ...     "MATCH (n:Document) RETURN n LIMIT 10",
            ...     database="neo4j"
            ... )
        """
        db = database or self.database
        parameters = parameters or {}

        # #region agent log
        try:
            with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "N", "location": "neo4j_client.py:execute_query:before", "message": "Neo4j query about to execute", "data": {"query": query[:200], "parameters": parameters, "database": db}, "timestamp": int(__import__("time").time() * 1000)}) + "\n")
        except: pass
        # #endregion

        try:
            with self.driver.session(database=db) as session:
                result = session.run(query, parameters)
                records = [dict(record) for record in result]
                # #region agent log
                try:
                    with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                        f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "O", "location": "neo4j_client.py:execute_query:after", "message": "Neo4j query executed successfully", "data": {"records_count": len(records), "records_sample": records[:2] if records else []}, "timestamp": int(__import__("time").time() * 1000)}) + "\n")
                except: pass
                # #endregion
                return records
        except Exception as e:
            # #region agent log
            try:
                with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "P", "location": "neo4j_client.py:execute_query:exception", "message": "Neo4j query failed", "data": {"error": str(e), "error_type": type(e).__name__}, "timestamp": int(__import__("time").time() * 1000)}) + "\n")
            except: pass
            # #endregion
            self.logger.error(f"执行查询失败: {e}, query={query[:100]}")
            raise

    def execute_write(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        执行写操作（事务）

        Args:
            query: Cypher 查询语句
            parameters: 查询参数
            database: 数据库名称（默认使用配置的数据库）

        Returns:
            操作结果列表

        Example:
            >>> client = Neo4jClient()
            >>> results = client.execute_write(
            ...     "CREATE (n:Document {id: $id, stock_code: $code}) RETURN n",
            ...     parameters={"id": "123", "code": "000001"}
            ... )
        """
        db = database or self.database
        parameters = parameters or {}

        try:
            with self.driver.session(database=db) as session:
                result = session.run(query, parameters)
                records = [dict(record) for record in result]
                # Neo4j 会话自动提交，不需要手动调用 commit()
                return records
        except Exception as e:
            self.logger.error(f"执行写操作失败: {e}, query={query[:100]}")
            raise

    def create_constraints_and_indexes(self, database: Optional[str] = None) -> None:
        """
        创建约束和索引（幂等操作）

        Args:
            database: 数据库名称（默认使用配置的数据库）

        Example:
            >>> client = Neo4jClient()
            >>> client.create_constraints_and_indexes()
        """
        db = database or self.database

        constraints_and_indexes = [
            # Company 节点约束和索引（根节点）
            "CREATE CONSTRAINT company_code IF NOT EXISTS FOR (c:Company) REQUIRE c.code IS UNIQUE",
            "CREATE INDEX company_name IF NOT EXISTS FOR (c:Company) ON (c.name)",
            
            # Document 节点约束和索引
            "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
            "CREATE INDEX document_stock_code IF NOT EXISTS FOR (d:Document) ON (d.stock_code)",
            "CREATE INDEX document_doc_type IF NOT EXISTS FOR (d:Document) ON (d.doc_type)",
            "CREATE INDEX document_year IF NOT EXISTS FOR (d:Document) ON (d.year)",
            "CREATE INDEX document_quarter IF NOT EXISTS FOR (d:Document) ON (d.quarter)",
            
            # Chunk 节点约束和索引
            "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
            "CREATE INDEX chunk_document_id IF NOT EXISTS FOR (c:Chunk) ON (c.document_id)",
            "CREATE INDEX chunk_title_level IF NOT EXISTS FOR (c:Chunk) ON (c.title_level)",
        ]

        try:
            with self.driver.session(database=db) as session:
                for cypher in constraints_and_indexes:
                    try:
                        session.run(cypher)
                        self.logger.debug(f"执行成功: {cypher[:50]}...")
                    except Exception as e:
                        # 如果约束/索引已存在，忽略错误
                        if "already exists" in str(e).lower() or "equivalent" in str(e).lower():
                            self.logger.debug(f"约束/索引已存在: {cypher[:50]}...")
                        else:
                            self.logger.warning(f"创建约束/索引失败: {e}, query={cypher[:50]}...")
                # Neo4j 会话自动提交，不需要手动调用 commit()
            self.logger.info("约束和索引创建完成")
        except Exception as e:
            self.logger.error(f"创建约束和索引失败: {e}")
            raise

    def merge_node(
        self,
        label: str,
        properties: Dict[str, Any],
        database: Optional[str] = None,
        primary_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建或更新节点（MERGE）

        Args:
            label: 节点标签（如 "Document", "Chunk", "Company"）
            properties: 节点属性字典
            database: 数据库名称（默认使用配置的数据库）
            primary_key: 主键字段名（默认 "id"，Company 节点使用 "code"）

        Returns:
            创建的节点信息

        Example:
            >>> client = Neo4jClient()
            >>> node = client.merge_node(
            ...     "Document",
            ...     {"id": "123", "stock_code": "000001", "company_name": "平安银行"}
            ... )
            >>> company = client.merge_node(
            ...     "Company",
            ...     {"code": "000001", "name": "平安银行"},
            ...     primary_key="code"
            ... )
        """
        db = database or self.database
        
        # 确定主键字段（Company 使用 code，其他使用 id）
        if primary_key is None:
            primary_key = "code" if label == "Company" else "id"
        
        if primary_key not in properties:
            raise ValueError(f"节点属性中缺少主键字段: {primary_key}")

        # 构建属性字符串
        props_str = ", ".join([f"n.{k} = ${k}" for k in properties.keys()])
        set_str = ", ".join([f"n.{k} = ${k}" for k in properties.keys()])

        query = f"""
        MERGE (n:{label} {{{primary_key}: ${primary_key}}})
        ON CREATE SET {props_str}
        ON MATCH SET {set_str}
        RETURN n
        """

        try:
            results = self.execute_write(query, parameters=properties, database=db)
            if results:
                return results[0].get('n', {})
            return {}
        except Exception as e:
            self.logger.error(f"创建节点失败: {e}, label={label}, {primary_key}={properties.get(primary_key)}")
            raise

    def batch_merge_nodes(
        self,
        label: str,
        nodes: List[Dict[str, Any]],
        database: Optional[str] = None,
        batch_size: int = 100
    ) -> int:
        """
        批量创建或更新节点

        Args:
            label: 节点标签
            nodes: 节点属性列表
            database: 数据库名称（默认使用配置的数据库）
            batch_size: 每批处理的节点数量

        Returns:
            创建的节点数量

        Example:
            >>> client = Neo4jClient()
            >>> count = client.batch_merge_nodes(
            ...     "Document",
            ...     [
            ...         {"id": "123", "stock_code": "000001"},
            ...         {"id": "124", "stock_code": "000002"}
            ...     ]
            ... )
        """
        db = database or self.database
        total_created = 0

        # 分批处理
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i + batch_size]
            
            # 使用 UNWIND 进行批量 MERGE（更高效）
            query = f"""
            UNWIND $nodes AS node
            MERGE (n:{label} {{id: node.id}})
            ON CREATE SET n += node
            ON MATCH SET n += node
            RETURN count(n) as count
            """

            try:
                results = self.execute_write(
                    query,
                    parameters={"nodes": batch},
                    database=db
                )
                if results:
                    total_created += results[0].get('count', len(batch))
            except Exception as e:
                self.logger.error(f"批量创建节点失败（批次 {i//batch_size + 1}）: {e}")
                # 如果批量失败，尝试单个创建
                for node in batch:
                    try:
                        self.merge_node(label, node, database=db)
                        total_created += 1
                    except Exception as e2:
                        self.logger.error(f"单个创建节点失败: {e2}, node_id={node.get('id')}")

        self.logger.info(f"批量创建节点完成: label={label}, total={total_created}")
        return total_created

    def create_relationship(
        self,
        from_label: str,
        from_id: str,
        to_label: str,
        to_id: str,
        relationship_type: str,
        properties: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None
    ) -> bool:
        """
        创建关系（边）

        Args:
            from_label: 起始节点标签
            from_id: 起始节点 ID（Company 节点使用 code，其他使用 id）
            to_label: 目标节点标签
            to_id: 目标节点 ID（Company 节点使用 code，其他使用 id）
            relationship_type: 关系类型（如 "HAS_DOCUMENT", "BELONGS_TO", "HAS_CHILD"）
            properties: 关系属性（可选）
            database: 数据库名称（默认使用配置的数据库）

        Returns:
            是否创建成功

        Example:
            >>> client = Neo4jClient()
            >>> success = client.create_relationship(
            ...     "Company", "000001",
            ...     "Document", "doc123",
            ...     "HAS_DOCUMENT"
            ... )
        """
        db = database or self.database
        properties = properties or {}

        # 确定主键字段（Company 使用 code，其他使用 id）
        from_key = "code" if from_label == "Company" else "id"
        to_key = "code" if to_label == "Company" else "id"

        # 先检查节点是否存在，如果不存在则记录警告
        # 然后使用 MERGE 创建关系（如果节点不存在，MERGE 会创建只有主键的节点）
        # 这样可以避免如果节点不存在时关系创建失败的问题
        check_query = f"""
        MATCH (a:{from_label} {{{from_key}: $from_id}})
        MATCH (b:{to_label} {{{to_key}: $to_id}})
        RETURN count(a) as from_exists, count(b) as to_exists
        """
        
        try:
            check_results = self.execute_query(check_query, {
                "from_id": from_id,
                "to_id": to_id
            }, database=db)
            
            if check_results:
                from_exists = check_results[0].get('from_exists', 0) > 0
                to_exists = check_results[0].get('to_exists', 0) > 0
                
                if not from_exists:
                    self.logger.warning(
                        f"创建关系时源节点不存在: {from_label}({from_id}) -[{relationship_type}]-> {to_label}({to_id})"
                    )
                if not to_exists:
                    self.logger.warning(
                        f"创建关系时目标节点不存在: {from_label}({from_id}) -[{relationship_type}]-> {to_label}({to_id})"
                    )
        except Exception as e:
            self.logger.debug(f"检查节点存在性时出错（继续创建关系）: {e}")
        
        # 使用 MERGE 确保节点存在，然后创建关系
        query = f"""
        MERGE (a:{from_label} {{{from_key}: $from_id}})
        MERGE (b:{to_label} {{{to_key}: $to_id}})
        MERGE (a)-[r:{relationship_type}]->(b)
        """
        
        if properties:
            props_str = ", ".join([f"r.{k} = ${k}" for k in properties.keys()])
            query += f" SET {props_str}"

        query += " RETURN r"

        try:
            parameters = {
                "from_id": from_id,
                "to_id": to_id,
                **properties
            }
            results = self.execute_write(query, parameters=parameters, database=db)
            return len(results) > 0
        except Exception as e:
            self.logger.error(
                f"创建关系失败: {e}, "
                f"{from_label}({from_id}) -[{relationship_type}]-> {to_label}({to_id})"
            )
            return False

    def batch_create_relationships(
        self,
        relationships: List[Dict[str, Any]],
        database: Optional[str] = None,
        batch_size: int = 100
    ) -> int:
        """
        批量创建关系

        Args:
            relationships: 关系列表，每个元素包含：
                - from_label: 起始节点标签
                - from_id: 起始节点 ID
                - to_label: 目标节点标签
                - to_id: 目标节点 ID
                - relationship_type: 关系类型
                - properties: 关系属性（可选）
            database: 数据库名称（默认使用配置的数据库）
            batch_size: 每批处理的关系数量

        Returns:
            创建的关系数量

        Example:
            >>> client = Neo4jClient()
            >>> count = client.batch_create_relationships([
            ...     {
            ...         "from_label": "Document",
            ...         "from_id": "doc123",
            ...         "to_label": "Chunk",
            ...         "to_id": "chunk456",
            ...         "relationship_type": "CONTAINS"
            ...     }
            ... ])
        """
        db = database or self.database
        total_created = 0

        # 分批处理
        for i in range(0, len(relationships), batch_size):
            batch = relationships[i:i + batch_size]
            
            for rel in batch:
                try:
                    success = self.create_relationship(
                        from_label=rel['from_label'],
                        from_id=rel['from_id'],
                        to_label=rel['to_label'],
                        to_id=rel['to_id'],
                        relationship_type=rel['relationship_type'],
                        properties=rel.get('properties'),
                        database=db
                    )
                    if success:
                        total_created += 1
                except Exception as e:
                    self.logger.error(f"创建关系失败: {e}, rel={rel}")

        self.logger.info(f"批量创建关系完成: total={total_created}")
        return total_created

    def check_node_exists(
        self,
        label: str,
        node_id: str,
        database: Optional[str] = None
    ) -> bool:
        """
        检查节点是否存在

        Args:
            label: 节点标签
            node_id: 节点 ID
            database: 数据库名称（默认使用配置的数据库）

        Returns:
            节点是否存在

        Example:
            >>> client = Neo4jClient()
            >>> exists = client.check_node_exists("Document", "doc123")
        """
        db = database or self.database

        query = f"MATCH (n:{label} {{id: $id}}) RETURN count(n) as count"
        
        try:
            results = self.execute_query(query, parameters={"id": node_id}, database=db)
            if results:
                return results[0].get('count', 0) > 0
            return False
        except Exception as e:
            self.logger.error(f"检查节点存在性失败: {e}, label={label}, id={node_id}")
            return False

    def batch_check_nodes_exist(
        self,
        label: str,
        node_ids: List[str],
        database: Optional[str] = None
    ) -> Dict[str, bool]:
        """
        批量检查节点是否存在

        Args:
            label: 节点标签
            node_ids: 节点 ID 列表
            database: 数据库名称（默认使用配置的数据库）

        Returns:
            字典，key 为节点 ID，value 为是否存在

        Example:
            >>> client = Neo4jClient()
            >>> exists_map = client.batch_check_nodes_exist("Document", ["doc1", "doc2", "doc3"])
            >>> print(exists_map["doc1"])  # True or False
        """
        db = database or self.database
        
        if not node_ids:
            self.logger.warning("batch_check_nodes_exist: 节点ID列表为空")
            return {}
        
        self.logger.debug(f"批量检查 {len(node_ids)} 个 {label} 节点是否存在")
        
        # 使用 IN 子句批量查询
        query = f"MATCH (n:{label}) WHERE n.id IN $ids RETURN n.id as id"
        
        try:
            results = self.execute_query(query, parameters={"ids": node_ids}, database=db)
            
            # 构建存在节点的集合
            existing_ids = {result.get('id') for result in results if result.get('id')}
            
            # 返回所有节点的存在状态
            result_map = {node_id: node_id in existing_ids for node_id in node_ids}
            
            # 调试信息
            existing_count = sum(1 for exists in result_map.values() if exists)
            self.logger.debug(
                f"批量检查完成: 总数={len(result_map)}, "
                f"已存在={existing_count}, 不存在={len(result_map) - existing_count}"
            )
            
            return result_map
        except Exception as e:
            self.logger.error(
                f"批量检查节点存在性失败: {e}, label={label}, "
                f"node_ids_count={len(node_ids)}",
                exc_info=True
            )
            # 如果批量查询失败，返回所有节点都不存在（保守策略）
            # 这样会尝试重新构建图，而不是跳过
            self.logger.warning(
                f"批量检查失败，返回所有节点都不存在（保守策略）"
            )
            return {node_id: False for node_id in node_ids}

    def get_node_count(self, label: Optional[str] = None, database: Optional[str] = None) -> int:
        """
        获取节点数量

        Args:
            label: 节点标签（如果为 None，返回所有节点数量）
            database: 数据库名称（默认使用配置的数据库）

        Returns:
            节点数量

        Example:
            >>> client = Neo4jClient()
            >>> count = client.get_node_count("Document")
        """
        db = database or self.database

        if label:
            query = f"MATCH (n:{label}) RETURN count(n) as count"
        else:
            query = "MATCH (n) RETURN count(n) as count"

        try:
            results = self.execute_query(query, database=db)
            if results:
                return results[0].get('count', 0)
            return 0
        except Exception as e:
            self.logger.error(f"获取节点数量失败: {e}")
            return 0

    def get_relationship_count(
        self,
        relationship_type: Optional[str] = None,
        database: Optional[str] = None
    ) -> int:
        """
        获取关系数量

        Args:
            relationship_type: 关系类型（如果为 None，返回所有关系数量）
            database: 数据库名称（默认使用配置的数据库）

        Returns:
            关系数量

        Example:
            >>> client = Neo4jClient()
            >>> count = client.get_relationship_count("CONTAINS")
        """
        db = database or self.database

        if relationship_type:
            query = f"MATCH ()-[r:{relationship_type}]->() RETURN count(r) as count"
        else:
            query = "MATCH ()-[r]->() RETURN count(r) as count"

        try:
            results = self.execute_query(query, database=db)
            if results:
                return results[0].get('count', 0)
            return 0
        except Exception as e:
            self.logger.error(f"获取关系数量失败: {e}")
            return 0

    def reset_schema(self, database: Optional[str] = None) -> Dict[str, Any]:
        """
        重置 schema：删除所有节点、边、约束和索引
        
        ⚠️ 警告：此操作会删除所有数据！
        
        Args:
            database: 数据库名称（默认使用配置的数据库）
            
        Returns:
            重置结果统计
            
        Example:
            >>> client = Neo4jClient()
            >>> result = client.reset_schema()
            >>> print(result)
        """
        db = database or self.database
        
        self.logger.warning("⚠️ 开始重置 Neo4j schema（将删除所有数据）")
        
        try:
            with self.driver.session(database=db) as session:
                # 删除所有关系
                result = session.run("MATCH ()-[r]->() DELETE r RETURN count(r) as count")
                record = result.single()
                relationships_deleted = record['count'] if record else 0
                
                # 删除所有节点
                result = session.run("MATCH (n) DELETE n RETURN count(n) as count")
                record = result.single()
                nodes_deleted = record['count'] if record else 0
                
                # 删除所有约束
                constraints_deleted = 0
                try:
                    result = session.run("SHOW CONSTRAINTS")
                    constraints = []
                    for record in result:
                        constraint_name = record.get('name') or record.get('id')
                        if constraint_name:
                            constraints.append(constraint_name)
                    
                    for constraint_name in constraints:
                        try:
                            # Neo4j 5.x 使用 DROP CONSTRAINT name IF EXISTS
                            session.run(f"DROP CONSTRAINT `{constraint_name}` IF EXISTS")
                            constraints_deleted += 1
                        except Exception as e:
                            self.logger.warning(f"删除约束失败: {constraint_name}, {e}")
                except Exception as e:
                    self.logger.warning(f"获取约束列表失败: {e}")
                
                # 删除所有索引（除了约束索引）
                indexes_deleted = 0
                try:
                    result = session.run("SHOW INDEXES")
                    indexes = []
                    for record in result:
                        # 只删除非约束索引
                        if not record.get('owningConstraint'):
                            index_name = record.get('name') or record.get('id')
                            if index_name:
                                indexes.append(index_name)
                    
                    for index_name in indexes:
                        try:
                            session.run(f"DROP INDEX `{index_name}` IF EXISTS")
                            indexes_deleted += 1
                        except Exception as e:
                            self.logger.warning(f"删除索引失败: {index_name}, {e}")
                except Exception as e:
                    self.logger.warning(f"获取索引列表失败: {e}")
                
                result = {
                    'success': True,
                    'nodes_deleted': nodes_deleted,
                    'relationships_deleted': relationships_deleted,
                    'constraints_deleted': constraints_deleted,
                    'indexes_deleted': indexes_deleted,
                }
                
                self.logger.info(
                    f"Schema 重置完成: 节点={nodes_deleted}, 边={relationships_deleted}, "
                    f"约束={constraints_deleted}, 索引={indexes_deleted}"
                )
                
                return result
                
        except Exception as e:
            self.logger.error(f"重置 schema 失败: {e}", exc_info=True)
            return {
                'success': False,
                'error_message': str(e),
            }

    def close(self) -> None:
        """
        关闭连接

        Example:
            >>> client = Neo4jClient()
            >>> # ... 使用 Neo4j ...
            >>> client.close()
        """
        try:
            if hasattr(self, 'driver') and self.driver:
                self.driver.close()
                self.logger.info("Neo4j 连接已关闭")
        except Exception as e:
            self.logger.error(f"关闭连接失败: {e}")


# 全局客户端实例（单例模式）
_neo4j_client: Optional[Neo4jClient] = None


def get_neo4j_client() -> Neo4jClient:
    """
    获取全局 Neo4j 客户端实例（单例）

    Returns:
        Neo4j 客户端

    Example:
        >>> from src.storage.graph.neo4j_client import get_neo4j_client
        >>> client = get_neo4j_client()
        >>> client.create_constraints_and_indexes()
    """
    global _neo4j_client
    if _neo4j_client is None:
        _neo4j_client = Neo4jClient()
    return _neo4j_client
