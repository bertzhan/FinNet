# -*- coding: utf-8 -*-
"""
A股定期报告爬虫实现（CNINFO）
继承自 CninfoBaseCrawler，集成 storage 层
"""
import os
import tempfile
import csv
import multiprocessing
from typing import List, Optional, Tuple

# 支持直接运行和作为模块导入
try:
    from .base_cninfo_crawler import CninfoBaseCrawler
except ImportError:
    from src.ingestion.a_share.crawlers.base_cninfo_crawler import CninfoBaseCrawler

from src.ingestion.base.base_crawler import CrawlTask, CrawlResult
from src.common.constants import Market, DocType
from src.common.logger import get_logger

logger = get_logger(__name__)


class ReportCrawler(CninfoBaseCrawler):
    """
    A股定期报告爬虫实现（CNINFO 巨潮资讯网）
    
    使用本地模块化的下载逻辑
    实现 _download_file() 方法，其余由基类自动处理
    """

    def __init__(
        self,
        enable_minio: bool = True,
        enable_postgres: bool = True,
        workers: int = 1
    ):
        """
        Args:
            enable_minio: 是否启用 MinIO 上传
            enable_postgres: 是否启用 PostgreSQL 记录
            workers: 并行进程数（1 表示单线程）
        """
        super().__init__(
            market=Market.A_SHARE,
            enable_minio=enable_minio,
            enable_postgres=enable_postgres
        )
        self.workers = workers

    def _download_file(self, task: CrawlTask) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        下载文件（通过调用现有爬虫逻辑）

        Args:
            task: 爬取任务

        Returns:
            (是否成功, 本地文件路径, 错误信息)
        """
        try:
            # 导入任务处理器模块
            try:
                from ..processor.report_processor import process_single_task
            except ImportError:
                from src.ingestion.a_share.processor.report_processor import process_single_task

            # 创建临时目录用于下载
            temp_dir = tempfile.mkdtemp(prefix='cninfo_download_')

            # 准备任务数据
            quarter_str = f"Q{task.quarter}" if task.quarter else "Q4"
            shared_lock = multiprocessing.Lock()

            # orgId缓存文件路径（使用基类方法）
            orgid_cache_file = self._get_cache_file_path('orgid_cache.json')
            code_change_cache_file = self._get_cache_file_path('code_change_cache.json')

            existing_pdf_cache = set()

            task_data = (
                task.stock_code,
                task.company_name,
                task.year,
                quarter_str,
                temp_dir,
                orgid_cache_file,
                code_change_cache_file,
                shared_lock,
                existing_pdf_cache
            )

            # 调用现有爬虫逻辑
            success, failure_record = process_single_task(task_data)

            if not success:
                error_msg = failure_record[4] if failure_record and len(failure_record) > 4 else "下载失败"
                self.logger.error(f"下载失败: {task.stock_code} {task.year} Q{task.quarter} - {error_msg}")
                return False, None, error_msg

            # 查找下载的文件
            expected_path = self._get_expected_file_path(temp_dir, task)
            self.logger.debug(f"期望文件路径: {expected_path}")
            file_path = self._find_downloaded_file(temp_dir, task)

            if not file_path:
                # 文件未找到，可能是以下情况：
                # 1. checkpoint 已存在（跳过下载，但文件不在 temp_dir）
                # 2. 下载失败但返回了成功（异常情况）
                
                # 检查临时目录中是否有任何文件
                temp_files = []
                if os.path.exists(temp_dir):
                    for root, dirs, files in os.walk(temp_dir):
                        for f in files:
                            if f.endswith('.pdf'):
                                temp_files.append(os.path.join(root, f))
                
                self.logger.warning(
                    f"文件未找到: {task.stock_code} {task.year} Q{task.quarter}\n"
                    f"  期望路径: {expected_path}\n"
                    f"  临时目录: {temp_dir}\n"
                    f"  临时目录中的PDF文件数: {len(temp_files)}\n"
                    f"  前3个PDF文件: {temp_files[:3]}"
                )
                
                # 检查 checkpoint
                from ..state.shared_state import SharedState
                checkpoint_file = os.path.join(temp_dir, "checkpoint.json")
                shared = SharedState(checkpoint_file, orgid_cache_file, code_change_cache_file, shared_lock)
                checkpoint = shared.load_checkpoint()
                key = f"{task.stock_code}-{task.year}-{quarter_str}"
                
                if checkpoint.get(key):
                    # checkpoint 存在但文件不在 temp_dir，说明是之前运行留下的 checkpoint
                    # 删除 checkpoint，强制重新下载
                    self.logger.warning(f"checkpoint存在但文件未找到，删除checkpoint并重新下载: {task.stock_code} {task.year} Q{task.quarter}")
                    shared.remove_checkpoint(key)
                    # 重新调用下载
                    success, failure_record = process_single_task(task_data)
                    if not success:
                        error_msg = failure_record[4] if failure_record and len(failure_record) > 4 else "下载失败"
                        self.logger.error(f"重新下载失败: {task.stock_code} {task.year} Q{task.quarter} - {error_msg}")
                        return False, None, error_msg
                    # 再次查找文件
                    file_path = self._find_downloaded_file(temp_dir, task)
                    if not file_path:
                        error_msg = "重新下载后文件仍未找到"
                        self.logger.error(f"{error_msg}: {task.stock_code} {task.year} Q{task.quarter}")
                        return False, None, error_msg
                else:
                    # 没有 checkpoint，说明下载失败
                    error_msg = "文件下载失败或未找到"
                    self.logger.error(
                        f"{error_msg}: {task.stock_code} {task.year} Q{task.quarter}\n"
                        f"  process_single_task 返回了成功，但文件不存在\n"
                        f"  可能原因：1) 下载函数返回成功但实际未保存文件 2) 文件保存路径不匹配"
                    )
                    return False, None, error_msg

            self.logger.info(f"下载成功: {file_path}")
            return True, file_path, None

        except Exception as e:
            error_msg = f"下载异常: {e}"
            self.logger.error(f"{error_msg}: {task.stock_code} {task.year} Q{task.quarter}", exc_info=True)
            return False, None, error_msg

    def _get_expected_file_path(self, output_root: str, task: CrawlTask) -> str:
        """
        获取期望的文件路径（用于调试）

        Args:
            output_root: 输出根目录
            task: 任务

        Returns:
            期望的文件路径
        """
        from src.storage.object_store.path_manager import PathManager
        from src.common.constants import Market, DocType
        
        quarter_num = task.quarter if task.quarter else 4
        
        if quarter_num == 4:
            doc_type = DocType.ANNUAL_REPORT
        elif quarter_num == 2:
            doc_type = DocType.INTERIM_REPORT
        else:
            doc_type = DocType.QUARTERLY_REPORT
        
        filename = "document.pdf"
        
        path_manager = PathManager()
        quarter_for_path = quarter_num if quarter_num not in [2, 4] else None
        minio_path = path_manager.get_bronze_path(
            market=Market.A_SHARE,
            doc_type=doc_type,
            stock_code=task.stock_code,
            year=task.year,
            quarter=quarter_for_path,
            filename=filename
        )
        
        return os.path.join(output_root, minio_path)

    def _find_downloaded_file(self, output_root: str, task: CrawlTask) -> Optional[str]:
        """
        查找下载的文件（使用与MinIO一致的路径结构）

        Args:
            output_root: 输出根目录
            task: 任务

        Returns:
            文件路径，如果未找到则返回 None
        """
        from src.storage.object_store.path_manager import PathManager
        from src.common.constants import Market, DocType
        
        # 使用 PathManager 生成与 MinIO 一致的路径结构
        quarter_num = task.quarter if task.quarter else 4
        
        # 根据季度确定文档类型
        if quarter_num == 4:
            doc_type = DocType.ANNUAL_REPORT
        elif quarter_num == 2:
            doc_type = DocType.INTERIM_REPORT
        else:
            doc_type = DocType.QUARTERLY_REPORT
        
        # 生成文件名
        filename = "document.pdf"
        
        # 使用 PathManager 生成路径
        path_manager = PathManager()
        quarter_for_path = quarter_num if quarter_num not in [2, 4] else None
        minio_path = path_manager.get_bronze_path(
            market=Market.A_SHARE,
            doc_type=doc_type,
            stock_code=task.stock_code,
            year=task.year,
            quarter=quarter_for_path,
            filename=filename
        )
        
        # 转换为本地文件系统路径
        file_path = os.path.join(output_root, minio_path)
        
        if os.path.exists(file_path):
            return file_path
        
        # 兼容旧格式：尝试查找旧路径结构
        exchanges = ['SZ', 'SH', 'BJ']
        for exchange in exchanges:
            code_dir = os.path.join(output_root, exchange, task.stock_code, str(task.year))
            if not os.path.exists(code_dir):
                continue
            
            old_file_path = os.path.join(code_dir, filename)
            if os.path.exists(old_file_path):
                return old_file_path
            
            # 旧格式：兼容旧文件名格式（如果有的话）
            import glob
            # 尝试查找旧格式的文件名
            old_pattern = f"{task.stock_code}_{task.year}_*.pdf"
            files = glob.glob(os.path.join(code_dir, old_pattern))
            if files:
                return files[0]

        return None

    def crawl_batch(self, tasks: List[CrawlTask]) -> List[CrawlResult]:
        """
        批量爬取

        Args:
            tasks: 任务列表

        Returns:
            结果列表
        """
        if not tasks:
            return []

        # 如果只有一个任务或不启用多进程，使用基类的单任务逻辑
        if len(tasks) == 1 or self.workers <= 1:
            return super().crawl_batch(tasks)

        # 多任务 + 多进程：使用现有的 run_multiprocessing
        return self._crawl_batch_multiprocessing(tasks)

    def _crawl_batch_multiprocessing(self, tasks: List[CrawlTask]) -> List[CrawlResult]:
        """
        使用多进程批量爬取

        Args:
            tasks: 任务列表

        Returns:
            结果列表
        """
        try:
            # 导入任务处理器模块
            try:
                from ..processor.report_processor import run_multiprocessing
            except ImportError:
                from src.ingestion.a_share.processor.report_processor import run_multiprocessing

            # 创建临时CSV文件
            temp_csv = self._create_temp_csv(
                tasks,
                ['code', 'name', 'year', 'quarter'],
                lambda task: [
                    task.stock_code,
                    task.company_name,
                    task.year,
                    f"Q{task.quarter}" if task.quarter else "Q4"
                ]
            )

            # 创建临时输出目录和失败记录文件
            temp_output = tempfile.mkdtemp(prefix='cninfo_batch_')
            temp_fail_csv = tempfile.NamedTemporaryFile(
                mode='w', suffix='.csv', delete=False, encoding='utf-8-sig', newline=''
            ).name

            try:
                # 调用现有的多进程爬虫逻辑
                run_multiprocessing(
                    input_csv=temp_csv,
                    out_root=temp_output,
                    fail_csv=temp_fail_csv,
                    workers=self.workers,
                    debug=False
                )

                # 读取失败记录
                failed_tasks = self._read_failed_tasks(
                    temp_fail_csv,
                    lambda row: (
                        row.get('code', '').strip(),
                        int(row.get('year', 0)),
                        row.get('quarter', '').strip()
                    )
                )

                # 构建结果列表
                results = []
                for task in tasks:
                    quarter_str = f"Q{task.quarter}" if task.quarter else "Q4"
                    task_key = (task.stock_code, task.year, quarter_str)

                    if task_key in failed_tasks:
                        # 失败任务
                        results.append(CrawlResult(
                            task=task,
                            success=False,
                            error_message="爬取失败，详见失败记录"
                        ))
                    else:
                        # 成功任务，查找文件
                        file_path = self._find_downloaded_file(temp_output, task)
                        if file_path and os.path.exists(file_path):
                            temp_result = self._process_downloaded_file(file_path, task)
                            results.append(temp_result)
                        else:
                            results.append(CrawlResult(
                                task=task,
                                success=False,
                                error_message="文件未找到"
                            ))

                return results

            finally:
                # 清理临时文件
                self._cleanup_temp_files(temp_csv, temp_fail_csv)

        except Exception as e:
            self.logger.error(f"多进程批量爬取失败: {e}", exc_info=True)
            # 降级到单任务模式
            return super().crawl_batch(tasks)


def main():
    """测试入口"""
    # 创建爬虫实例
    crawler = ReportCrawler(
        enable_minio=True,
        enable_postgres=True,
        workers=4
    )

    # 创建测试任务
    task = CrawlTask(
        stock_code="000001",
        company_name="平安银行",
        market=Market.A_SHARE,
        doc_type=DocType.ANNUAL_REPORT,
        year=2023,
        quarter=4
    )

    # 执行爬取
    result = crawler.crawl(task)

    # 打印结果
    if result.success:
        print(f"✅ 爬取成功：{result.local_file_path}")
        print(f"   MinIO: {result.minio_object_path}")
        print(f"   数据库ID: {result.document_id}")
    else:
        print(f"❌ 爬取失败：{result.error_message}")


if __name__ == '__main__':
    main()
