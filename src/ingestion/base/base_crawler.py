# -*- coding: utf-8 -*-
"""
爬虫基类
定义统一的爬虫接口，支持 A股、港股、美股三大市场
遵循 plan.md 设计，集成 storage 层
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
import os

from src.common.constants import Market, DocType, DocumentStatus
from src.common.logger import get_logger, LoggerMixin
from src.common.config import minio_config
from src.storage.object_store.minio_client import MinIOClient
from src.storage.object_store.path_manager import PathManager
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.storage.metadata.quarantine_manager import QuarantineManager


@dataclass
class CrawlTask:
    """
    爬取任务
    """
    stock_code: str                      # 股票代码
    company_name: str                    # 公司名称
    market: Market                       # 市场类型
    doc_type: DocType                    # 文档类型
    year: Optional[int] = None           # 年份（IPO类型不需要）
    quarter: Optional[int] = None        # 季度 (1-4)，None 表示年报（IPO类型不需要）
    metadata: Dict = field(default_factory=dict)  # 额外元数据

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'stock_code': self.stock_code,
            'company_name': self.company_name,
            'market': self.market.value,
            'doc_type': self.doc_type.value,
            'year': self.year,
            'quarter': self.quarter,
            'metadata': self.metadata
        }


@dataclass
class CrawlResult:
    """
    爬取结果
    """
    task: CrawlTask                      # 任务信息
    success: bool                        # 是否成功
    local_file_path: Optional[str] = None    # 本地文件路径（临时）
    minio_object_name: Optional[str] = None  # MinIO 对象名称
    document_id: Optional[int] = None        # 数据库文档 ID
    file_size: Optional[int] = None          # 文件大小（字节）
    file_hash: Optional[str] = None          # 文件哈希
    error_message: Optional[str] = None      # 错误信息（失败时）
    metadata: Dict = field(default_factory=dict)  # 元数据

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'task': self.task.to_dict(),
            'success': self.success,
            'local_file_path': self.local_file_path,
            'minio_object_name': self.minio_object_name,
            'document_id': self.document_id,
            'file_size': self.file_size,
            'file_hash': self.file_hash,
            'error_message': self.error_message,
            'metadata': self.metadata
        }


class BaseCrawler(ABC, LoggerMixin):
    """
    爬虫基类
    所有市场爬虫都应继承此类并实现抽象方法

    集成功能：
    - 自动上传到 MinIO
    - 自动记录到 PostgreSQL
    - 文件哈希计算
    - 路径管理
    """

    def __init__(
        self,
        market: Market,
        enable_minio: bool = True,
        enable_postgres: bool = True,
        enable_quarantine: bool = True
    ):
        """
        Args:
            market: 市场类型
            enable_minio: 是否启用 MinIO 上传
            enable_postgres: 是否启用 PostgreSQL 记录
            enable_quarantine: 是否启用自动隔离（验证失败时）
        """
        self.market = market
        self.enable_minio = enable_minio
        self.enable_postgres = enable_postgres
        self.enable_quarantine = enable_quarantine

        # 从配置读取 bucket 名称，确保 PathManager 和 MinIOClient 使用相同的 bucket
        self.bucket_name = minio_config.MINIO_BUCKET
        self.logger.info(f"BaseCrawler 初始化 - 从配置读取 bucket: '{self.bucket_name}' (环境变量 MINIO_BUCKET: {os.getenv('MINIO_BUCKET', '未设置')})")

        # 初始化组件
        self.path_manager = PathManager(bucket=self.bucket_name)

        if self.enable_minio:
            try:
                self.minio_client = MinIOClient(bucket=self.bucket_name)
                self.logger.info(f"MinIO 客户端初始化成功，bucket: {self.bucket_name}")
            except Exception as e:
                self.logger.warning(f"MinIO 客户端初始化失败: {e}")
                self.enable_minio = False
                self.minio_client = None
        else:
            self.minio_client = None

        if self.enable_postgres:
            try:
                self.pg_client = get_postgres_client()
                self.logger.info("PostgreSQL 客户端初始化成功")
            except Exception as e:
                self.logger.warning(f"PostgreSQL 客户端初始化失败: {e}")
                self.enable_postgres = False
                self.pg_client = None
        else:
            self.pg_client = None

        # 初始化隔离管理器（如果启用）
        if self.enable_quarantine and self.enable_minio and self.enable_postgres:
            try:
                self.quarantine_manager = QuarantineManager(
                    minio_client=self.minio_client,
                    path_manager=self.path_manager
                )
                self.logger.info("隔离管理器初始化成功")
            except Exception as e:
                self.logger.warning(f"隔离管理器初始化失败: {e}")
                self.enable_quarantine = False
                self.quarantine_manager = None
        else:
            self.quarantine_manager = None

    @abstractmethod
    def _download_file(self, task: CrawlTask) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        下载文件（由子类实现）

        Args:
            task: 爬取任务

        Returns:
            (是否成功, 本地文件路径, 错误信息)
        """
        pass

    def crawl(self, task: CrawlTask) -> CrawlResult:
        """
        执行单个爬取任务

        完整流程：
        1. 下载文件到本地
        2. 计算文件哈希
        3. 上传到 MinIO（如果启用）
        4. 记录到 PostgreSQL（如果启用）

        Args:
            task: 爬取任务

        Returns:
            爬取结果
        """
        if task.doc_type == DocType.IPO_PROSPECTUS:
            self.logger.info(f"开始爬取: {task.stock_code} IPO招股说明书")
        else:
            self.logger.info(f"开始爬取: {task.stock_code} {task.year} Q{task.quarter}")

        # 1. 下载文件
        success, local_file_path, error_message = self._download_file(task)

        if not success:
            error_msg = error_message or "未知错误"
            self.logger.error(
                f"下载失败: {task.stock_code} ({task.company_name}) "
                f"{task.year if task.year else 'N/A'} Q{task.quarter if task.quarter else 'N/A'} - {error_msg}"
            )
            return CrawlResult(
                task=task,
                success=False,
                error_message=error_msg
            )

        # 2. 计算文件哈希和大小
        try:
            from src.common.utils import calculate_file_hash
            from pathlib import Path

            file_hash = calculate_file_hash(local_file_path, algorithm='md5')
            file_size = Path(local_file_path).stat().st_size

            self.logger.debug(f"文件信息: size={file_size}, hash={file_hash[:16]}...")
        except Exception as e:
            self.logger.error(f"计算文件信息失败: {e}")
            file_hash = None
            file_size = None

        # 3. 生成 MinIO 路径
        if task.doc_type == DocType.IPO_PROSPECTUS:
            # IPO招股说明书：从下载的文件名中提取实际文件名
            import os
            actual_filename = os.path.basename(local_file_path)
            minio_object_name = self.path_manager.get_bronze_path(
                market=task.market,
                doc_type=task.doc_type,
                stock_code=task.stock_code,
                year=None,
                quarter=None,
                filename=actual_filename
            )
        else:
            filename = f"{task.stock_code}_{task.year}_Q{task.quarter}.pdf"
            minio_object_name = self.path_manager.get_bronze_path(
                market=task.market,
                doc_type=task.doc_type,
                stock_code=task.stock_code,
                year=task.year,
                quarter=task.quarter,
                filename=filename
            )

        # 4. 上传到 MinIO
        document_id = None
        if not self.enable_minio:
            self.logger.warning(f"⚠️ MinIO 未启用，跳过上传: {minio_object_name}")
        elif not self.minio_client:
            self.logger.error(f"❌ MinIO 客户端未初始化，无法上传: {minio_object_name}")
        else:
            try:
                self.logger.info(f"开始上传到 MinIO: {minio_object_name}")
                upload_success = self.minio_client.upload_file(
                    object_name=minio_object_name,
                    file_path=local_file_path,
                    metadata={
                        'stock_code': task.stock_code,
                        'year': str(task.year) if task.year else '',
                        'quarter': str(task.quarter) if task.quarter else '',
                        **task.metadata
                    }
                )

                if upload_success:
                    self.logger.info(f"✅ MinIO 上传成功: {minio_object_name}")
                else:
                    self.logger.error(f"❌ MinIO 上传失败（返回 False）: {minio_object_name}")
            except Exception as e:
                self.logger.error(f"❌ MinIO 上传异常: {e}", exc_info=True)

        # 5. 记录到 PostgreSQL
        if self.enable_postgres and self.pg_client:
            try:
                with self.pg_client.get_session() as session:
                    # 检查是否已存在
                    existing_doc = crud.get_document_by_path(session, minio_object_name)

                    if existing_doc:
                        self.logger.info(f"文档已存在: id={existing_doc.id}")
                        document_id = existing_doc.id
                    else:
                        # 对于IPO类型，从文件名中提取年份
                        year = task.year
                        if task.doc_type == DocType.IPO_PROSPECTUS and not year:
                            # 从文件名提取年份（格式：code_year_date.ext）
                            import os
                            filename = os.path.basename(local_file_path)
                            parts = filename.replace(".pdf", "").replace(".html", "").replace(".htm", "").split("_")
                            if len(parts) > 1 and parts[1].isdigit():
                                year = int(parts[1])
                            else:
                                # 如果无法提取，使用当前年份作为默认值
                                from datetime import datetime
                                year = datetime.now().year
                        
                        # 创建新记录
                        doc = crud.create_document(
                            session=session,
                            stock_code=task.stock_code,
                            company_name=task.company_name,
                            market=task.market.value,
                            doc_type=task.doc_type.value,
                            year=year if year else datetime.now().year,  # 确保year不为None
                            quarter=task.quarter if task.quarter else None,
                            minio_object_name=minio_object_name,
                            file_size=file_size,
                            file_hash=file_hash,
                            metadata=task.metadata
                        )
                        document_id = doc.id
                        self.logger.info(f"✅ PostgreSQL 记录成功: id={document_id}")
            except Exception as e:
                self.logger.error(f"❌ PostgreSQL 记录异常: {e}", exc_info=True)
                # 记录失败但不影响整体成功状态（因为 MinIO 上传已成功）
                document_id = None

        # 6. 创建结果对象
        result = CrawlResult(
            task=task,
            success=True,
            local_file_path=local_file_path,
            minio_object_name=minio_object_name,
            document_id=document_id,
            file_size=file_size,
            file_hash=file_hash,
            metadata=task.metadata
        )

        # 7. 验证结果（如果启用自动隔离）
        if self.enable_quarantine and self.quarantine_manager:
            is_valid, error_msg = self.validate_result(result)
            
            if not is_valid:
                # 验证失败，自动隔离
                self.logger.warning(f"验证失败，自动隔离: {error_msg}")
                try:
                    self.quarantine_manager.quarantine_document(
                        document_id=document_id,
                        source_type=task.market.value,
                        doc_type=task.doc_type.value,
                        original_path=minio_object_name,
                        failure_stage="validation_failed",
                        failure_reason=error_msg or "验证失败",
                        failure_details=f"文件大小: {file_size} bytes, 文件哈希: {file_hash}",
                        extra_metadata={
                            "stock_code": task.stock_code,
                            "company_name": task.company_name,
                            "year": task.year,
                            "quarter": task.quarter
                        }
                    )
                    self.logger.info(f"✅ 文档已自动隔离: {minio_object_name}")
                except Exception as e:
                    self.logger.error(f"❌ 自动隔离失败: {e}", exc_info=True)

        # 8. 返回结果
        return result

    def crawl_batch(self, tasks: List[CrawlTask]) -> List[CrawlResult]:
        """
        批量爬取

        Args:
            tasks: 任务列表

        Returns:
            结果列表
        """
        self.logger.info(f"开始批量爬取: {len(tasks)} 个任务")

        results = []
        for task in tasks:
            result = self.crawl(task)
            results.append(result)

        # 统计结果
        success_count = sum(1 for r in results if r.success)
        fail_count = len(results) - success_count

        self.logger.info(f"批量爬取完成: 成功 {success_count}, 失败 {fail_count}")

        return results

    def validate_result(self, result: CrawlResult) -> Tuple[bool, Optional[str]]:
        """
        验证爬取结果

        Args:
            result: 爬取结果

        Returns:
            (是否通过验证, 错误信息)
        """
        if not result.success:
            return False, result.error_message

        if not result.local_file_path:
            return False, "本地文件路径为空"

        # 检查文件是否存在
        from pathlib import Path
        if not Path(result.local_file_path).exists():
            return False, "本地文件不存在"

        # 检查文件大小
        if result.file_size and result.file_size < 1024:  # 小于 1KB
            return False, f"文件太小: {result.file_size} bytes"

        return True, None
