# -*- coding: utf-8 -*-
"""
CRUD 操作辅助类
提供常用的数据库增删改查操作
"""

import uuid
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

from src.storage.metadata.models import (
    Document, DocumentChunk, CrawlTask, ParseTask,
    ValidationLog, QuarantineRecord, EmbeddingTask,
    ParsedDocument, Image, ImageAnnotation, ListedCompany
)
from src.common.constants import DocumentStatus
from src.common.logger import get_logger

logger = get_logger(__name__)


# ==================== UUID 辅助函数 ====================

def _to_uuid(value: Union[uuid.UUID, str]) -> uuid.UUID:
    """将字符串或 UUID 转换为 UUID 对象"""
    if isinstance(value, str):
        return uuid.UUID(value)
    return value


# ==================== Document CRUD ====================

def create_document(
    session: Session,
    stock_code: str,
    company_name: str,
    market: str,
    doc_type: str,
    year: int,
    quarter: Optional[int],
    minio_object_path: str,
    file_size: Optional[int] = None,
    file_hash: Optional[str] = None,
    metadata: Optional[Dict] = None,
    source_url: Optional[str] = None,
    publish_date: Optional[datetime] = None
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
        minio_object_path: MinIO 对象路径
        file_size: 文件大小
        file_hash: 文件哈希
        metadata: 元数据（用于提取source_url和publish_date，不会保存到数据库）
        source_url: 文档来源URL（如果为None，会尝试从metadata中提取）
        publish_date: 文档发布日期（如果为None，会尝试从metadata中提取）

    Returns:
        Document 对象

    Example:
        >>> with get_postgres_client().get_session() as session:
        ...     doc = create_document(
        ...         session, "000001", "平安银行", "a_share",
        ...         "quarterly_reports", 2023, 3,
        ...         minio_object_path="bronze/a_share/quarterly_reports/2023/Q3/000001/report.pdf",
        ...         source_url="https://www.cninfo.com.cn/...",
        ...         publish_date=datetime(2023, 10, 1)
        ...     )
        ...     print(doc.id)
    """
    # 如果source_url未提供，尝试从metadata中提取
    if source_url is None and metadata:
        source_url = metadata.get('source_url') or metadata.get('doc_url') or metadata.get('pdf_url')
    
    # 如果publish_date未提供，尝试从metadata中提取
    if publish_date is None and metadata:
        # 尝试多种日期字段名和格式
        date_str = metadata.get('publication_date_iso') or metadata.get('pub_date_iso') or metadata.get('publish_date_iso')
        if date_str:
            try:
                # 尝试解析ISO格式日期字符串
                if isinstance(date_str, str):
                    # ISO格式: "2023-10-01T00:00:00" 或 "2023-10-01"
                    if 'T' in date_str:
                        publish_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    else:
                        publish_date = datetime.fromisoformat(date_str)
                elif isinstance(date_str, datetime):
                    publish_date = date_str
            except (ValueError, TypeError) as e:
                logger.warning(f"无法解析发布日期: {date_str}, 错误: {e}")
    
    doc = Document(
        stock_code=stock_code,
        company_name=company_name,
        market=market,
        doc_type=doc_type,
        year=year,
        quarter=quarter,
        minio_object_path=minio_object_path,
        file_size=file_size,
        file_hash=file_hash,
        source_url=source_url,
        publish_date=publish_date,
        status=DocumentStatus.CRAWLED.value,
        crawled_at=datetime.now()
    )

    session.add(doc)
    session.flush()  # 获取 ID
    logger.debug(f"创建文档记录: id={doc.id}, stock_code={stock_code}")
    return doc


def get_document_by_id(session: Session, document_id: Union[uuid.UUID, str]) -> Optional[Document]:
    """获取文档（按 ID）"""
    document_id = _to_uuid(document_id)
    return session.query(Document).filter(Document.id == document_id).first()


def get_document_by_path(session: Session, minio_object_path: str) -> Optional[Document]:
    """获取文档（按 MinIO 路径）"""
    return session.query(Document).filter(Document.minio_object_path == minio_object_path).first()


def get_document_by_task(
    session: Session,
    stock_code: str,
    market: str,
    doc_type: str,
    year: Optional[int] = None,
    quarter: Optional[int] = None
) -> Optional[Document]:
    """
    根据任务信息查询文档（用于去重检查）
    
    Args:
        session: 数据库会话
        stock_code: 股票代码
        market: 市场类型
        doc_type: 文档类型
        year: 年份（IPO类型可能为None）
        quarter: 季度（IPO类型可能为None）
        
    Returns:
        Document 对象，如果不存在则返回 None
    """
    query = session.query(Document).filter(
        Document.stock_code == stock_code,
        Document.market == market,
        Document.doc_type == doc_type
    )
    
    # IPO 类型：只根据 stock_code、market、doc_type 查询
    # 因为 IPO 的 year 和 quarter 可能不确定，或者数据库中存储的值不一致
    if doc_type == 'ipo_prospectus':
        # IPO 类型不需要 year 和 quarter，直接返回第一个匹配的
        # 按创建时间倒序，返回最新的
        return query.order_by(Document.created_at.desc()).first()
    
    # 定期报告：需要精确匹配 year 和 quarter
    if year is not None:
        query = query.filter(Document.year == year)
    if quarter is not None:
        query = query.filter(Document.quarter == quarter)
    
    return query.first()


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
        Document.crawled_at.asc()
    ).limit(limit).offset(offset).all()


def update_document_status(
    session: Session,
    document_id: Union[uuid.UUID, str],
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
    document_id = _to_uuid(document_id)
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


def get_document_id_by_filters(
    session: Session,
    stock_code: str,
    year: int,
    quarter: Optional[int],
    doc_type: str
) -> Optional[uuid.UUID]:
    """
    根据stock_code, year, quarter, doc_type查询document_id
    
    Args:
        session: 数据库会话
        stock_code: 股票代码
        year: 年份
        quarter: 季度（可选，如果为None则查询年度文档）
        doc_type: 文档类型
        
    Returns:
        document_id (UUID) 如果找到，否则返回 None
        
    Example:
        >>> with get_postgres_client().get_session() as session:
        ...     doc_id = get_document_id_by_filters(
        ...         session, "000001", 2023, 3, "quarterly_reports"
        ...     )
        ...     print(doc_id)
    """
    query = session.query(Document.id).filter(
        Document.stock_code == stock_code,
        Document.year == year,
        Document.doc_type == doc_type
    )
    
    if quarter is not None:
        query = query.filter(Document.quarter == quarter)
    else:
        # 如果quarter为None，查询年度文档
        # 注意：年报可能存储为quarter=NULL或quarter=4，需要同时匹配两种情况
        if doc_type == "annual_reports":
            # 对于年报，查询quarter为NULL或4的文档
            query = query.filter(
                or_(
                    Document.quarter.is_(None),
                    Document.quarter == 4
                )
            )
        else:
            # 对于其他文档类型，只查询quarter为NULL的文档
            query = query.filter(Document.quarter.is_(None))
    
    result = query.first()
    return result[0] if result else None


# ==================== DocumentChunk CRUD ====================

def create_document_chunk(
    session: Session,
    document_id: Union[uuid.UUID, str],
    chunk_index: int,
    chunk_text: str,
    chunk_size: int,
    title: Optional[str] = None,
    title_level: Optional[int] = None,
    heading_index: Optional[int] = None,
    parent_chunk_id: Optional[Union[uuid.UUID, str]] = None,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    is_table: bool = False,
    embedding_model: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> DocumentChunk:
    """
    创建文档分块
    
    注意：向量化状态通过 vectorized_at 字段判断。
    vector_id 字段已移除，因为 Milvus 使用 chunk_id 作为主键。
    """
    document_id = _to_uuid(document_id)
    if parent_chunk_id:
        parent_chunk_id = _to_uuid(parent_chunk_id)
    
    chunk = DocumentChunk(
        document_id=document_id,
        chunk_index=chunk_index,
        chunk_text=chunk_text,
        chunk_size=chunk_size,
        title=title,
        title_level=title_level,
        heading_index=heading_index,
        parent_chunk_id=parent_chunk_id,
        start_line=start_line,
        end_line=end_line,
        is_table=is_table,
        embedding_model=embedding_model,
        extra_metadata=metadata or {}
    )

    session.add(chunk)
    session.flush()
    logger.debug(f"创建文档分块: document_id={document_id}, chunk_index={chunk_index}")
    return chunk


def get_document_chunks(session: Session, document_id: Union[uuid.UUID, str]) -> List[DocumentChunk]:
    """获取文档的所有分块"""
    document_id = _to_uuid(document_id)
    return session.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id
    ).order_by(DocumentChunk.chunk_index).all()


def create_document_chunks_batch(
    session: Session,
    chunks_data: List[Dict]
) -> List[DocumentChunk]:
    """
    批量创建文档分块
    
    Args:
        session: 数据库会话
        chunks_data: 分块数据列表，每个字典包含：
            - document_id: 文档ID
            - chunk_index: 分块索引
            - chunk_text: 分块文本
            - chunk_size: 分块大小
            - title: 分块标题（可选）
            - title_level: 标题层级（可选）
            - heading_index: 标题索引（可选）
            - parent_chunk_id: 父分块ID（可选）
            - start_line: 起始行号（可选）
            - end_line: 结束行号（可选）
            - is_table: 是否是表格（可选，默认 False）
            - metadata: 额外元数据（可选）
    
    Returns:
        创建的分块列表
    """
    chunks = []
    for chunk_data in chunks_data:
        document_id = _to_uuid(chunk_data['document_id'])
        parent_chunk_id = _to_uuid(chunk_data.get('parent_chunk_id')) if chunk_data.get('parent_chunk_id') else None
        
        chunk = DocumentChunk(
            document_id=document_id,
            chunk_index=chunk_data['chunk_index'],
            chunk_text=chunk_data['chunk_text'],
            chunk_size=chunk_data['chunk_size'],
            title=chunk_data.get('title'),
            title_level=chunk_data.get('title_level'),
            heading_index=chunk_data.get('heading_index'),
            parent_chunk_id=parent_chunk_id,
            start_line=chunk_data.get('start_line'),
            end_line=chunk_data.get('end_line'),
            is_table=chunk_data.get('is_table', False),
            extra_metadata=chunk_data.get('metadata', {})
        )
        chunks.append(chunk)
        session.add(chunk)
    
    session.flush()
    logger.info(f"批量创建 {len(chunks)} 个文档分块")
    return chunks


def delete_document_chunks(
    session: Session,
    document_id: Union[uuid.UUID, str]
) -> int:
    """
    删除文档的所有分块
    
    Args:
        session: 数据库会话
        document_id: 文档ID
    
    Returns:
        删除的分块数量
    """
    document_id = _to_uuid(document_id)
    chunks = session.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id
    ).all()
    
    count = len(chunks)
    for chunk in chunks:
        session.delete(chunk)
    
    session.flush()
    logger.info(f"删除文档 {document_id} 的 {count} 个分块")
    return count


def update_chunk_embedding(
    session: Session,
    chunk_id: Union[uuid.UUID, str],
    embedding_model: str
) -> bool:
    """
    更新分块的向量化信息
    
    注意：不再更新 vector_id，因为 Milvus 使用 chunk_id 作为主键
    使用 vectorized_at 字段来判断是否已向量化
    """
    chunk_id = _to_uuid(chunk_id)
    chunk = session.query(DocumentChunk).filter(DocumentChunk.id == chunk_id).first()
    if not chunk:
        return False

    chunk.embedding_model = embedding_model
    chunk.vectorized_at = datetime.now()
    session.flush()
    return True


# 保留旧函数名以向后兼容（已废弃）
def update_chunk_vector_id(
    session: Session,
    chunk_id: Union[uuid.UUID, str],
    vector_id: str,
    embedding_model: str
) -> bool:
    """
    更新分块的向量 ID（已废弃）
    
    注意：此函数已废弃，请使用 update_chunk_embedding
    vector_id 参数将被忽略，因为 Milvus 使用 chunk_id 作为主键
    """
    return update_chunk_embedding(session, chunk_id, embedding_model)


def update_parsed_document_chunk_info(
    session: Session,
    parsed_document_id: Union[uuid.UUID, str],
    structure_json_path: Optional[str] = None,
    chunks_json_path: Optional[str] = None,
    structure_json_hash: Optional[str] = None,
    chunks_json_hash: Optional[str] = None,
    chunks_count: Optional[int] = None
) -> Optional[ParsedDocument]:
    """
    更新 ParsedDocument 的分块相关字段
    
    Args:
        session: 数据库会话
        parsed_document_id: ParsedDocument ID
        structure_json_path: structure.json 文件路径
        chunks_json_path: chunks.json 文件路径
        structure_json_hash: structure.json 文件哈希
        chunks_json_hash: chunks.json 文件哈希
        chunks_count: 分块数量
    
    Returns:
        更新后的 ParsedDocument 对象，如果不存在则返回 None
    """
    parsed_document_id = _to_uuid(parsed_document_id)
    parsed_doc = session.query(ParsedDocument).filter(
        ParsedDocument.id == parsed_document_id
    ).first()
    
    if not parsed_doc:
        logger.warning(f"ParsedDocument 不存在: {parsed_document_id}")
        return None
    
    if structure_json_path is not None:
        parsed_doc.structure_json_path = structure_json_path
    if chunks_json_path is not None:
        parsed_doc.chunks_json_path = chunks_json_path
    if structure_json_hash is not None:
        parsed_doc.structure_json_hash = structure_json_hash
    if chunks_json_hash is not None:
        parsed_doc.chunks_json_hash = chunks_json_hash
    if chunks_count is not None:
        parsed_doc.chunks_count = chunks_count
    
    parsed_doc.chunked_at = datetime.now()
    session.flush()
    
    logger.debug(f"更新 ParsedDocument 分块信息: {parsed_document_id}")
    return parsed_doc


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
    document_id: Optional[Union[uuid.UUID, str]] = None,
    error_message: Optional[str] = None
) -> bool:
    """更新爬取任务状态"""
    task = session.query(CrawlTask).filter(CrawlTask.id == task_id).first()
    if not task:
        return False

    task.status = status
    task.success = success
    if document_id:
        task.document_id = _to_uuid(document_id)
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
    document_id: Union[uuid.UUID, str],
    parser_type: str,
    parser_version: Optional[str] = None
) -> ParseTask:
    """创建解析任务"""
    document_id = _to_uuid(document_id)
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
    document_id: Union[uuid.UUID, str],
    validation_stage: str,
    validation_rule: str,
    validation_level: str,
    passed: bool,
    message: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> ValidationLog:
    """创建验证日志"""
    document_id = _to_uuid(document_id)
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
    document_id: Union[uuid.UUID, str],
    validation_stage: Optional[str] = None
) -> List[ValidationLog]:
    """获取验证日志"""
    document_id = _to_uuid(document_id)
    query = session.query(ValidationLog).filter(ValidationLog.document_id == document_id)

    if validation_stage:
        query = query.filter(ValidationLog.validation_stage == validation_stage)

    return query.order_by(ValidationLog.created_at).all()


# ==================== QuarantineRecord CRUD ====================

def create_quarantine_record(
    session: Session,
    document_id: Optional[Union[uuid.UUID, str]],
    source_type: str,
    doc_type: str,
    original_path: str,
    quarantine_path: str,
    failure_stage: str,
    failure_reason: str,
    failure_details: Optional[str] = None
) -> QuarantineRecord:
    """创建隔离记录"""
    if document_id is not None:
        document_id = _to_uuid(document_id)
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


def get_quarantine_record_by_id(
    session: Session,
    record_id: int
) -> Optional[QuarantineRecord]:
    """根据ID获取隔离记录"""
    return session.query(QuarantineRecord).filter(
        QuarantineRecord.id == record_id
    ).first()


def update_quarantine_record_status(
    session: Session,
    record_id: int,
    status: str,
    handler: Optional[str] = None,
    resolution: Optional[str] = None
) -> Optional[QuarantineRecord]:
    """更新隔离记录状态"""
    record = session.query(QuarantineRecord).filter(
        QuarantineRecord.id == record_id
    ).first()
    
    if not record:
        return None
    
    record.status = status
    if handler:
        record.handler = handler
    if resolution:
        record.resolution = resolution
    record.resolution_time = datetime.now()
    
    session.flush()
    return record


# ==================== ParsedDocument CRUD ====================

def create_parsed_document(
    session: Session,
    document_id: Union[uuid.UUID, str],
    parse_task_id: Union[uuid.UUID, str],
    content_json_path: str,
    content_json_hash: str,
    source_document_hash: str,
    parser_type: str,
    parser_version: Optional[str] = None,
    markdown_path: Optional[str] = None,
    markdown_hash: Optional[str] = None,
    middle_json_path: Optional[str] = None,
    model_json_path: Optional[str] = None,
    image_folder_path: Optional[str] = None,
    text_length: int = 0,
    tables_count: int = 0,
    images_count: int = 0,
    pages_count: int = 0,
    parsing_quality_score: Optional[float] = None,
    has_tables: bool = False,
    has_images: bool = False,
    status: str = 'active'
) -> ParsedDocument:
    """
    创建解析文档记录
    
    Args:
        session: 数据库会话
        document_id: 文档ID
        parse_task_id: 解析任务ID
        content_json_path: JSON文件路径
        content_json_hash: JSON文件哈希
        source_document_hash: 源PDF哈希
        parser_type: 解析器类型
        parser_version: 解析器版本
        markdown_path: Markdown文件路径（可选）
        markdown_hash: Markdown文件哈希（可选）
        image_folder_path: 图片文件夹路径（可选）
        text_length: 文本长度
        tables_count: 表格数量
        images_count: 图片数量
        pages_count: 页数
        parsing_quality_score: 解析质量评分
        has_tables: 是否包含表格
        has_images: 是否包含图片
        status: 状态
    
    Returns:
        ParsedDocument 对象
    """
    document_id = _to_uuid(document_id)
    parse_task_id = _to_uuid(parse_task_id)
    parsed_doc = ParsedDocument(
        document_id=document_id,
        parse_task_id=parse_task_id,
        content_json_path=content_json_path,
        content_json_hash=content_json_hash,
        source_document_hash=source_document_hash,
        parser_type=parser_type,
        parser_version=parser_version,
        markdown_path=markdown_path,
        markdown_hash=markdown_hash,
        middle_json_path=middle_json_path,
        model_json_path=model_json_path,
        image_folder_path=image_folder_path,
        text_length=text_length,
        tables_count=tables_count,
        images_count=images_count,
        pages_count=pages_count,
        parsing_quality_score=parsing_quality_score,
        has_tables=has_tables,
        has_images=has_images,
        status=status
    )
    
    session.add(parsed_doc)
    session.flush()
    logger.debug(f"创建解析文档记录: id={parsed_doc.id}, document_id={document_id}")
    return parsed_doc


def get_parsed_document_by_id(session: Session, parsed_doc_id: Union[uuid.UUID, str]) -> Optional[ParsedDocument]:
    """获取解析文档（按ID）"""
    parsed_doc_id = _to_uuid(parsed_doc_id)
    return session.query(ParsedDocument).filter(ParsedDocument.id == parsed_doc_id).first()


def get_parsed_documents_by_document_id(
    session: Session,
    document_id: Union[uuid.UUID, str],
    status: Optional[str] = None
) -> List[ParsedDocument]:
    """获取文档的所有解析结果"""
    document_id = _to_uuid(document_id)
    query = session.query(ParsedDocument).filter(ParsedDocument.document_id == document_id)
    if status:
        query = query.filter(ParsedDocument.status == status)
    return query.order_by(desc(ParsedDocument.parsed_at)).all()


def get_latest_parsed_document(
    session: Session,
    document_id: Union[uuid.UUID, str]
) -> Optional[ParsedDocument]:
    """获取文档的最新解析结果"""
    document_id = _to_uuid(document_id)
    return session.query(ParsedDocument).filter(
        ParsedDocument.document_id == document_id,
        ParsedDocument.status == 'active'
    ).order_by(desc(ParsedDocument.parsed_at)).first()


def update_parsed_document_status(
    session: Session,
    parsed_doc_id: int,
    status: str
) -> bool:
    """更新解析文档状态"""
    parsed_doc = session.query(ParsedDocument).filter(ParsedDocument.id == parsed_doc_id).first()
    if not parsed_doc:
        return False
    
    parsed_doc.status = status
    parsed_doc.updated_at = datetime.now()
    session.flush()
    return True


# ==================== Image CRUD ====================

def create_image(
    session: Session,
    parsed_document_id: Union[uuid.UUID, str],
    document_id: Union[uuid.UUID, str],
    image_index: int,
    filename: str,
    file_path: str,
    page_number: int,
    file_hash: Optional[str] = None,
    bbox: Optional[Dict] = None,
    description: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    file_size: Optional[int] = None
) -> Image:
    """
    创建图片记录
    
    Args:
        session: 数据库会话
        parsed_document_id: 解析文档ID
        document_id: 文档ID
        image_index: 图片序号
        filename: 文件名
        file_path: MinIO完整路径
        page_number: 页码
        file_hash: 文件哈希
        bbox: 边界框
        description: 描述
        width: 宽度
        height: 高度
        file_size: 文件大小
    
    Returns:
        Image 对象
    """
    parsed_document_id = _to_uuid(parsed_document_id)
    document_id = _to_uuid(document_id)
    image = Image(
        parsed_document_id=parsed_document_id,
        document_id=document_id,
        image_index=image_index,
        filename=filename,
        file_path=file_path,
        page_number=page_number,
        file_hash=file_hash,
        bbox=bbox,
        description=description,
        width=width,
        height=height,
        file_size=file_size
    )
    
    session.add(image)
    session.flush()
    logger.debug(f"创建图片记录: id={image.id}, filename={filename}")
    return image


def get_images_by_parsed_document(
    session: Session,
    parsed_document_id: Union[uuid.UUID, str]
) -> List[Image]:
    """获取解析文档的所有图片"""
    parsed_document_id = _to_uuid(parsed_document_id)
    return session.query(Image).filter(
        Image.parsed_document_id == parsed_document_id
    ).order_by(Image.image_index).all()


def get_images_by_document_id(
    session: Session,
    document_id: Union[uuid.UUID, str]
) -> List[Image]:
    """获取文档的所有图片"""
    return session.query(Image).filter(
        Image.document_id == document_id
    ).order_by(Image.page_number, Image.image_index).all()


def get_image_by_id(session: Session, image_id: Union[uuid.UUID, str]) -> Optional[Image]:
    """获取图片（按ID）"""
    image_id = _to_uuid(image_id)
    return session.query(Image).filter(Image.id == image_id).first()


# ==================== ImageAnnotation CRUD ====================

def create_image_annotation(
    session: Session,
    image_id: Union[uuid.UUID, str],
    category: str,
    annotator_type: str,
    annotator_id: Optional[str] = None,
    annotator_name: Optional[str] = None,
    subcategory: Optional[str] = None,
    confidence: Optional[float] = None,
    annotation_text: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict] = None,
    status: str = 'pending'
) -> ImageAnnotation:
    """
    创建图片标注
    
    Args:
        session: 数据库会话
        image_id: 图片ID
        category: 分类类别
        annotator_type: 标注者类型（human/ai/auto）
        annotator_id: 标注者ID
        annotator_name: 标注者名称
        subcategory: 子类别
        confidence: 置信度
        annotation_text: 标注文本
        tags: 标签列表
        metadata: 元数据
        status: 状态
    
    Returns:
        ImageAnnotation 对象
    """
    image_id = _to_uuid(image_id)
    # 获取当前最大版本号
    max_version = session.query(
        func.max(ImageAnnotation.annotation_version)
    ).filter(
        ImageAnnotation.image_id == image_id
    ).scalar() or 0
    
    annotation = ImageAnnotation(
        image_id=image_id,
        annotation_version=max_version + 1,
        category=category,
        annotator_type=annotator_type,
        annotator_id=annotator_id,
        annotator_name=annotator_name,
        subcategory=subcategory,
        confidence=confidence,
        annotation_text=annotation_text,
        tags=tags or [],
        extra_metadata=metadata or {},
        status=status
    )
    
    session.add(annotation)
    session.flush()
    logger.debug(f"创建图片标注: id={annotation.id}, image_id={image_id}, category={category}")
    return annotation


def get_image_annotations_by_image_id(
    session: Session,
    image_id: Union[uuid.UUID, str],
    status: Optional[str] = None
) -> List[ImageAnnotation]:
    """获取图片的所有标注"""
    image_id = _to_uuid(image_id)
    query = session.query(ImageAnnotation).filter(ImageAnnotation.image_id == image_id)
    if status:
        query = query.filter(ImageAnnotation.status == status)
    return query.order_by(desc(ImageAnnotation.annotation_version)).all()


def get_latest_image_annotation(
    session: Session,
    image_id: Union[uuid.UUID, str]
) -> Optional[ImageAnnotation]:
    """获取图片的最新标注"""
    image_id = _to_uuid(image_id)
    return session.query(ImageAnnotation).filter(
        ImageAnnotation.image_id == image_id,
        ImageAnnotation.status == 'approved'
    ).order_by(desc(ImageAnnotation.annotation_version)).first()


def update_image_annotation_status(
    session: Session,
    annotation_id: int,
    status: str,
    reviewed_by: Optional[str] = None
) -> bool:
    """更新图片标注状态"""
    annotation = session.query(ImageAnnotation).filter(ImageAnnotation.id == annotation_id).first()
    if not annotation:
        return False
    
    annotation.status = status
    if reviewed_by:
        annotation.reviewed_by = reviewed_by
        annotation.reviewed_at = datetime.now()
    annotation.updated_at = datetime.now()
    session.flush()
    return True


# ==================== ListedCompany CRUD ====================

def upsert_listed_company(
    session: Session,
    code: str,
    name: str,
    # stock_individual_basic_info_xq 返回的所有字段
    org_id: Optional[str] = None,
    org_name_cn: Optional[str] = None,
    org_short_name_cn: Optional[str] = None,
    org_name_en: Optional[str] = None,
    org_short_name_en: Optional[str] = None,
    pre_name_cn: Optional[str] = None,
    main_operation_business: Optional[str] = None,
    operating_scope: Optional[str] = None,
    org_cn_introduction: Optional[str] = None,
    telephone: Optional[str] = None,
    postcode: Optional[str] = None,
    fax: Optional[str] = None,
    email: Optional[str] = None,
    org_website: Optional[str] = None,
    reg_address_cn: Optional[str] = None,
    reg_address_en: Optional[str] = None,
    office_address_cn: Optional[str] = None,
    office_address_en: Optional[str] = None,
    legal_representative: Optional[str] = None,
    general_manager: Optional[str] = None,
    secretary: Optional[str] = None,
    chairman: Optional[str] = None,
    executives_nums: Optional[int] = None,
    district_encode: Optional[str] = None,
    provincial_name: Optional[str] = None,
    actual_controller: Optional[str] = None,
    classi_name: Optional[str] = None,
    established_date: Optional[int] = None,
    listed_date: Optional[int] = None,
    reg_asset: Optional[float] = None,
    staff_num: Optional[int] = None,
    actual_issue_vol: Optional[float] = None,
    issue_price: Optional[float] = None,
    actual_rc_net_amt: Optional[float] = None,
    pe_after_issuing: Optional[float] = None,
    online_success_rate_of_issue: Optional[float] = None,
    currency_encode: Optional[str] = None,
    currency: Optional[str] = None,
    affiliate_industry: Optional[Dict[str, Any]] = None,
) -> ListedCompany:
    """
    插入或更新上市公司信息
    
    注意：code 是主键，如果已存在会自动更新，不存在则创建
    数据来源：akshare stock_individual_basic_info_xq 接口
    
    Args:
        session: 数据库会话
        code: 股票代码（主键）
        name: 公司简称（如：平安银行）
        ... 其他所有字段（来自 stock_individual_basic_info_xq）
        
    Returns:
        ListedCompany 对象
        
    Example:
        >>> with get_postgres_client().get_session() as session:
        ...     company = upsert_listed_company(
        ...         session, "000001", "平安银行",
        ...         org_name_cn="平安银行股份有限公司"
        ...     )
        ...     print(company.code)
    """
    # 清理 name 字段：去除所有空格（包括中间的空格）
    if name:
        name = name.replace(" ", "").replace("　", "")  # 去除半角和全角空格
    
    # 使用主键查询（更高效）
    company = session.get(ListedCompany, code)
    
    # 准备更新数据字典（只包含非 None 的值）
    update_data = {
        'name': name,
        'updated_at': datetime.now()
    }
    
    # 添加所有新字段
    field_mapping = {
        'org_id': org_id,
        'org_name_cn': org_name_cn,
        'org_short_name_cn': org_short_name_cn,
        'org_name_en': org_name_en,
        'org_short_name_en': org_short_name_en,
        'pre_name_cn': pre_name_cn,
        'main_operation_business': main_operation_business,
        'operating_scope': operating_scope,
        'org_cn_introduction': org_cn_introduction,
        'telephone': telephone,
        'postcode': postcode,
        'fax': fax,
        'email': email,
        'org_website': org_website,
        'reg_address_cn': reg_address_cn,
        'reg_address_en': reg_address_en,
        'office_address_cn': office_address_cn,
        'office_address_en': office_address_en,
        'legal_representative': legal_representative,
        'general_manager': general_manager,
        'secretary': secretary,
        'chairman': chairman,
        'executives_nums': executives_nums,
        'district_encode': district_encode,
        'provincial_name': provincial_name,
        'actual_controller': actual_controller,
        'classi_name': classi_name,
        'established_date': established_date,
        'listed_date': listed_date,
        'reg_asset': reg_asset,
        'staff_num': staff_num,
        'actual_issue_vol': actual_issue_vol,
        'issue_price': issue_price,
        'actual_rc_net_amt': actual_rc_net_amt,
        'pe_after_issuing': pe_after_issuing,
        'online_success_rate_of_issue': online_success_rate_of_issue,
        'currency_encode': currency_encode,
        'currency': currency,
        'affiliate_industry': affiliate_industry,
    }
    
    # 只添加非 None 的字段
    for key, value in field_mapping.items():
        if value is not None:
            update_data[key] = value
    
    if company:
        # 更新现有记录
        for key, value in update_data.items():
            setattr(company, key, value)
        logger.debug(f"更新上市公司: {code} - {name}")
    else:
        # 创建新记录
        company = ListedCompany(code=code, **update_data)
        session.add(company)
        logger.debug(f"新增上市公司: {code} - {name}")
    
    session.flush()
    return company


def get_listed_company_by_code(
    session: Session,
    code: str
) -> Optional[ListedCompany]:
    """
    根据股票代码获取上市公司信息
    
    Args:
        session: 数据库会话
        code: 股票代码
        
    Returns:
        ListedCompany 对象，如果不存在则返回 None
    """
    return session.query(ListedCompany).filter(ListedCompany.code == code).first()


def get_all_listed_companies(
    session: Session,
    limit: Optional[int] = None,
    offset: Optional[int] = None
) -> List[ListedCompany]:
    """
    获取所有上市公司列表
    
    Args:
        session: 数据库会话
        limit: 限制返回数量
        offset: 偏移量
        
    Returns:
        ListedCompany 对象列表
    """
    query = session.query(ListedCompany).order_by(ListedCompany.code)
    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)
    return query.all()


def _normalize_company_name(name: str) -> str:
    """
    规范化公司名称，用于匹配比较
    
    处理：
    - 去除所有空格（包括全角空格）
    - 去除末尾的 A/B/Ａ/Ｂ（股票后缀）
    - 去除特殊字符如 * （退市标记）
    - 去除常见企业后缀词（公司、集团、股份、有限公司等）
    """
    if not name:
        return ""
    # 去除空格
    normalized = name.replace(" ", "").replace("　", "")
    # 去除末尾的 A/B（半角和全角）
    if normalized and normalized[-1] in "ABＡＢab":
        normalized = normalized[:-1]
    # 去除开头的 * （退市标记）
    normalized = normalized.lstrip("*")
    # 去除 ST、*ST 标记
    for prefix in ["ST", "*ST"]:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
    
    # 去除常见企业后缀词（按长度从长到短排序，避免部分匹配）
    # 例如：先删除"股份有限公司"，再删除"有限公司"，再删除"公司"
    company_suffixes = [
        "股份有限公司",
        "有限责任公司",
        "有限公司",
        "集团公司",
        "集团股份",
        "集团",
        "股份公司",
        "股份",
        "公司",
        "控股公司",
        "控股集团",
    ]
    
    for suffix in company_suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]
            break  # 只删除一个后缀（最长匹配）
    
    return normalized


def search_listed_company(
    session: Session,
    company_name: str,
    max_candidates: int = 5
) -> List[ListedCompany]:
    """
    根据公司名称搜索上市公司（支持模糊匹配）
    
    返回所有匹配的公司列表（按匹配优先级排序）：
    - 列表长度为 1：唯一匹配，可直接使用
    - 列表长度 > 1：多个候选，需要用户选择
    - 列表为空：未找到匹配
    
    搜索策略（按优先级）：
    1. 精确匹配（name, org_name_cn, org_short_name_cn, org_name_en, org_short_name_en）
    2. 规范化后精确匹配（去除空格、ST标记、股票后缀等）
    3. 名称包含查询词（如：查询"平安" -> 匹配"平安银行"）
    4. 查询词包含名称（如：查询"深圳振业" -> 匹配"深振业"）
    5. 曾用名匹配（pre_name_cn）
    
    特殊处理：
    - 自动处理空格（如 "万  科Ａ" -> "万科"）
    - 自动处理股票后缀（如 "深振业Ａ" -> "深振业"）
    - 自动处理 ST 标记
    
    Args:
        session: 数据库会话
        company_name: 公司名称（可以是简称、全称、英文名或部分名称）
        max_candidates: 最大返回候选数量（默认 30）
        
    Returns:
        匹配的 ListedCompany 对象列表（按匹配优先级排序）
        
    Example:
        >>> with get_postgres_client().get_session() as session:
        ...     companies = search_listed_company(session, "平安银行")
        ...     if len(companies) == 1:
        ...         print(f"唯一匹配: {companies[0].code} - {companies[0].name}")
        ...     elif len(companies) > 1:
        ...         print(f"找到 {len(companies)} 个候选")
        ...     else:
        ...         print("未找到匹配")
    """
    # 预处理查询词
    query_name = company_name.strip().replace(" ", "").replace("　", "")
    query_normalized = _normalize_company_name(query_name)
    
    if not query_name:
        return []
    
    candidates = []
    seen_codes = set()  # 避免重复
    
    # 获取所有公司进行匹配（按 code 排序）
    all_companies = session.query(ListedCompany).order_by(ListedCompany.code).all()
    
    # 1. 精确匹配（所有字段）
    for company in all_companies:
        if company.code in seen_codes:
            continue
        
        fields_to_check = [
            company.name,
            company.org_name_cn,
            company.org_short_name_cn,
            company.org_name_en,
            company.org_short_name_en,
        ]
        
        for field_value in fields_to_check:
            if field_value and field_value == query_name:
                candidates.append(company)
                seen_codes.add(company.code)
                break
    
    # 2. 规范化后精确匹配
    if len(candidates) < max_candidates:
        for company in all_companies:
            if company.code in seen_codes:
                continue
            
            fields_to_check = [
                company.name,
                company.org_name_cn,
                company.org_short_name_cn,
                company.org_name_en,
                company.org_short_name_en,
            ]
            
            for field_value in fields_to_check:
                if field_value:
                    field_normalized = _normalize_company_name(field_value)
                    if field_normalized == query_normalized:
                        candidates.append(company)
                        seen_codes.add(company.code)
                        break
    
    # 3. 名称包含查询词
    if len(candidates) < max_candidates:
        for company in all_companies:
            if company.code in seen_codes:
                continue
            
            fields_to_check = [
                company.name,
                company.org_name_cn,
                company.org_short_name_cn,
                company.org_name_en,
                company.org_short_name_en,
            ]
            
            for field_value in fields_to_check:
                if field_value:
                    field_normalized = _normalize_company_name(field_value)
                    if query_normalized in field_normalized:
                        candidates.append(company)
                        seen_codes.add(company.code)
                        break
    
    # 4. 查询词包含名称
    if len(candidates) < max_candidates:
        for company in all_companies:
            if company.code in seen_codes:
                continue
            
            fields_to_check = [
                company.name,
                company.org_name_cn,
                company.org_short_name_cn,
                company.org_name_en,
                company.org_short_name_en,
            ]
            
            for field_value in fields_to_check:
                if field_value:
                    field_normalized = _normalize_company_name(field_value)
                    if field_normalized and field_normalized in query_normalized:
                        candidates.append(company)
                        seen_codes.add(company.code)
                        break
    
    # 5. 曾用名匹配
    if len(candidates) < max_candidates:
        for company in all_companies:
            if company.code in seen_codes:
                continue
            
            if company.pre_name_cn:
                former_list = [n.strip() for n in company.pre_name_cn.split(',')]
                for former in former_list:
                    former_normalized = _normalize_company_name(former)
                    if query_normalized == former_normalized or query_normalized in former_normalized or former_normalized in query_normalized:
                        candidates.append(company)
                        seen_codes.add(company.code)
                        break
    
    result = candidates[:max_candidates]
    logger.debug(f"公司搜索: {query_name} -> 找到 {len(result)} 个匹配")
    return result
