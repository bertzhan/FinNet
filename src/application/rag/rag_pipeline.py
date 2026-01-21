# -*- coding: utf-8 -*-
"""
RAG Pipeline
整合检索、上下文构建、LLM 生成
"""

from typing import Dict, Any, Optional, List, Iterator, Tuple
from dataclasses import dataclass
import time

from src.application.rag.retriever import Retriever, RetrievalResult
from src.application.rag.context_builder import ContextBuilder
from src.processing.ai.llm.llm_service import get_llm_service, LLMService
from src.common.logger import get_logger, LoggerMixin


@dataclass
class Source:
    """引用来源"""
    chunk_id: str
    document_id: str
    title: Optional[str]
    stock_code: str
    company_name: str
    doc_type: str
    year: int
    quarter: Optional[int]
    score: float
    snippet: str  # 相关文本片段


@dataclass
class RAGResponse:
    """RAG 响应"""
    answer: str  # 生成的答案
    sources: List[Source]  # 引用来源
    metadata: Dict[str, Any]  # 元数据（检索数量、生成时间等）


class RAGPipeline(LoggerMixin):
    """
    RAG Pipeline
    整合检索、上下文构建、LLM 生成，执行端到端 RAG 查询
    """

    # 系统提示词模板
    SYSTEM_PROMPT_TEMPLATE = """你是一个专业的金融数据分析助手，擅长分析上市公司财报和公告。

请基于以下文档内容回答用户问题：

{context}

用户问题：{question}

要求：
1. 答案要准确、专业
2. 如果文档中没有相关信息，请明确说明
3. 引用具体的文档来源（如：根据文档1中的信息...）
4. 使用中文回答
5. 如果涉及数字，请准确引用"""

    def __init__(
        self,
        retriever: Optional[Retriever] = None,
        context_builder: Optional[ContextBuilder] = None,
        llm_service: Optional[LLMService] = None,
        max_context_length: int = 4000
    ):
        """
        初始化 RAG Pipeline

        Args:
            retriever: 检索器（默认自动创建）
            context_builder: 上下文构建器（默认自动创建）
            llm_service: LLM 服务（默认自动创建）
            max_context_length: 最大上下文长度（字符数）
        """
        self.retriever = retriever or Retriever()
        self.context_builder = context_builder or ContextBuilder(max_length=max_context_length)
        self.llm_service = llm_service or get_llm_service()
        self.max_context_length = max_context_length

    def query(
        self,
        question: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> RAGResponse:
        """
        执行 RAG 查询

        Args:
            question: 用户问题
            filters: 过滤条件（stock_code, year, quarter, doc_type等）
            top_k: 检索数量（默认 5）
            temperature: LLM 温度参数（默认 0.7）
            max_tokens: 最大生成长度（默认 1000）

        Returns:
            RAG 响应

        Example:
            >>> pipeline = RAGPipeline()
            >>> response = pipeline.query(
            ...     "平安银行2023年第三季度的营业收入是多少？",
            ...     filters={"stock_code": "000001", "year": 2023, "quarter": 3},
            ...     top_k=5
            ... )
            >>> print(response.answer)
            >>> for source in response.sources:
            ...     print(f"来源: {source.company_name} - {source.title}")
        """
        start_time = time.time()

        try:
            # 1. 检索相关文档分块
            self.logger.info(f"开始 RAG 查询: question='{question[:50]}...'")
            retrieval_results = self.retriever.retrieve(
                query=question,
                top_k=top_k,
                filters=filters
            )

            if not retrieval_results:
                self.logger.warning("检索结果为空，返回空答案")
                return RAGResponse(
                    answer="抱歉，没有找到相关的文档信息。",
                    sources=[],
                    metadata={
                        "retrieval_count": 0,
                        "generation_time": time.time() - start_time,
                        "model": self.llm_service.model
                    }
                )

            # 2. 构建上下文
            context = self.context_builder.build_context(
                retrieval_results,
                max_length=self.max_context_length
            )

            if not context:
                self.logger.warning("上下文为空，返回空答案")
                return RAGResponse(
                    answer="抱歉，无法构建有效的上下文信息。",
                    sources=[],
                    metadata={
                        "retrieval_count": len(retrieval_results),
                        "generation_time": time.time() - start_time,
                        "model": self.llm_service.model
                    }
                )

            # 3. 构建 Prompt
            system_prompt = self.SYSTEM_PROMPT_TEMPLATE.format(
                context=context,
                question=question
            )

            # 4. LLM 生成答案
            self.logger.debug("调用 LLM 生成答案...")
            answer = self.llm_service.generate(
                prompt=question,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )

            # 5. 构建来源列表
            sources = self._build_sources(retrieval_results)

            generation_time = time.time() - start_time
            self.logger.info(
                f"RAG 查询完成: 检索数量={len(retrieval_results)}, "
                f"生成时间={generation_time:.2f}s"
            )

            return RAGResponse(
                answer=answer,
                sources=sources,
                metadata={
                    "retrieval_count": len(retrieval_results),
                    "generation_time": generation_time,
                    "model": self.llm_service.model,
                    "provider": self.llm_service.provider
                }
            )

        except Exception as e:
            self.logger.error(f"RAG 查询失败: {e}", exc_info=True)
            return RAGResponse(
                answer=f"查询过程中发生错误: {str(e)}",
                sources=[],
                metadata={
                    "error": str(e),
                    "generation_time": time.time() - start_time
                }
            )

    def _build_sources(self, retrieval_results: List[RetrievalResult]) -> List[Source]:
        """
        构建来源列表

        Args:
            retrieval_results: 检索结果列表

        Returns:
            来源列表
        """
        sources = []
        for result in retrieval_results:
            metadata = result.metadata
            snippet = result.chunk_text[:200] + "..." if len(result.chunk_text) > 200 else result.chunk_text

            source = Source(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                title=result.title,
                stock_code=metadata.get("stock_code", "N/A"),
                company_name=metadata.get("company_name", "N/A"),
                doc_type=metadata.get("doc_type", "N/A"),
                year=metadata.get("year", 0),
                quarter=metadata.get("quarter"),
                score=result.score,
                snippet=snippet
            )
            sources.append(source)

        return sources

    def query_stream(
        self,
        question: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Iterator[Tuple[str, Optional[List[Source]], Optional[Dict[str, Any]]]]:
        """
        流式执行 RAG 查询

        Args:
            question: 用户问题
            filters: 过滤条件（stock_code, year, quarter, doc_type等）
            top_k: 检索数量（默认 5）
            temperature: LLM 温度参数（默认 0.7）
            max_tokens: 最大生成长度（默认 1000）

        Yields:
            Tuple[str, Optional[List[Source]], Optional[Dict[str, Any]]]:
            - 第一个元素：答案文本块（字符串）
            - 第二个元素：来源列表（在最后一个块时返回，其他时候为 None）
            - 第三个元素：元数据（在最后一个块时返回，其他时候为 None）

        Example:
            >>> pipeline = RAGPipeline()
            >>> sources = None
            >>> metadata = None
            >>> for chunk, srcs, meta in pipeline.query_stream("平安银行2023年第三季度的营业收入是多少？"):
            ...     if chunk:
            ...         print(chunk, end="", flush=True)
            ...     if srcs is not None:
            ...         sources = srcs
            ...     if meta is not None:
            ...         metadata = meta
        """
        start_time = time.time()
        retrieval_results = None
        sources = None

        try:
            # 1. 检索相关文档分块（非流式）
            self.logger.info(f"开始 RAG 流式查询: question='{question[:50]}...'")
            retrieval_results = self.retriever.retrieve(
                query=question,
                top_k=top_k,
                filters=filters
            )

            if not retrieval_results:
                self.logger.warning("检索结果为空，返回空答案")
                yield ("抱歉，没有找到相关的文档信息。", [], {
                    "retrieval_count": 0,
                    "generation_time": time.time() - start_time,
                    "model": self.llm_service.model
                })
                return

            # 2. 构建上下文（非流式）
            context = self.context_builder.build_context(
                retrieval_results,
                max_length=self.max_context_length
            )

            if not context:
                self.logger.warning("上下文为空，返回空答案")
                yield ("抱歉，无法构建有效的上下文信息。", [], {
                    "retrieval_count": len(retrieval_results),
                    "generation_time": time.time() - start_time,
                    "model": self.llm_service.model
                })
                return

            # 3. 构建 Prompt
            system_prompt = self.SYSTEM_PROMPT_TEMPLATE.format(
                context=context,
                question=question
            )

            # 4. 流式调用 LLM 生成答案
            self.logger.debug("调用 LLM 流式生成答案...")
            answer_chunks = []
            for chunk in self.llm_service.generate_stream(
                prompt=question,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            ):
                answer_chunks.append(chunk)
                # 流式返回文本块（不包含来源和元数据）
                yield (chunk, None, None)

            # 5. 构建来源列表
            sources = self._build_sources(retrieval_results)

            generation_time = time.time() - start_time
            full_answer = "".join(answer_chunks)
            
            self.logger.info(
                f"RAG 流式查询完成: 检索数量={len(retrieval_results)}, "
                f"生成时间={generation_time:.2f}s"
            )

            # 最后一个块：返回空字符串（表示结束），但包含来源和元数据
            yield ("", sources, {
                "retrieval_count": len(retrieval_results),
                "generation_time": generation_time,
                "model": self.llm_service.model,
                "provider": self.llm_service.provider
            })

        except Exception as e:
            self.logger.error(f"RAG 流式查询失败: {e}", exc_info=True)
            yield (f"查询过程中发生错误: {str(e)}", [], {
                "error": str(e),
                "generation_time": time.time() - start_time
            })
