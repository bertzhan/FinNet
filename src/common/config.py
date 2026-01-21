# -*- coding: utf-8 -*-
"""
全局配置管理
统一管理所有配置项，支持从环境变量、配置文件读取
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


class CommonConfig(BaseSettings):
    """公共配置"""
    # 项目根目录
    PROJECT_ROOT: str = str(Path(__file__).parent.parent.parent)

    # 数据根目录
    DATA_ROOT: str = os.getenv("FINNET_DATA_ROOT", os.path.join(PROJECT_ROOT, "data"))

    # 日志级别
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # 环境
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 忽略额外字段


class MinIOConfig(BaseSettings):
    """MinIO 对象存储配置（plan.md 4.1.1）"""
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "admin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "admin123456")
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "finnet-datalake")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 忽略额外字段


class PostgreSQLConfig(BaseSettings):
    """PostgreSQL 配置（plan.md 4.1）"""
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "finnet")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "finnet")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "finnet123456")

    @property
    def database_url(self) -> str:
        """生成数据库连接 URL"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 忽略额外字段


class MilvusConfig(BaseSettings):
    """Milvus 向量数据库配置（plan.md 4.1.3）"""
    MILVUS_HOST: str = os.getenv("MILVUS_HOST", "localhost")
    MILVUS_PORT: int = int(os.getenv("MILVUS_PORT", "19530"))
    MILVUS_USER: Optional[str] = os.getenv("MILVUS_USER")
    MILVUS_PASSWORD: Optional[str] = os.getenv("MILVUS_PASSWORD")

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 忽略额外字段


class NebulaGraphConfig(BaseSettings):
    """NebulaGraph 图数据库配置（plan.md 4.1.4）"""
    NEBULA_HOST: str = os.getenv("NEBULA_HOST", "localhost")
    NEBULA_GRAPH_PORT: int = int(os.getenv("NEBULA_GRAPH_PORT", "9669"))
    NEBULA_META_PORT: int = int(os.getenv("NEBULA_META_PORT", "9559"))
    NEBULA_STORAGE_PORT: int = int(os.getenv("NEBULA_STORAGE_PORT", "9779"))
    NEBULA_USER: str = os.getenv("NEBULA_USER", "root")
    NEBULA_PASSWORD: str = os.getenv("NEBULA_PASSWORD", "nebula")
    NEBULA_SPACE: str = os.getenv("NEBULA_SPACE", "finnet")

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 忽略额外字段


class CrawlerConfig(BaseSettings):
    """爬虫配置"""
    CRAWLER_WORKERS: int = int(os.getenv("CRAWLER_WORKERS", "6"))
    CRAWLER_TIMEOUT: int = int(os.getenv("CRAWLER_TIMEOUT", "30"))
    CRAWLER_RETRY: int = int(os.getenv("CRAWLER_RETRY", "3"))
    CRAWLER_USER_AGENT: str = os.getenv(
        "CRAWLER_USER_AGENT",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    )

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 忽略额外字段


class EmbeddingConfig(BaseSettings):
    """Embedding 向量化配置（plan.md 4.3.3）"""
    # 模式选择：local（本地模型）或 api（API 调用）
    EMBEDDING_MODE: str = os.getenv("EMBEDDING_MODE", "local")  # local or api
    
    # 本地模型配置
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "bge-large-zh-v1.5")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1024"))
    EMBEDDING_BATCH_SIZE: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
    EMBEDDING_DEVICE: str = os.getenv("EMBEDDING_DEVICE", "cpu")  # cpu or cuda

    # HuggingFace 模型路径
    BGE_MODEL_PATH: str = os.getenv(
        "BGE_MODEL_PATH",
        "BAAI/bge-large-zh-v1.5"
    )
    BCE_MODEL_PATH: str = os.getenv(
        "BCE_MODEL_PATH",
        "maidalun1020/bce-embedding-base_v1"
    )
    
    # API 配置（OpenAI 兼容接口）
    EMBEDDING_API_URL: Optional[str] = os.getenv("EMBEDDING_API_URL")  # API 地址
    EMBEDDING_API_KEY: Optional[str] = os.getenv("EMBEDDING_API_KEY")  # API Key
    EMBEDDING_API_MODEL: Optional[str] = os.getenv("EMBEDDING_API_MODEL", "text-embedding-ada-002")  # API 模型名称
    EMBEDDING_API_TIMEOUT: int = int(os.getenv("EMBEDDING_API_TIMEOUT", "30"))  # API 超时时间（秒）
    EMBEDDING_API_MAX_RETRIES: int = int(os.getenv("EMBEDDING_API_MAX_RETRIES", "3"))  # 最大重试次数

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 忽略额外字段


