# -*- coding: utf-8 -*-
"""
OpenAI 兼容的 API Routes
用于 LibreChat 集成
"""

import json
import uuid
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from src.api.schemas.openai import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChunk,
    ChatCompletionMessage,
    ChatCompletionChoice,
    ChatCompletionChunkChoice,
    ChatCompletionDelta,
    Usage,
    ErrorResponse,
    ModelsListResponse,
    ModelInfo
)
from src.application.rag.rag_pipeline import RAGPipeline
from src.common.logger import get_logger
from src.common.config import api_config

router = APIRouter(prefix="/v1", tags=["OpenAI"])
logger = get_logger(__name__)


def verify_api_key(authorization: Optional[str]) -> bool:
    """
    验证 API Key
    
    Args:
        authorization: Authorization 头的值（格式: "Bearer <api_key>"）
        
    Returns:
        验证是否通过
    """
    # 如果未配置 API Key，则不验证（允许所有请求）
    if not api_config.LIBRECHAT_API_KEY:
        return True
    
    # 如果配置了 API Key，则验证
    if not authorization:
        return False
    
    # 提取 Bearer token
    try:
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            return False
        return token == api_config.LIBRECHAT_API_KEY
    except ValueError:
        return False

# 全局 RAG Pipeline 实例
_pipeline: Optional[RAGPipeline] = None


def get_pipeline() -> RAGPipeline:
    """获取 RAG Pipeline 实例（单例）"""
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline


def extract_user_message(messages: list) -> str:
    """
    从消息列表中提取最后一条用户消息
    
    Args:
        messages: 消息列表
        
    Returns:
        用户消息内容
    """
    # 从后往前查找最后一条用户消息
    for msg in reversed(messages):
        if isinstance(msg, dict):
            role = msg.get("role", "")
            content = msg.get("content", "")
        else:
            role = getattr(msg, "role", "")
            content = getattr(msg, "content", "")
        
        if role == "user" and content:
            return content
    
    # 如果没有找到用户消息，返回第一条消息的内容
    if messages:
        first_msg = messages[0]
        if isinstance(first_msg, dict):
            return first_msg.get("content", "")
        else:
            return getattr(first_msg, "content", "")
    
    raise ValueError("消息列表为空，无法提取用户消息")


def estimate_tokens(text: str) -> int:
    """
    估算文本的 token 数量（简单估算：中文按字符，英文按单词）
    
    Args:
        text: 文本内容
        
    Returns:
        估算的 token 数量
    """
    # 简单估算：中文字符按1个token，英文单词按1.3个token
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    english_words = len([w for w in text.split() if w.isascii()])
    return int(chinese_chars + english_words * 1.3)


