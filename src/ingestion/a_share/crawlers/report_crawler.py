# -*- coding: utf-8 -*-
"""
A股定期报告爬虫实现（CNINFO）
继承自 CninfoBaseCrawler，集成 storage 层
"""
import os
import tempfile
import csv
import multiprocessing
import queue
import threading
import time
from typing import List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

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
        使用多进程批量爬取 + 主线程异步上传
        
        优化：下载和上传并行进行，而不是串行等待
        
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

            # 0. 检查数据库，过滤已存在的任务（避免重复爬取）
            tasks_to_crawl = []
            skipped_results = {}  # {task_key: CrawlResult}
            
            if self.enable_postgres and self.pg_client:
                try:
                    from src.storage.metadata import crud
                    with self.pg_client.get_session() as session:
                        for task in tasks:
                            quarter_str = f"Q{task.quarter}" if task.quarter else "Q4"
                            task_key = (task.stock_code, task.year, quarter_str)
                            
                            existing_doc = crud.get_document_by_task(
                                session=session,
                                stock_code=task.stock_code,
                                market=task.market.value,
                                doc_type=task.doc_type.value,
                                year=task.year,
                                quarter=task.quarter
                            )
                            
                            if existing_doc:
                                # 文档已存在，跳过下载
                                self.logger.info(
                                    f"✅ 文档已存在，跳过下载: {task.stock_code} {task.year} Q{task.quarter} "
                                    f"(id={existing_doc.id}, path={existing_doc.minio_object_path})"
                                )
                                skipped_results[task_key] = CrawlResult(
                                    task=task,
                                    success=True,
                                    minio_object_path=existing_doc.minio_object_path,
                                    document_id=existing_doc.id,
                                    file_size=existing_doc.file_size,
                                    file_hash=existing_doc.file_hash,
                                    metadata=task.metadata
                                )
                            else:
                                # 需要爬取的任务
                                tasks_to_crawl.append(task)
                except Exception as e:
                    # 检查失败不影响爬取流程，记录警告后继续
                    self.logger.warning(f"⚠️ 检查数据库时发生异常，继续爬取所有任务: {e}")
                    tasks_to_crawl = tasks
            else:
                # 未启用 PostgreSQL，爬取所有任务
                tasks_to_crawl = tasks
            
            if not tasks_to_crawl:
                # 所有任务都已存在
                self.logger.info(f"✅ 所有 {len(tasks)} 个任务都已存在，跳过爬取")
                return list(skipped_results.values())
            
            if len(skipped_results) > 0:
                self.logger.info(f"跳过 {len(skipped_results)} 个已存在的任务，剩余 {len(tasks_to_crawl)} 个任务需要爬取")

            # 创建临时CSV文件（只包含需要爬取的任务）
            temp_csv = self._create_temp_csv(
                tasks_to_crawl,
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

            # 创建上传队列和结果字典
            upload_queue = queue.Queue()
            upload_results = {}  # {task_key: CrawlResult}
            upload_lock = threading.Lock()
            processed_files = set()  # 已处理的文件路径集合
            
            # 创建上传线程池（使用较少的线程，避免过度占用资源）
            upload_workers = min(4, max(1, len(tasks_to_crawl) // 10))  # 根据任务数量动态调整
            self.logger.info(f"启动 {upload_workers} 个上传线程")
            
            upload_executor = ThreadPoolExecutor(max_workers=upload_workers)
            upload_futures = {}  # {task_key: future}
            
            def upload_file(task: CrawlTask, file_path: str):
                """上传单个文件"""
                try:
                    self.logger.debug(f"开始上传: {task.stock_code} {task.year} Q{task.quarter}")
                    result = self._process_downloaded_file(file_path, task)
                    return result
                except Exception as e:
                    self.logger.error(f"上传异常: {task.stock_code} {task.year} Q{task.quarter} - {e}", exc_info=True)
                    return CrawlResult(
                        task=task,
                        success=False,
                        error_message=f"上传异常: {e}"
                    )
            
            try:
                # 启动下载（在后台线程）
                download_exception = []
                download_thread = threading.Thread(
                    target=lambda: self._run_download_with_exception_handling(
                        run_multiprocessing,
                        temp_csv,
                        temp_output,
                        temp_fail_csv,
                        download_exception
                    ),
                    daemon=False
                )
                download_thread.start()
                self.logger.info(f"下载线程已启动，workers={self.workers}")
                
                # 主线程轮询检查下载完成的文件并异步上传
                poll_interval = 0.5  # 轮询间隔（秒）
                last_file_count = 0
                no_new_file_count = 0
                max_no_new_file_count = 10  # 连续10次没有新文件，认为下载完成
                
                while download_thread.is_alive() or no_new_file_count < max_no_new_file_count:
                    # 检查是否有下载异常
                    if download_exception:
                        raise download_exception[0]
                    
                    # 检查新下载的文件
                    current_file_count = 0
                    for task in tasks_to_crawl:
                        quarter_str = f"Q{task.quarter}" if task.quarter else "Q4"
                        task_key = (task.stock_code, task.year, quarter_str)
                        
                        # 跳过已处理的任务
                        if task_key in upload_results or task_key in upload_futures:
                            current_file_count += 1
                            continue
                        
                        # 查找文件
                        file_path = self._find_downloaded_file(temp_output, task)
                        if file_path and os.path.exists(file_path) and file_path not in processed_files:
                            # 检查文件是否下载完成（文件大小稳定）
                            if self._is_file_stable(file_path):
                                # 文件已下载完成，提交到上传线程池
                                processed_files.add(file_path)
                                future = upload_executor.submit(upload_file, task, file_path)
                                upload_futures[task_key] = future
                                current_file_count += 1
                                self.logger.debug(f"发现新文件，已提交上传: {task.stock_code} {task.year} Q{task.quarter}")
                            # 如果文件不稳定，等待下次轮询再检查
                    
                    # 检查已完成的上传
                    completed_futures = []
                    for task_key, future in upload_futures.items():
                        if future.done():
                            try:
                                result = future.result()
                                with upload_lock:
                                    upload_results[task_key] = result
                                completed_futures.append(task_key)
                                if result.success:
                                    self.logger.debug(f"上传完成: {task_key}")
                                else:
                                    self.logger.warning(f"上传失败: {task_key} - {result.error_message}")
                            except Exception as e:
                                self.logger.error(f"获取上传结果异常: {task_key} - {e}", exc_info=True)
                                with upload_lock:
                                    upload_results[task_key] = CrawlResult(
                                        task=next(t for t in tasks_to_crawl if (t.stock_code, t.year, f"Q{t.quarter}" if t.quarter else "Q4") == task_key),
                                        success=False,
                                        error_message=f"上传异常: {e}"
                                    )
                                completed_futures.append(task_key)
                    
                    # 清理已完成的上传任务
                    for task_key in completed_futures:
                        del upload_futures[task_key]
                    
                    # 检查是否有新文件
                    if current_file_count > last_file_count:
                        no_new_file_count = 0
                        last_file_count = current_file_count
                    else:
                        no_new_file_count += 1
                    
                    # 等待一段时间再检查
                    time.sleep(poll_interval)
                
                # 等待下载线程完成
                download_thread.join(timeout=300)  # 最多等待5分钟
                if download_thread.is_alive():
                    self.logger.warning("下载线程超时，继续处理已下载的文件")
                
                # 等待所有上传完成
                self.logger.info(f"等待 {len(upload_futures)} 个上传任务完成...")
                for task_key, future in upload_futures.items():
                    try:
                        result = future.result(timeout=60)  # 每个上传最多等待1分钟
                        with upload_lock:
                            upload_results[task_key] = result
                    except Exception as e:
                        self.logger.error(f"等待上传完成异常: {task_key} - {e}", exc_info=True)
                        with upload_lock:
                            upload_results[task_key] = CrawlResult(
                                task=next(t for t in tasks_to_crawl if (t.stock_code, t.year, f"Q{t.quarter}" if t.quarter else "Q4") == task_key),
                                success=False,
                                error_message=f"上传超时或异常: {e}"
                            )
                
                # 关闭上传线程池
                upload_executor.shutdown(wait=True)
                
                # 读取失败记录
                failed_tasks = set()
                if os.path.exists(temp_fail_csv):
                    failed_tasks = self._read_failed_tasks(
                        temp_fail_csv,
                        lambda row: (
                            row.get('code', '').strip(),
                            int(row.get('year', 0)),
                            row.get('quarter', '').strip()
                        )
                    )

                # 构建结果列表（包含跳过的任务）
                results = []
                for task in tasks:
                    quarter_str = f"Q{task.quarter}" if task.quarter else "Q4"
                    task_key = (task.stock_code, task.year, quarter_str)

                    # 如果任务被跳过（已存在），直接添加跳过结果
                    if task_key in skipped_results:
                        results.append(skipped_results[task_key])
                    elif task_key in failed_tasks:
                        # 失败任务
                        results.append(CrawlResult(
                            task=task,
                            success=False,
                            error_message="爬取失败，详见失败记录"
                        ))
                    elif task_key in upload_results:
                        # 已上传的任务
                        results.append(upload_results[task_key])
                    else:
                        # 未找到文件或未处理
                        file_path = self._find_downloaded_file(temp_output, task)
                        if file_path and os.path.exists(file_path):
                            # 文件存在但未上传，可能是轮询时遗漏了，立即上传
                            self.logger.warning(f"发现遗漏的文件，立即上传: {task.stock_code} {task.year} Q{task.quarter}")
                            temp_result = self._process_downloaded_file(file_path, task)
                            results.append(temp_result)
                        else:
                            results.append(CrawlResult(
                                task=task,
                                success=False,
                                error_message="文件未找到或未处理"
                            ))

                # 统计结果
                success_count = sum(1 for r in results if r.success)
                upload_success_count = sum(1 for r in results if r.success and r.minio_object_path)
                self.logger.info(
                    f"批量爬取完成: 总计 {len(results)}, 成功 {success_count}, "
                    f"MinIO上传成功 {upload_success_count}"
                )

                return results

            finally:
                # 确保上传线程池关闭
                upload_executor.shutdown(wait=True)
                # 清理临时文件
                self._cleanup_temp_files(temp_csv, temp_fail_csv)

        except Exception as e:
            self.logger.error(f"多进程批量爬取失败: {e}", exc_info=True)
            # 降级到单任务模式
            return super().crawl_batch(tasks)
    
    def _run_download_with_exception_handling(
        self,
        run_multiprocessing_func,
        temp_csv: str,
        temp_output: str,
        temp_fail_csv: str,
        exception_list: list
    ):
        """
        在独立线程中运行下载，捕获异常
        
        Args:
            run_multiprocessing_func: run_multiprocessing 函数
            temp_csv: 临时CSV文件路径
            temp_output: 临时输出目录
            temp_fail_csv: 失败记录CSV路径
            exception_list: 异常列表（用于传递异常）
        """
        try:
            run_multiprocessing_func(
                input_csv=temp_csv,
                out_root=temp_output,
                fail_csv=temp_fail_csv,
                workers=self.workers,
                debug=False
            )
        except Exception as e:
            self.logger.error(f"下载线程异常: {e}", exc_info=True)
            exception_list.append(e)


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
