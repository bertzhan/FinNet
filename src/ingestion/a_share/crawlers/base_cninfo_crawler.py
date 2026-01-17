# -*- coding: utf-8 -*-
"""
CNINFO爬虫基类
提取公共逻辑，减少代码重复
"""
import os
import tempfile
import csv
from typing import List, Optional, Tuple
from pathlib import Path

from src.ingestion.base.base_crawler import BaseCrawler, CrawlTask, CrawlResult
from src.common.logger import get_logger

logger = get_logger(__name__)


class CninfoBaseCrawler(BaseCrawler):
    """
    CNINFO爬虫基类
    提供公共的文件处理、批量爬取等功能
    """

    def _get_a_share_dir(self) -> str:
        """
        获取 a_share 目录路径
        
        Returns:
            a_share 目录的绝对路径
        """
        # crawlers/ 目录的父目录就是 a_share 目录
        return os.path.dirname(os.path.dirname(__file__))

    def _get_cache_file_path(self, filename: str) -> str:
        """
        获取缓存文件路径
        
        Args:
            filename: 缓存文件名（如 'orgid_cache.json'）
            
        Returns:
            缓存文件的完整路径
        """
        return os.path.join(self._get_a_share_dir(), filename)

    def _safe_import(self, relative_path: str, absolute_path: str):
        """
        安全的模块导入（支持相对和绝对导入）
        
        Args:
            relative_path: 相对导入路径
            absolute_path: 绝对导入路径
            
        Returns:
            导入的模块或函数
        """
        try:
            # 尝试相对导入
            module_parts = relative_path.split('.')
            if len(module_parts) == 2:
                from importlib import import_module
                module = import_module(relative_path, package=__package__)
                return module
            else:
                # 动态导入
                exec(f"from {relative_path} import *")
        except ImportError:
            # 如果相对导入失败，使用绝对导入
            try:
                from importlib import import_module
                return import_module(absolute_path)
            except ImportError as e:
                logger.error(f"导入失败: {relative_path} / {absolute_path}: {e}")
                raise

    def _process_downloaded_file(
        self, 
        file_path: str, 
        task: CrawlTask,
        extract_year_from_filename: bool = False
    ) -> CrawlResult:
        """
        处理已下载的文件（计算哈希、上传MinIO、记录PostgreSQL）
        
        Args:
            file_path: 文件路径
            task: 任务
            extract_year_from_filename: 是否从文件名提取年份（IPO使用）
            
        Returns:
            爬取结果
        """
        # 读取metadata文件（如果存在），将URL等信息添加到task.metadata
        metadata_file = file_path.replace('.pdf', '.meta.json').replace('.html', '.meta.json').replace('.htm', '.meta.json')
        if os.path.exists(metadata_file):
            try:
                from ..utils.file_utils import load_json
                metadata_info = load_json(metadata_file, {})
                # 将URL等信息添加到task.metadata
                if 'source_url' in metadata_info:
                    task.metadata['source_url'] = metadata_info['source_url']
                # 保留其他metadata字段（如publication_date等）
                for key, value in metadata_info.items():
                    if key not in task.metadata:
                        task.metadata[key] = value
                self.logger.debug(f"从metadata文件读取URL: {metadata_info.get('source_url', 'N/A')}")
            except Exception as e:
                self.logger.warning(f"读取metadata文件失败: {e}")

        # 计算文件哈希和大小
        try:
            from src.common.utils import calculate_file_hash
            file_hash = calculate_file_hash(file_path, algorithm='md5')
            file_size = Path(file_path).stat().st_size
        except Exception as e:
            self.logger.error(f"计算文件信息失败: {e}")
            file_hash = None
            file_size = None

        # 生成文件名和年份
        if extract_year_from_filename:
            # IPO: 文件名统一为 document.pdf 或 document.html，年份从metadata获取
            filename = os.path.basename(file_path)
            # 从task.metadata中获取年份（如果processor传递了）
            year = task.metadata.get('publication_year') if task.metadata else None
            if year:
                try:
                    year = int(year)
                except (ValueError, TypeError):
                    year = None
            quarter = None
        else:
            # 定期报告: 使用任务的year和quarter
            year = task.year
            quarter = task.quarter
            filename = "document.pdf"
        
        # 生成 MinIO 路径
        # Q2（半年报）和 Q4（年报）不需要季度文件夹
        if quarter in [2, 4]:
            quarter_for_path = None
        else:
            quarter_for_path = quarter
        
        # 调试：记录路径生成参数
        self.logger.debug(f"[路径生成] quarter={quarter}, quarter_for_path={quarter_for_path}, doc_type={task.doc_type}")
        
        minio_object_path = self.path_manager.get_bronze_path(
            market=task.market,
            doc_type=task.doc_type,
            stock_code=task.stock_code,
            year=year,
            quarter=quarter_for_path,
            filename=filename
        )
        
        # 调试：验证路径生成
        self.logger.debug(f"[路径生成] 生成的路径: {minio_object_path}")
        if quarter == 4 and '/Q4/' in minio_object_path:
            self.logger.warning(f"⚠️ Q4路径仍包含Q4文件夹: {minio_object_path}, quarter_for_path={quarter_for_path}, quarter={quarter}")

        # 上传到 MinIO
        document_id = None
        if not self.enable_minio:
            self.logger.warning(f"⚠️ MinIO 未启用，跳过上传: {minio_object_path}")
        elif not self.minio_client:
            self.logger.error(f"❌ MinIO 客户端未初始化，无法上传: {minio_object_path}")
        else:
            try:
                self.logger.info(f"开始上传到 MinIO: {minio_object_path}")
                # 统一metadata格式：只保留source_url和publish_date
                minio_metadata = self._prepare_minio_metadata(task)
                upload_success = self.minio_client.upload_file(
                    object_name=minio_object_path,
                    file_path=file_path,
                    metadata=minio_metadata
                )

                if upload_success:
                    self.logger.info(f"✅ MinIO 上传成功: {minio_object_path}")
                else:
                    self.logger.error(f"❌ MinIO 上传失败（返回 False）: {minio_object_path}")
            except Exception as e:
                self.logger.error(f"❌ MinIO 上传异常: {e}", exc_info=True)

        # 记录到 PostgreSQL
        document_id = None
        if not self.enable_postgres:
            self.logger.warning(f"⚠️ PostgreSQL 未启用，跳过记录: {minio_object_path}")
        elif not self.pg_client:
            self.logger.error(f"❌ PostgreSQL 客户端未初始化，无法记录: {minio_object_path}")
        elif self.enable_postgres and self.pg_client:
            try:
                from src.storage.metadata import crud
                with self.pg_client.get_session() as session:
                    # 检查是否已存在
                    existing_doc = crud.get_document_by_path(session, minio_object_path)

                    if existing_doc:
                        self.logger.info(f"文档已存在: id={existing_doc.id}")
                        document_id = existing_doc.id
                    else:
                        # 创建新记录
                        doc = crud.create_document(
                            session=session,
                            stock_code=task.stock_code,
                            company_name=task.company_name,
                            market=task.market.value,
                            doc_type=task.doc_type.value,
                            year=year,
                            quarter=quarter,
                            minio_object_path=minio_object_path,
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

        return CrawlResult(
            task=task,
            success=True,
            local_file_path=file_path,
            minio_object_path=minio_object_path,
            document_id=document_id,
            file_size=file_size,
            file_hash=file_hash,
            metadata=task.metadata
        )

    def _create_temp_csv(
        self, 
        tasks: List[CrawlTask], 
        columns: List[str],
        row_builder
    ) -> str:
        """
        创建临时CSV文件
        
        Args:
            tasks: 任务列表
            columns: CSV列名
            row_builder: 行构建函数，接收task，返回行数据
            
        Returns:
            临时CSV文件路径
        """
        with tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.csv', 
            delete=False, 
            encoding='utf-8-sig', 
            newline=''
        ) as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            
            for task in tasks:
                row = row_builder(task)
                writer.writerow(row)
            
            return f.name

    def _read_failed_tasks(self, fail_csv: str, task_key_extractor) -> set:
        """
        读取失败任务记录
        
        Args:
            fail_csv: 失败记录CSV文件路径
            task_key_extractor: 从CSV行提取任务键的函数
            
        Returns:
            失败任务键的集合
        """
        failed_tasks = set()
        if os.path.exists(fail_csv):
            with open(fail_csv, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    task_key = task_key_extractor(row)
                    if task_key:
                        failed_tasks.add(task_key)
        return failed_tasks

    def _cleanup_temp_files(self, *file_paths):
        """
        清理临时文件
        
        Args:
            *file_paths: 要删除的文件路径
        """
        for file_path in file_paths:
            try:
                if file_path and os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception as e:
                self.logger.warning(f"清理临时文件失败 {file_path}: {e}")