class LLMConfig(BaseSettings):
    """LLM 配置（plan.md 4.3.2）"""
    # 本地 LLM 配置
    LOCAL_LLM_ENABLED: bool = os.getenv("LOCAL_LLM_ENABLED", "true").lower() == "true"
    LOCAL_LLM_MODEL: str = os.getenv("LOCAL_LLM_MODEL", "qwen2.5:7b")
    LOCAL_LLM_API_BASE: str = os.getenv("LOCAL_LLM_API_BASE", "http://localhost:11434")  # Ollama

    # 云端 LLM 配置（备用）
    CLOUD_LLM_ENABLED: bool = os.getenv("CLOUD_LLM_ENABLED", "false").lower() == "true"
    CLOUD_LLM_API_KEY: Optional[str] = os.getenv("CLOUD_LLM_API_KEY")
    CLOUD_LLM_API_BASE: Optional[str] = os.getenv("CLOUD_LLM_API_BASE") 
    CLOUD_LLM_MODEL: str = os.getenv("CLOUD_LLM_MODEL", "gpt-4")

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 忽略额外字段


class PDFParserConfig(BaseSettings):
    """PDF 解析器配置（plan.md 4.3.1）"""
    # 默认解析器：mineru, docling
    DEFAULT_PARSER: str = os.getenv("PDF_PARSER", "mineru")

    # MinerU 配置
    MINERU_API_BASE: Optional[str] = os.getenv("MINERU_API_BASE")
    MINERU_BATCH_SIZE: int = int(os.getenv("MINERU_BATCH_SIZE", "5"))

    # Docling 配置（备用）
    DOCLING_API_BASE: Optional[str] = os.getenv("DOCLING_API_BASE")

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 忽略额外字段


class DagsterConfig(BaseSettings):
    """Dagster 调度配置（plan.md 4.2.2）"""
    DAGSTER_HOME: str = os.getenv("DAGSTER_HOME", os.path.join(Path.home(), ".dagster"))
    DAGSTER_PORT: int = int(os.getenv("DAGSTER_PORT", "3000"))

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 忽略额外字段


class APIConfig(BaseSettings):
    """API 服务配置"""
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_WORKERS: int = int(os.getenv("API_WORKERS", "4"))
    API_RELOAD: bool = os.getenv("API_RELOAD", "false").lower() == "true"

    # CORS 配置
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

    # LibreChat 集成配置
    LIBRECHAT_ENABLED: bool = os.getenv("LIBRECHAT_ENABLED", "true").lower() == "true"
    LIBRECHAT_MODEL_NAME: str = os.getenv("LIBRECHAT_MODEL_NAME", "finnet-rag")
    LIBRECHAT_API_KEY: Optional[str] = os.getenv("LIBRECHAT_API_KEY")  # 可选：API 密钥验证

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 忽略额外字段


# 全局配置实例
common_config = CommonConfig()
llm_config = LLMConfig()
minio_config = MinIOConfig()
postgres_config = PostgreSQLConfig()
milvus_config = MilvusConfig()
nebula_config = NebulaGraphConfig()
crawler_config = CrawlerConfig()
embedding_config = EmbeddingConfig()
llm_config = LLMConfig()
pdf_parser_config = PDFParserConfig()
dagster_config = DagsterConfig()
api_config = APIConfig()
