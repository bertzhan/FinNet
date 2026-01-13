# -*- coding: utf-8 -*-
"""
PostgreSQL 数据库模型
定义所有元数据表结构
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, Text,
    BigInteger, Float, JSON, Index, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

from src.common.constants import DocumentStatus, ValidationLevel, ValidationStage

Base = declarative_base()


class Document(Base):
    """
    文档元数据表
    存储所有爬取文档的基本信息
    """
    __tablename__ = 'documents'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 基本信息
    stock_code = Column(String(20), nullable=False, index=True)
    company_name = Column(String(200))
    market = Column(String(50), nullable=False, index=True)  # a_share, hk_stock, us_stock
    doc_type = Column(String(50), nullable=False, index=True)  # quarterly_reports, annual_reports, etc.
    year = Column(Integer, nullable=False, index=True)
    quarter = Column(Integer)  # 1-4, NULL for annual reports

    # MinIO 路径
    minio_object_name = Column(String(500), nullable=False, unique=True)
    file_size = Column(BigInteger)  # 字节
    file_hash = Column(String(64))  # MD5 或 SHA256

    # 状态管理
    status = Column(
        String(50),
        nullable=False,
        default=DocumentStatus.PENDING.value,
        index=True
    )

    # 时间戳
    created_at = Column(DateTime, nullable=False, default=func.now())
    crawled_at = Column(DateTime)
    parsed_at = Column(DateTime)
    vectorized_at = Column(DateTime)
    updated_at = Column(DateTime, onupdate=func.now())

    # 错误信息
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)

    # 元数据（JSON 格式）
    extra_metadata = Column(JSON)  # 发布日期、URL 等额外信息

    # 索引
    __table_args__ = (
        Index('idx_stock_year_quarter', 'stock_code', 'year', 'quarter'),
        Index('idx_status_created', 'status', 'created_at'),
        UniqueConstraint('stock_code', 'year', 'quarter', 'doc_type', name='uq_document'),
    )

    def __repr__(self):
        return f"<Document(id={self.id}, stock_code={self.stock_code}, year={self.year}, quarter={self.quarter}, status={self.status})>"


class DocumentChunk(Base):
    """
    文档分块表
    存储文档分块信息，用于向量化和 RAG
    """
    __tablename__ = 'document_chunks'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 关联文档
    document_id = Column(Integer, nullable=False, index=True)

    # 分块信息
    chunk_index = Column(Integer, nullable=False)  # 分块序号（从 0 开始）
    chunk_text = Column(Text, nullable=False)
    chunk_size = Column(Integer)  # 字符数或 token 数

    # 向量信息
    vector_id = Column(String(100))  # Milvus 向量 ID
    embedding_model = Column(String(100))  # 使用的 Embedding 模型

    # MinIO 路径（可选，如果分块也存储到 MinIO）
    minio_object_name = Column(String(500))

    # 时间戳
    created_at = Column(DateTime, nullable=False, default=func.now())
    vectorized_at = Column(DateTime)

    # 元数据
    extra_metadata = Column(JSON)  # 页码、段落信息等

    # 索引
    __table_args__ = (
        Index('idx_document_chunk', 'document_id', 'chunk_index'),
        Index('idx_vector_id', 'vector_id'),
    )

    def __repr__(self):
        return f"<DocumentChunk(id={self.id}, document_id={self.document_id}, chunk_index={self.chunk_index})>"


class CrawlTask(Base):
    """
    爬取任务表
    记录所有爬取任务的执行情况
    """
    __tablename__ = 'crawl_tasks'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 任务信息
    task_type = Column(String(50), nullable=False)  # daily, history, manual
    stock_code = Column(String(20), nullable=False, index=True)
    company_name = Column(String(200))
    market = Column(String(50), nullable=False)
    doc_type = Column(String(50), nullable=False)
    year = Column(Integer, nullable=False)
    quarter = Column(Integer)

    # 任务状态
    status = Column(String(50), nullable=False, default='pending', index=True)

    # 执行信息
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)

    # 结果信息
    success = Column(Boolean, default=False)
    document_id = Column(Integer)  # 关联的文档 ID
    error_message = Column(Text)

    # 时间戳
    created_at = Column(DateTime, nullable=False, default=func.now())

    # 元数据
    extra_metadata = Column(JSON)

    # 索引
    __table_args__ = (
        Index('idx_status_created', 'status', 'created_at'),
        Index('idx_task_key', 'stock_code', 'year', 'quarter', 'doc_type'),
    )

    def __repr__(self):
        return f"<CrawlTask(id={self.id}, stock_code={self.stock_code}, status={self.status})>"


class ParseTask(Base):
    """
    解析任务表
    记录文档解析任务
    """
    __tablename__ = 'parse_tasks'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 关联文档
    document_id = Column(Integer, nullable=False, index=True)

    # 解析器信息
    parser_type = Column(String(50), nullable=False)  # mineru, docling
    parser_version = Column(String(50))

    # 任务状态
    status = Column(String(50), nullable=False, default='pending', index=True)

    # 执行信息
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)

    # 结果信息
    success = Column(Boolean, default=False)
    output_path = Column(String(500))  # Silver 层路径
    extracted_text_length = Column(Integer)
    extracted_tables_count = Column(Integer)
    extracted_images_count = Column(Integer)
    error_message = Column(Text)

    # 时间戳
    created_at = Column(DateTime, nullable=False, default=func.now())

    # 元数据
    extra_metadata = Column(JSON)

    # 索引
    __table_args__ = (
        Index('idx_document_status', 'document_id', 'status'),
    )

    def __repr__(self):
        return f"<ParseTask(id={self.id}, document_id={self.document_id}, status={self.status})>"


class ValidationLog(Base):
    """
    验证日志表
    记录所有数据验证结果
    """
    __tablename__ = 'validation_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 关联文档
    document_id = Column(Integer, index=True)

    # 验证信息
    validation_stage = Column(String(50), nullable=False, index=True)  # ingestion, bronze, silver
    validation_rule = Column(String(100), nullable=False)
    validation_level = Column(String(50), nullable=False)  # info, warning, error, critical

    # 验证结果
    passed = Column(Boolean, nullable=False)
    message = Column(Text)

    # 时间戳
    created_at = Column(DateTime, nullable=False, default=func.now())

    # 元数据
    extra_metadata = Column(JSON)

    # 索引
    __table_args__ = (
        Index('idx_document_stage', 'document_id', 'validation_stage'),
        Index('idx_passed_level', 'passed', 'validation_level'),
    )

    def __repr__(self):
        return f"<ValidationLog(id={self.id}, document_id={self.document_id}, passed={self.passed})>"


class QuarantineRecord(Base):
    """
    隔离记录表
    记录被隔离的数据
    """
    __tablename__ = 'quarantine_records'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 数据信息
    document_id = Column(Integer, index=True)
    source_type = Column(String(50), nullable=False)  # a_share, hk_stock, us_stock
    doc_type = Column(String(50), nullable=False)
    original_path = Column(String(500), nullable=False)
    quarantine_path = Column(String(500), nullable=False)

    # 隔离原因
    failure_stage = Column(String(50), nullable=False, index=True)  # ingestion_failed, validation_failed, content_failed
    failure_reason = Column(String(200), nullable=False)
    failure_details = Column(Text)

    # 处理状态
    status = Column(String(50), nullable=False, default='pending', index=True)  # pending, processing, resolved, discarded
    handler = Column(String(100))  # 处理人
    resolution = Column(Text)  # 处理结果
    resolution_time = Column(DateTime)

    # 时间戳
    quarantine_time = Column(DateTime, nullable=False, default=func.now())

    # 元数据
    extra_metadata = Column(JSON)

    # 索引
    __table_args__ = (
        Index('idx_status_stage', 'status', 'failure_stage'),
    )

    def __repr__(self):
        return f"<QuarantineRecord(id={self.id}, failure_stage={self.failure_stage}, status={self.status})>"


class EmbeddingTask(Base):
    """
    向量化任务表
    记录文档向量化任务
    """
    __tablename__ = 'embedding_tasks'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 关联文档
    document_id = Column(Integer, nullable=False, index=True)

    # Embedding 信息
    embedding_model = Column(String(100), nullable=False)  # bge-large-zh-v1.5
    embedding_dim = Column(Integer, nullable=False)  # 1024
    chunk_size = Column(Integer, nullable=False)  # 512
    chunk_overlap = Column(Integer, nullable=False)  # 50

    # 任务状态
    status = Column(String(50), nullable=False, default='pending', index=True)

    # 执行信息
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)

    # 结果信息
    success = Column(Boolean, default=False)
    chunks_count = Column(Integer)  # 总分块数
    vectors_count = Column(Integer)  # 成功向量化的数量
    error_message = Column(Text)

    # 时间戳
    created_at = Column(DateTime, nullable=False, default=func.now())

    # 元数据
    extra_metadata = Column(JSON)

    # 索引
    __table_args__ = (
        Index('idx_document_status', 'document_id', 'status'),
    )

    def __repr__(self):
        return f"<EmbeddingTask(id={self.id}, document_id={self.document_id}, status={self.status})>"
