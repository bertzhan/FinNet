# -*- coding: utf-8 -*-
"""
隔离区管理器
按照 plan.md 7.6 设计，实现数据隔离和管理功能
"""

import uuid
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from sqlalchemy.orm import Session

from src.storage.object_store.minio_client import MinIOClient
from src.storage.object_store.path_manager import PathManager
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import QuarantineRecord, Document
from src.storage.metadata import crud
from src.common.constants import QuarantineReason, DocumentStatus
from src.common.logger import get_logger, LoggerMixin


class QuarantineManager(LoggerMixin):
    """
    隔离区管理器
    负责将验证失败的数据移动到隔离区，并提供管理功能
    """

    def __init__(
        self,
        minio_client: Optional[MinIOClient] = None,
        path_manager: Optional[PathManager] = None
    ):
        """
        初始化隔离管理器

        Args:
            minio_client: MinIO 客户端（默认创建新实例）
            path_manager: 路径管理器（默认创建新实例）
        """
        self.minio_client = minio_client or MinIOClient()
        self.path_manager = path_manager or PathManager()
        self.pg_client = get_postgres_client()

    def quarantine_document(
        self,
        document_id: Optional[Union[uuid.UUID, str]],
        source_type: str,
        doc_type: str,
        original_path: str,
        failure_stage: str,
        failure_reason: str,
        failure_details: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> QuarantineRecord:
        """
        将文档移动到隔离区

        完整流程：
        1. 生成隔离区路径
        2. 从 MinIO 复制文件到隔离区（保留原文件，避免数据丢失）
        3. 创建隔离记录
        4. 更新文档状态为 quarantined

        Args:
            document_id: 文档ID（可选，如果文档还未入库）
            source_type: 数据来源（a_share/hk_stock/us_stock）
            doc_type: 文档类型
            original_path: 原始文件路径（MinIO 对象名）
            failure_stage: 失败阶段（ingestion_failed/validation_failed/content_failed）
            failure_reason: 失败原因（简要描述）
            failure_details: 详细错误信息（可选）
            extra_metadata: 额外元数据（可选）

        Returns:
            隔离记录对象

        Example:
            >>> manager = QuarantineManager()
            >>> record = manager.quarantine_document(
            ...     document_id=123,
            ...     source_type="a_share",
            ...     doc_type="quarterly_report",
            ...     original_path="bronze/a_share/quarterly_reports/2023/Q3/000001/report.pdf",
            ...     failure_stage="validation_failed",
            ...     failure_reason="文件大小异常（小于1KB）",
            ...     failure_details="文件大小: 512 bytes，小于最小阈值 1024 bytes"
            ... )
        """
        # 1. 确定隔离原因枚举值
        reason_map = {
            "ingestion_failed": QuarantineReason.INGESTION_FAILED,
            "validation_failed": QuarantineReason.VALIDATION_FAILED,
            "content_failed": QuarantineReason.CONTENT_FAILED,
        }
        reason = reason_map.get(failure_stage, QuarantineReason.VALIDATION_FAILED)

        # 2. 生成隔离区路径
        quarantine_path = self.path_manager.get_quarantine_path(
            reason=reason,
            original_path=original_path
        )

        self.logger.warning(
            f"开始隔离文档: document_id={document_id}, "
            f"original_path={original_path}, reason={failure_reason}"
        )

        # 3. 复制文件到隔离区（如果文件存在）
        file_copied = False
        if self.minio_client.file_exists(original_path):
            try:
                # 下载文件
                file_data = self.minio_client.download_file(original_path)
                if file_data:
                    # 上传到隔离区
                    content_type = self._guess_content_type(original_path)
                    # MinIO 元数据仅支持 US-ASCII，使用 document_id 代替中文错误信息
                    metadata = {
                        "original_path": original_path,
                        "failure_stage": failure_stage,
                        "quarantine_time": datetime.now().isoformat()
                    }
                    # 仅在 document_id 存在时添加
                    if document_id:
                        metadata["document_id"] = str(document_id)

                    success = self.minio_client.upload_file(
                        object_name=quarantine_path,
                        data=file_data,
                        content_type=content_type,
                        metadata=metadata
                    )
                    if success:
                        file_copied = True
                        self.logger.info(f"✅ 文件已复制到隔离区: {quarantine_path}")
                    else:
                        self.logger.warning(f"⚠️ 文件复制到隔离区失败: {quarantine_path}")
                else:
                    self.logger.warning(f"⚠️ 无法下载文件: {original_path}")
            except Exception as e:
                self.logger.error(f"❌ 复制文件到隔离区异常: {e}", exc_info=True)
        else:
            self.logger.warning(f"⚠️ 原始文件不存在，跳过文件复制: {original_path}")

        # 4. 创建隔离记录
        with self.pg_client.get_session() as session:
            record = crud.create_quarantine_record(
                session=session,
                document_id=document_id,
                source_type=source_type,
                doc_type=doc_type,
                original_path=original_path,
                quarantine_path=quarantine_path,
                failure_stage=failure_stage,
                failure_reason=failure_reason,
                failure_details=failure_details
            )

            # 添加额外元数据
            if extra_metadata:
                record.extra_metadata = extra_metadata
            if not file_copied:
                record.extra_metadata = record.extra_metadata or {}
                record.extra_metadata["file_copied"] = False

            session.commit()
            self.logger.info(f"✅ 隔离记录已创建: id={record.id}")

            # 5. 更新文档状态（如果文档存在）
            if document_id:
                try:
                    doc = session.query(Document).filter(Document.id == document_id).first()
                    if doc:
                        doc.status = DocumentStatus.QUARANTINED.value
                        session.commit()
                        self.logger.info(f"✅ 文档状态已更新为 quarantined: document_id={document_id}")
                except Exception as e:
                    self.logger.error(f"❌ 更新文档状态失败: {e}", exc_info=True)

        return record

    def get_pending_records(
        self,
        limit: int = 100,
        failure_stage: Optional[str] = None
    ) -> List[QuarantineRecord]:
        """
        获取待处理的隔离记录

        Args:
            limit: 最大返回数量
            failure_stage: 失败阶段过滤（可选）

        Returns:
            隔离记录列表

        Example:
            >>> manager = QuarantineManager()
            >>> records = manager.get_pending_records(limit=50, failure_stage="validation_failed")
            >>> for record in records:
            ...     print(f"ID: {record.id}, 原因: {record.failure_reason}")
        """
        with self.pg_client.get_session() as session:
            query = session.query(QuarantineRecord).filter(
                QuarantineRecord.status == 'pending'
            )

            if failure_stage:
                query = query.filter(QuarantineRecord.failure_stage == failure_stage)

            records = query.order_by(QuarantineRecord.quarantine_time).limit(limit).all()
            self.logger.debug(f"查询到 {len(records)} 条待处理隔离记录")
            return records

    def get_record_by_id(self, record_id: Union[uuid.UUID, str]) -> Optional[QuarantineRecord]:
        """
        根据ID获取隔离记录

        Args:
            record_id: 隔离记录ID

        Returns:
            隔离记录对象，如果不存在返回 None
        """
        with self.pg_client.get_session() as session:
            return session.query(QuarantineRecord).filter(
                QuarantineRecord.id == record_id
            ).first()

    def resolve_record(
        self,
        record_id: Union[uuid.UUID, str],
        resolution: str,
        handler: str,
        action: str = "discard"
    ) -> QuarantineRecord:
        """
        处理隔离记录

        Args:
            record_id: 隔离记录ID
            resolution: 处理结果说明
            handler: 处理人
            action: 处理动作
                - "restore": 修复后重新入库（从隔离区移回正常路径）
                - "re_crawl": 重新采集（删除记录，触发重新爬取）
                - "discard": 永久丢弃（标记为已丢弃）

        Returns:
            更新后的隔离记录

        Example:
            >>> manager = QuarantineManager()
            >>> # 修复后重新入库
            >>> record = manager.resolve_record(
            ...     record_id=123,
            ...     resolution="文件已修复，重新验证通过",
            ...     handler="admin",
            ...     action="restore"
            ... )
        """
        with self.pg_client.get_session() as session:
            record = session.query(QuarantineRecord).filter(
                QuarantineRecord.id == record_id
            ).first()

            if not record:
                raise ValueError(f"隔离记录不存在: id={record_id}")

            if record.status != 'pending':
                raise ValueError(f"隔离记录状态不是 pending，无法处理: status={record.status}")

            # 更新记录
            record.status = 'resolved' if action != 'discard' else 'discarded'
            record.handler = handler
            record.resolution = resolution
            record.resolution_time = datetime.now()

            # 根据动作执行相应操作
            if action == "restore":
                # 修复后重新入库：从隔离区移回正常路径
                self._restore_from_quarantine(record, session)
            elif action == "re_crawl":
                # 重新采集：删除隔离记录和文件，触发重新爬取
                self._prepare_re_crawl(record, session)
            elif action == "discard":
                # 永久丢弃：仅标记状态，保留记录和文件用于审计
                self.logger.info(f"标记为已丢弃: record_id={record_id}")
            else:
                raise ValueError(f"未知的处理动作: {action}")

            session.commit()
            self.logger.info(f"✅ 隔离记录已处理: id={record_id}, action={action}")

            return record

    def _restore_from_quarantine(
        self,
        record: QuarantineRecord,
        session: Session
    ) -> None:
        """
        从隔离区恢复文件到正常路径

        Args:
            record: 隔离记录
            session: 数据库会话
        """
        try:
            # 检查隔离区文件是否存在
            if not self.minio_client.file_exists(record.quarantine_path):
                self.logger.warning(f"隔离区文件不存在: {record.quarantine_path}")
                return

            # 下载隔离区文件
            file_data = self.minio_client.download_file(record.quarantine_path)
            if not file_data:
                self.logger.error(f"无法下载隔离区文件: {record.quarantine_path}")
                return

            # 上传到正常路径
            content_type = self._guess_content_type(record.original_path)
            success = self.minio_client.upload_file(
                object_name=record.original_path,
                data=file_data,
                content_type=content_type,
                metadata={
                    "restored_from_quarantine": True,
                    "restore_time": datetime.now().isoformat(),
                    "original_quarantine_id": record.id
                }
            )

            if success:
                self.logger.info(f"✅ 文件已恢复到正常路径: {record.original_path}")

                # 更新文档状态
                if record.document_id:
                    doc = session.query(Document).filter(
                        Document.id == record.document_id
                    ).first()
                    if doc:
                        doc.status = DocumentStatus.CRAWLED.value
                        self.logger.info(f"✅ 文档状态已更新为 crawled: document_id={record.document_id}")
            else:
                self.logger.error(f"❌ 恢复文件失败: {record.original_path}")

        except Exception as e:
            self.logger.error(f"❌ 恢复文件异常: {e}", exc_info=True)

    def _prepare_re_crawl(
        self,
        record: QuarantineRecord,
        session: Session
    ) -> None:
        """
        准备重新采集：删除隔离记录和文件

        Args:
            record: 隔离记录
            session: 数据库会话
        """
        try:
            # 删除隔离区文件
            if self.minio_client.file_exists(record.quarantine_path):
                self.minio_client.delete_file(record.quarantine_path)
                self.logger.info(f"✅ 已删除隔离区文件: {record.quarantine_path}")

            # 删除文档记录（如果存在）
            if record.document_id:
                doc = session.query(Document).filter(
                    Document.id == record.document_id
                ).first()
                if doc:
                    session.delete(doc)
                    self.logger.info(f"✅ 已删除文档记录: document_id={record.document_id}")

            # 注意：隔离记录本身保留，但状态标记为 resolved
            # 这样可以在数据库中追踪历史

        except Exception as e:
            self.logger.error(f"❌ 准备重新采集异常: {e}", exc_info=True)

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取隔离区统计信息

        Returns:
            统计信息字典

        Example:
            >>> manager = QuarantineManager()
            >>> stats = manager.get_statistics()
            >>> print(f"待处理: {stats['pending_count']}")
        """
        with self.pg_client.get_session() as session:
            # 按状态统计
            pending_count = session.query(QuarantineRecord).filter(
                QuarantineRecord.status == 'pending'
            ).count()

            processing_count = session.query(QuarantineRecord).filter(
                QuarantineRecord.status == 'processing'
            ).count()

            resolved_count = session.query(QuarantineRecord).filter(
                QuarantineRecord.status == 'resolved'
            ).count()

            discarded_count = session.query(QuarantineRecord).filter(
                QuarantineRecord.status == 'discarded'
            ).count()

            # 按失败阶段统计
            by_stage = {}
            for stage in ['ingestion_failed', 'validation_failed', 'content_failed']:
                count = session.query(QuarantineRecord).filter(
                    QuarantineRecord.failure_stage == stage,
                    QuarantineRecord.status == 'pending'
                ).count()
                by_stage[stage] = count

            return {
                "pending_count": pending_count,
                "processing_count": processing_count,
                "resolved_count": resolved_count,
                "discarded_count": discarded_count,
                "total_count": pending_count + processing_count + resolved_count + discarded_count,
                "by_stage": by_stage,
                "alert_threshold": 100,
                "status": "warning" if pending_count > 100 else "ok"
            }

    def _guess_content_type(self, file_path: str) -> str:
        """
        根据文件路径猜测内容类型

        Args:
            file_path: 文件路径

        Returns:
            MIME 类型
        """
        ext = file_path.lower().split('.')[-1] if '.' in file_path else ''
        content_types = {
            'pdf': 'application/pdf',
            'json': 'application/json',
            'txt': 'text/plain',
            'html': 'text/html',
            'htm': 'text/html',
            'xml': 'application/xml',
            'csv': 'text/csv',
        }
        return content_types.get(ext, 'application/octet-stream')


# 便捷函数：获取默认的隔离管理器实例
def get_quarantine_manager() -> QuarantineManager:
    """
    获取默认的隔离管理器实例（单例模式）

    Returns:
        隔离管理器实例
    """
    return QuarantineManager()
