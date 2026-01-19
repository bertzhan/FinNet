# -*- coding: utf-8 -*-
"""
文本分块服务
封装 StructureGenerator 和 ChunkGenerator，实现从 Silver 层读取 Markdown 和执行分块的完整流程
"""

import json
import tempfile
import hashlib
import uuid
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime
from pathlib import Path

from src.processing.text.chunk_by_rules import StructureGenerator, ChunkGenerator
from src.storage.object_store.minio_client import MinIOClient
from src.storage.object_store.path_manager import PathManager
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.storage.metadata.models import Document, ParsedDocument, DocumentChunk
from src.common.constants import Market, DocType
from src.common.logger import get_logger, LoggerMixin
from src.common.utils import calculate_file_hash


class TextChunker(LoggerMixin):
    """
    文本分块服务
    实现文档的智能分块功能
    """

    def __init__(
        self,
        minio_client: Optional[MinIOClient] = None,
        path_manager: Optional[PathManager] = None
    ):
        """
        初始化文本分块服务

        Args:
            minio_client: MinIO 客户端（默认创建新实例）
            path_manager: 路径管理器（默认创建新实例）
        """
        self.minio_client = minio_client or MinIOClient()
        self.path_manager = path_manager or PathManager()
        self.pg_client = get_postgres_client()

    def chunk_document(
        self,
        document_id: Union[uuid.UUID, str],
        force_rechunk: bool = False
    ) -> Dict[str, Any]:
        """
        对单个文档进行分块（完整流程）

        流程：
        1. 获取 ParsedDocument 和 Document 信息
        2. 从 Silver 层读取 Markdown 文件
        3. 生成文档结构（structure.json）
        4. 根据结构生成分块（chunks.json）
        5. 保存 structure.json 和 chunks.json 到 Silver 层
        6. 保存分块到数据库
        7. 更新 ParsedDocument 记录

        Args:
            document_id: 文档ID
            force_rechunk: 是否强制重新分块（删除旧分块）

        Returns:
            分块结果字典，包含：
            - success: 是否成功
            - parsed_document_id: ParsedDocument ID
            - structure_path: structure.json 路径
            - chunks_path: chunks.json 路径
            - chunks_count: 分块数量
            - error_message: 错误信息（失败时）
        """
        start_time = datetime.now()

        try:
            with self.pg_client.get_session() as session:
                # 1. 获取 Document 信息
                doc = crud.get_document_by_id(session, document_id)
                if not doc:
                    return {
                        "success": False,
                        "error_message": f"文档不存在: document_id={document_id}"
                    }

                # 2. 获取 ParsedDocument 信息
                parsed_doc = crud.get_latest_parsed_document(session, document_id)

                if not parsed_doc:
                    return {
                        "success": False,
                        "error_message": f"ParsedDocument 不存在: document_id={document_id}"
                    }

                if not parsed_doc.markdown_path:
                    return {
                        "success": False,
                        "error_message": f"Markdown 文件路径不存在: document_id={document_id}"
                    }

                # 检查是否已分块
                if parsed_doc.chunks_count > 0 and not force_rechunk:
                    self.logger.info(f"文档已分块: document_id={document_id}, chunks_count={parsed_doc.chunks_count}")
                    return {
                        "success": True,
                        "parsed_document_id": parsed_doc.id,
                        "structure_path": parsed_doc.structure_json_path,
                        "chunks_path": parsed_doc.chunks_json_path,
                        "chunks_count": parsed_doc.chunks_count,
                        "message": "文档已分块，跳过"
                    }

                # 保存需要的属性值（在 session 关闭前）
                markdown_path = parsed_doc.markdown_path
                parsed_doc_id = parsed_doc.id
                market = Market(doc.market)
                doc_type = DocType(doc.doc_type)
                stock_code = doc.stock_code
                year = doc.year
                quarter = doc.quarter

            # 3. 从 Silver 层读取 Markdown
            markdown_content = self._load_markdown_from_silver(markdown_path)
            if not markdown_content:
                return {
                    "success": False,
                    "error_message": f"无法读取 Markdown 文件: {markdown_path}"
                }

            # 4. 生成文档结构
            structure = self._generate_structure(markdown_content)
            if not structure:
                return {
                    "success": False,
                    "error_message": "生成文档结构失败"
                }

            # 5. 生成分块
            chunks = self._generate_chunks(markdown_content, structure)
            if not chunks:
                return {
                    "success": False,
                    "error_message": "生成分块失败"
                }

            # 6. 保存 structure.json 到 Silver 层（与 markdown 文件相同目录）
            structure_path, structure_hash = self._save_structure_to_silver(
                structure=structure,
                document_id=document_id,
                markdown_path=markdown_path,
                stock_code=stock_code
            )

            # 7. 保存 chunks.json 到 Silver 层（与 markdown 文件相同目录）
            chunks_path, chunks_hash = self._save_chunks_to_silver(
                chunks=chunks,
                document_id=document_id,
                markdown_path=markdown_path,
                stock_code=stock_code
            )

            # 8. 如果强制重新分块，先删除旧分块
            if force_rechunk:
                with self.pg_client.get_session() as session:
                    crud.delete_document_chunks(session, document_id)

            # 9. 保存分块到数据库
            with self.pg_client.get_session() as session:
                self._save_chunks_to_db(session, chunks, document_id)

            # 10. 更新 ParsedDocument 记录
            with self.pg_client.get_session() as session:
                crud.update_parsed_document_chunk_info(
                    session=session,
                    parsed_document_id=parsed_doc_id,
                    structure_json_path=structure_path,
                    chunks_json_path=chunks_path,
                    structure_json_hash=structure_hash,
                    chunks_json_hash=chunks_hash,
                    chunks_count=len(chunks)
                )

            duration = (datetime.now() - start_time).total_seconds()
            self.logger.info(
                f"✅ 文档分块完成: document_id={document_id}, "
                f"chunks_count={len(chunks)}, duration={duration:.2f}s"
            )

            return {
                "success": True,
                "parsed_document_id": parsed_doc_id,
                "structure_path": structure_path,
                "chunks_path": chunks_path,
                "chunks_count": len(chunks),
                "duration": duration
            }

        except Exception as e:
            self.logger.error(f"文档分块失败: document_id={document_id}, error={e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }

    def _load_markdown_from_silver(self, markdown_path: str) -> Optional[str]:
        """
        从 Silver 层加载 Markdown 文件

        Args:
            markdown_path: Markdown 文件路径

        Returns:
            Markdown 内容，失败返回 None
        """
        tmp_path = None
        try:
            # 首先检查文件是否存在
            if not self.minio_client.file_exists(markdown_path):
                self.logger.error(f"Markdown 文件不存在于 MinIO: {markdown_path}")
                return None

            # 下载到临时文件
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.md', delete=False, encoding='utf-8') as tmp_file:
                tmp_path = tmp_file.name

            # download_file 在提供 file_path 时，成功返回 None，失败也返回 None
            # 所以需要通过检查文件是否存在来判断是否成功
            result = self.minio_client.download_file(
                object_name=markdown_path,
                file_path=tmp_path
            )

            # 检查文件是否成功下载（文件应该存在且大小 > 0）
            if not Path(tmp_path).exists() or Path(tmp_path).stat().st_size == 0:
                self.logger.error(f"下载 Markdown 文件失败: {markdown_path} (文件不存在或为空)")
                if Path(tmp_path).exists():
                    Path(tmp_path).unlink()
                return None

            # 读取内容
            with open(tmp_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 清理临时文件
            Path(tmp_path).unlink()
            tmp_path = None

            self.logger.debug(f"✅ 成功读取 Markdown 文件: {markdown_path} ({len(content)} 字符)")
            return content

        except FileNotFoundError as e:
            self.logger.error(f"Markdown 文件不存在: {markdown_path}, error={e}")
            if tmp_path and Path(tmp_path).exists():
                Path(tmp_path).unlink()
            return None
        except Exception as e:
            self.logger.error(f"读取 Markdown 文件失败: {markdown_path}, error={e}", exc_info=True)
            if tmp_path and Path(tmp_path).exists():
                Path(tmp_path).unlink()
            return None

    def _generate_structure(self, markdown_content: str) -> Optional[List[Dict[str, Any]]]:
        """
        生成文档结构

        Args:
            markdown_content: Markdown 内容

        Returns:
            文档结构（树形结构），失败返回 None
        """
        try:
            # 保存到临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tmp_file:
                tmp_path = tmp_file.name
                tmp_file.write(markdown_content)

            # 使用 StructureGenerator 生成结构
            structure_generator = StructureGenerator(document_path=tmp_path)
            structure = structure_generator.run()

            # 清理临时文件
            Path(tmp_path).unlink()

            return structure

        except Exception as e:
            self.logger.error(f"生成文档结构失败: {e}", exc_info=True)
            return None

    def _generate_chunks(
        self,
        markdown_content: str,
        structure: List[Dict[str, Any]]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        根据结构生成分块

        Args:
            markdown_content: Markdown 内容
            structure: 文档结构

        Returns:
            分块列表，失败返回 None
        """
        try:
            # 保存到临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tmp_md:
                tmp_md_path = tmp_md.name
                tmp_md.write(markdown_content)

            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as tmp_json:
                tmp_structure_path = tmp_json.name
                json.dump(structure, tmp_json, ensure_ascii=False, indent=2)

            # 使用 ChunkGenerator 生成分块
            chunk_generator = ChunkGenerator(
                document_path=tmp_md_path,
                structure_path=tmp_structure_path
            )
            chunks = chunk_generator.run()

            # 清理临时文件
            Path(tmp_md_path).unlink()
            Path(tmp_structure_path).unlink()

            return chunks

        except Exception as e:
            self.logger.error(f"生成分块失败: {e}", exc_info=True)
            return None

    def _generate_structure_txt(self, structure: List[Dict[str, Any]]) -> str:
        """
        生成目录结构树的文本格式

        Args:
            structure: 文档结构（树形结构）

        Returns:
            文本格式的目录结构树
        """
        lines = []
        
        def print_tree_node(node: Dict[str, Any], indent: int = 0) -> None:
            """递归打印树节点"""
            prefix = '  ' * indent
            level_marker = f"[L{node['level']}] " if node.get('level') else ""
            lines.append(f"{prefix}{level_marker}{node['title']}")
            
            for child in node.get('children', []):
                print_tree_node(child, indent + 1)
        
        for root_node in structure:
            print_tree_node(root_node)
        
        return '\n'.join(lines)

    def _save_structure_to_silver(
        self,
        structure: List[Dict[str, Any]],
        document_id: Union[uuid.UUID, str],
        markdown_path: str,
        stock_code: str
    ) -> Tuple[str, str]:
        """
        保存 structure.json 和 structure.txt 到 Silver 层（与 markdown 文件相同目录）

        Args:
            structure: 文档结构
            document_id: 文档ID
            markdown_path: Markdown 文件路径（用于提取目录）
            stock_code: 股票代码（用于元数据）

        Returns:
            (文件路径, 文件哈希)
        """
        # 从 markdown_path 提取目录，生成 structure.json 路径
        # 例如: silver/a_share/mineru/annual_reports/2023/Q4/300542/document.md
        # -> silver/a_share/mineru/annual_reports/2023/Q4/300542/structure.json
        markdown_dir = "/".join(markdown_path.split("/")[:-1])  # 去掉文件名，保留目录
        structure_path = f"{markdown_dir}/structure.json"
        structure_txt_path = f"{markdown_dir}/structure.txt"

        # 准备 JSON 数据
        structure_data = {
            "document_id": str(document_id),
            "stock_code": stock_code,
            "generated_at": datetime.now().isoformat(),
            "structure": structure,
            "total_headings": self._count_headings(structure),
            "metadata": {}
        }

        # 序列化为 JSON
        json_str = json.dumps(structure_data, ensure_ascii=False, indent=2)
        json_bytes = json_str.encode('utf-8')

        # 计算哈希
        structure_hash = hashlib.sha256(json_bytes).hexdigest()

        # 上传 structure.json 到 MinIO
        success = self.minio_client.upload_file(
            object_name=structure_path,
            data=json_bytes,
            content_type="application/json",
            metadata={
                "document_id": str(document_id),
                "stock_code": stock_code,
                "file_type": "structure_json",
                "uploaded_at": datetime.now().isoformat()
            }
        )

        if not success:
            raise Exception(f"上传 structure.json 失败: {structure_path}")

        self.logger.debug(f"✅ structure.json 已保存: {structure_path}")

        # 生成并上传 structure.txt
        structure_txt_content = self._generate_structure_txt(structure)
        structure_txt_bytes = structure_txt_content.encode('utf-8')

        success_txt = self.minio_client.upload_file(
            object_name=structure_txt_path,
            data=structure_txt_bytes,
            content_type="text/plain",
            metadata={
                "document_id": str(document_id),
                "stock_code": stock_code,
                "file_type": "structure_txt",
                "uploaded_at": datetime.now().isoformat()
            }
        )

        if not success_txt:
            raise Exception(f"上传 structure.txt 失败: {structure_txt_path}")

        self.logger.debug(f"✅ structure.txt 已保存: {structure_txt_path}")

        return structure_path, structure_hash

    def _save_chunks_to_silver(
        self,
        chunks: List[Dict[str, Any]],
        document_id: Union[uuid.UUID, str],
        markdown_path: str,
        stock_code: str
    ) -> Tuple[str, str]:
        """
        保存 chunks.json 到 Silver 层（与 markdown 文件相同目录）

        Args:
            chunks: 分块列表
            document_id: 文档ID
            markdown_path: Markdown 文件路径（用于提取目录）
            stock_code: 股票代码（用于元数据）

        Returns:
            (文件路径, 文件哈希)
        """
        # 从 markdown_path 提取目录，生成 chunks.json 路径
        # 例如: silver/a_share/mineru/annual_reports/2023/Q4/300542/document.md
        # -> silver/a_share/mineru/annual_reports/2023/Q4/300542/chunks.json
        markdown_dir = "/".join(markdown_path.split("/")[:-1])  # 去掉文件名，保留目录
        chunks_path = f"{markdown_dir}/chunks.json"

        # 为每个 chunk 添加 content_length 字段
        chunks_with_length = []
        for chunk in chunks:
            chunk_copy = chunk.copy()
            chunk_copy['content_length'] = len(chunk.get('content', ''))
            chunks_with_length.append(chunk_copy)

        # 准备 JSON 数据
        chunks_data = {
            "document_id": str(document_id),
            "stock_code": stock_code,
            "chunked_at": datetime.now().isoformat(),
            "chunks": chunks_with_length,  # 使用包含 content_length 的 chunks
            "total_chunks": len(chunks),
            "metadata": {}
        }

        # 序列化为 JSON
        json_str = json.dumps(chunks_data, ensure_ascii=False, indent=2)
        json_bytes = json_str.encode('utf-8')

        # 计算哈希
        chunks_hash = hashlib.sha256(json_bytes).hexdigest()

        # 上传到 MinIO
        success = self.minio_client.upload_file(
            object_name=chunks_path,
            data=json_bytes,
            content_type="application/json",
            metadata={
                "document_id": str(document_id),
                "stock_code": stock_code,
                "file_type": "chunks_json",
                "uploaded_at": datetime.now().isoformat()
            }
        )

        if not success:
            raise Exception(f"上传 chunks.json 失败: {chunks_path}")

        self.logger.debug(f"✅ chunks.json 已保存: {chunks_path}")
        return chunks_path, chunks_hash

    def _save_chunks_to_db(
        self,
        session,
        chunks: List[Dict[str, Any]],
        document_id: Union[uuid.UUID, str]
    ) -> None:
        """
        保存分块到数据库

        Args:
            session: 数据库会话
            chunks: 分块列表
            document_id: 文档ID
        """
        chunks_data = []
        parent_chunk_map = {}  # 用于映射 chunk_id 到实际的数据库 ID

        for chunk in chunks:
            chunk_data = {
                "document_id": document_id,
                "chunk_index": chunk.get("chunk_index", chunk.get("chunk_id", 0)) - 1,  # 转换为 0-based
                "chunk_text": chunk.get("content", ""),
                "chunk_size": len(chunk.get("content", "")),
                "title": chunk.get("title"),
                "title_level": chunk.get("title_level"),
                "heading_index": chunk.get("heading_index"),
                "start_line": chunk.get("start_line"),
                "end_line": chunk.get("end_line"),
                "is_table": chunk.get("is_table", False),
                "metadata": {
                    "parent_id": chunk.get("parent_id")
                }
            }
            chunks_data.append(chunk_data)

        # 批量创建分块
        created_chunks = crud.create_document_chunks_batch(session, chunks_data)

        # 更新父分块关系
        for i, chunk in enumerate(chunks):
            parent_id = chunk.get("parent_id")
            if parent_id and i < len(created_chunks):
                # 查找父分块
                parent_index = parent_id - 1  # 转换为 0-based
                if 0 <= parent_index < len(created_chunks):
                    created_chunks[i].parent_chunk_id = created_chunks[parent_index].id
                    session.flush()

        self.logger.info(f"✅ 已保存 {len(created_chunks)} 个分块到数据库")

    def _count_headings(self, structure: List[Dict[str, Any]]) -> int:
        """
        递归计算标题数量

        Args:
            structure: 文档结构

        Returns:
            标题总数
        """
        count = 0
        for node in structure:
            count += 1
            if "children" in node and node["children"]:
                count += self._count_headings(node["children"])
        return count


def get_text_chunker(
    minio_client: Optional[MinIOClient] = None,
    path_manager: Optional[PathManager] = None
) -> TextChunker:
    """
    获取文本分块服务实例（便捷函数）

    Args:
        minio_client: MinIO 客户端（可选）
        path_manager: 路径管理器（可选）

    Returns:
        TextChunker 实例
    """
    return TextChunker(minio_client=minio_client, path_manager=path_manager)
