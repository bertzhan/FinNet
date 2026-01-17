# -*- coding: utf-8 -*-
"""
CRUD 操作辅助类
提供常用的数据库增删改查操作
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

from src.storage.metadata.models import (
    Document, DocumentChunk, CrawlTask, ParseTask,
    ValidationLog, QuarantineRecord, EmbeddingTask,
    ParsedDocument, Image, ImageAnnotation
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
        Document.crawled_at.asc()
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
    document_id: int,
    parse_task_id: int,
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


def get_parsed_document_by_id(session: Session, parsed_doc_id: int) -> Optional[ParsedDocument]:
    """获取解析文档（按ID）"""
    return session.query(ParsedDocument).filter(ParsedDocument.id == parsed_doc_id).first()


def get_parsed_documents_by_document_id(
    session: Session,
    document_id: int,
    status: Optional[str] = None
) -> List[ParsedDocument]:
    """获取文档的所有解析结果"""
    query = session.query(ParsedDocument).filter(ParsedDocument.document_id == document_id)
    if status:
        query = query.filter(ParsedDocument.status == status)
    return query.order_by(desc(ParsedDocument.parsed_at)).all()


def get_latest_parsed_document(
    session: Session,
    document_id: int
) -> Optional[ParsedDocument]:
    """获取文档的最新解析结果"""
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
    parsed_document_id: int,
    document_id: int,
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
    parsed_document_id: int
) -> List[Image]:
    """获取解析文档的所有图片"""
    return session.query(Image).filter(
        Image.parsed_document_id == parsed_document_id
    ).order_by(Image.image_index).all()


def get_images_by_document_id(
    session: Session,
    document_id: int
) -> List[Image]:
    """获取文档的所有图片"""
    return session.query(Image).filter(
        Image.document_id == document_id
    ).order_by(Image.page_number, Image.image_index).all()


def get_image_by_id(session: Session, image_id: int) -> Optional[Image]:
    """获取图片（按ID）"""
    return session.query(Image).filter(Image.id == image_id).first()


# ==================== ImageAnnotation CRUD ====================

def create_image_annotation(
    session: Session,
    image_id: int,
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
    image_id: int,
    status: Optional[str] = None
) -> List[ImageAnnotation]:
    """获取图片的所有标注"""
    query = session.query(ImageAnnotation).filter(ImageAnnotation.image_id == image_id)
    if status:
        query = query.filter(ImageAnnotation.status == status)
    return query.order_by(desc(ImageAnnotation.annotation_version)).all()


def get_latest_image_annotation(
    session: Session,
    image_id: int
) -> Optional[ImageAnnotation]:
    """获取图片的最新标注"""
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
