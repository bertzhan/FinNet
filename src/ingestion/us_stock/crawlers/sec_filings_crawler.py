# -*- coding: utf-8 -*-
"""
SEC财报爬虫（继承BaseCrawler，复用存储逻辑）

功能：
- 爬取SEC财报（10-K/10-Q/20-F/40-F/6-K等）
- 下载HTML文档到临时目录
- 处理HTML中的图片（下载并本地化）
- 上传HTML和图片到MinIO
- 写入documents表
"""
import os
import tempfile
import hashlib
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.common.constants import Market, DocType
from src.common.logger import get_logger
from src.ingestion.base.base_crawler import BaseCrawler, CrawlTask, CrawlResult
from src.ingestion.us_stock.crawlers.sec_api_client import SECAPIClient
from src.ingestion.us_stock.crawlers.utils.html_processor import (
    process_html_preserve_encoding,
    build_image_replacement_mapping
)

logger = get_logger(__name__)


class SECFilingsCrawler(BaseCrawler):
    """
    SEC财报爬虫（适配FinNet架构）

    流程：
    1. 调用sec_api_client获取财报元数据
    2. 下载主HTML文档到临时目录
    3. 处理HTML中的图片（下载并本地化）
    4. 上传HTML到MinIO（作为主Document）
    5. 上传图片到MinIO（子对象）
    6. 可选：下载XBRL文件包
    7. 写入documents表
    """

    def __init__(
        self,
        enable_minio: bool = True,
        enable_postgres: bool = True,
        enable_quarantine: bool = True,
        download_images: bool = True,
        force_recrawl: bool = False
    ):
        """
        初始化SEC财报爬虫

        Args:
            enable_minio: 是否启用MinIO上传
            enable_postgres: 是否启用PostgreSQL记录
            enable_quarantine: 是否启用自动隔离
            download_images: 是否下载HTML中的图片（默认True）
            force_recrawl: 强制重新爬取，忽略已存在记录并清理下游
        """
        super().__init__(
            market=Market.US_STOCK,
            enable_minio=enable_minio,
            enable_postgres=enable_postgres,
            enable_quarantine=enable_quarantine,
            force_recrawl=force_recrawl
        )

        self.download_images = download_images
        self.sec_client = SECAPIClient()

        logger.info(
            "SEC财报爬虫已初始化",
            extra={
                "market": Market.US_STOCK.value,
                "download_images": download_images
            }
        )

    def _prepare_us_minio_metadata(self, task: CrawlTask, html_url: str) -> Dict[str, str]:
        """
        准备美股 MinIO 上传的 metadata，与 A股/港股统一格式：source_url、publish_date

        Args:
            task: 爬取任务
            html_url: 文档来源 URL

        Returns:
            统一的 metadata 字典，包含 source_url 和 publish_date（ISO 格式）
        """
        metadata: Dict[str, str] = {}
        if html_url:
            metadata["source_url"] = str(html_url)
        fd = task.metadata.get("filing_date") if task.metadata else None
        if fd:
            if hasattr(fd, "isoformat"):
                # date/datetime 对象：补全为完整 ISO 格式以与 HK 一致
                iso_str = fd.isoformat()
                if "T" not in iso_str:
                    iso_str = f"{iso_str}T00:00:00"
                metadata["publish_date"] = iso_str
            else:
                metadata["publish_date"] = str(fd)
        return metadata

    def _download_file(self, task: CrawlTask) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        下载SEC财报HTML文件（实现BaseCrawler抽象方法）

        Args:
            task: 爬取任务（metadata需包含accession_number、primary_document、org_id）

        Returns:
            (是否成功, 本地文件路径, 错误信息)
        """
        try:
            accession_number = task.metadata.get('accession_number')
            primary_document = task.metadata.get('primary_document')
            org_id = task.metadata.get('org_id') or task.metadata.get('cik')

            if not accession_number or not org_id:
                return False, None, "缺少必需的元数据：accession_number或org_id"

            html_url = self.sec_client.construct_primary_html_url(
                cik=org_id,
                accession=accession_number,
                primary_document=primary_document
            )

            temp_dir = tempfile.mkdtemp(prefix='sec_filing_')
            html_filename = f"{task.stock_code}_{task.year}_{'FY' if not task.quarter else f'Q{task.quarter}'}.htm"
            html_path = Path(temp_dir) / html_filename

            self.sec_client.download_file(
                url=html_url,
                output_path=str(html_path)
            )
            return True, str(html_path), None

        except Exception as e:
            logger.error(f"下载失败: {e}", exc_info=True)
            return False, None, str(e)

    def crawl_one(self, task: CrawlTask) -> CrawlResult:
        """
        爬取单个SEC财报

        Args:
            task: 爬取任务（包含股票代码、表单类型、年份等）

        Returns:
            爬取结果

        流程：
        1. 从task.metadata中获取accession_number和primary_document
        2. 构造HTML URL并下载到临时目录
        3. 如果enable_images，解析HTML并下载图片
        4. 更新HTML中的图片路径为相对路径
        5. 上传HTML和图片到MinIO
        6. 写入documents表
        """
        logger.info(
            f"开始爬取: {task.stock_code} {task.doc_type.value} {task.year}Q{task.quarter or 'FY'}",
            extra={
                "stock_code": task.stock_code,
                "doc_type": task.doc_type.value,
                "year": task.year,
                "quarter": task.quarter
            }
        )

        try:
            # 1. 获取必需的元数据
            accession_number = task.metadata.get('accession_number')
            primary_document = task.metadata.get('primary_document')
            org_id = task.metadata.get('org_id') or task.metadata.get('cik')

            if not accession_number or not org_id:
                error_msg = "缺少必需的元数据：accession_number或org_id"
                logger.error(error_msg)
                return CrawlResult(
                    task=task,
                    success=False,
                    error_message=error_msg
                )

            # 2. 构造HTML URL
            html_url = self.sec_client.construct_primary_html_url(
                cik=org_id,
                accession=accession_number,
                primary_document=primary_document
            )

            logger.debug(f"HTML URL: {html_url}")

            # 3. 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)

                # 下载HTML
                html_filename = f"{task.stock_code}_{task.year}_{'FY' if not task.quarter else f'Q{task.quarter}'}.htm"
                html_temp_path = temp_dir_path / html_filename

                logger.info(f"下载HTML: {html_url}")
                file_size = self.sec_client.download_file(
                    url=html_url,
                    output_path=str(html_temp_path)
                )

                # 4. 处理HTML（如果启用图片下载）
                image_paths = []
                if self.download_images:
                    logger.info("处理HTML中的图片...")
                    image_paths = self._process_html_images(
                        html_path=html_temp_path,
                        html_url=html_url,
                        temp_dir=temp_dir_path,
                        task=task
                    )

                # 5. 计算文件哈希
                file_hash = self._calculate_file_hash(html_temp_path)

                # 6. 构造 MinIO 路径：bronze/us_stock/{stock_code}/{year}/{period}/document.htm
                period = self._get_us_stock_period(task)
                minio_path = self.path_manager.get_us_stock_bronze_path(
                    stock_code=task.stock_code,
                    year=task.year,
                    period=period,
                    filename="document.htm"
                )

                # 6.1 force_recrawl：在上传前清理已有文档的 MinIO 和下游
                source_url = html_url
                if self.force_recrawl and self.enable_postgres and self.pg_client and self.minio_client:
                    from src.storage.metadata import crud
                    try:
                        with self.pg_client.get_session() as session:
                            existing_doc = crud.get_document_by_source_url(session, source_url)
                            if existing_doc:
                                crud.delete_document_minio_artifacts(self.minio_client, session, existing_doc.id)
                                crud.delete_document_downstream_data(session, existing_doc.id)
                                logger.info(f"force_recrawl: 已清理 {task.stock_code} {task.year} 的下游数据")
                    except Exception as e:
                        logger.warning(f"force_recrawl 清理失败: {e}", exc_info=True)

                if self.enable_minio:
                    logger.info(f"上传HTML到MinIO: {minio_path}")
                    minio_metadata = self._prepare_us_minio_metadata(task, html_url)
                    self.minio_client.upload_file(
                        object_name=minio_path,
                        file_path=str(html_temp_path),
                        metadata=minio_metadata
                    )

                    # 上传图片（如果有）
                    for img_local_path in image_paths:
                        img_filename = Path(img_local_path).name
                        img_minio_path = self.path_manager.get_us_stock_bronze_path(
                            stock_code=task.stock_code,
                            year=task.year,
                            period=period,
                            filename=img_filename
                        )
                        logger.debug(f"上传图片: {img_minio_path}")
                        self.minio_client.upload_file(
                            object_name=img_minio_path,
                            file_path=img_local_path
                        )

                # 7. 写入PostgreSQL（使用BaseCrawler的写入逻辑）
                document_id = None
                if self.enable_postgres:
                    from src.storage.metadata import crud

                    with self.pg_client.get_session() as session:
                        document_id = crud.create_or_update_document(
                            session=session,
                            stock_code=task.stock_code,
                            company_name=task.company_name,
                            market=task.market.value,
                            doc_type=task.doc_type.value,
                            year=task.year,
                            quarter=task.quarter,
                            minio_object_path=minio_path,
                            file_size=file_size,
                            file_hash=file_hash,
                            source_url=source_url,
                            publish_date=task.metadata.get('filing_date'),
                            status='crawled'
                        )

                # 8. 返回结果
                return CrawlResult(
                    task=task,
                    success=True,
                    local_file_path=str(html_temp_path),
                    minio_object_path=minio_path,
                    document_id=document_id,
                    file_size=file_size,
                    file_hash=file_hash,
                    metadata={
                        'accession_number': accession_number,
                        'filing_date': str(task.metadata.get('filing_date')),
                        'images_count': len(image_paths),
                        'html_url': html_url
                    }
                )

        except Exception as e:
            logger.error(
                f"爬取失败: {task.stock_code}",
                extra={
                    "stock_code": task.stock_code,
                    "error": str(e)
                },
                exc_info=True
            )
            return CrawlResult(
                task=task,
                success=False,
                error_message=str(e)
            )

    def _process_html_images(
        self,
        html_path: Path,
        html_url: str,
        temp_dir: Path,
        task: CrawlTask
    ) -> List[str]:
        """
        处理HTML中的图片（下载并本地化路径）

        Args:
            html_path: HTML文件路径
            html_url: HTML的URL
            temp_dir: 临时目录
            task: 爬取任务

        Returns:
            下载的图片本地路径列表
        """
        try:
            html_content = html_path.read_bytes()
            soup = BeautifulSoup(html_content, 'html.parser')
            img_tags = soup.find_all('img')

            if not img_tags:
                return []

            # 解析 base_url（HTML 所在目录，用于解析相对路径）
            base_url = html_url.rsplit('/', 1)[0] + '/'
            sec_base = self.sec_client.BASE_URL

            image_artifacts = []
            downloaded_paths = []

            for i, img in enumerate(img_tags, 1):
                src = img.get('src')
                if not src or src.startswith('data:'):
                    continue

                # 解析为绝对 URL
                if src.startswith('http'):
                    full_url = src
                elif src.startswith('/'):
                    full_url = urljoin(sec_base, src)
                else:
                    full_url = urljoin(base_url, src)

                # 仅处理 SEC 域名的图片
                if 'sec.gov' not in full_url:
                    logger.debug(f"跳过非 SEC 图片: {full_url[:80]}...")
                    continue

                # 确定文件扩展名
                ext = Path(full_url.split('?')[0]).suffix or '.png'
                img_filename = f"{task.stock_code}_{task.year}_{'FY' if not task.quarter else f'Q{task.quarter}'}_image-{i:03d}{ext}"
                img_local_path = temp_dir / img_filename

                try:
                    self.sec_client.download_file(
                        url=full_url,
                        output_path=str(img_local_path)
                    )
                    artifact = SimpleNamespace(
                        url=full_url,
                        filename=Path(full_url).name.split('?')[0],
                        local_path=str(img_local_path)
                    )
                    image_artifacts.append(artifact)
                    downloaded_paths.append(str(img_local_path))
                except Exception as e:
                    logger.warning(f"图片下载失败: {full_url[:80]}... - {e}")
                    continue

            if not image_artifacts:
                return []

            # 构建替换映射并更新 HTML
            img_replacements = build_image_replacement_mapping(html_url, image_artifacts)
            processed_html = process_html_preserve_encoding(html_content, img_replacements)
            html_path.write_bytes(processed_html)

            logger.info(f"已下载并本地化 {len(downloaded_paths)} 张图片")
            return downloaded_paths

        except Exception as e:
            logger.warning(f"图片处理失败: {e}", exc_info=True)
            return []

    def _get_us_stock_period(self, task: CrawlTask) -> str:
        """
        获取美股报告期（Q1/Q2/Q3/FY）

        10-K、20-F、40-F 为年报，period=FY；
        10-Q 根据 quarter 返回 Q1/Q2/Q3，quarter 为 4 时报错（10-Q 无 Q4）。
        """
        if task.doc_type in (DocType.FORM_10K, DocType.FORM_20F, DocType.FORM_40F):
            return "FY"
        if task.doc_type == DocType.FORM_10Q:
            if task.quarter == 4:
                raise ValueError(
                    f"10-Q 无 Q4 报告期，quarter=4 非法。"
                    f"stock_code={task.stock_code}, year={task.year}"
                )
            if task.quarter in (1, 2, 3):
                return f"Q{task.quarter}"
            raise ValueError(
                f"10-Q 需要 quarter 为 1/2/3，当前 quarter={task.quarter}。"
                f"stock_code={task.stock_code}, year={task.year}"
            )
        return "FY"

    def _calculate_file_hash(self, file_path: Path) -> str:
        """
        计算文件SHA256哈希

        Args:
            file_path: 文件路径

        Returns:
            SHA256哈希值（十六进制字符串）
        """
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def crawl_batch(self, tasks: List[CrawlTask]) -> List[CrawlResult]:
        """
        批量爬取（遵守SEC限流）

        Args:
            tasks: 爬取任务列表

        Returns:
            爬取结果列表
        """
        results = []
        total = len(tasks)

        logger.info(f"开始批量爬取，任务数: {total}")

        for idx, task in enumerate(tasks, 1):
            logger.info(f"进度: {idx}/{total}")
            result = self.crawl_one(task)
            results.append(result)

            # 统计
            if idx % 10 == 0:
                success_count = sum(1 for r in results if r.success)
                logger.info(
                    f"批量爬取进度: {idx}/{total}, 成功: {success_count}, 失败: {idx - success_count}"
                )

        success_count = sum(1 for r in results if r.success)
        logger.info(
            f"批量爬取完成: 总计 {total}, 成功 {success_count}, 失败 {total - success_count}"
        )

        return results
