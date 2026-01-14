# -*- coding: utf-8 -*-
"""
全局常量定义
遵循 plan.md 设计，定义市场、文档类型、数据层次等枚举
"""

from enum import Enum


class Market(Enum):
    """市场类型（plan.md 2.1）"""
    A_SHARE = "a_share"      # A股（上交所、深交所、北交所）
    HK_STOCK = "hk_stock"    # 港股（香港联交所）
    US_STOCK = "us_stock"    # 美股（NYSE、NASDAQ）


class DocType(Enum):
    """文档类型（plan.md 2.3）"""
    # A股文档类型
    ANNUAL_REPORT = "annual_reports"         # 年报
    INTERIM_REPORT = "interim_reports"       # 半年报（中报）
    QUARTERLY_REPORT = "quarterly_reports"   # 季度报告
    IPO_PROSPECTUS = "ipo_prospectus"        # 招股说明书
    ANNOUNCEMENT = "announcements"           # 公告

    # 港股文档类型
    HK_ANNUAL_REPORT = "hk_annual_reports"
    HK_INTERIM_REPORT = "hk_interim_reports"
    HK_QUARTERLY_REPORT = "hk_quarterly_reports"
    HK_IPO_PROSPECTUS = "hk_ipo_prospectus"
    EARNINGS_CALL = "earnings_calls"         # 财报电话会

    # 美股文档类型
    FORM_10K = "10k"                         # 年报
    FORM_10Q = "10q"                         # 季报
    FORM_8K = "8k"                           # 临时公告
    FORM_S1 = "s1_f1"                        # 招股书
    FORM_4 = "form4"                         # 内部人交易
    PROXY = "proxy"                          # 代理声明


class DataLayer(Enum):
    """数据层次（plan.md 5.1 湖仓分层模型）"""
    BRONZE = "bronze"           # 原始数据层（PDF/HTML/JSON）
    SILVER = "silver"           # 清洗数据层（解析后文本、表格）
    GOLD = "gold"               # 聚合数据层（财务指标、知识图谱）
    APPLICATION = "application" # 应用数据层（训练数据集、向量索引）
    QUARANTINE = "quarantine"   # 隔离区（验证失败数据）


class QuarantineReason(Enum):
    """隔离原因（plan.md 7.6）"""
    INGESTION_FAILED = "ingestion_failed"       # 采集阶段失败
    VALIDATION_FAILED = "validation_failed"     # 入湖验证失败
    CONTENT_FAILED = "content_failed"           # 内容验证失败


class DocumentStatus(Enum):
    """文档处理状态"""
    PENDING = "pending"         # 待处理
    CRAWLING = "crawling"       # 爬取中
    CRAWLED = "crawled"         # 已爬取
    PARSING = "parsing"         # 解析中
    PARSED = "parsed"           # 已解析
    PROCESSING = "processing"   # 处理中
    PROCESSED = "processed"     # 已处理
    VECTORIZING = "vectorizing" # 向量化中
    VECTORIZED = "vectorized"   # 已向量化
    FAILED = "failed"           # 失败
    QUARANTINED = "quarantined" # 已隔离


class ValidationLevel(Enum):
    """验证级别（plan.md 7.1）"""
    INFO = "info"           # 信息
    WARNING = "warning"     # 警告
    ERROR = "error"         # 错误
    CRITICAL = "critical"   # 严重错误


class ValidationStage(Enum):
    """验证阶段（plan.md 7.1）"""
    INGESTION = "ingestion"     # 采集阶段验证
    BRONZE = "bronze"           # 入湖前验证
    SILVER = "silver"           # 内容验证
    QUALITY = "quality"         # 持续质量监控


# 文件类型常量
class FileType:
    """文件类型常量"""
    PDF = "application/pdf"
    JSON = "application/json"
    CSV = "text/csv"
    TXT = "text/plain"
    PARQUET = "application/parquet"


# MinIO 桶常量
class MinIOBucket:
    """MinIO 桶名称（plan.md 5.2）"""
    DATALAKE = "finnet-datalake"  # 主数据湖桶


# PostgreSQL 表名常量
class PostgreSQLTable:
    """PostgreSQL 表名"""
    DOCUMENTS = "documents"                 # 文档元数据
    DOCUMENT_CHUNKS = "document_chunks"     # 文档分块
    CRAWL_TASKS = "crawl_tasks"            # 爬取任务
    PARSE_TASKS = "parse_tasks"            # 解析任务
    VALIDATION_LOGS = "validation_logs"    # 验证日志
    QUARANTINE_RECORDS = "quarantine_records"  # 隔离记录


# Milvus Collection 常量
class MilvusCollection:
    """Milvus Collection 名称"""
    DOCUMENTS = "financial_documents"       # 金融文档向量集合
    COMPANIES = "company_profiles"          # 公司画像向量集合


# 向量化配置
class EmbeddingConfig:
    """向量化配置（plan.md 4.3.3）"""
    CHUNK_SIZE = 512           # 文本分块大小（tokens）
    CHUNK_OVERLAP = 50         # 分块重叠（tokens）
    VECTOR_DIM_BGE = 1024      # BGE 向量维度
    VECTOR_DIM_BCE = 768       # BCE 向量维度


# 中文季度映射
QUARTER_MAP = {
    1: "Q1",
    2: "Q2",
    3: "Q3",
    4: "Q4"
}

# 市场显示名称
MARKET_DISPLAY_NAMES = {
    Market.A_SHARE: "A股",
    Market.HK_STOCK: "港股",
    Market.US_STOCK: "美股"
}

# 文档类型显示名称
DOCTYPE_DISPLAY_NAMES = {
    DocType.ANNUAL_REPORT: "年报",
    DocType.INTERIM_REPORT: "半年报",
    DocType.QUARTERLY_REPORT: "季报",
    DocType.IPO_PROSPECTUS: "招股说明书",
    DocType.ANNOUNCEMENT: "公告",
}
