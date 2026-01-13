# -*- coding: utf-8 -*-
"""
A股爬虫适配器
将现有的CNINFO爬虫代码适配到统一接口
"""

import os
import sys
from typing import List, Tuple, Optional
from datetime import datetime

# 添加父目录到路径，以便导入base_crawler
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from src.crawler.base_crawler import BaseCrawler, Market, DocType, CrawlTask, CrawlResult
from .main import run_multiprocessing
import tempfile
import csv


class CNInfoCrawler(BaseCrawler):
    """
    A股CNINFO爬虫适配器
    将现有的main.py逻辑封装为统一接口
    """

    def __init__(self, output_root: str, workers: int = 6, old_pdf_dir: Optional[str] = None):
        """
        Args:
            output_root: 输出根目录
            workers: 并行进程数
            old_pdf_dir: 旧PDF目录（用于跳过已下载文件）
        """
        super().__init__(Market.A_SHARE, output_root)
        self.workers = workers
        self.old_pdf_dir = old_pdf_dir

    def crawl(self, task: CrawlTask) -> CrawlResult:
        """
        执行单个爬取任务
        
        Args:
            task: 爬取任务
            
        Returns:
            爬取结果
        """
        # 将单个任务转换为批量任务
        results = self.crawl_batch([task])
        return results[0] if results else CrawlResult(
            success=False,
            task=task,
            error_message="爬取失败"
        )

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

        # 创建临时CSV文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['code', 'name', 'year', 'quarter'])
            
            for task in tasks:
                quarter_str = f"Q{task.quarter}" if task.quarter else "Q4"  # 年报默认Q4
                writer.writerow([task.stock_code, task.company_name, task.year, quarter_str])
            
            temp_csv = f.name

        # 创建临时输出目录（用于本次爬取）
        temp_output = os.path.join(self.output_root, "temp_crawl")
        os.makedirs(temp_output, exist_ok=True)

        # 创建临时失败记录文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8-sig', newline='') as f:
            temp_fail_csv = f.name

        try:
            # 调用现有的爬虫逻辑
            run_multiprocessing(
                input_csv=temp_csv,
                out_root=temp_output,
                fail_csv=temp_fail_csv,
                workers=self.workers,
                debug=False,
                old_pdf_dir=self.old_pdf_dir
            )

            # 读取失败记录
            failed_tasks = set()
            if os.path.exists(temp_fail_csv):
                with open(temp_fail_csv, 'r', encoding='utf-8-sig', newline='') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        code = row.get('code', '').strip()
                        year = int(row.get('year', 0))
                        quarter = row.get('quarter', '').strip()
                        failed_tasks.add((code, year, quarter))

            # 构建结果列表
            results = []
            for task in tasks:
                quarter_str = f"Q{task.quarter}" if task.quarter else "Q4"
                task_key = (task.stock_code, task.year, quarter_str)
                
                if task_key in failed_tasks:
                    # 失败任务
                    results.append(CrawlResult(
                        success=False,
                        task=task,
                        error_message="爬取失败，详见失败记录"
                    ))
                else:
                    # 成功任务，查找文件
                    file_path = self._find_downloaded_file(temp_output, task)
                    if file_path and os.path.exists(file_path):
                        file_size = os.path.getsize(file_path)
                        # 移动到标准路径
                        standard_path = self._move_to_standard_path(file_path, task)
                        
                        # 注意：MinIO上传已在process_single_task中完成（下载时立即上传）
                        # 这里不再需要批量上传
                        
                        results.append(CrawlResult(
                            success=True,
                            task=task,
                            file_path=standard_path,
                            file_size=file_size,
                            metadata=self.get_metadata(task)
                        ))
                    else:
                        results.append(CrawlResult(
                            success=False,
                            task=task,
                            error_message="文件未找到"
                        ))

            return results

        finally:
            # 清理临时文件
            try:
                os.unlink(temp_csv)
                if os.path.exists(temp_fail_csv):
                    os.unlink(temp_fail_csv)
            except:
                pass

    def _find_downloaded_file(self, output_root: str, task: CrawlTask) -> Optional[str]:
        """
        查找下载的文件
        
        Args:
            output_root: 输出根目录
            task: 任务
            
        Returns:
            文件路径，如果未找到则返回None
        """
        # 根据现有代码的目录结构查找
        # 格式：{output_root}/{exchange}/{code}/{year}/{code}_{year}_{quarter}_{date}.pdf
        exchanges = ['SZ', 'SH', 'BJ']
        quarter_str = f"Q{task.quarter}" if task.quarter else "Q4"
        
        for exchange in exchanges:
            code_dir = os.path.join(output_root, exchange, task.stock_code, str(task.year))
            if not os.path.exists(code_dir):
                continue
            
            # 查找匹配的文件
            pattern = f"{task.stock_code}_{task.year}_{quarter_str}_*.pdf"
            import glob
            files = glob.glob(os.path.join(code_dir, pattern))
            if files:
                return files[0]  # 返回第一个匹配的文件
        
        return None

    def _move_to_standard_path(self, file_path: str, task: CrawlTask) -> str:
        """
        将文件移动到标准路径（按plan.md规范）
        
        Args:
            file_path: 当前文件路径
            task: 任务
            
        Returns:
            新的文件路径
        """
        filename = os.path.basename(file_path)
        standard_path = self.get_storage_path(task, filename)
        
        # 创建目录
        os.makedirs(os.path.dirname(standard_path), exist_ok=True)
        
        # 移动文件
        if file_path != standard_path:
            import shutil
            shutil.move(file_path, standard_path)
        
        return standard_path

    def _upload_to_minio_if_enabled(self, file_path: str, task: CrawlTask):
        """
        如果启用了MinIO，上传文件到MinIO
        
        Args:
            file_path: 本地文件路径
            task: 任务
        """
        try:
            from src.crawler.config import CrawlerConfig
            from src.crawler.minio_storage import create_minio_storage_from_config
            
            # 重新加载配置（确保获取最新的环境变量）
            config = CrawlerConfig.from_env()
            
            minio_storage = create_minio_storage_from_config(config)
            if minio_storage is None:
                # 只在第一次时打印提示
                if not hasattr(self, '_minio_warning_printed'):
                    import logging
                    logging.info("MinIO未启用，文件仅保存到本地。要启用MinIO上传，请设置环境变量：")
                    logging.info("  export USE_MINIO=true")
                    logging.info("  export MINIO_ENDPOINT=http://localhost:9000")
                    logging.info("  export MINIO_ACCESS_KEY=admin")
                    logging.info("  export MINIO_SECRET_KEY=admin123456")
                    self._minio_warning_printed = True
                return  # MinIO未启用或配置不完整
            
            # 生成MinIO对象名称（去掉本地路径前缀，只保留相对路径）
            filename = os.path.basename(file_path)
            object_name = self.get_storage_path(task, filename)
            
            # 如果output_root是绝对路径，需要转换为相对路径
            if object_name.startswith(self.output_root):
                object_name = object_name[len(self.output_root):].lstrip('/')
            
            # 上传到MinIO
            success = minio_storage.upload_file(file_path, object_name, content_type='application/pdf')
            if success:
                import logging
                logging.info(f"✅ 已上传到MinIO: {object_name}")
            
        except ImportError as e:
            import logging
            logging.warning(f"MinIO库未安装，跳过上传: {e}")
            logging.warning("安装命令: pip install minio")
        except Exception as e:
            import logging
            logging.warning(f"MinIO上传失败（文件仍保存在本地）: {e}")

    def validate_result(self, result: CrawlResult) -> Tuple[bool, Optional[str]]:
        """
        验证爬取结果
        
        Args:
            result: 爬取结果
            
        Returns:
            (是否通过验证, 错误信息)
        """
        if not result.success:
            return False, result.error_message or "爬取失败"

        if not result.file_path or not os.path.exists(result.file_path):
            return False, "文件不存在"

        # 检查文件大小
        if result.file_size is None:
            result.file_size = os.path.getsize(result.file_path)
        
        if result.file_size == 0:
            return False, "文件大小为0"

        # 检查是否为PDF文件
        if not result.file_path.lower().endswith('.pdf'):
            return False, "文件格式不是PDF"

        # 检查PDF文件头
        try:
            with open(result.file_path, 'rb') as f:
                header = f.read(5)
                if not header.startswith(b'%PDF-'):
                    return False, "文件不是有效的PDF格式"
        except Exception as e:
            return False, f"文件读取失败: {str(e)}"

        return True, None
