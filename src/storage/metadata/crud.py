# -*- coding: utf-8 -*-
"""
CRUD 操作辅助类
提供常用的数据库增删改查操作
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from src.storage.metadata.models import (
    Document, DocumentChunk, CrawlTask, ParseTask,
    ValidationLog, QuarantineRecord, EmbeddingTask
)
from src.common.constants import DocumentStatus
from src.common.logger import get_logger

logger = get_logger(__name__)


# ==================== Document CRUD ====================

def create_document(
    session: Session,
    stock_code: str,
    company_name: str,
    market: str,
    doc_type: str,
    year: int,
    quarter: Optional[int],
    minio_object_name: str,
    file_size: Optional[int] = None,
    file_hash: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> Document:
    """
    创建文档记录

    Args:
        session: 数据库会话
        stock_code: 股票代码
        company_name: 公司名称
        market: 市场类型
        doc_type: 文档类型
        year: 年份
        quarter: 季度
        minio_object_name: MinIO 对象名称
        file_size: 文件大小
        file_hash: 文件哈希
        metadata: 元数据

    Returns:
        Document 对象

    Example:
        >>> with get_postgres_client().get_session() as session:
        ...     doc = create_document(
        ...         session, "000001", "平安银行", "a_share",
        ...         "quarterly_reports", 2023, 3,
        ...         "bronze/a_share/quarterly_reports/2023/Q3/000001/report.pdf"
        ...     )
        ...     print(doc.id)
    """
    doc = Document(
        stock_code=stock_code,
        company_name=company_name,
        market=market,
        doc_type=doc_type,
        year=year,
        quarter=quarter,
        minio_object_name=minio_object_name,
        file_size=file_size,
        file_hash=file_hash,
        status=DocumentStatus.CRAWLED.value,
        crawled_at=datetime.now(),
        extra_metadata=metadata or {}
    )

    session.add(doc)
    session.flush()  # 获取 ID
    logger.debug(f"创建文档记录: id={doc.id}, stock_code={stock_code}")
    return doc


def get_document_by_id(session: Session, document_id: int) -> Optional[Document]:
    """获取文档（按 ID）"""
    return session.query(Document).filter(Document.id == document_id).first()


def get_document_by_path(session: Session, minio_object_name: str) -> Optional[Document]:
    """获取文档（按 MinIO 路径）"""
    return session.query(Document).filter(Document.minio_object_name == minio_object_name).first()


def get_documents_by_status(
    session: Session,
    status: str,
    limit: int = 100,
    offset: int = 0
) -> List[Document]:
    """
    获取指定状态的文档

    Args:
        session: 数据库会话
        status: 文档状态
        limit: 返回数量
        offset: 偏移量

    Returns:
        Document 列表

    Example:
        >>> with get_postgres_client().get_session() as session:
        ...     docs = get_documents_by_status(session, "pending", limit=10)
        ...     for doc in docs:
        ...         print(doc.stock_code, doc.year, doc.quarter)
    """
    return session.query(Document).filter(
        Document.status == status
    ).order_by(
        Document.created_at.asc()
    ).limit(limit).offset(offset).all()


def update_document_status(
    session: Session,
    document_id: int,
    status: str,
    error_message: Optional[str] = None,
    **kwargs
) -> bool:
    """
    更新文档状态

    Args:
        session: 数据库会话
        document_id: 文档 ID
        status: 新状态
        error_message: 错误信息（可选）
        **kwargs: 其他更新字段（如 parsed_at, vectorized_at）

    Returns:
        是否更新成功

    Example:
        >>> with get_postgres_client().get_session() as session:
        ...     success = update_document_status(
        ...         session, 1, "parsed", parsed_at=datetime.now()
        ...     )
    """
    doc = session.query(Document).filter(Document.id == document_id).first()
    if not doc:
        logger.error(f"文档不存在: id={document_id}")
        return False

    doc.status = status
    if error_message:
        doc.error_message = error_message
        doc.retry_count += 1

    for key, value in kwargs.items():
        if hasattr(doc, key):
            setattr(doc, key, value)

    session.flush()
    logger.debug(f"更新文档状态: id={document_id}, status={status}")
    return True


def get_documents_by_stock(
    session: Session,
    stock_code: str,
    year: Optional[int] = None,
    quarter: Optional[int] = None
) -> List[Document]:
    """
    获取指定股票的文档

    Args:
        session: 数据库会话
        stock_code: 股票代码
        year: 年份（可选）
        quarter: 季度（可选）

    Returns:
        Document 列表
    """
    query = session.query(Document).filter(Document.stock_code == stock_code)

    if year:
        query = query.filter(Document.year == year)
    if quarter:
        query = query.filter(Document.quarter == quarter)

    return query.order_by(desc(Document.year), desc(Document.quarter)).all()


# ==================== DocumentChunk CRUD ====================

def create_document_chunk(
    session: Session,
    document_id: int,
    chunk_index: int,
    chunk_text: str,
    chunk_size: int,
    vector_id: Optional[str] = None,
    embedding_model: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> DocumentChunk:
    """创建文档分块"""
    chunk = DocumentChunk(
        document_id=document_id,
        chunk_index=chunk_index,
        chunk_text=chunk_text,
        chunk_size=chunk_size,
        vector_id=vector_id,
        embedding_model=embedding_model,
        extra_metadata=metadata or {}
    )

    session.add(chunk)
    session.flush()
    logger.debug(f"创建文档分块: document_id={document_id}, chunk_index={chunk_index}")
    return chunk


def get_document_chunks(session: Session, document_id: int) -> List[DocumentChunk]:
    """获取文档的所有分块"""
    return session.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id
    ).order_by(DocumentChunk.chunk_index).all()


def update_chunk_vector_id(
    session: Session,
    chunk_id: int,
    vector_id: str,
    embedding_model: str
) -> bool:
    """更新分块的向量 ID"""
    chunk = session.query(DocumentChunk).filter(DocumentChunk.id == chunk_id).first()
    if not chunk:
        return False

    chunk.vector_id = vector_id
    chunk.embedding_model = embedding_model
    chunk.vectorized_at = datetime.now()
    session.flush()
    return True


# ==================== CrawlTask CRUD ====================

def create_crawl_task(
    session: Session,
    task_type: str,
    stock_code: str,
    company_name: str,
    market: str,
    doc_type: str,
    year: int,
    quarter: Optional[int] = None,
    metadata: Optional[Dict] = None
) -> CrawlTask:
    """创建爬取任务"""
    task = CrawlTask(
        task_type=task_type,
        stock_code=stock_code,
        company_name=company_name,
        market=market,
        doc_type=doc_type,
        year=year,
        quarter=quarter,
        status='pending',
        extra_metadata=metadata or {}
    )

    session.add(task)
    session.flush()
    logger.debug(f"创建爬取任务: stock_code={stock_code}, year={year}, quarter={quarter}")
    return task


def update_crawl_task_status(
    session: Session,
    task_id: int,
    status: str,
    success: bool = False,
    document_id: Optional[int] = None,
    error_message: Optional[str] = None
) -> bool:
    """更新爬取任务状态"""
    task = session.query(CrawlTask).filter(CrawlTask.id == task_id).first()
    if not task:
        return False

    task.status = status
    task.success = success
    if document_id:
        task.document_id = document_id
    if error_message:
        task.error_message = error_message

    if status == 'running' and not task.started_at:
        task.started_at = datetime.now()
    elif status in ['completed', 'failed']:
        task.completed_at = datetime.now()
        if task.started_at:
            task.duration_seconds = (task.completed_at - task.started_at).total_seconds()

    session.flush()
    return True


# ==================== ParseTask CRUD ====================

def create_parse_task(
    session: Session,
    document_id: int,
    parser_type: str,
    parser_version: Optional[str] = None
) -> ParseTask:
    """创建解析任务"""
    task = ParseTask(
        document_id=document_id,
        parser_type=parser_type,
        parser_version=parser_version,
        status='pending'
    )

    session.add(task)
    session.flush()
    logger.debug(f"创建解析任务: document_id={document_id}, parser_type={parser_type}")
    return task


def get_pending_parse_tasks(session: Session, limit: int = 10) -> List[ParseTask]:
    """获取待解析任务"""
    return session.query(ParseTask).filter(
        ParseTask.status == 'pending'
    ).order_by(ParseTask.created_at).limit(limit).all()


# ==================== ValidationLog CRUD ====================

def create_validation_log(
    session: Session,
    document_id: int,
    validation_stage: str,
    validation_rule: str,
    validation_level: str,
    passed: bool,
    message: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> ValidationLog:
    """创建验证日志"""
    log = ValidationLog(
        document_id=document_id,
        validation_stage=validation_stage,
        validation_rule=validation_rule,
        validation_level=validation_level,
        passed=passed,
        message=message,
        extra_metadata=metadata or {}
    )

    session.add(log)
    session.flush()
    return log


def get_validation_logs(
    session: Session,
    document_id: int,
    validation_stage: Optional[str] = None
) -> List[ValidationLog]:
    """获取验证日志"""
    query = session.query(ValidationLog).filter(ValidationLog.document_id == document_id)

    if validation_stage:
        query = query.filter(ValidationLog.validation_stage == validation_stage)

    return query.order_by(ValidationLog.created_at).all()


# ==================== QuarantineRecord CRUD ====================

def create_quarantine_record(
    session: Session,
    document_id: int,
    source_type: str,
    doc_type: str,
    original_path: str,
    quarantine_path: str,
    failure_stage: str,
    failure_reason: str,
    failure_details: Optional[str] = None
) -> QuarantineRecord:
    """创建隔离记录"""
    record = QuarantineRecord(
        document_id=document_id,
        source_type=source_type,
        doc_type=doc_type,
        original_path=original_path,
        quarantine_path=quarantine_path,
        failure_stage=failure_stage,
        failure_reason=failure_reason,
        failure_details=failure_details,
        status='pending'
    )

    session.add(record)
    session.flush()
    logger.warning(f"创建隔离记录: document_id={document_id}, reason={failure_reason}")
    return record


def get_quarantine_records(
    session: Session,
    status: str = 'pending',
    limit: int = 100
) -> List[QuarantineRecord]:
    """获取隔离记录"""
    return session.query(QuarantineRecord).filter(
        QuarantineRecord.status == status
    ).order_by(QuarantineRecord.quarantine_time).limit(limit).all()
