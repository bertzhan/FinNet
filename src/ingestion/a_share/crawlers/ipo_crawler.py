# -*- coding: utf-8 -*-
"""
A股IPO招股说明书爬虫实现（CNINFO）
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


class CninfoIPOProspectusCrawler(CninfoBaseCrawler):
    """
    A股IPO招股说明书爬虫实现（CNINFO 巨潮资讯网）

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
        下载文件（IPO招股说明书）

        Args:
            task: 爬取任务（IPO不需要year和quarter，但CrawlTask要求，可以传入任意值）

        Returns:
            (是否成功, 本地文件路径, 错误信息)
        """
        try:
            # 导入任务处理器模块
            try:
                from ..processor.ipo_processor import process_single_ipo_task
            except ImportError:
                from src.ingestion.a_share.processor.ipo_processor import process_single_ipo_task

            # 创建临时目录用于下载
            temp_dir = tempfile.mkdtemp(prefix='cninfo_ipo_download_')

            # 准备任务数据
            # IPO任务格式：(code, name, out_root, checkpoint_file, orgid_cache_file)
            shared_lock = multiprocessing.Lock()

            # orgId缓存文件路径（使用基类方法）
            orgid_cache_file = self._get_cache_file_path('orgid_cache_ipo.json')

            # checkpoint文件路径
            checkpoint_file = os.path.join(temp_dir, 'checkpoint_ipo.json')

            task_data = (
                task.stock_code,
                task.company_name,
                temp_dir,
                checkpoint_file,
                orgid_cache_file
            )

            # 调用下载逻辑
            success, failure_record = process_single_ipo_task(task_data)

            if not success:
                error_msg = failure_record[2] if failure_record and len(failure_record) > 2 else "下载失败"
                self.logger.error(f"下载失败: {task.stock_code} - {error_msg}")
                return False, None, error_msg

            # 查找下载的文件
            file_path = self._find_downloaded_file(temp_dir, task)

            if not file_path:
                error_msg = "文件下载成功但未找到"
                self.logger.error(f"{error_msg}: {task.stock_code}")
                return False, None, error_msg

            # 如果是HTML文件，验证内容
            if file_path.lower().endswith(('.html', '.htm')):
                is_valid, error_reason = self._validate_html_file(file_path)
                if not is_valid:
                    self.logger.warning(f"HTML文件验证失败: {task.stock_code} - {error_reason}")
                    return False, None, f"HTML文件验证失败: {error_reason}"

            # 读取发布日期信息和URL（从metadata文件）
            metadata_file = file_path.replace('.pdf', '.meta.json').replace('.html', '.meta.json')
            if os.path.exists(metadata_file):
                try:
                    from ..utils.file_utils import load_json
                    metadata_info = load_json(metadata_file, {})
                    # 将发布日期信息和URL添加到task.metadata
                    task.metadata.update({
                        'publication_date': metadata_info.get('publication_date', ''),
                        'publication_year': metadata_info.get('publication_year', ''),
                        'publication_date_iso': metadata_info.get('publication_date_iso', ''),
                        'source_url': metadata_info.get('source_url', '')  # 文档来源URL
                    })
                except Exception as e:
                    self.logger.warning(f"读取metadata文件失败: {e}")

            self.logger.info(f"下载成功: {file_path}")
            return True, file_path, None

        except Exception as e:
            error_msg = f"下载异常: {e}"
            self.logger.error(f"{error_msg}: {task.stock_code}", exc_info=True)
            return False, None, error_msg

    def _find_downloaded_file(self, output_root: str, task: CrawlTask) -> Optional[str]:
        """
        查找下载的文件（IPO版本）

        Args:
            output_root: 输出根目录
            task: 任务

        Returns:
            文件路径，如果未找到则返回 None
        """
        # IPO文件格式（与MinIO一致）：{output_root}/bronze/a_share/ipo_prospectus/{code}/document.pdf 或 document.html
        from src.storage.object_store.path_manager import PathManager
        from src.common.constants import Market, DocType
        
        path_manager = PathManager()
        
        # 构建IPO目录路径（不包含文件名）
        ipo_dir = os.path.join(
            output_root,
            "bronze",
            Market.A_SHARE.value,
            DocType.IPO_PROSPECTUS.value,
            task.stock_code
        )
        
        if not os.path.exists(ipo_dir):
            return None

        import glob
        # IPO文件命名：统一为 document.pdf 或 document.html
        # 先尝试精确匹配：document.pdf 或 document.html
        exact_pdf = os.path.join(ipo_dir, "document.pdf")
        if os.path.exists(exact_pdf):
            return exact_pdf
        
        exact_html = os.path.join(ipo_dir, "document.html")
        if os.path.exists(exact_html):
            return exact_html
        
        # 兼容旧格式：{code}_*.pdf 或 {code}_*.html（如果有的话）
        pattern = f"{task.stock_code}_*.pdf"
        pdf_files = glob.glob(os.path.join(ipo_dir, pattern))
        if pdf_files:
            return pdf_files[0]  # 返回最新的PDF文件

        # 也检查HTML文件
        pattern = f"{task.stock_code}_*.html"
        html_files = glob.glob(os.path.join(ipo_dir, pattern))
        if html_files:
            return html_files[0]  # 返回最新的HTML文件

        return None

    def _validate_html_file(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        验证HTML文件是否包含招股说明书相关内容
        
        Args:
            file_path: HTML文件路径
            
        Returns:
            (是否有效, 错误原因)
        """
        try:
            # 检查文件大小（< 1KB 视为无效）
            file_size = os.path.getsize(file_path)
            if file_size < 1024:  # 1KB
                return False, f"文件过小 ({file_size} bytes)，可能是空文件或错误页面"
            
            # 读取HTML内容
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
            except UnicodeDecodeError:
                # 尝试其他编码
                try:
                    with open(file_path, 'r', encoding='gb2312') as f:
                        html_content = f.read()
                except:
                    with open(file_path, 'r', encoding='gbk') as f:
                        html_content = f.read()
            
            # 使用BeautifulSoup提取文本内容
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # 移除不需要的标签
                for element in soup(["script", "style", "meta", "link", "noscript", "comment"]):
                    element.decompose()
                
                # 提取文本内容
                text_content = soup.get_text(separator=' ', strip=True)
                
                # 检查文本长度（< 100 字符视为无效）
                if len(text_content) < 100:
                    return False, f"提取的文本内容过短 ({len(text_content)} 字符)，可能是导航页面或列表页面"
                
                # 检查是否包含IPO关键词
                from ..config import IPO_KEYWORDS
                text_lower = text_content.lower()
                has_keyword = any(keyword in text_content or keyword in text_lower for keyword in IPO_KEYWORDS)
                
                if not has_keyword:
                    return False, f"HTML内容中未找到招股说明书关键词 ({', '.join(IPO_KEYWORDS)})"
                
                return True, None
                
            except Exception as e:
                self.logger.warning(f"解析HTML文件失败: {file_path} - {e}")
                return False, f"解析HTML文件失败: {str(e)}"
                
        except Exception as e:
            self.logger.error(f"验证HTML文件时出错: {file_path} - {e}", exc_info=True)
            return False, f"验证HTML文件时出错: {str(e)}"

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

        # 多任务 + 多进程：使用现有的 run_ipo_multiprocessing
        return self._crawl_batch_multiprocessing(tasks)

    def _crawl_batch_multiprocessing(self, tasks: List[CrawlTask]) -> List[CrawlResult]:
        """
        使用多进程批量爬取 + 主线程异步上传（IPO版本）
        
        优化：下载和上传并行进行，而不是串行等待

        Args:
            tasks: 任务列表

        Returns:
            结果列表
        """
        try:
            # 导入任务处理器模块
            try:
                from ..processor.ipo_processor import run_ipo_multiprocessing
            except ImportError:
                from src.ingestion.a_share.processor.ipo_processor import run_ipo_multiprocessing

            # 0. 检查数据库，过滤已存在的任务（避免重复爬取）
            tasks_to_crawl = []
            skipped_results = {}  # {stock_code: CrawlResult}
            
            if self.enable_postgres and self.pg_client:
                try:
                    from src.storage.metadata import crud
                    with self.pg_client.get_session() as session:
                        for task in tasks:
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
                                    f"✅ 文档已存在，跳过下载（IPO）: {task.stock_code} "
                                    f"(id={existing_doc.id}, path={existing_doc.minio_object_path})"
                                )
                                skipped_results[task.stock_code] = CrawlResult(
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
                self.logger.info(f"✅ 所有 {len(tasks)} 个IPO任务都已存在，跳过爬取")
                return list(skipped_results.values())
            
            if len(skipped_results) > 0:
                self.logger.info(f"跳过 {len(skipped_results)} 个已存在的任务，剩余 {len(tasks_to_crawl)} 个任务需要爬取")

            # 创建临时CSV文件（只包含需要爬取的任务）
            temp_csv = self._create_temp_csv(
                tasks_to_crawl,
                ['code', 'name'],
                lambda task: [task.stock_code, task.company_name]
            )

            # 创建临时输出目录和失败记录文件
            temp_output = tempfile.mkdtemp(prefix='cninfo_ipo_batch_')
            temp_fail_csv = tempfile.NamedTemporaryFile(
                mode='w', suffix='.csv', delete=False, encoding='utf-8-sig', newline=''
            ).name

            # 创建上传队列和结果字典
            upload_results = {}  # {stock_code: CrawlResult}
            upload_lock = threading.Lock()
            processed_files = set()  # 已处理的文件路径集合
            
            # 创建上传线程池
            upload_workers = min(4, max(1, len(tasks) // 10))
            self.logger.info(f"启动 {upload_workers} 个上传线程（IPO）")
            
            upload_executor = ThreadPoolExecutor(max_workers=upload_workers)
            upload_futures = {}  # {stock_code: future}
            
            def upload_file(task: CrawlTask, file_path: str):
                """上传单个文件"""
                try:
                    # 如果是HTML文件，先验证内容
                    if file_path.lower().endswith(('.html', '.htm')):
                        is_valid, error_reason = self._validate_html_file(file_path)
                        if not is_valid:
                            self.logger.warning(f"HTML文件验证失败（IPO）: {task.stock_code} - {error_reason}")
                            return CrawlResult(
                                task=task,
                                success=False,
                                error_message=f"HTML文件验证失败: {error_reason}"
                            )
                    
                    # 读取发布日期信息和URL（从metadata文件）
                    metadata_file = file_path.replace('.pdf', '.meta.json').replace('.html', '.meta.json')
                    if os.path.exists(metadata_file):
                        try:
                            from ..utils.file_utils import load_json
                            metadata_info = load_json(metadata_file, {})
                            # 将发布日期信息和URL添加到task.metadata
                            task.metadata.update({
                                'publication_date': metadata_info.get('publication_date', ''),
                                'publication_year': metadata_info.get('publication_year', ''),
                                'publication_date_iso': metadata_info.get('publication_date_iso', ''),
                                'source_url': metadata_info.get('source_url', '')
                            })
                        except Exception as e:
                            self.logger.warning(f"读取metadata文件失败: {e}")
                    
                    self.logger.debug(f"开始上传（IPO）: {task.stock_code}")
                    result = self._process_downloaded_file(
                        file_path, 
                        task, 
                        extract_year_from_filename=True
                    )
                    return result
                except Exception as e:
                    self.logger.error(f"上传异常（IPO）: {task.stock_code} - {e}", exc_info=True)
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
                        run_ipo_multiprocessing,
                        temp_csv,
                        temp_output,
                        temp_fail_csv,
                        download_exception
                    ),
                    daemon=False
                )
                download_thread.start()
                self.logger.info(f"下载线程已启动（IPO），workers={self.workers}")
                
                # 主线程轮询检查下载完成的文件并异步上传
                poll_interval = 0.5
                last_file_count = 0
                no_new_file_count = 0
                max_no_new_file_count = 10
                
                while download_thread.is_alive() or no_new_file_count < max_no_new_file_count:
                    # 检查是否有下载异常
                    if download_exception:
                        raise download_exception[0]
                    
                    # 检查新下载的文件
                    current_file_count = 0
                    for task in tasks_to_crawl:
                        stock_code = task.stock_code
                        
                        # 跳过已处理的任务
                        if stock_code in upload_results or stock_code in upload_futures:
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
                                upload_futures[stock_code] = future
                                current_file_count += 1
                                self.logger.debug(f"发现新文件，已提交上传（IPO）: {stock_code}")
                            # 如果文件不稳定，等待下次轮询再检查
                    
                    # 检查已完成的上传
                    completed_futures = []
                    for stock_code, future in upload_futures.items():
                        if future.done():
                            try:
                                result = future.result()
                                with upload_lock:
                                    upload_results[stock_code] = result
                                completed_futures.append(stock_code)
                                if result.success:
                                    self.logger.debug(f"上传完成（IPO）: {stock_code}")
                                else:
                                    self.logger.warning(f"上传失败（IPO）: {stock_code} - {result.error_message}")
                            except Exception as e:
                                self.logger.error(f"获取上传结果异常（IPO）: {stock_code} - {e}", exc_info=True)
                                with upload_lock:
                                    upload_results[stock_code] = CrawlResult(
                                        task=next(t for t in tasks_to_crawl if t.stock_code == stock_code),
                                        success=False,
                                        error_message=f"上传异常: {e}"
                                    )
                                completed_futures.append(stock_code)
                    
                    # 清理已完成的上传任务
                    for stock_code in completed_futures:
                        del upload_futures[stock_code]
                    
                    # 检查是否有新文件
                    if current_file_count > last_file_count:
                        no_new_file_count = 0
                        last_file_count = current_file_count
                    else:
                        no_new_file_count += 1

                    # 显示进度（每10个任务或每次有新文件时显示）
                    completed_count = len(upload_results)
                    total_count = len(tasks_to_crawl)
                    if current_file_count > last_file_count or completed_count % 10 == 0:
                        progress_pct = completed_count / total_count * 100 if total_count > 0 else 0
                        self.logger.info(
                            f"📦 进度 (IPO): 已完成 {completed_count}/{total_count} ({progress_pct:.1f}%) | "
                            f"上传中: {len(upload_futures)}"
                        )

                    # 等待一段时间再检查
                    time.sleep(poll_interval)
                
                # 等待下载线程完成
                download_thread.join(timeout=300)
                if download_thread.is_alive():
                    self.logger.warning("下载线程超时（IPO），继续处理已下载的文件")
                
                # 等待所有上传完成
                self.logger.info(f"等待 {len(upload_futures)} 个上传任务完成（IPO）...")
                for stock_code, future in upload_futures.items():
                    try:
                        result = future.result(timeout=60)
                        with upload_lock:
                            upload_results[stock_code] = result
                    except Exception as e:
                        self.logger.error(f"等待上传完成异常（IPO）: {stock_code} - {e}", exc_info=True)
                        with upload_lock:
                            upload_results[stock_code] = CrawlResult(
                                task=next(t for t in tasks_to_crawl if t.stock_code == stock_code),
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
                        lambda row: row.get('code', '').strip()
                    )

                # 构建结果列表（包含跳过的任务）
                results = []
                for task in tasks:
                    stock_code = task.stock_code
                    
                    # 如果任务被跳过（已存在），直接添加跳过结果
                    if stock_code in skipped_results:
                        results.append(skipped_results[stock_code])
                    elif stock_code in failed_tasks:
                        # 失败任务
                        results.append(CrawlResult(
                            task=task,
                            success=False,
                            error_message="爬取失败，详见失败记录"
                        ))
                    elif stock_code in upload_results:
                        # 已上传的任务
                        results.append(upload_results[stock_code])
                    else:
                        # 未找到文件或未处理
                        file_path = self._find_downloaded_file(temp_output, task)
                        if file_path and os.path.exists(file_path):
                            # 如果是HTML文件，先验证内容
                            if file_path.lower().endswith(('.html', '.htm')):
                                is_valid, error_reason = self._validate_html_file(file_path)
                                if not is_valid:
                                    self.logger.warning(f"HTML文件验证失败（遗漏文件，IPO）: {stock_code} - {error_reason}")
                                    results.append(CrawlResult(
                                        task=task,
                                        success=False,
                                        error_message=f"HTML文件验证失败: {error_reason}"
                                    ))
                                    continue
                            
                            # 文件存在但未上传，立即上传
                            self.logger.warning(f"发现遗漏的文件，立即上传（IPO）: {stock_code}")
                            # 读取metadata
                            metadata_file = file_path.replace('.pdf', '.meta.json').replace('.html', '.meta.json')
                            if os.path.exists(metadata_file):
                                try:
                                    from ..utils.file_utils import load_json
                                    metadata_info = load_json(metadata_file, {})
                                    task.metadata.update({
                                        'publication_date': metadata_info.get('publication_date', ''),
                                        'publication_year': metadata_info.get('publication_year', ''),
                                        'publication_date_iso': metadata_info.get('publication_date_iso', ''),
                                        'source_url': metadata_info.get('source_url', '')
                                    })
                                except Exception as e:
                                    self.logger.warning(f"读取metadata文件失败: {e}")
                            
                            temp_result = self._process_downloaded_file(
                                file_path, 
                                task, 
                                extract_year_from_filename=True
                            )
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
                    f"批量爬取完成（IPO）: 总计 {len(results)}, 成功 {success_count}, "
                    f"MinIO上传成功 {upload_success_count}"
                )

                return results

            finally:
                # 确保上传线程池关闭
                upload_executor.shutdown(wait=True)
                # 清理临时文件
                self._cleanup_temp_files(temp_csv, temp_fail_csv)

        except Exception as e:
            self.logger.error(f"多进程批量爬取失败（IPO）: {e}", exc_info=True)
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
        在独立线程中运行下载，捕获异常（IPO版本）
        
        Args:
            run_multiprocessing_func: run_ipo_multiprocessing 函数
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
            self.logger.error(f"下载线程异常（IPO）: {e}", exc_info=True)
            exception_list.append(e)


def main():
    """测试入口"""
    # 创建爬虫实例
    crawler = CninfoIPOProspectusCrawler(
        enable_minio=True,
        enable_postgres=True,
        workers=4
    )

    # 创建测试任务（IPO不需要year和quarter）
    task = CrawlTask(
        stock_code="688111",
        company_name="金山办公",
        market=Market.A_SHARE,
        doc_type=DocType.IPO_PROSPECTUS,
        year=None,
        quarter=None
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
