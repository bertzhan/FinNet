# -*- coding: utf-8 -*-
"""
数据库模型定义
定义所有数据库表的 SQLAlchemy 模型
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, Float, BigInteger, Text, JSON,
    ForeignKey, Index, UniqueConstraint, ForeignKeyConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Document(Base):
    """
    文档表（Bronze 层）
    存储爬取的原始文档信息
    """
    __tablename__ = 'documents'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 基本信息
    stock_code = Column(String(20), nullable=False, index=True)
    company_name = Column(String(200), nullable=False)
    market = Column(String(50), nullable=False, index=True)
    doc_type = Column(String(50), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    quarter = Column(Integer, nullable=True, index=True)
    
    # 文件信息
    minio_object_path = Column(String(500), nullable=False, unique=True, index=True)
    file_size = Column(BigInteger)
    file_hash = Column(String(64), index=True)
    source_url = Column(String(1000), nullable=True, index=True)  # 文档来源URL
    
    # 状态和时间
    status = Column(String(50), nullable=False, default='pending', index=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    crawled_at = Column(DateTime)
    parsed_at = Column(DateTime)
    chunked_at = Column(DateTime)
    vectorized_at = Column(DateTime)
    graphed_at = Column(DateTime)
    updated_at = Column(DateTime, onupdate=func.now())
    publish_date = Column(DateTime, nullable=True, index=True)  # 文档发布日期

    # 错误和重试
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    
    # 索引
    __table_args__ = (
        Index('idx_stock_year_quarter', 'stock_code', 'year', 'quarter'),
        Index('idx_market_doc_type', 'market', 'doc_type'),
    )


class ParseTask(Base):
    """
    解析任务表
    存储文档解析任务信息
    """
    __tablename__ = 'parse_tasks'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 关联字段
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # 解析器信息
    parser_type = Column(String(50), nullable=False)  # mineru/docling
    parser_version = Column(String(100))
    
    # 状态
    status = Column(String(50), nullable=False, default='pending', index=True)  # pending/processing/completed/failed
    
    # 输出路径
    output_path = Column(String(500))
    
    # 错误信息
    error_message = Column(Text)
    
    # 时间戳
    created_at = Column(DateTime, nullable=False, default=func.now())
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # 元数据
    extra_metadata = Column(JSON, default={})
    
    # 索引
    __table_args__ = (
        Index('idx_document_status', 'document_id', 'status'),
        Index('idx_status_created', 'status', 'created_at'),
    )


class ParsedDocument(Base):
    """
    Silver 层解析文档表
    存储解析后的文档信息和路径
    """
    __tablename__ = 'parsed_documents'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # ==================== 关联字段 ====================
    document_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    parse_task_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # ==================== 路径信息 ====================
    content_json_path = Column(String(500), nullable=False)    # 内容 JSON 文件路径（主文件）
    markdown_path = Column(String(500), nullable=True)         # Markdown 文件路径（可选）
    middle_json_path = Column(String(500), nullable=True)      # Middle JSON 文件路径（可选）
    model_json_path = Column(String(500), nullable=True)       # Model JSON 文件路径（可选）
    image_folder_path = Column(String(500), nullable=True)     # 图片文件夹路径（可选）
    structure_json_path = Column(String(500), nullable=True)   # structure.json 文件路径（可选）
    chunks_json_path = Column(String(500), nullable=True)       # chunks.json 文件路径（可选）
    
    # ==================== 哈希值字段 ====================
    content_json_hash = Column(String(64), nullable=False, index=True)      # JSON 文件哈希
    markdown_hash = Column(String(64), nullable=True)                      # Markdown 文件哈希
    source_document_hash = Column(String(64), nullable=False, index=True)  # 源 PDF 哈希
    structure_json_hash = Column(String(64), nullable=True, index=True)    # structure.json 文件哈希
    chunks_json_hash = Column(String(64), nullable=True, index=True)       # chunks.json 文件哈希
    
    # ==================== 解析结果统计 ====================
    text_length = Column(Integer, default=0)                   # 文本长度（字符数）
    tables_count = Column(Integer, default=0)                  # 表格数量
    images_count = Column(Integer, default=0)                   # 图片数量
    pages_count = Column(Integer, default=0)                    # 页数
    chunks_count = Column(Integer, default=0)                   # 分块数量
    
    # ==================== 解析器信息 ====================
    parser_type = Column(String(50), nullable=False)            # mineru/docling
    parser_version = Column(String(100))                        # 解析器版本
    
    # ==================== 解析质量指标 ====================
    parsing_quality_score = Column(Float)                      # 解析质量评分（0-1）
    has_tables = Column(Boolean, default=False)                 # 是否包含表格
    has_images = Column(Boolean, default=False)                # 是否包含图片
    
    # ==================== 时间戳 ====================
    parsed_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    chunked_at = Column(DateTime, nullable=True)               # 分块时间
    
    # ==================== 状态 ====================
    status = Column(String(50), default='active')              # active/archived
    
    # ==================== 索引和约束 ====================
    __table_args__ = (
        # 索引
        Index('idx_document_parsed', 'document_id', 'parsed_at'),
        Index('idx_parse_task', 'parse_task_id'),
        Index('idx_source_hash', 'source_document_hash'),
        Index('idx_json_hash', 'content_json_hash'),
        Index('idx_text_length', 'text_length'),
        
        # 外键约束
        ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['parse_task_id'], ['parse_tasks.id'], ondelete='CASCADE'),
    )



class Image(Base):
    """
    图片元数据表
    存储从 PDF 提取的图片信息
    """
    __tablename__ = 'images'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 关联字段
    parsed_document_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), nullable=False, index=True)          # 关联 Document（快速查询）
    
    # 图片基本信息
    image_index = Column(Integer, nullable=False)                      # 图片序号（在文档中的顺序）
    filename = Column(String(200), nullable=False)                      # 文件名（如 img_001.jpg）
    file_path = Column(String(500), nullable=False)                     # MinIO 完整路径
    
    # 图片元数据
    page_number = Column(Integer, nullable=False)                       # 所在页码（从1开始）
    bbox = Column(JSON, nullable=True)                                 # 边界框 [x1, y1, x2, y2]
    description = Column(String(500))                                  # 解析器提取的描述
    
    # 图片属性
    width = Column(Integer)                                            # 图片宽度（像素）
    height = Column(Integer)                                           # 图片高度（像素）
    file_size = Column(BigInteger)                                     # 文件大小（字节）
    file_hash = Column(String(64), index=True)                          # 图片文件哈希（SHA256）
    
    # 时间戳
    created_at = Column(DateTime, nullable=False, default=func.now())
    extracted_at = Column(DateTime, nullable=False, default=func.now())  # 提取时间
    
    # 索引
    __table_args__ = (
        Index('idx_parsed_doc_image', 'parsed_document_id', 'image_index'),
        Index('idx_document_id', 'document_id'),
        Index('idx_file_hash', 'file_hash'),
        ForeignKeyConstraint(['parsed_document_id'], ['parsed_documents.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    )


class ImageAnnotation(Base):
    """
    图片标注表
    存储图片的分类标注信息，支持版本管理
    """
    __tablename__ = 'image_annotations'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 关联字段
    image_id = Column(UUID(as_uuid=True), nullable=False, index=True)            # 关联 Image
    annotation_version = Column(Integer, nullable=False, default=1)    # 标注版本号
    
    # 标注信息
    category = Column(String(100), nullable=False, index=True)         # 分类类别（如：财务图表、组织结构图）
    subcategory = Column(String(100))                                 # 子类别（可选）
    confidence = Column(Float)                                         # 标注置信度（0-1，如果是自动标注）
    
    # 标注者信息
    annotator_type = Column(String(50), nullable=False)                # 标注者类型：human/ai/auto
    annotator_id = Column(String(100))                                 # 标注者ID（用户ID或模型名称）
    annotator_name = Column(String(200))                               # 标注者名称
    
    # 标注状态
    status = Column(String(50), default='pending', index=True)         # pending/approved/rejected/archived
    reviewed_by = Column(String(100))                                  # 审核人
    reviewed_at = Column(DateTime)                                     # 审核时间
    
    # 标注内容
    annotation_text = Column(Text)                                     # 标注说明文本
    tags = Column(JSON)                                                # 标签列表（JSON数组）
    extra_metadata = Column(JSON)                                      # 额外元数据
    
    # 时间戳
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # 索引
    __table_args__ = (
        Index('idx_image_version', 'image_id', 'annotation_version'),
        Index('idx_category', 'category'),
        Index('idx_status', 'status'),
        Index('idx_annotator', 'annotator_type', 'annotator_id'),
        UniqueConstraint('image_id', 'annotation_version', name='uq_image_version'),
        ForeignKeyConstraint(['image_id'], ['images.id'], ondelete='CASCADE'),
    )



class DocumentChunk(Base):
    """
    文档分块表
    存储文档的分块信息（用于向量化）
    """
    __tablename__ = 'document_chunks'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_size = Column(Integer, nullable=False)
    
    # 结构化分块字段
    title = Column(String(500), nullable=True)                # 分块标题
    title_level = Column(Integer, nullable=True)              # 标题层级（1-5）
    heading_index = Column(Integer, nullable=True)            # 标题索引（在文档结构中的索引位置）
    parent_chunk_id = Column(UUID(as_uuid=True), nullable=True)  # 父分块ID（用于构建层级关系）
    start_line = Column(Integer, nullable=True)               # 在原始文档中的起始行号
    end_line = Column(Integer, nullable=True)                 # 在原始文档中的结束行号
    is_table = Column(Boolean, default=False)                 # 是否是表格分块
    
    # 向量化相关字段
    # 注意：不再使用 vector_id，因为 Milvus 使用 chunk_id 作为主键
    # 使用 vectorized_at 字段来判断是否已向量化（向后兼容）
    # 新代码应使用 status 字段
    status = Column(String(50), default='pending', index=True)  # 向量化状态：pending/vectorizing/vectorized/failed
    embedding_model = Column(String(100))  # 使用的向量化模型（如 "openai/text-embedding-3-large"）
    vectorized_at = Column(DateTime)       # 向量化时间戳（NULL 表示未向量化）
    vectorization_error = Column(Text)     # 向量化失败原因
    vectorization_retry_count = Column(Integer, default=0)  # 向量化重试次数

    # Elasticsearch 索引相关字段
    es_indexed_at = Column(DateTime)       # ES 索引时间戳（NULL 表示未索引）

    # 额外元数据
    extra_metadata = Column(JSON, default={})
    
    __table_args__ = (
        Index('idx_document_chunk', 'document_id', 'chunk_index'),
        Index('idx_parent_chunk', 'parent_chunk_id'),
        UniqueConstraint('document_id', 'chunk_index', name='uq_doc_chunk'),
    )


class CrawlTask(Base):
    """
    爬取任务表
    存储爬取任务信息
    """
    __tablename__ = 'crawl_tasks'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type = Column(String(50), nullable=False)
    stock_code = Column(String(20), nullable=False, index=True)
    company_name = Column(String(200), nullable=False)
    market = Column(String(50), nullable=False, index=True)
    doc_type = Column(String(50), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    quarter = Column(Integer, nullable=True, index=True)
    status = Column(String(50), nullable=False, default='pending', index=True)
    success = Column(Boolean, default=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id', ondelete='SET NULL'))
    error_message = Column(Text)
    created_at = Column(DateTime, nullable=False, default=func.now())
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    extra_metadata = Column(JSON, default={})
    
    __table_args__ = (
        Index('idx_task_status', 'status', 'created_at'),
        Index('idx_stock_year_quarter_task', 'stock_code', 'year', 'quarter'),
    )


class ValidationLog(Base):
    """
    验证日志表
    存储数据验证日志
    """
    __tablename__ = 'validation_logs'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True)
    validation_type = Column(String(50), nullable=False)
    validation_status = Column(String(50), nullable=False)  # passed/failed/warning
    message = Column(Text)
    details = Column(JSON)
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    __table_args__ = (
        Index('idx_doc_validation', 'document_id', 'created_at'),
    )


class QuarantineRecord(Base):
    """
    隔离记录表
    存储被隔离的文档记录
    """
    __tablename__ = 'quarantine_records'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id', ondelete='CASCADE'), nullable=True, index=True)  # 允许为空

    # 来源和类型信息
    source_type = Column(String(50), nullable=False)  # a_share/hk_stock/us_stock
    doc_type = Column(String(50), nullable=False)     # 文档类型

    # 路径信息
    original_path = Column(String(500), nullable=False)    # 原始路径
    quarantine_path = Column(String(500), nullable=False)  # 隔离区路径

    # 失败信息
    failure_stage = Column(String(50), nullable=False)     # ingestion_failed/validation_failed/content_failed
    failure_reason = Column(String(500), nullable=False)   # 失败原因
    failure_details = Column(Text)                         # 详细错误信息

    # 状态和处理信息
    status = Column(String(50), default='pending', index=True)  # pending/processing/resolved/discarded
    handler = Column(String(100))                               # 处理人
    resolution = Column(Text)                                   # 处理说明

    # 时间戳
    quarantine_time = Column(DateTime, nullable=False, default=func.now())  # 隔离时间
    resolution_time = Column(DateTime)                                      # 处理时间

    # 额外元数据
    extra_metadata = Column(JSON)

    __table_args__ = (
        Index('idx_quarantine_status', 'status', 'quarantine_time'),
        Index('idx_failure_stage', 'failure_stage'),
        Index('idx_quarantine_document_id', 'document_id'),
    )


class EmbeddingTask(Base):
    """
    向量化任务表
    存储文档向量化任务信息
    """
    __tablename__ = 'embedding_tasks'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True)
    embedding_model = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False, default='pending', index=True)
    chunks_count = Column(Integer, default=0)
    completed_chunks = Column(Integer, default=0)
    error_message = Column(Text)
    created_at = Column(DateTime, nullable=False, default=func.now())
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    extra_metadata = Column(JSON, default={})
    
    __table_args__ = (
        Index('idx_doc_embedding', 'document_id', 'status'),
    )


class ListedCompany(Base):
    """
    A股上市公司表
    存储A股上市公司的代码和名称信息
    
    注意：使用 code（股票代码）作为主键，确保不会出现重复的公司记录
    数据来源：akshare stock_individual_basic_info_xq 接口
    """
    __tablename__ = 'listed_companies'

    # ==================== 基本信息 ====================
    code = Column(String(20), primary_key=True)  # 股票代码（如：000001），主键
    name = Column(String(100), nullable=False)   # 公司简称（如：平安银行）
    
    # ==================== 公司名称信息 ====================
    org_id = Column(String(100), nullable=True)  # 机构ID
    org_name_cn = Column(String(100), nullable=True)  # 公司全称（中文）
    org_short_name_cn = Column(String(100), nullable=True)  # 公司简称（中文）
    org_name_en = Column(String(100), nullable=True)  # 公司全称（英文）
    org_short_name_en = Column(String(100), nullable=True)  # 公司简称（英文）
    pre_name_cn = Column(String(100), nullable=True)  # 曾用名
    
    # ==================== 业务信息 ====================
    main_operation_business = Column(Text, nullable=True)  # 主营业务
    operating_scope = Column(Text, nullable=True)  # 经营范围
    org_cn_introduction = Column(Text, nullable=True)  # 公司简介
    
    # ==================== 联系信息 ====================
    telephone = Column(String(100), nullable=True)  # 电话（可能包含多个号码）
    postcode = Column(String(20), nullable=True)  # 邮编
    fax = Column(String(50), nullable=True)  # 传真（可能包含多个号码）
    email = Column(String(50), nullable=True)  # 邮箱
    org_website = Column(String(100), nullable=True)  # 网站
    reg_address_cn = Column(String(200), nullable=True)  # 注册地址（中文）
    reg_address_en = Column(String(200), nullable=True)  # 注册地址（英文）
    office_address_cn = Column(String(200), nullable=True)  # 办公地址（中文）
    office_address_en = Column(String(200), nullable=True)  # 办公地址（英文）
    
    # ==================== 管理信息 ====================
    legal_representative = Column(String(10), nullable=True)  # 法定代表人
    general_manager = Column(String(10), nullable=True)  # 总经理
    secretary = Column(String(10), nullable=True)  # 董事会秘书
    chairman = Column(String(10), nullable=True)  # 董事长
    executives_nums = Column(Integer, nullable=True)  # 高管人数
    
    # ==================== 地区信息 ====================
    district_encode = Column(String(10), nullable=True)  # 地区编码
    provincial_name = Column(String(10), nullable=True)  # 省份名称
    actual_controller = Column(String(10), nullable=True)  # 实际控制人
    classi_name = Column(String(10), nullable=True)  # 分类名称
    
    # ==================== 财务信息 ====================
    established_date = Column(BigInteger, nullable=True)  # 成立日期（时间戳）
    listed_date = Column(BigInteger, nullable=True)  # 上市日期（时间戳）
    reg_asset = Column(Float, nullable=True)  # 注册资本
    staff_num = Column(Integer, nullable=True)  # 员工人数
    actual_issue_vol = Column(Float, nullable=True)  # 实际发行量
    issue_price = Column(Float, nullable=True)  # 发行价格
    actual_rc_net_amt = Column(Float, nullable=True)  # 实际募集资金净额
    pe_after_issuing = Column(Float, nullable=True)  # 发行后市盈率
    online_success_rate_of_issue = Column(Float, nullable=True)  # 网上发行中签率
    
    # ==================== 其他信息 ====================
    currency_encode = Column(String(100), nullable=True)  # 货币编码
    currency = Column(String(20), nullable=True)  # 货币
    affiliate_industry = Column(JSON, nullable=True)  # 所属行业（JSON格式）
    
    # ==================== 时间戳 ====================
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