@router.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest, http_request: Request):
    """
    OpenAI 兼容的 Chat Completions 接口
    
    Args:
        request: Chat Completion 请求
        http_request: HTTP 请求对象（用于获取流式响应）
        
    Returns:
        Chat Completion 响应（流式或非流式）
    """
    try:
        # 验证 API Key（如果已配置）
        authorization = http_request.headers.get("Authorization")
        if not verify_api_key(authorization):
            logger.warning(f"API Key 验证失败: Authorization={authorization[:20] if authorization else 'None'}...")
            error_response = ErrorResponse(
                error={
                    "message": "Invalid API key",
                    "type": "invalid_request_error",
                    "code": "invalid_api_key"
                }
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_response.dict(),
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        logger.info(f"收到 Chat Completion 请求: model={request.model}, stream={request.stream}, messages={len(request.messages)}")
        
        # 提取用户消息
        try:
            user_message = extract_user_message(request.messages)
        except ValueError as e:
            logger.error(f"提取用户消息失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        
        # 获取 Pipeline
        pipeline = get_pipeline()
        
        # 准备参数
        temperature = request.temperature or 0.7
        max_tokens = request.max_tokens or 1000
        
        # 流式响应
        if request.stream:
            return StreamingResponse(
                _generate_stream_response(
                    pipeline=pipeline,
                    question=user_message,
                    model=request.model,
                    temperature=temperature,
                    max_tokens=max_tokens
                ),
                media_type="text/event-stream"
            )
        
        # 非流式响应
        rag_response = pipeline.query(
            question=user_message,
            filters=None,  # LibreChat 请求中不包含过滤条件
            top_k=5,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # 估算 token 使用量
        prompt_tokens = estimate_tokens(user_message)
        completion_tokens = estimate_tokens(rag_response.answer)
        
        # 构建响应
        response = ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant",
                        content=rag_response.answer
                    ),
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens
            )
        )
        
        logger.info(f"Chat Completion 完成: 答案长度={len(rag_response.answer)}, tokens={response.usage.total_tokens}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat Completion 失败: {e}", exc_info=True)
        error_response = ErrorResponse(
            error={
                "message": f"Internal server error: {str(e)}",
                "type": "server_error",
                "code": "internal_error"
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.dict()
        )


async def _generate_stream_response(
    pipeline: RAGPipeline,
    question: str,
    model: str,
    temperature: float,
    max_tokens: int
):
    """
    生成流式响应（Server-Sent Events 格式）
    
    Args:
        pipeline: RAG Pipeline 实例
        question: 用户问题
        model: 模型名称
        temperature: 温度参数
        max_tokens: 最大生成长度
        
    Yields:
        SSE 格式的数据块
    """
    response_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())
    
    try:
        sources = None
        metadata = None
        full_content = ""
        
        # 流式查询
        for chunk, srcs, meta in pipeline.query_stream(
            question=question,
            filters=None,
            top_k=5,
            temperature=temperature,
            max_tokens=max_tokens
        ):
            if chunk:
                full_content += chunk
                # 发送内容增量
                chunk_response = ChatCompletionChunk(
                    id=response_id,
                    created=created,
                    model=model,
                    choices=[
                        ChatCompletionChunkChoice(
                            index=0,
                            delta=ChatCompletionDelta(
                                role="assistant",
                                content=chunk
                            ),
                            finish_reason=None
                        )
                    ]
                )
                yield f"data: {chunk_response.json()}\n\n"
            
            # 保存来源和元数据（在最后一个块时）
            if srcs is not None:
                sources = srcs
            if meta is not None:
                metadata = meta
        
        # 发送结束标记
        final_chunk = ChatCompletionChunk(
            id=response_id,
            created=created,
            model=model,
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionDelta(),
                    finish_reason="stop"
                )
            ]
        )
        yield f"data: {final_chunk.json()}\n\n"
        yield "data: [DONE]\n\n"
        
        logger.info(f"流式响应完成: 内容长度={len(full_content)}")
        
    except Exception as e:
        logger.error(f"流式响应生成失败: {e}", exc_info=True)
        # 发送错误块
        error_chunk = ChatCompletionChunk(
            id=response_id,
            created=created,
            model=model,
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionDelta(
                        content=f"\n\n[错误: {str(e)}]"
                    ),
                    finish_reason="stop"
                )
            ]
        )
        yield f"data: {error_chunk.json()}\n\n"
        yield "data: [DONE]\n\n"


@router.get("/models")
async def list_models(http_request: Request):
    """
    OpenAI 兼容的模型列表接口
    
    注意：此端点不需要 API Key 验证，因为模型列表通常是公开信息，
    允许 LibreChat 在配置阶段验证可用模型。
    
    Returns:
        模型列表响应
    """
    # 模型列表端点不需要 API Key 验证（公开信息）
    # 返回模型列表
    model_name = api_config.LIBRECHAT_MODEL_NAME
    response = ModelsListResponse(
        data=[
            ModelInfo(
                id=model_name,
                created=int(time.time()),
                owned_by="finnet"
            )
        ]
    )
    
    logger.info(f"返回模型列表: {model_name} (无需验证)")
    return response


