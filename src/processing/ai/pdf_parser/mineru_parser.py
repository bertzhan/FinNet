# -*- coding: utf-8 -*-
"""
MinerU PDF 解析器
按照 plan.md 4.3.1 设计，实现 PDF 解析功能
解析结果直接上传到 Silver 层
"""

import os
import json
import tempfile
import hashlib
import uuid
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from pathlib import Path

from src.storage.object_store.minio_client import MinIOClient
from src.storage.object_store.path_manager import PathManager
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata.models import Document, ParseTask, ParsedDocument, Image
from src.storage.metadata import crud
from src.common.constants import Market, DocType, DocumentStatus
from src.common.config import pdf_parser_config, minio_config
from src.common.logger import get_logger, LoggerMixin


class MinerUParser(LoggerMixin):
    """
    MinerU PDF 解析器
    支持通过 API 或 Python 包方式调用 MinerU
    """

    def __init__(
        self,
        minio_client: Optional[MinIOClient] = None,
        path_manager: Optional[PathManager] = None
    ):
        """
        初始化 MinerU 解析器

        Args:
            minio_client: MinIO 客户端（默认创建新实例）
            path_manager: 路径管理器（默认创建新实例）
        """
        self.minio_client = minio_client or MinIOClient()
        self.path_manager = path_manager or PathManager()
        self.pg_client = get_postgres_client()
        
        # MinerU API 配置
        # 默认使用 OpenBayes API
        self.api_base = pdf_parser_config.MINERU_API_BASE or "https://hanco9-bb.gear-c1.openbayes.net"
        self.use_api = True  # 强制使用 API 模式
        
        self.logger.info(f"使用 MinerU API 模式: {self.api_base}")

    def parse_document(
        self,
        document_id: Union[uuid.UUID, str],
        save_to_silver: bool = True,
        start_page_id: int = 0,
        end_page_id: Optional[int] = None,
        force_reparse: bool = False
    ) -> Dict[str, Any]:
        """
        解析文档

        完整流程：
        1. 从数据库获取文档信息
        2. 从 MinIO 下载 PDF
        3. 调用 MinerU 解析
        4. 保存解析结果到 Silver 层
        5. 记录 ParseTask 到数据库
        6. 更新文档状态

        Args:
            document_id: 文档ID
            save_to_silver: 是否保存到 Silver 层
            start_page_id: 起始页码（从0开始），默认0（解析全部）
            end_page_id: 结束页码（从0开始），None 表示解析到最后
            force_reparse: 是否强制重新解析（即使文档已解析），默认 False

        Returns:
            解析结果字典，包含：
            - success: 是否成功
            - parse_task_id: 解析任务ID
            - output_path: Silver 层路径
            - extracted_text_length: 提取的文本长度
            - extracted_tables_count: 提取的表格数量
            - extracted_images_count: 提取的图片数量
            - error_message: 错误信息（失败时）

        Example:
            >>> parser = MinerUParser()
            >>> result = parser.parse_document(document_id=123)
            >>> print(f"解析成功: {result['success']}")
        """
        start_time = datetime.now()
        
        # 在 session 内获取文档信息并保存需要的属性
        minio_object_path = None
        doc_status = None
        
        with self.pg_client.get_session() as session:
            # 1. 获取文档信息
            doc = crud.get_document_by_id(session, document_id)
            if not doc:
                return {
                    "success": False,
                    "error_message": f"文档不存在: document_id={document_id}"
                }

            # 保存需要的属性值（在 session 关闭前）
            minio_object_path = doc.minio_object_path
            doc_status = doc.status

            # 检查是否已解析（除非强制重新解析）
            if doc_status == DocumentStatus.PARSED.value and not force_reparse:
                self.logger.info(f"文档已解析: document_id={document_id}（跳过重新解析）")
                # 查找已有的解析任务
                existing_task = session.query(ParseTask).filter(
                    ParseTask.document_id == document_id,
                    ParseTask.status == 'completed'
                ).first()
                if existing_task:
                    # 从 extra_metadata 中读取统计信息
                    metadata = existing_task.extra_metadata or {}
                    return {
                        "success": True,
                        "parse_task_id": existing_task.id,
                        "output_path": existing_task.output_path,
                        "extracted_text_length": metadata.get("extracted_text_length", 0),
                        "extracted_tables_count": metadata.get("extracted_tables_count", 0),
                        "extracted_images_count": metadata.get("extracted_images_count", 0)
                    }

            # 如果是强制重新解析，记录日志
            if doc_status == DocumentStatus.PARSED.value and force_reparse:
                self.logger.info(f"强制重新解析文档: document_id={document_id}")

            # 2. 创建解析任务记录
            parse_task = ParseTask(
                document_id=document_id,
                parser_type="mineru",
                parser_version=self._get_mineru_version(),
                status="processing",
                started_at=start_time
            )
            session.add(parse_task)
            session.flush()
            parse_task_id = parse_task.id

            self.logger.info(
                f"开始解析文档: document_id={document_id}, "
                f"parse_task_id={parse_task_id}, "
                f"minio_path={minio_object_path}"
            )

        # 3. 下载 PDF 到临时文件
        temp_pdf_path = None
        try:
            temp_pdf_path = self._download_pdf_to_temp(minio_object_path)
            if not temp_pdf_path:
                raise Exception("PDF 下载失败")

            # 4. 调用 MinerU 解析（支持页面范围）
            try:
                parse_result = self._parse_with_mineru(
                    temp_pdf_path,
                    start_page_id=start_page_id,
                    end_page_id=end_page_id
                )
            except KeyboardInterrupt:
                # 用户手动中断
                self.logger.warning("⚠️ PDF 解析被用户中断")
                self._update_parse_task_failed(parse_task_id, "解析被用户中断")
                raise
            except Exception as e:
                # 检查是否是中断异常
                error_type = type(e).__name__
                if "Interrupt" in error_type or "Interrupted" in error_type:
                    self.logger.warning(f"⚠️ PDF 解析被中断: {error_type}")
                    self._update_parse_task_failed(parse_task_id, f"解析被中断: {error_type}")
                    raise
                # 其他异常继续处理
                raise
            
            if not parse_result.get("success"):
                error_msg = parse_result.get("error_message", "解析失败")
                self._update_parse_task_failed(parse_task_id, error_msg)
                return {
                    "success": False,
                    "parse_task_id": parse_task_id,
                    "error_message": error_msg
                }

            # 5. 保存解析结果到 Silver 层
            output_path = None
            if save_to_silver:
                # 重新获取文档对象（因为之前的 session 已关闭）
                with self.pg_client.get_session() as session:
                    doc = crud.get_document_by_id(session, document_id)
                    if not doc:
                        raise Exception(f"文档不存在: document_id={document_id}")
                    
                    output_path = self._save_to_silver(
                        doc=doc,
                        parse_task_id=parse_task_id,
                        parse_result=parse_result
                    )
                    if not output_path:
                        raise Exception("保存到 Silver 层失败")

            # 6. 更新解析任务和文档状态
            duration = (datetime.now() - start_time).total_seconds()
            self._update_parse_task_success(
                parse_task_id=parse_task_id,
                output_path=output_path,
                extracted_text_length=parse_result.get("text_length", 0),
                extracted_tables_count=parse_result.get("tables_count", 0),
                extracted_images_count=parse_result.get("images_count", 0),
                duration=duration
            )

            self._update_document_parsed(document_id)

            self.logger.info(
                f"✅ 解析完成: document_id={document_id}, "
                f"output_path={output_path}, "
                f"文本长度={parse_result.get('text_length', 0)}"
            )

            return {
                "success": True,
                "parse_task_id": parse_task_id,
                "output_path": output_path,
                "extracted_text_length": parse_result.get("text_length", 0),
                "extracted_tables_count": parse_result.get("tables_count", 0),
                "extracted_images_count": parse_result.get("images_count", 0)
            }

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"❌ 解析异常: {error_msg}", exc_info=True)
            self._update_parse_task_failed(parse_task_id, error_msg)
            return {
                "success": False,
                "parse_task_id": parse_task_id,
                "error_message": error_msg
            }
        finally:
            # 清理临时文件
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                try:
                    os.remove(temp_pdf_path)
                except Exception as e:
                    self.logger.warning(f"清理临时文件失败: {e}")

    def _download_pdf_to_temp(self, minio_object_path: str) -> Optional[str]:
        """
        从 MinIO 下载 PDF 到临时文件

        Args:
            minio_object_path: MinIO 对象路径

        Returns:
            临时文件路径
        """
        try:
            # 下载文件数据
            file_data = self.minio_client.download_file(minio_object_path)
            if not file_data:
                self.logger.error(f"无法下载文件: {minio_object_path}")
                return None

            # 创建临时文件
            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(
                temp_dir,
                f"mineru_parse_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}.pdf"
            )

            with open(temp_file, "wb") as f:
                f.write(file_data)

            self.logger.debug(f"PDF 已下载到临时文件: {temp_file}")
            return temp_file

        except Exception as e:
            self.logger.error(f"下载 PDF 失败: {e}", exc_info=True)
            return None

    def _parse_with_mineru(self, pdf_path: str, start_page_id: int = 0, end_page_id: Optional[int] = None) -> Dict[str, Any]:
        """
        使用 MinerU 解析 PDF（通过 API）

        Args:
            pdf_path: PDF 文件路径
            start_page_id: 起始页码（从0开始），默认0
            end_page_id: 结束页码（从0开始），None 表示解析到最后

        Returns:
            解析结果字典
        """
        # 强制使用 API 模式
        return self._parse_with_api(pdf_path, start_page_id=start_page_id, end_page_id=end_page_id)

    def _parse_with_api(self, pdf_path: str, start_page_id: int = 0, end_page_id: Optional[int] = None) -> Dict[str, Any]:
        """
        通过 API 调用 MinerU (OpenBayes API)

        API 文档: https://hanco9-bb.gear-c1.openbayes.net/docs#/default/parse_pdf_file_parse_post
        API 端点: POST /file_parse

        Args:
            pdf_path: PDF 文件路径

        Returns:
            解析结果字典
        """
        try:
            import requests

            # 读取 PDF 文件
            with open(pdf_path, "rb") as f:
                pdf_data = f.read()

            # 调用 MinerU API
            # API 端点: /file_parse
            # 文档: https://hanco9-bb.gear-c1.openbayes.net/docs#/default/parse_pdf_file_parse_post
            url = f"{self.api_base}/file_parse"
            
            # 准备文件上传（files 参数是数组，格式: array<string>）
            # 注意：requests 库中，files 参数如果是数组，需要这样传递
            files = [
                ("files", ("document.pdf", pdf_data, "application/pdf"))
            ]
            
            # 准备请求参数（multipart/form-data）
            # 注意：对于数组参数 lang_list，需要转换为列表或多次传递
            # 使用 tuple 列表形式来传递数组参数
            data = [
                ("lang_list", "ch"),  # 中文，A股文档主要是中文（数组参数需要多次传递）
                ("backend", "hybrid-auto-engine"),  # 使用混合引擎，高精度，支持多语言
                ("parse_method", "auto"),  # 自动选择解析方法
                ("formula_enable", "true"),  # 启用公式解析（boolean，转换为字符串）
                ("table_enable", "true"),  # 启用表格解析（boolean，转换为字符串）
                ("return_md", "true"),  # 返回 markdown（boolean，转换为字符串）
                ("return_middle_json", "true"),  # 返回 middle JSON（boolean，转换为字符串）
                ("return_content_list", "true"),  # 返回内容列表（boolean，转换为字符串）
                ("return_images", "true"),  # 返回图片（包含图片文件）
                ("return_model_output", "true"),  # 返回模型原始输出
                ("response_format_zip", "true"),  # 返回 ZIP 格式
                ("start_page_id", str(start_page_id)),  # 起始页码（从0开始）
            ]
            
            # 如果指定了结束页码，添加到参数中
            if end_page_id is not None:
                data.append(("end_page_id", str(end_page_id)))
            
            self.logger.info(f"调用 MinerU API: {url}")
            self.logger.debug(f"PDF 文件大小: {len(pdf_data)} bytes")
            # 从 data 列表中提取参数用于日志
            data_dict = dict(data)
            self.logger.debug(f"请求参数: backend={data_dict.get('backend')}, parse_method={data_dict.get('parse_method')}, start_page={start_page_id}, end_page={end_page_id}")
            
            # 发送 POST 请求
            # 设置较长的超时时间，因为 PDF 解析可能需要较长时间
            # 连接超时：30秒（建立连接的时间）
            # 读取超时：3600秒（60分钟，处理大文件时需要更长时间）
            connect_timeout = 30  # 连接超时：30秒
            read_timeout = 1200   # 读取超时：20分钟
            timeout = (connect_timeout, read_timeout)  # requests支持tuple格式：(connect_timeout, read_timeout)
            
            self.logger.info(f"API 请求超时设置: 连接超时={connect_timeout}秒, 读取超时={read_timeout//60}分钟")
            
            # 创建带重试机制的 Session
            session = requests.Session()
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            # 配置重试策略
            retry_strategy = Retry(
                total=3,  # 最多重试3次
                status_forcelist=[429, 500, 502, 503, 504],  # 这些状态码会重试
                allowed_methods=["POST"],
                backoff_factor=2,  # 重试延迟：2秒、4秒、8秒
                raise_on_status=False
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            response = session.post(
                url,
                files=files,
                data=data,
                timeout=timeout,
                headers={
                    "Accept": "application/json"
                }
            )
            
            # 检查响应状态
            response.raise_for_status()
            
            # 检查响应类型：ZIP 或 JSON
            content_type = response.headers.get("Content-Type", "").lower()
            
            if "application/zip" in content_type or "application/x-zip-compressed" in content_type or response.content[:2] == b'PK':
                # 响应是 ZIP 文件，需要解压（通过 Content-Type 或文件头判断）
                self.logger.info("API 返回 ZIP 格式，开始解压...")
                return self._process_zip_response(response, pdf_path)
            else:
                # 响应是 JSON 格式
                result = response.json()
                self.logger.debug(f"API 响应状态: {response.status_code}")
                self.logger.debug(f"API 响应键: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
                return self._process_json_response(result)

        except ImportError:
            self.logger.error("requests 库未安装，请安装: pip install requests")
            return {
                "success": False,
                "error_message": "requests 库未安装"
            }
        except requests.exceptions.ConnectTimeout:
            self.logger.error(f"API 连接超时（超过30秒），无法连接到服务器: {self.api_base}")
            return {
                "success": False,
                "error_message": f"API 连接超时，无法连接到服务器 {self.api_base}。请检查网络连接或代理设置。"
            }
        except requests.exceptions.ReadTimeout:
            read_timeout_minutes = 60
            self.logger.error(f"API 读取超时（超过 {read_timeout_minutes} 分钟），PDF 解析可能需要更长时间")
            return {
                "success": False,
                "error_message": f"API 读取超时（超过 {read_timeout_minutes} 分钟），PDF 文件可能过大或服务器处理较慢。建议稍后重试或联系管理员。"
            }
        except requests.exceptions.Timeout:
            self.logger.error(f"API 请求超时（连接或读取超时）")
            return {
                "success": False,
                "error_message": "API 请求超时，可能是网络连接问题或服务器响应过慢。请检查网络连接后重试。"
            }
        except requests.exceptions.ProxyError as e:
            self.logger.error(f"API 代理错误: {e}")
            return {
                "success": False,
                "error_message": f"代理连接失败: {str(e)}。请检查代理设置或尝试不使用代理。"
            }
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"API 连接错误: {e}")
            return {
                "success": False,
                "error_message": f"无法连接到 API 服务器 {self.api_base}: {str(e)}。请检查网络连接和服务器状态。"
            }
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else "未知"
            error_text = e.response.text[:200] if e.response else str(e)
            self.logger.error(f"API HTTP 错误: {status_code} - {error_text}")
            return {
                "success": False,
                "error_message": f"API HTTP 错误: {status_code} - {error_text}"
            }
        except KeyboardInterrupt:
            # 用户手动中断（Ctrl+C）
            self.logger.warning("⚠️ API 请求被用户中断")
            # 重新抛出，让上层处理
            raise
        except Exception as e:
            # 首先检查是否是中断异常（DagsterExecutionInterruptedError 等）
            # 必须在所有其他异常处理之前检查，因为中断异常可能在底层抛出
            error_type = type(e).__name__
            if "Interrupt" in error_type or "Interrupted" in error_type:
                self.logger.warning(f"⚠️ API 请求被中断: {error_type}")
                # 重新抛出，让上层处理
                raise
            
            # 检查异常原因中是否包含中断信息
            error_msg = str(e)
            if "interrupt" in error_msg.lower() or "interrupted" in error_msg.lower():
                self.logger.warning(f"⚠️ API 请求被中断: {error_msg}")
                raise
            
            # 检查异常的 __cause__ 或 __context__ 是否是中断异常
            if hasattr(e, '__cause__') and e.__cause__:
                cause_type = type(e.__cause__).__name__
                if "Interrupt" in cause_type or "Interrupted" in cause_type:
                    self.logger.warning(f"⚠️ API 请求被中断（通过异常链）: {cause_type}")
                    raise
            
            # 处理 requests 特定的异常
            if isinstance(e, requests.exceptions.ConnectTimeout):
                self.logger.error(f"API 连接超时（超过30秒），无法连接到服务器: {self.api_base}")
                return {
                    "success": False,
                    "error_message": f"API 连接超时，无法连接到服务器 {self.api_base}。请检查网络连接或代理设置。"
                }
            elif isinstance(e, requests.exceptions.ReadTimeout):
                read_timeout_minutes = 60
                self.logger.error(f"API 读取超时（超过 {read_timeout_minutes} 分钟），PDF 解析可能需要更长时间")
                return {
                    "success": False,
                    "error_message": f"API 读取超时（超过 {read_timeout_minutes} 分钟），PDF 文件可能过大或服务器处理较慢。建议稍后重试或联系管理员。"
                }
            elif isinstance(e, requests.exceptions.Timeout):
                self.logger.error(f"API 请求超时（连接或读取超时）")
                return {
                    "success": False,
                    "error_message": "API 请求超时，可能是网络连接问题或服务器响应过慢。请检查网络连接后重试。"
                }
            elif isinstance(e, requests.exceptions.ProxyError):
                self.logger.error(f"API 代理错误: {e}")
                return {
                    "success": False,
                    "error_message": f"代理连接失败: {str(e)}。请检查代理设置或尝试不使用代理。"
                }
            elif isinstance(e, requests.exceptions.ConnectionError):
                self.logger.error(f"API 连接错误: {e}")
                return {
                    "success": False,
                    "error_message": f"无法连接到 API 服务器 {self.api_base}: {str(e)}。请检查网络连接和服务器状态。"
                }
            elif isinstance(e, requests.exceptions.HTTPError):
                status_code = e.response.status_code if e.response else "未知"
                error_text = e.response.text[:200] if e.response else str(e)
                self.logger.error(f"API HTTP 错误: {status_code} - {error_text}")
                return {
                    "success": False,
                    "error_message": f"API HTTP 错误: {status_code} - {error_text}"
                }
            elif isinstance(e, requests.exceptions.RequestException):
                self.logger.error(f"API 请求异常: {e}", exc_info=True)
                return {
                    "success": False,
                    "error_message": f"API 请求失败: {str(e)}"
                }
            elif isinstance(e, ImportError):
                self.logger.error("requests 库未安装，请安装: pip install requests")
                return {
                    "success": False,
                    "error_message": "requests 库未安装"
                }
            else:
                # 其他未知异常
                self.logger.error(f"MinerU API 调用失败: {e}", exc_info=True)
                return {
                    "success": False,
                    "error_message": f"API 调用失败: {str(e)}"
                }
    
    def _process_zip_response(self, response, pdf_path: str) -> Dict[str, Any]:
        """
        处理 ZIP 格式的 API 响应
        
        Args:
            response: requests.Response 对象（包含 ZIP 数据）
            pdf_path: 原始 PDF 文件路径（用于确定文件名）
            
        Returns:
            解析结果字典
        """
        import zipfile
        import io
        
        temp_extract_dir = None
        try:
            # 读取 ZIP 文件内容
            zip_data = response.content
            self.logger.debug(f"ZIP 文件大小: {len(zip_data)} bytes")
            
            # 创建临时目录用于解压
            temp_extract_dir = tempfile.mkdtemp(prefix="mineru_zip_extract_")
            
            # 解压 ZIP 文件
            with zipfile.ZipFile(io.BytesIO(zip_data), 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)
                self.logger.debug(f"ZIP 文件已解压到: {temp_extract_dir}")
            
            # 查找解压后的文件
            # MinerU 通常会在 {pdf_name}/{parse_method}/ 目录下生成文件
            pdf_file_name = Path(pdf_path).stem
            extract_path = Path(temp_extract_dir)
            
            # 查找 PDF 名称的目录
            pdf_dir = None
            for item in extract_path.iterdir():
                if item.is_dir() and pdf_file_name in item.name:
                    pdf_dir = item
                    break
            
            if not pdf_dir:
                # 如果找不到，尝试查找第一个目录
                dirs = [d for d in extract_path.iterdir() if d.is_dir()]
                if dirs:
                    pdf_dir = dirs[0]
                    self.logger.warning(f"未找到 PDF 名称目录，使用第一个目录: {pdf_dir}")
            
            if not pdf_dir:
                raise FileNotFoundError(f"ZIP 文件中未找到预期的目录结构")
            
            # 查找 parse_method 子目录（如 hybrid_auto）
            # 排除 images 目录，因为那是图片目录
            result_dir = None
            for item in pdf_dir.iterdir():
                if item.is_dir() and item.name != "images":
                    result_dir = item
                    break
            
            if not result_dir:
                # 如果没有子目录，直接使用 pdf_dir
                result_dir = pdf_dir
                self.logger.info(f"未找到 parse_method 子目录，使用: {result_dir}")
            
            self.logger.info(f"解析结果目录: {result_dir}")
            
            # 读取文件
            markdown_content = ""
            middle_json = {}
            content_list = []
            tables = []
            images = []
            
            # 查找并读取 Markdown 文件
            md_files = list(result_dir.glob("*.md"))
            if md_files:
                md_file = md_files[0]
                with open(md_file, "r", encoding="utf-8") as f:
                    markdown_content = f.read()
                self.logger.debug(f"读取 Markdown 文件: {md_file.name}, 大小: {len(markdown_content)} 字符")
            
            # 查找并读取 middle_json 文件
            json_files = list(result_dir.glob("*_middle.json"))
            if json_files:
                json_file = json_files[0]
                with open(json_file, "r", encoding="utf-8") as f:
                    middle_json = json.load(f)
                self.logger.debug(f"读取 middle_json 文件: {json_file.name}")
            
            # 查找并读取 content_list 文件
            content_list_files = list(result_dir.glob("*_content_list.json"))
            if content_list_files:
                content_list_file = content_list_files[0]
                with open(content_list_file, "r", encoding="utf-8") as f:
                    content_list = json.load(f)
                self.logger.debug(f"读取 content_list 文件: {content_list_file.name}")
            
            # 查找图片目录（通常在 result_dir 的父目录或同级目录）
            # MinerU 通常会在 {pdf_name}/images/ 或 {parse_method}/images/ 目录下保存图片
            image_dir = None
            # 先尝试在 result_dir 的父目录查找 images 目录
            parent_dir = result_dir.parent
            potential_image_dirs = [
                parent_dir / "images",
                result_dir / "images",
                pdf_dir / "images",
            ]
            for img_dir in potential_image_dirs:
                if img_dir.exists() and img_dir.is_dir():
                    image_dir = img_dir
                    break
            
            # 从 middle_json 中提取表格和图片
            if middle_json:
                # pdf_info 可能是字典或列表
                pdf_info = middle_json.get("pdf_info", {})
                if isinstance(pdf_info, list):
                    # 如果 pdf_info 是列表，直接使用
                    pages = pdf_info
                elif isinstance(pdf_info, dict):
                    # 如果 pdf_info 是字典，提取 pages
                    pages = pdf_info.get("pages", [])
                else:
                    pages = []
                
                for page in pages:
                    # 提取表格
                    page_tables = page.get("tables", [])
                    for table in page_tables:
                        tables.append({
                            "table_index": len(tables),
                            "page": page.get("page_id", 0),
                            "markdown": table.get("markdown", ""),
                            "bbox": table.get("bbox", [])
                        })
                    
                    # 提取图片元数据
                    page_images = page.get("images", [])
                    for image in page_images:
                        images.append({
                            "image_index": len(images),
                            "page": page.get("page_id", 0),
                            "description": image.get("description", ""),
                            "bbox": image.get("bbox", []),
                            "image_path": None  # 稍后填充实际路径
                        })
            
            # 收集所有需要上传的文件
            uploaded_images = []
            all_files_to_upload = []  # 所有需要上传的文件列表
            
            # 计算基础路径（用于去除 document/ 前缀）
            # 找到 result_dir 相对于 temp_extract_dir 的路径，提取 document 或类似的前缀
            base_relative_path = None
            try:
                base_relative_path = os.path.relpath(str(result_dir), temp_extract_dir)
                base_relative_path = base_relative_path.replace(os.sep, '/')
                # 如果路径是 document 或类似结构，提取出来用于后续去除
                if '/' in base_relative_path:
                    # 例如：document/hybrid_auto -> document
                    base_prefix = base_relative_path.split('/')[0]
                else:
                    base_prefix = base_relative_path
            except ValueError:
                base_prefix = None
            
            # 1. 收集图片文件（去除 document/ 前缀，直接使用 images/）
            if image_dir and image_dir.exists():
                image_files = list(image_dir.glob("*.*"))
                image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
                image_files = [f for f in image_files if f.suffix.lower() in image_extensions]
                
                self.logger.info(f"找到 {len(image_files)} 个图片文件在目录: {image_dir}")
                
                for img_file in image_files:
                    # 图片文件直接放在 images/ 目录下
                    relative_path = f"images/{img_file.name}"
                    
                    uploaded_images.append({
                        "local_path": str(img_file),
                        "filename": img_file.name,
                        "relative_path": relative_path,
                        "size": img_file.stat().st_size,
                        "file_type": "image"
                    })
                    all_files_to_upload.append({
                        "local_path": str(img_file),
                        "filename": img_file.name,
                        "relative_path": relative_path,
                        "size": img_file.stat().st_size,
                        "file_type": "image"
                    })
            else:
                self.logger.debug(f"未找到图片目录，跳过图片上传")
            
            # 2. 收集 Markdown 文件（去除 document/ 前缀，直接使用文件名）
            if md_files:
                md_file = md_files[0]
                relative_path = md_file.name  # 直接使用文件名，不包含 document/ 前缀
                all_files_to_upload.append({
                    "local_path": str(md_file),
                    "filename": md_file.name,
                    "relative_path": relative_path,
                    "size": md_file.stat().st_size,
                    "file_type": "markdown"
                })
                self.logger.debug(f"找到 Markdown 文件: {md_file.name}, 相对路径: {relative_path}")
            
            # 3. 收集 Middle JSON 文件（去除 document/ 前缀，直接使用文件名）
            if json_files:
                json_file = json_files[0]
                relative_path = json_file.name  # 直接使用文件名
                all_files_to_upload.append({
                    "local_path": str(json_file),
                    "filename": json_file.name,
                    "relative_path": relative_path,
                    "size": json_file.stat().st_size,
                    "file_type": "middle_json"
                })
                self.logger.debug(f"找到 Middle JSON 文件: {json_file.name}, 相对路径: {relative_path}")
            
            # 4. 收集 Content List 文件（去除 document/ 前缀，直接使用文件名）
            if content_list_files:
                content_list_file = content_list_files[0]
                relative_path = content_list_file.name  # 直接使用文件名
                all_files_to_upload.append({
                    "local_path": str(content_list_file),
                    "filename": content_list_file.name,
                    "relative_path": relative_path,
                    "size": content_list_file.stat().st_size,
                    "file_type": "content_list"
                })
                self.logger.debug(f"找到 Content List 文件: {content_list_file.name}, 相对路径: {relative_path}")
            
            # 5. 查找其他可能的文件（如 model.json 等，去除 document/ 前缀）
            other_files = []
            # 查找所有 JSON 文件（除了已经找到的）
            all_json_files = list(result_dir.glob("*.json"))
            for json_file in all_json_files:
                if json_file not in json_files and json_file not in content_list_files:
                    other_files.append(json_file)
            
            # 查找其他类型的文件
            other_extensions = {'.txt', '.pdf', '.xml'}
            for ext in other_extensions:
                other_files.extend(list(result_dir.glob(f"*{ext}")))
            
            for other_file in other_files:
                relative_path = other_file.name  # 直接使用文件名
                all_files_to_upload.append({
                    "local_path": str(other_file),
                    "filename": other_file.name,
                    "relative_path": relative_path,
                    "size": other_file.stat().st_size,
                    "file_type": "other"
                })
                self.logger.debug(f"找到其他文件: {other_file.name}, 相对路径: {relative_path}")
            
            self.logger.info(f"总共找到 {len(all_files_to_upload)} 个文件需要上传")
            
            # 提取纯文本
            text_content = self._extract_text_from_markdown(markdown_content)
            
            self.logger.info(
                f"✅ ZIP 解析成功: "
                f"文本长度={len(text_content)}, "
                f"表格数量={len(tables)}, "
                f"图片数量={len(images)}"
            )
            
            return {
                "success": True,
                "text": text_content,
                "markdown": markdown_content,
                "tables": tables,
                "images": images,
                "content_list": content_list,
                "middle_json": middle_json,
                "text_length": len(text_content),
                "tables_count": len(tables),
                "images_count": len(images),
                "image_files": uploaded_images,  # 添加图片文件列表
                "all_files": all_files_to_upload,  # 添加所有文件列表
                "temp_extract_dir": temp_extract_dir,  # 保存临时目录路径，延迟清理
                "metadata": {
                    "api_base": self.api_base,
                    "response_format": "zip",
                    "extract_dir": str(result_dir),
                    "image_dir": str(image_dir) if image_dir else None,
                    "temp_extract_dir": temp_extract_dir  # 也保存在 metadata 中
                }
            }
            
            # 注意：临时目录的清理延迟到 _save_to_silver 完成后
            # 因为图片文件需要先上传到 MinIO
            # 如果发生异常，临时目录会在 except 块中清理
                    
        except zipfile.BadZipFile:
            self.logger.error("响应不是有效的 ZIP 文件")
            # 清理临时目录
            if temp_extract_dir and os.path.exists(temp_extract_dir):
                try:
                    import shutil
                    shutil.rmtree(temp_extract_dir)
                except:
                    pass
            return {
                "success": False,
                "error_message": "API 返回的不是有效的 ZIP 文件"
            }
        except Exception as e:
            self.logger.error(f"处理 ZIP 响应失败: {e}", exc_info=True)
            # 清理临时目录
            if temp_extract_dir and os.path.exists(temp_extract_dir):
                try:
                    import shutil
                    shutil.rmtree(temp_extract_dir)
                except:
                    pass
            return {
                "success": False,
                "error_message": f"处理 ZIP 响应失败: {str(e)}"
            }
    
    def _process_json_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理 JSON 格式的 API 响应
        
        Args:
            result: API 返回的 JSON 数据
            
        Returns:
            解析结果字典
        """
        # 根据 API 响应格式提取解析结果
        # API 根据请求参数返回相应的字段：
        # - return_md=True -> markdown 字段
        # - return_middle_json=True -> middle_json 字段
        # - return_content_list=True -> content_list 字段
        # - return_images=True -> images 字段
        
        markdown_content = ""
        text_content = ""
        tables = []
        images = []
        content_list = []
        middle_json = {}
        
        # 提取 markdown（如果请求了 return_md=True）
        if "markdown" in result:
            markdown_content = result.get("markdown", "")
        elif "content" in result:
            markdown_content = result.get("content", "")
        elif "text" in result:
            markdown_content = result.get("text", "")
        
        # 提取 middle_json（如果请求了 return_middle_json=True）
        if "middle_json" in result:
            middle_json = result.get("middle_json", {})
            if isinstance(middle_json, str):
                # 如果是字符串，尝试解析 JSON
                try:
                    middle_json = json.loads(middle_json)
                except:
                    self.logger.warning("middle_json 是字符串但无法解析为 JSON")
                    middle_json = {}
        
        # 提取 content_list（如果请求了 return_content_list=True）
        if "content_list" in result:
            content_list = result.get("content_list", [])
            if isinstance(content_list, str):
                try:
                    content_list = json.loads(content_list)
                except:
                    self.logger.warning("content_list 是字符串但无法解析为 JSON")
                    content_list = []
        
        # 提取 images（如果请求了 return_images=True）
        if "images" in result:
            images = result.get("images", [])
        
        # 从 middle_json 中提取表格和图片信息（如果存在）
        if middle_json:
            pdf_info = middle_json.get("pdf_info", {})
            pages = pdf_info.get("pages", [])
            
            for page in pages:
                # 提取表格
                page_tables = page.get("tables", [])
                for table in page_tables:
                    tables.append({
                        "table_index": len(tables),
                        "page": page.get("page_id", 0),
                        "markdown": table.get("markdown", ""),
                        "bbox": table.get("bbox", [])
                    })
                
                # 提取图片（如果 middle_json 中有但 images 中没有）
                if not images:
                    page_images = page.get("images", [])
                    for image in page_images:
                        images.append({
                            "image_index": len(images),
                            "page": page.get("page_id", 0),
                            "description": image.get("description", ""),
                            "bbox": image.get("bbox", [])
                        })
        
        # 如果还是没有找到 markdown，尝试从整个响应中提取文本
        if not markdown_content:
            # 尝试将整个 JSON 转换为字符串（作为后备方案）
            markdown_content = json.dumps(result, ensure_ascii=False, indent=2)
            self.logger.warning("API 响应中未找到 markdown/content/text 字段，使用完整 JSON 作为后备")
        
        # 提取纯文本（从 Markdown 中去除格式）
        text_content = self._extract_text_from_markdown(markdown_content)
        
        # 如果表格和图片为空，尝试从 middle_json 中提取
        if not tables or not images:
            pdf_info = middle_json.get("pdf_info", {}) if middle_json else {}
            pages = pdf_info.get("pages", []) if pdf_info else []
            
            for page in pages:
                # 提取表格
                if not tables:
                    page_tables = page.get("tables", [])
                    for table in page_tables:
                        tables.append({
                            "table_index": len(tables),
                            "page": page.get("page_id", 0),
                            "markdown": table.get("markdown", ""),
                            "bbox": table.get("bbox", [])
                        })
                
                # 提取图片
                if not images:
                    page_images = page.get("images", [])
                    for image in page_images:
                        images.append({
                            "image_index": len(images),
                            "page": page.get("page_id", 0),
                            "description": image.get("description", ""),
                            "bbox": image.get("bbox", [])
                        })
        
        self.logger.info(
            f"✅ API 解析成功: "
            f"文本长度={len(text_content)}, "
            f"表格数量={len(tables)}, "
            f"图片数量={len(images)}"
        )
        
        return {
            "success": True,
            "text": text_content,
            "markdown": markdown_content,
            "tables": tables,
            "images": images,
            "content_list": content_list,
            "middle_json": middle_json,
            "text_length": len(text_content),
            "tables_count": len(tables),
            "images_count": len(images),
            "metadata": {
                "api_base": self.api_base,
                "response_keys": list(result.keys()) if isinstance(result, dict) else [],
                "raw_response": result if not middle_json else {}  # 如果已经有 middle_json，不保存原始响应
            }
        }

    def _parse_with_package(self, pdf_path: str) -> Dict[str, Any]:
        """
        使用 MinerU Python 包解析

        Args:
            pdf_path: PDF 文件路径

        Returns:
            解析结果字典
        """
        try:
            # 尝试导入 MinerU
            try:
                from mineru.cli.common import do_parse
                from pathlib import Path
            except ImportError:
                return {
                    "success": False,
                    "error_message": "MinerU 包未安装，请安装: pip install mineru"
                }

            # 读取 PDF 文件
            pdf_file_path = Path(pdf_path)
            pdf_file_name = pdf_file_path.stem
            
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()

            # 创建临时输出目录
            temp_output_dir = tempfile.mkdtemp(prefix="mineru_output_")
            
            self.logger.debug(f"开始 MinerU 解析流程... output_dir={temp_output_dir}")

            # 调用 MinerU 的 do_parse 函数
            # 使用 hybrid-auto-engine backend（推荐，高精度）
            parse_method_param = "auto"  # 传递给 do_parse 的参数
            do_parse(
                output_dir=temp_output_dir,
                pdf_file_names=[pdf_file_name],
                pdf_bytes_list=[pdf_bytes],
                p_lang_list=["ch"],  # 中文，A股文档主要是中文
                backend="hybrid-auto-engine",  # 使用混合引擎，自动选择最佳方案
                parse_method=parse_method_param,  # 自动选择解析方法
                formula_enable=True,  # 启用公式解析
                table_enable=True,  # 启用表格解析
                f_dump_md=True,  # 输出 Markdown
                f_dump_middle_json=True,  # 输出中间 JSON
                f_dump_content_list=True,  # 输出内容列表
                f_dump_model_output=False,  # 不输出模型原始输出（节省空间）
                f_dump_orig_pdf=False,  # 不输出原始 PDF（已存在）
                f_draw_layout_bbox=False,  # 不绘制布局框
                f_draw_span_bbox=False,  # 不绘制 span 框
            )

            # 从输出目录读取解析结果
            # MinerU 会在 output_dir/{pdf_file_name}/{parse_method}/ 目录下生成文件
            # hybrid-auto-engine 会将 parse_method 转换为 "hybrid_auto"
            actual_parse_method = f"hybrid_{parse_method_param}"
            result_dir = Path(temp_output_dir) / pdf_file_name / actual_parse_method
            
            # 如果目录不存在，尝试其他可能的路径
            if not result_dir.exists():
                # 尝试直接使用 parse_method
                result_dir = Path(temp_output_dir) / pdf_file_name / parse_method_param
                if not result_dir.exists():
                    # 尝试查找实际存在的目录
                    pdf_dir = Path(temp_output_dir) / pdf_file_name
                    if pdf_dir.exists():
                        subdirs = [d for d in pdf_dir.iterdir() if d.is_dir()]
                        if subdirs:
                            result_dir = subdirs[0]
                            actual_parse_method = result_dir.name
                            self.logger.info(f"使用实际输出目录: {result_dir}")
                        else:
                            raise FileNotFoundError(f"找不到解析结果目录: {pdf_dir}")
                    else:
                        raise FileNotFoundError(f"PDF 输出目录不存在: {pdf_dir}")
            
            # 读取 Markdown 文件
            md_file = result_dir / f"{pdf_file_name}.md"
            md_content = ""
            if md_file.exists():
                with open(md_file, "r", encoding="utf-8") as f:
                    md_content = f.read()
            else:
                self.logger.warning(f"Markdown 文件不存在: {md_file}")

            # 读取 middle_json 文件（包含结构化信息）
            middle_json_file = result_dir / f"{pdf_file_name}_middle.json"
            middle_json = {}
            tables = []
            images = []
            
            if middle_json_file.exists():
                with open(middle_json_file, "r", encoding="utf-8") as f:
                    middle_json = json.load(f)
                
                # 从 middle_json 中提取表格和图片信息
                pdf_info = middle_json.get("pdf_info", {})
                pages = pdf_info.get("pages", [])
                
                for page in pages:
                    # 提取表格
                    page_tables = page.get("tables", [])
                    for table in page_tables:
                        tables.append({
                            "table_index": len(tables),
                            "page": page.get("page_id", 0),
                            "markdown": table.get("markdown", ""),
                            "bbox": table.get("bbox", [])
                        })
                    
                    # 提取图片
                    page_images = page.get("images", [])
                    for image in page_images:
                        images.append({
                            "image_index": len(images),
                            "page": page.get("page_id", 0),
                            "description": image.get("description", ""),
                            "bbox": image.get("bbox", [])
                        })
            else:
                self.logger.warning(f"Middle JSON 文件不存在: {middle_json_file}")

            # 读取 content_list（如果需要更详细的内容结构）
            content_list_file = result_dir / f"{pdf_file_name}_content_list.json"
            content_list = []
            if content_list_file.exists():
                with open(content_list_file, "r", encoding="utf-8") as f:
                    content_list = json.load(f)

            # 清理临时输出目录
            try:
                import shutil
                shutil.rmtree(temp_output_dir)
                self.logger.debug(f"已清理临时输出目录: {temp_output_dir}")
            except Exception as e:
                self.logger.warning(f"清理临时输出目录失败: {e}")

            # 提取纯文本（从 Markdown 中去除格式）
            text_content = self._extract_text_from_markdown(md_content)

            return {
                "success": True,
                "text": text_content,
                "markdown": md_content,
                "tables": tables,
                "images": images,
                "content_list": content_list,
                "middle_json": middle_json,
                "text_length": len(text_content),
                "tables_count": len(tables),
                "images_count": len(images),
                "metadata": {
                    "pdf_info": middle_json.get("pdf_info", {}),
                    "parse_method": actual_parse_method,
                    "backend": "hybrid-auto-engine"
                }
            }

        except ImportError as e:
            self.logger.error(f"MinerU 包导入失败: {e}")
            return {
                "success": False,
                "error_message": f"MinerU 包未正确安装: {str(e)}"
            }
        except Exception as e:
            self.logger.error(f"MinerU 包解析失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": f"解析失败: {str(e)}"
            }

    def _extract_text_from_markdown(self, markdown: str) -> str:
        """
        从 Markdown 中提取纯文本（去除格式标记）

        Args:
            markdown: Markdown 内容

        Returns:
            纯文本内容
        """
        import re
        
        # 移除 Markdown 格式标记
        # 移除图片标记 ![alt](url)
        text = re.sub(r'!\[.*?\]\(.*?\)', '', markdown)
        # 移除链接标记 [text](url)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        # 移除标题标记 #
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
        # 移除粗体/斜体标记
        text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^\*]+)\*', r'\1', text)
        # 移除代码块标记
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # 移除表格标记（保留内容）
        text = re.sub(r'\|', ' ', text)
        # 移除多余空白
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = text.strip()
        
        return text

    def _save_to_silver(
        self,
        doc: Document,
        parse_task_id: Union[uuid.UUID, str],
        parse_result: Dict[str, Any]
    ) -> Optional[str]:
        """
        保存解析结果到 Silver 层（包括图片文件）

        Args:
            doc: 文档对象
            parse_result: 解析结果

        Returns:
            Silver 层路径
        """
        try:
            # 1. 上传所有原始文件（图片、Markdown、JSON 等）到统一目录
            all_files = parse_result.get("all_files", [])
            uploaded_file_paths = {}  # 按文件类型分类存储路径
            uploaded_image_paths = []
            uploaded_image_sizes = {}  # 记录图片文件大小 {minio_path: file_size}
            
            if all_files:
                self.logger.info(f"开始上传 {len(all_files)} 个原始文件...")
                
                # 生成统一的存储路径：silver/{market}/mineru/{doc_type}/{stock_code}/
                market = Market(doc.market)
                doc_type = DocType(doc.doc_type)

                if doc_type == DocType.IPO_PROSPECTUS:
                    base_path = f"silver/{market.value}/mineru/{doc_type.value}/{doc.stock_code}"
                else:
                    base_path = f"silver/{market.value}/mineru/{doc_type.value}/{doc.year}/Q{doc.quarter if doc.quarter else 'Annual'}/{doc.stock_code}"
                
                # 所有文件都上传到同一个目录，保持相对路径结构
                for file_info in all_files:
                    local_path = file_info.get("local_path")
                    filename = file_info.get("filename")
                    relative_path = file_info.get("relative_path", filename)  # 使用相对路径，如果没有则使用文件名
                    file_type = file_info.get("file_type", "other")
                    
                    if not local_path or not os.path.exists(local_path):
                        self.logger.warning(f"文件不存在: {local_path}")
                        continue
                    
                    # 使用相对路径构建 MinIO 路径，并重命名特定文件
                    # 重命名规则：
                    # - document_content_list.json -> content_list.json
                    # - document_middle.json -> middle.json
                    # - document_model.json -> model.json
                    renamed_path = relative_path
                    if filename == "document_content_list.json":
                        renamed_path = "content_list.json"
                    elif filename == "document_middle.json":
                        renamed_path = "middle.json"
                    elif filename == "document_model.json":
                        renamed_path = "model.json"

                    object_path = f"{base_path}/{renamed_path}"
                    
                    # 根据文件类型确定 Content-Type
                    if file_type == "image":
                        content_type = self._get_image_content_type(filename)
                    elif file_type == "markdown":
                        content_type = "text/markdown"
                    elif file_type in ["middle_json", "content_list"]:
                        content_type = "application/json"
                    else:
                        content_type = self._get_content_type_by_extension(filename)
                    
                    # 读取文件并上传
                    try:
                        with open(local_path, "rb") as f:
                            file_data = f.read()

                        file_size = len(file_data)  # 记录文件大小

                        success = self.minio_client.upload_file(
                            object_name=object_path,
                            data=file_data,
                            content_type=content_type,
                            metadata={
                                "document_id": str(doc.id),
                                "stock_code": doc.stock_code,
                                "parser": "mineru",
                                "file_type": file_type,
                                "uploaded_at": datetime.now().isoformat()
                            }
                        )

                        if success:
                            if file_type not in uploaded_file_paths:
                                uploaded_file_paths[file_type] = []
                            uploaded_file_paths[file_type].append(object_path)

                            if file_type == "image":
                                uploaded_image_paths.append(object_path)
                                uploaded_image_sizes[object_path] = file_size  # 记录图片大小

                            self.logger.debug(f"✅ {file_type} 文件已上传: {object_path}")
                        else:
                            self.logger.warning(f"❌ {file_type} 文件上传失败: {object_path}")
                    except Exception as e:
                        self.logger.error(f"上传 {file_type} 文件失败 {local_path}: {e}", exc_info=True)
                
                # 统计上传结果
                total_uploaded = sum(len(paths) for paths in uploaded_file_paths.values())
                self.logger.info(f"✅ 已上传 {total_uploaded}/{len(all_files)} 个文件")
                for file_type, paths in uploaded_file_paths.items():
                    self.logger.info(f"   - {file_type}: {len(paths)} 个文件")
            
            # 2. 更新图片元数据，添加 MinIO 路径
            images_metadata = parse_result.get("images", [])
            for i, img_meta in enumerate(images_metadata):
                if i < len(uploaded_image_paths):
                    img_meta["minio_path"] = uploaded_image_paths[i]
            
            # 3. 生成 Silver 层基础路径（用于数据库记录，不创建汇总 JSON）
            market = Market(doc.market)
            doc_type = DocType(doc.doc_type)

            if doc_type == DocType.IPO_PROSPECTUS:
                base_path = f"silver/{market.value}/mineru/{doc_type.value}/{doc.stock_code}"
            else:
                base_path = f"silver/{market.value}/mineru/{doc_type.value}/{doc.year}/Q{doc.quarter if doc.quarter else 'Annual'}/{doc.stock_code}"
            
            # 使用 base_path 作为 output_path（用于数据库记录）
            silver_path = base_path

            # 4. 统计上传结果并记录日志
            total_files = sum(len(paths) for paths in uploaded_file_paths.values())
            self.logger.info(
                f"✅ 解析结果已保存到 Silver 层: {silver_path} "
                f"(包含 {len(uploaded_image_paths)} 个图片, 总共 {total_files} 个文件)"
            )
            
            # 5. 创建 ParsedDocument 和 Image 记录
            try:
                self._create_parsed_document_records(
                    doc=doc,
                    parse_task_id=parse_task_id,
                    silver_path=silver_path,
                    uploaded_file_paths=uploaded_file_paths,
                    uploaded_image_paths=uploaded_image_paths,
                    uploaded_image_sizes=uploaded_image_sizes,
                    images_metadata=images_metadata,
                    parse_result=parse_result
                )
            except Exception as e:
                self.logger.error(f"创建 ParsedDocument 记录失败: {e}", exc_info=True)
                # 如果创建数据库记录失败，返回 None 表示保存失败
                # 这样可以避免文档状态被错误地标记为 parsed
                return None
            
            # 6. 清理临时目录（如果存在）
            temp_extract_dir = parse_result.get("temp_extract_dir") or parse_result.get("metadata", {}).get("temp_extract_dir")
            if temp_extract_dir and os.path.exists(temp_extract_dir):
                try:
                    import shutil
                    shutil.rmtree(temp_extract_dir)
                    self.logger.debug(f"已清理临时解压目录: {temp_extract_dir}")
                except Exception as e:
                    self.logger.warning(f"清理临时目录失败: {e}")
            
            return silver_path

        except Exception as e:
            self.logger.error(f"保存到 Silver 层异常: {e}", exc_info=True)
            return None
    
    def _get_image_content_type(self, filename: str) -> str:
        """根据文件名获取图片的 Content-Type"""
        ext = Path(filename).suffix.lower()
        content_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
        }
        return content_types.get(ext, 'application/octet-stream')
    
    def _get_content_type_by_extension(self, filename: str) -> str:
        """根据文件扩展名获取 Content-Type"""
        ext = Path(filename).suffix.lower()
        content_types = {
            '.json': 'application/json',
            '.md': 'text/markdown',
            '.txt': 'text/plain',
            '.xml': 'application/xml',
            '.pdf': 'application/pdf',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
        }
        return content_types.get(ext, 'application/octet-stream')
    
    def _calculate_file_hash(self, file_path: str) -> Optional[str]:
        """
        计算文件的 SHA256 哈希值
        
        Args:
            file_path: MinIO 对象路径或本地文件路径
        
        Returns:
            SHA256 哈希值（64字符十六进制字符串），失败返回 None
        """
        try:
            # 如果是 MinIO 路径，从 MinIO 下载文件数据
            if file_path.startswith(('silver/', 'bronze/', 'gold/')):
                file_data = self.minio_client.download_file(file_path)
                if not file_data:
                    self.logger.warning(f"无法下载文件计算哈希: {file_path}")
                    return None
            else:
                # 本地文件路径
                if not os.path.exists(file_path):
                    self.logger.warning(f"文件不存在: {file_path}")
                    return None
                with open(file_path, 'rb') as f:
                    file_data = f.read()
            
            # 计算 SHA256 哈希
            hash_obj = hashlib.sha256(file_data)
            return hash_obj.hexdigest()
        except Exception as e:
            self.logger.error(f"计算文件哈希失败 {file_path}: {e}", exc_info=True)
            return None
    
    def _create_parsed_document_records(
        self,
        doc: Document,
        parse_task_id: Union[uuid.UUID, str],
        silver_path: str,
        uploaded_file_paths: Dict[str, List[str]],
        uploaded_image_paths: List[str],
        uploaded_image_sizes: Dict[str, int],
        images_metadata: List[Dict[str, Any]],
        parse_result: Dict[str, Any]
    ) -> None:
        """
        创建 ParsedDocument 和 Image 记录
        
        Args:
            doc: 文档对象
            parse_task_id: 解析任务ID
            silver_path: Silver 层基础路径
            uploaded_file_paths: 已上传的文件路径（按类型分类）
            uploaded_image_paths: 已上传的图片路径列表
            images_metadata: 图片元数据列表
            parse_result: 解析结果
        """
        with self.pg_client.get_session() as session:
            try:
                # 1. 确定文件路径
                content_list_paths = uploaded_file_paths.get("content_list", [])
                markdown_paths = uploaded_file_paths.get("markdown", [])
                middle_json_paths = uploaded_file_paths.get("middle_json", [])
                model_json_paths = uploaded_file_paths.get("other", [])  # model_json 在 other 分类中

                # 使用新的路径格式
                content_json_path = None
                markdown_path = None
                middle_json_path = None
                model_json_path = None
                image_folder_path = None

                # 查找 content_list.json 文件
                for path in content_list_paths:
                    if path.endswith("content_list.json"):
                        content_json_path = path
                        break

                # 如果没有找到，使用第一个 content_list 文件
                if not content_json_path and content_list_paths:
                    content_json_path = content_list_paths[0]

                # 查找 markdown 文件
                for path in markdown_paths:
                    if path.endswith("document.md"):
                        markdown_path = path
                        break

                # 如果没有找到，使用第一个 markdown 文件
                if not markdown_path and markdown_paths:
                    markdown_path = markdown_paths[0]

                # 查找 middle.json 文件
                for path in middle_json_paths:
                    if path.endswith("middle.json"):
                        middle_json_path = path
                        break

                if not middle_json_path and middle_json_paths:
                    middle_json_path = middle_json_paths[0]

                # 查找 model.json 文件
                for path in model_json_paths:
                    if path.endswith("model.json"):
                        model_json_path = path
                        break

                # 确定图片文件夹路径
                if uploaded_image_paths:
                    # 使用第一个图片路径的目录作为图片文件夹路径
                    first_image_path = uploaded_image_paths[0]
                    image_folder_path = os.path.dirname(first_image_path) + "/"
                
                # 2. 计算哈希值
                content_json_hash = ""
                markdown_hash = None
                source_document_hash = doc.file_hash or ""
                
                if content_json_path:
                    content_json_hash = self._calculate_file_hash(content_json_path) or ""
                
                if markdown_path:
                    markdown_hash = self._calculate_file_hash(markdown_path)
                
                # 3. 获取统计信息
                text_length = parse_result.get("text_length", 0)
                tables_count = parse_result.get("tables_count", 0)
                images_count = len(uploaded_image_paths)
                pages_count = parse_result.get("pages_count", 0)
                
                # 4. 获取解析器信息
                parser_type = "mineru"
                parser_version = self._get_mineru_version()
                
                # 5. 创建 ParsedDocument 记录
                if not content_json_path:
                    error_msg = "未找到 content_list.json 文件，无法创建 ParsedDocument 记录"
                    self.logger.error(error_msg)
                    raise Exception(error_msg)
                
                parsed_doc = crud.create_parsed_document(
                    session=session,
                    document_id=doc.id,
                    parse_task_id=parse_task_id,
                    content_json_path=content_json_path,
                    content_json_hash=content_json_hash,
                    source_document_hash=source_document_hash,
                    parser_type=parser_type,
                    parser_version=parser_version,
                    markdown_path=markdown_path,
                    markdown_hash=markdown_hash,
                    middle_json_path=middle_json_path,
                    model_json_path=model_json_path,
                    image_folder_path=image_folder_path,
                    text_length=text_length,
                    tables_count=tables_count,
                    images_count=images_count,
                    pages_count=pages_count,
                    has_tables=tables_count > 0,
                    has_images=images_count > 0
                )
                
                parsed_document_id = parsed_doc.id
                self.logger.info(f"✅ 创建 ParsedDocument 记录: id={parsed_document_id}")
                
                # 6. 创建 Image 记录
                self.logger.info(f"准备创建 Image 记录: images_metadata 数量={len(images_metadata)}, uploaded_image_paths 数量={len(uploaded_image_paths)}")

                # 如果有上传的图片但没有元数据，创建基本的 Image 记录
                if uploaded_image_paths:
                    if not images_metadata:
                        # 没有详细元数据，创建基本记录
                        self.logger.warning(f"图片元数据为空，将为 {len(uploaded_image_paths)} 张图片创建基本记录")
                        images_metadata = []
                        for idx, img_path in enumerate(uploaded_image_paths):
                            images_metadata.append({
                                "image_index": idx,
                                "page": 0,  # 未知页码
                                "filename": os.path.basename(img_path),
                                "description": None,
                                "bbox": None,
                                "width": None,
                                "height": None,
                                "file_size": None
                            })

                    for idx, (img_meta, img_path) in enumerate(zip(images_metadata, uploaded_image_paths)):
                        try:
                            # 获取图片信息
                            image_index = img_meta.get("image_index", idx)
                            page_number = img_meta.get("page", img_meta.get("page_number", 1))
                            filename = os.path.basename(img_path)
                            bbox = img_meta.get("bbox")
                            description = img_meta.get("description")
                            
                            # 计算图片文件哈希
                            image_hash = self._calculate_file_hash(img_path)
                            
                            # 获取图片尺寸（如果元数据中有）
                            width = img_meta.get("width")
                            height = img_meta.get("height")
                            file_size = uploaded_image_sizes.get(img_path)
                            
                            # 创建 Image 记录
                            image = crud.create_image(
                                session=session,
                                parsed_document_id=parsed_document_id,
                                document_id=doc.id,
                                image_index=image_index,
                                filename=filename,
                                file_path=img_path,
                                page_number=page_number,
                                file_hash=image_hash,
                                bbox=bbox,
                                description=description,
                                width=width,
                                height=height,
                                file_size=file_size
                            )
                            self.logger.debug(f"✅ 创建 Image 记录: id={image.id}, filename={filename}")
                        except Exception as e:
                            self.logger.error(f"创建 Image 记录失败 (image_index={idx}): {e}", exc_info=True)
                            continue
                    
                    self.logger.info(f"✅ 创建 {len(uploaded_image_paths)} 个 Image 记录")
                
                session.commit()
                
            except Exception as e:
                session.rollback()
                raise e

    def _update_parse_task_success(
        self,
        parse_task_id: Union[uuid.UUID, str],
        output_path: str,
        extracted_text_length: int,
        extracted_tables_count: int,
        extracted_images_count: int,
        duration: float
    ) -> None:
        """更新解析任务为成功状态"""
        with self.pg_client.get_session() as session:
            task = session.query(ParseTask).filter(
                ParseTask.id == parse_task_id
            ).first()
            if task:
                task.status = "completed"
                task.completed_at = datetime.now()
                task.output_path = output_path

                # 将额外信息存储到 extra_metadata
                metadata = task.extra_metadata or {}
                metadata.update({
                    "success": True,
                    "duration_seconds": duration,
                    "extracted_text_length": extracted_text_length,
                    "extracted_tables_count": extracted_tables_count,
                    "extracted_images_count": extracted_images_count
                })
                task.extra_metadata = metadata

                session.commit()

    def _update_parse_task_failed(
        self,
        parse_task_id: Union[uuid.UUID, str],
        error_message: str
    ) -> None:
        """更新解析任务为失败状态"""
        with self.pg_client.get_session() as session:
            task = session.query(ParseTask).filter(
                ParseTask.id == parse_task_id
            ).first()
            if task:
                task.status = "failed"
                task.completed_at = datetime.now()
                task.error_message = error_message

                # 将额外信息存储到 extra_metadata
                metadata = task.extra_metadata or {}
                metadata.update({
                    "success": False
                })
                task.extra_metadata = metadata

                session.commit()

    def _update_document_parsed(self, document_id: Union[uuid.UUID, str]) -> None:
        """更新文档状态为已解析"""
        with self.pg_client.get_session() as session:
            doc = crud.get_document_by_id(session, document_id)
            if doc:
                doc.status = DocumentStatus.PARSED.value
                doc.parsed_at = datetime.now()
                session.commit()

    def _get_mineru_version(self) -> str:
        """获取 MinerU 版本"""
        return f"api-{self.api_base}"


# 便捷函数：获取默认的解析器实例
def get_mineru_parser() -> MinerUParser:
    """
    获取默认的 MinerU 解析器实例

    Returns:
        MinerU 解析器实例
    """
    return MinerUParser()
