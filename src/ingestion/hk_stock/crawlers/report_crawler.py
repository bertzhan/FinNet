# -*- coding: utf-8 -*-
"""
港股定期报告爬虫实现
继承自 BaseCrawler，集成 storage 层
"""

import os
import tempfile
import hashlib
from typing import List, Optional, Tuple, Dict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.ingestion.base.base_crawler import BaseCrawler, CrawlTask, CrawlResult
from src.common.constants import Market, DocType
from src.common.logger import get_logger
from ..api.hkex_client import HKEXClient

logger = get_logger(__name__)


# 港股文档类型映射
HKEX_DOC_TYPE_MAP = {
    DocType.HK_ANNUAL_REPORT: ('年报', 'Q4'),
    DocType.HK_INTERIM_REPORT: ('中期报告', 'Q2'),
    DocType.HK_QUARTERLY_REPORT: ('季度报告', None),  # 季度需要从 task.quarter 确定
}

# 季度映射
QUARTER_MAP = {
    1: 'Q1',
    2: 'Q2',
    3: 'Q3',
    4: 'Q4',
}


class HKReportCrawler(BaseCrawler):
    """
    港股定期报告爬虫
    
    使用披露易 API 查询和下载港股年报、中报、季报
    实现 _download_file() 方法，其余由基类自动处理
    """
    
    def __init__(
        self,
        enable_minio: bool = True,
        enable_postgres: bool = True,
        enable_quarantine: bool = True,
        start_date: str = "2022-01-01",
        end_date: str = "2025-12-31",
        workers: int = 4,
    ):
        """
        Args:
            enable_minio: 是否启用 MinIO 上传
            enable_postgres: 是否启用 PostgreSQL 记录
            enable_quarantine: 是否启用隔离功能
            start_date: 查询报告的开始日期
            end_date: 查询报告的结束日期
            workers: 并行线程数（默认4，1表示单线程）
        """
        super().__init__(
            market=Market.HK_STOCK,
            enable_minio=enable_minio,
            enable_postgres=enable_postgres,
            enable_quarantine=enable_quarantine
        )
        
        self.start_date = start_date
        self.end_date = end_date
        self.workers = workers
        
        # 初始化 HKEX API 客户端
        self.hkex_client = HKEXClient()
        
        self.logger.info(f"HKReportCrawler 初始化完成，查询范围: {start_date} ~ {end_date}, workers={workers}")
    
    def _download_file(self, task: CrawlTask) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        下载文件（实现基类抽象方法）
        
        Args:
            task: 爬取任务
            
        Returns:
            (是否成功, 本地文件路径, 错误信息)
        """
        try:
            # 1. 获取 orgId
            org_id = self._get_org_id(task)
            if not org_id:
                return False, None, f"无法获取 orgId: {task.stock_code}"
            
            # 2. 确定报告类型和季度
            report_type, default_quarter = self._get_report_type_info(task)
            if not report_type:
                return False, None, f"不支持的文档类型: {task.doc_type}"
            
            # 确定目标季度
            if task.quarter:
                target_quarter = QUARTER_MAP.get(task.quarter, default_quarter)
            else:
                target_quarter = default_quarter
            
            if not target_quarter:
                return False, None, f"无法确定目标季度: task.quarter={task.quarter}, doc_type={task.doc_type}"
            
            # 3. 查询报告列表
            self.logger.debug(f"查询报告: {task.stock_code} ({task.company_name}) {task.year} {target_quarter}")
            announcements, error = self.hkex_client.query_reports(
                stock_code=task.stock_code,
                org_id=org_id,
                report_type=report_type,
                start_date=self.start_date,
                end_date=self.end_date
            )
            
            if error:
                return False, None, f"查询报告失败: {error}"
            
            if not announcements:
                return False, None, f"未找到报告: {task.stock_code} {task.year} {target_quarter}"
            
            # 4. 选择最佳报告
            best_report = self.hkex_client.select_best_report(
                announcements=announcements,
                year=task.year,
                quarter=target_quarter
            )
            
            if not best_report:
                return False, None, f"未找到匹配的报告: {task.stock_code} {task.year} {target_quarter}"
            
            # 5. 下载 PDF
            pdf_url = best_report.get("adjunctUrl", "")
            if not pdf_url:
                return False, None, "报告缺少下载链接"
            
            # 创建临时文件
            temp_dir = tempfile.mkdtemp(prefix='hkex_download_')
            filename = self._generate_filename(task, best_report)
            local_path = os.path.join(temp_dir, filename)
            
            self.logger.debug(f"下载 PDF: {pdf_url} -> {local_path}")
            success, download_error = self.hkex_client.download_pdf(
                pdf_url=pdf_url,
                save_path=local_path
            )
            
            if not success:
                return False, None, f"下载失败: {download_error}"
            
            # 6. 验证文件
            if not os.path.exists(local_path):
                return False, None, "下载后文件不存在"
            
            file_size = os.path.getsize(local_path)
            if file_size < 1024:  # 小于 1KB 认为下载失败
                return False, None, f"文件太小: {file_size} bytes"
            
            # 7. 更新 task metadata
            task.metadata.update({
                'source_url': f"{self.hkex_client.pdf_base_url}{pdf_url}",
                'announcement_title': best_report.get("announcementTitle", ""),
                'announcement_time': best_report.get("announcementTime"),
                'hkex_fiscal_year': best_report.get("hkexFiscalYear"),
                'hkex_quarter': best_report.get("hkexQuarter"),
            })
            
            # 添加发布日期
            ann_time = best_report.get("announcementTime")
            if ann_time:
                try:
                    pub_date = datetime.fromtimestamp(ann_time / 1000)
                    task.metadata['publish_date_iso'] = pub_date.isoformat()
                except (OSError, ValueError):
                    pass
            
            self.logger.info(f"下载成功: {task.stock_code} {task.year} {target_quarter} -> {local_path}")
            return True, local_path, None
            
        except Exception as e:
            error_msg = f"下载异常: {e}"
            self.logger.error(f"{error_msg}: {task.stock_code} {task.year}", exc_info=True)
            return False, None, error_msg
    
    def _get_org_id(self, task: CrawlTask) -> Optional[int]:
        """
        获取股票的 orgId
        
        优先从 task.metadata 获取，否则调用 API 查询
        """
        # 从 metadata 获取（兼容 stock_id）
        org_id = task.metadata.get('org_id') or task.metadata.get('stock_id')
        if org_id:
            return int(org_id)
        
        # 从 API 获取
        org_id = self.hkex_client.get_org_id(task.stock_code)
        if org_id:
            task.metadata['org_id'] = org_id
        
        return org_id
    
    def _get_report_type_info(self, task: CrawlTask) -> Tuple[Optional[str], Optional[str]]:
        """
        获取报告类型信息
        
        Args:
            task: 爬取任务
            
        Returns:
            (report_type, default_quarter)
        """
        if task.doc_type in HKEX_DOC_TYPE_MAP:
            return HKEX_DOC_TYPE_MAP[task.doc_type]
        
        # 根据季度推断类型
        if task.quarter == 4:
            return ('年报', 'Q4')
        elif task.quarter == 2:
            return ('中期报告', 'Q2')
        elif task.quarter in [1, 3]:
            return ('季度报告', QUARTER_MAP.get(task.quarter))
        
        return None, None
    
    def _generate_filename(self, task: CrawlTask, report: Dict) -> str:
        """生成文件名"""
        quarter = report.get("hkexQuarter", "")
        fiscal_year = report.get("hkexFiscalYear", task.year)
        return f"{task.stock_code}_{fiscal_year}_{quarter}.pdf"
    
    def crawl_batch(self, tasks: List[CrawlTask]) -> List[CrawlResult]:
        """
        批量爬取（支持多线程并行）
        
        Args:
            tasks: 任务列表
            
        Returns:
            结果列表
        """
        if not tasks:
            return []
        
        # 如果只有一个任务或不启用多线程，使用基类的单任务逻辑
        if len(tasks) == 1 or self.workers <= 1:
            return super().crawl_batch(tasks)
        
        # 多任务 + 多线程并行
        return self._crawl_batch_multithreaded(tasks)
    
    def _crawl_batch_multithreaded(self, tasks: List[CrawlTask]) -> List[CrawlResult]:
        """
        使用多线程批量爬取
        
        Args:
            tasks: 任务列表
            
        Returns:
            结果列表
        """
        self.logger.info(f"开始多线程批量爬取: {len(tasks)} 个任务，使用 {self.workers} 个线程")
        
        results = []
        total = len(tasks)
        
        # 使用线程池并行执行
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            # 提交所有任务
            future_to_task = {
                executor.submit(self.crawl, task): task 
                for task in tasks
            }
            
            # 收集结果
            completed = 0
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                completed += 1
                
                try:
                    result = future.result()
                    results.append(result)
                    
                    # 显示进度：每10个或每10%显示一次，或最后一个
                    if completed % 10 == 0 or completed % max(1, total // 10) == 0 or completed == total:
                        progress_pct = completed / total * 100
                        status = "✅" if result.success else "❌"
                        self.logger.info(
                            f"📦 [{completed}/{total}] {progress_pct:.1f}% | "
                            f"{status} {task.stock_code} - {task.company_name} "
                            f"{task.year}Q{task.quarter if task.quarter else ''}"
                        )
                except Exception as e:
                    self.logger.error(
                        f"❌ 任务执行异常: {task.stock_code} {task.year} Q{task.quarter} - {e}",
                        exc_info=True
                    )
                    results.append(CrawlResult(
                        task=task,
                        success=False,
                        error_message=f"执行异常: {e}"
                    ))
        
        # 统计结果
        success_count = sum(1 for r in results if r.success)
        fail_count = len(results) - success_count
        
        self.logger.info(f"多线程批量爬取完成: 成功 {success_count}, 失败 {fail_count}")
        
        return results
    
    def crawl_company_reports(
        self,
        stock_code: str,
        company_name: str,
        org_id: Optional[int] = None,
        years: Optional[List[int]] = None,
        report_types: Optional[List[str]] = None
    ) -> List[CrawlResult]:
        """
        爬取指定公司的所有报告
        
        Args:
            stock_code: 股票代码
            company_name: 公司名称
            org_id: 披露易 orgId（可选，兼容 stock_id）
            years: 年份列表（默认近5年）
            report_types: 报告类型列表（默认年报和中报）
            
        Returns:
            爬取结果列表
        """
        if years is None:
            current_year = datetime.now().year
            years = list(range(current_year - 4, current_year + 1))
        
        if report_types is None:
            report_types = ['年报', '中期报告']
        
        # 构建任务列表
        tasks = []
        for year in years:
            for report_type in report_types:
                if report_type == '年报':
                    doc_type = DocType.HK_ANNUAL_REPORT
                    quarter = 4
                elif report_type == '中期报告':
                    doc_type = DocType.HK_INTERIM_REPORT
                    quarter = 2
                else:
                    continue
                
                task = CrawlTask(
                    stock_code=stock_code,
                    company_name=company_name,
                    market=Market.HK_STOCK,
                    doc_type=doc_type,
                    year=year,
                    quarter=quarter,
                    metadata={'org_id': org_id} if org_id else {}
                )
                tasks.append(task)
        
        # 执行批量爬取
        return self.crawl_batch(tasks)


def main():
    """测试入口"""
    # 创建爬虫实例
    crawler = HKReportCrawler(
        enable_minio=True,
        enable_postgres=True,
        start_date="2022-01-01",
        end_date="2025-12-31"
    )
    
    # 测试：爬取长和（00001）2023年年报
    task = CrawlTask(
        stock_code="00001",
        company_name="長和",
        market=Market.HK_STOCK,
        doc_type=DocType.HK_ANNUAL_REPORT,
        year=2023,
        quarter=4,
        metadata={'org_id': 1}
    )
    
    result = crawler.crawl(task)
    
    if result.success:
        print(f"✅ 爬取成功：{result.local_file_path}")
        print(f"   MinIO: {result.minio_object_path}")
        print(f"   数据库ID: {result.document_id}")
    else:
        print(f"❌ 爬取失败：{result.error_message}")


if __name__ == '__main__':
    main()
