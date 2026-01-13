# -*- coding: utf-8 -*-
"""
PostgreSQL 客户端
提供数据库连接和基本操作
"""

from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from src.common.config import postgres_config
from src.common.logger import get_logger, LoggerMixin
from src.storage.metadata.models import Base


class PostgreSQLClient(LoggerMixin):
    """
    PostgreSQL 客户端封装
    提供数据库连接、表管理、基本CRUD操作
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        pool_size: int = 5,
        max_overflow: int = 10,
        echo: bool = False
    ):
        """
        初始化 PostgreSQL 客户端

        Args:
            database_url: 数据库连接 URL（默认从配置读取）
            pool_size: 连接池大小
            max_overflow: 最大溢出连接数
            echo: 是否打印 SQL 语句
        """
        self.database_url = database_url or postgres_config.database_url

        # 创建引擎
        self.engine = create_engine(
            self.database_url,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            echo=echo,
            pool_pre_ping=True  # 连接前检查有效性
        )

        # 创建 Session 工厂
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

        self.logger.info(f"PostgreSQL 客户端初始化成功: {postgres_config.POSTGRES_HOST}:{postgres_config.POSTGRES_PORT}/{postgres_config.POSTGRES_DB}")

    @contextmanager
    def get_session(self) -> Session:
        """
        获取数据库会话（上下文管理器）

        Yields:
            SQLAlchemy Session

        Example:
            >>> client = PostgreSQLClient()
            >>> with client.get_session() as session:
            ...     documents = session.query(Document).all()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            session.close()

    def create_tables(self, checkfirst: bool = True) -> None:
        """
        创建所有表

        Args:
            checkfirst: 如果为 True，会先检查表是否存在，避免重复创建

        Example:
            >>> client = PostgreSQLClient()
            >>> client.create_tables()
        """
        try:
            Base.metadata.create_all(bind=self.engine, checkfirst=checkfirst)
            self.logger.info("数据库表创建成功")
        except Exception as e:
            self.logger.error(f"创建表失败: {e}")
            raise

    def drop_tables(self) -> None:
        """
        删除所有表（谨慎使用！）

        Example:
            >>> client = PostgreSQLClient()
            >>> client.drop_tables()
        """
        try:
            Base.metadata.drop_all(bind=self.engine)
            self.logger.warning("数据库表已删除")
        except Exception as e:
            self.logger.error(f"删除表失败: {e}")
            raise

    def table_exists(self, table_name: str) -> bool:
        """
        检查表是否存在

        Args:
            table_name: 表名

        Returns:
            是否存在

        Example:
            >>> client = PostgreSQLClient()
            >>> client.table_exists('documents')
            True
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = :table_name)"
                ), {"table_name": table_name})
                return result.scalar()
        except Exception as e:
            self.logger.error(f"检查表是否存在失败: {e}")
            return False

    def execute_sql(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        执行原生 SQL

        Args:
            sql: SQL 语句
            params: 参数字典

        Returns:
            查询结果

        Example:
            >>> client = PostgreSQLClient()
            >>> result = client.execute_sql(
            ...     "SELECT COUNT(*) FROM documents WHERE status = :status",
            ...     {"status": "pending"}
            ... )
            >>> print(result.scalar())
        """
        try:
            with self.engine.connect() as conn:
                if params:
                    result = conn.execute(text(sql), params)
                else:
                    result = conn.execute(text(sql))
                conn.commit()
                return result
        except Exception as e:
            self.logger.error(f"执行 SQL 失败: {sql}, 错误: {e}")
            raise

    def get_table_count(self, table_name: str) -> int:
        """
        获取表的记录数

        Args:
            table_name: 表名

        Returns:
            记录数

        Example:
            >>> client = PostgreSQLClient()
            >>> count = client.get_table_count('documents')
            >>> print(f"文档数量: {count}")
        """
        try:
            result = self.execute_sql(f"SELECT COUNT(*) FROM {table_name}")
            return result.scalar()
        except Exception as e:
            self.logger.error(f"获取表记录数失败: {table_name}, 错误: {e}")
            return 0

    def get_table_info(self) -> Dict[str, int]:
        """
        获取所有表的统计信息

        Returns:
            表名 -> 记录数 字典

        Example:
            >>> client = PostgreSQLClient()
            >>> info = client.get_table_info()
            >>> for table, count in info.items():
            ...     print(f"{table}: {count}")
        """
        tables = [
            'documents',
            'document_chunks',
            'crawl_tasks',
            'parse_tasks',
            'validation_logs',
            'quarantine_records',
            'embedding_tasks'
        ]

        info = {}
        for table in tables:
            if self.table_exists(table):
                info[table] = self.get_table_count(table)
            else:
                info[table] = 0

        return info

    def vacuum_analyze(self, table_name: Optional[str] = None) -> None:
        """
        执行 VACUUM ANALYZE 优化表

        Args:
            table_name: 表名（可选，不指定则优化所有表）

        Example:
            >>> client = PostgreSQLClient()
            >>> client.vacuum_analyze('documents')
        """
        try:
            with self.engine.connect() as conn:
                conn.execution_options(isolation_level="AUTOCOMMIT")
                if table_name:
                    conn.execute(text(f"VACUUM ANALYZE {table_name}"))
                    self.logger.info(f"表优化成功: {table_name}")
                else:
                    conn.execute(text("VACUUM ANALYZE"))
                    self.logger.info("数据库优化成功")
        except Exception as e:
            self.logger.error(f"表优化失败: {e}")

    def test_connection(self) -> bool:
        """
        测试数据库连接

        Returns:
            连接是否成功

        Example:
            >>> client = PostgreSQLClient()
            >>> if client.test_connection():
            ...     print("数据库连接成功")
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            self.logger.info("数据库连接测试成功")
            return True
        except Exception as e:
            self.logger.error(f"数据库连接测试失败: {e}")
            return False

    def get_database_size(self) -> Optional[str]:
        """
        获取数据库大小

        Returns:
            数据库大小（格式化字符串，如 "123 MB"）

        Example:
            >>> client = PostgreSQLClient()
            >>> size = client.get_database_size()
            >>> print(f"数据库大小: {size}")
        """
        try:
            result = self.execute_sql(
                "SELECT pg_size_pretty(pg_database_size(:db_name))",
                {"db_name": postgres_config.POSTGRES_DB}
            )
            return result.scalar()
        except Exception as e:
            self.logger.error(f"获取数据库大小失败: {e}")
            return None

    def close(self) -> None:
        """
        关闭连接池

        Example:
            >>> client = PostgreSQLClient()
            >>> # ... 使用数据库 ...
            >>> client.close()
        """
        try:
            self.engine.dispose()
            self.logger.info("PostgreSQL 连接池已关闭")
        except Exception as e:
            self.logger.error(f"关闭连接池失败: {e}")


# 全局客户端实例（单例模式）
_postgres_client: Optional[PostgreSQLClient] = None


def get_postgres_client() -> PostgreSQLClient:
    """
    获取全局 PostgreSQL 客户端实例（单例）

    Returns:
        PostgreSQL 客户端

    Example:
        >>> from src.storage.metadata.postgres_client import get_postgres_client
        >>> client = get_postgres_client()
        >>> with client.get_session() as session:
        ...     documents = session.query(Document).all()
    """
    global _postgres_client
    if _postgres_client is None:
        _postgres_client = PostgreSQLClient()
    return _postgres_client
