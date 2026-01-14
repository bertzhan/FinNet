# -*- coding: utf-8 -*-
"""
A股IPO招股说明书爬虫实现（CNINFO）
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

            # 检查文件格式，如果是HTML则不保存
            if file_path.lower().endswith(('.html', '.htm')):
                self.logger.info(f"检测到HTML格式文件，跳过保存: {file_path}")
                return False, None, "HTML格式文件不保存"

            # 读取发布日期信息（从metadata文件）
            metadata_file = file_path.replace('.pdf', '.meta.json').replace('.html', '.meta.json')
            if os.path.exists(metadata_file):
                try:
                    from ..utils.file_utils import load_json
                    metadata_info = load_json(metadata_file, {})
                    # 将发布日期信息添加到task.metadata
                    task.metadata.update({
                        'publication_date': metadata_info.get('publication_date', ''),
                        'publication_year': metadata_info.get('publication_year', ''),
                        'publication_date_iso': metadata_info.get('publication_date_iso', '')
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
        # IPO文件格式（与MinIO一致）：{output_root}/bronze/a_share/ipo_prospectus/{code}/{code}_{year}_{date}.pdf 或 .html
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
        # IPO文件命名：根据 ipo_processor.py，文件名格式为 {code}.pdf 或 {code}.html
        # 先尝试精确匹配：{code}.pdf 或 {code}.html
        exact_pdf = os.path.join(ipo_dir, f"{task.stock_code}.pdf")
        if os.path.exists(exact_pdf):
            return exact_pdf
        
        exact_html = os.path.join(ipo_dir, f"{task.stock_code}.html")
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
        使用多进程批量爬取（IPO版本）

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

            # 创建临时CSV文件
            temp_csv = self._create_temp_csv(
                tasks,
                ['code', 'name'],
                lambda task: [task.stock_code, task.company_name]
            )

            # 创建临时输出目录和失败记录文件
            temp_output = tempfile.mkdtemp(prefix='cninfo_ipo_batch_')
            temp_fail_csv = tempfile.NamedTemporaryFile(
                mode='w', suffix='.csv', delete=False, encoding='utf-8-sig', newline=''
            ).name

            try:
                # 调用现有的多进程爬虫逻辑
                run_ipo_multiprocessing(
                    input_csv=temp_csv,
                    out_root=temp_output,
                    fail_csv=temp_fail_csv,
                    workers=self.workers,
                    debug=False
                )

                # 读取失败记录
                failed_tasks = self._read_failed_tasks(
                    temp_fail_csv,
                    lambda row: row.get('code', '').strip()
                )

                # 构建结果列表
                results = []
                for task in tasks:
                    if task.stock_code in failed_tasks:
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
                            # 检查文件格式，如果是HTML则不保存（与单任务模式一致）
                            if file_path.lower().endswith(('.html', '.htm')):
                                self.logger.info(f"检测到HTML格式文件，跳过保存: {file_path}")
                                results.append(CrawlResult(
                                    task=task,
                                    success=False,
                                    error_message="HTML格式文件不保存"
                                ))
                                continue
                            
                            # 读取发布日期信息（从metadata文件）
                            metadata_file = file_path.replace('.pdf', '.meta.json').replace('.html', '.meta.json')
                            if os.path.exists(metadata_file):
                                try:
                                    from ..utils.file_utils import load_json
                                    metadata_info = load_json(metadata_file, {})
                                    # 将发布日期信息添加到task.metadata
                                    task.metadata.update({
                                        'publication_date': metadata_info.get('publication_date', ''),
                                        'publication_year': metadata_info.get('publication_year', ''),
                                        'publication_date_iso': metadata_info.get('publication_date_iso', '')
                                    })
                                except Exception as e:
                                    self.logger.warning(f"读取metadata文件失败: {e}")
                            
                            # IPO需要从metadata获取年份
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
        print(f"   MinIO: {result.minio_object_name}")
        print(f"   数据库ID: {result.document_id}")
    else:
        print(f"❌ 爬取失败：{result.error_message}")


if __name__ == '__main__':
    main()
