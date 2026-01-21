# -*- coding: utf-8 -*-
"""
RAG 上下文构建器
将检索结果构建为 LLM 可用的上下文
"""

from typing import List, Optional
from src.application.rag.retriever import RetrievalResult
from src.common.logger import get_logger, LoggerMixin


class ContextBuilder(LoggerMixin):
    """
    RAG 上下文构建器
    将检索结果合并为格式化的上下文，控制 Token 长度
    """

    def __init__(self, max_length: int = 4000):
        """
        初始化上下文构建器

        Args:
            max_length: 最大上下文长度（字符数，默认 4000）
                       注意：这是字符数，不是 Token 数
                       可以根据实际需求调整
        """
        self.max_length = max_length

    def build_context(
        self,
        retrieval_results: List[RetrievalResult],
        max_length: Optional[int] = None
    ) -> str:
        """
        构建上下文

        Args:
            retrieval_results: 检索结果列表
            max_length: 最大长度（覆盖初始化时的设置）

        Returns:
            格式化后的上下文文本

        Example:
            >>> builder = ContextBuilder(max_length=4000)
            >>> context = builder.build_context(results)
        """
        max_len = max_length or self.max_length

        if not retrieval_results:
            self.logger.warning("检索结果为空，返回空上下文")
            return ""

        # 格式化每个分块
        formatted_chunks = []
        current_length = 0

        for i, result in enumerate(retrieval_results):
            formatted_chunk = self._format_chunk(result, index=i + 1)
            chunk_length = len(formatted_chunk)

            # 检查是否超过长度限制
            if current_length + chunk_length > max_len:
                self.logger.debug(
                    f"达到长度限制: 当前长度={current_length}, "
                    f"分块长度={chunk_length}, 限制={max_len}, "
                    f"已包含 {len(formatted_chunks)} 个分块"
                )
                break

            formatted_chunks.append(formatted_chunk)
            current_length += chunk_length

        if not formatted_chunks:
            self.logger.warning("没有可用的分块（可能都超过长度限制）")
            return ""

        context = "\n\n".join(formatted_chunks)
        self.logger.debug(f"构建上下文完成: 长度={len(context)}, 分块数={len(formatted_chunks)}")
        return context

    def _format_chunk(self, result: RetrievalResult, index: int) -> str:
        """
        格式化单个分块

        Args:
            result: 检索结果
            index: 分块序号

        Returns:
            格式化后的文本
        """
        metadata = result.metadata
        stock_code = metadata.get("stock_code", "N/A")
        company_name = metadata.get("company_name", "N/A")
        doc_type = metadata.get("doc_type", "N/A")
        year = metadata.get("year", "N/A")
        quarter = metadata.get("quarter")

        # 构建文档标题
        doc_title_parts = [company_name]
        if year != "N/A":
            if quarter:
                doc_title_parts.append(f"{year}年第{quarter}季度报告")
            else:
                doc_title_parts.append(f"{year}年报告")
        doc_title = " ".join(doc_title_parts)

        # 构建分块标题
        chunk_title = ""
        if result.title:
            chunk_title = result.title
        elif result.title_level:
            chunk_title = f"标题层级 {result.title_level}"

        # 格式化文本
        lines = [
            f"文档{index}: {doc_title}",
        ]

        if chunk_title:
            lines.append(f"标题: {chunk_title}")

        lines.append("内容:")
        lines.append(result.chunk_text)

        return "\n".join(lines)

    def format_chunks(
        self,
        retrieval_results: List[RetrievalResult]
    ) -> List[str]:
        """
        格式化所有分块（不合并）

        Args:
            retrieval_results: 检索结果列表

        Returns:
            格式化后的分块文本列表
        """
        return [
            self._format_chunk(result, index=i + 1)
            for i, result in enumerate(retrieval_results)
        ]

    def add_metadata(
        self,
        context: str,
        retrieval_results: List[RetrievalResult]
    ) -> str:
        """
        在上下文末尾添加元数据信息

        Args:
            context: 上下文文本
            retrieval_results: 检索结果列表

        Returns:
            添加元数据后的上下文
        """
        if not retrieval_results:
            return context

        metadata_lines = ["\n\n--- 文档来源信息 ---"]
        for i, result in enumerate(retrieval_results, 1):
            metadata = result.metadata
            metadata_lines.append(
                f"文档{i}: {metadata.get('company_name')} "
                f"({metadata.get('stock_code')}) - "
                f"{metadata.get('doc_type')} - "
                f"{metadata.get('year')}年"
            )

        return context + "\n".join(metadata_lines)
