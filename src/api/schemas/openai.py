# -*- coding: utf-8 -*-
"""
OpenAI 兼容的 API Schemas
用于 LibreChat 集成
"""

from typing import Optional, List, Literal, Union
from pydantic import BaseModel, Field
import time
import uuid


class ChatMessage(BaseModel):
    """聊天消息"""
    role: Literal["system", "user", "assistant"] = Field(..., description="消息角色")
    content: str = Field(..., description="消息内容")

    class Config:
        json_schema_extra = {
            "example": {
                "role": "user",
                "content": "平安银行2023年第三季度的营业收入是多少？"
            }
        }


class ChatCompletionRequest(BaseModel):
    """Chat Completion 请求（OpenAI 兼容格式）"""
    model: str = Field(..., description="模型名称")
    messages: List[ChatMessage] = Field(..., description="消息列表", min_items=1)
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: Optional[int] = Field(1000, ge=1, le=4000, description="最大生成长度")
    stream: Optional[bool] = Field(False, description="是否流式返回")
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="Top-p 采样")
    frequency_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0, description="频率惩罚")
    presence_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0, description="存在惩罚")
    stop: Optional[Union[str, List[str]]] = Field(None, description="停止序列")
    user: Optional[str] = Field(None, description="用户ID")

    class Config:
        json_schema_extra = {
            "example": {
                "model": "finnet-rag",
                "messages": [
                    {"role": "user", "content": "平安银行2023年第三季度的营业收入是多少？"}
                ],
                "temperature": 0.7,
                "max_tokens": 1000,
                "stream": False
            }
        }


class ChatCompletionMessage(BaseModel):
    """Chat Completion 消息响应"""
    role: Literal["assistant"] = Field("assistant", description="角色")
    content: str = Field(..., description="消息内容")


class ChatCompletionChoice(BaseModel):
    """Chat Completion 选择"""
    index: int = Field(..., description="索引")
    message: ChatCompletionMessage = Field(..., description="消息")
    finish_reason: Optional[Literal["stop", "length", "content_filter"]] = Field(
        "stop", description="完成原因"
    )


class Usage(BaseModel):
    """Token 使用统计"""
    prompt_tokens: int = Field(..., description="提示词 tokens")
    completion_tokens: int = Field(..., description="完成 tokens")
    total_tokens: int = Field(..., description="总 tokens")


class ChatCompletionResponse(BaseModel):
    """Chat Completion 响应（非流式）"""
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}", description="响应ID")
    object: Literal["chat.completion"] = Field("chat.completion", description="对象类型")
    created: int = Field(default_factory=lambda: int(time.time()), description="创建时间戳")
    model: str = Field(..., description="模型名称")
    choices: List[ChatCompletionChoice] = Field(..., description="选择列表")
    usage: Optional[Usage] = Field(None, description="Token 使用统计")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "chatcmpl-abc123",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "finnet-rag",
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "根据2023年第三季度报告..."
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 200,
                    "total_tokens": 300
                }
            }
        }


class ChatCompletionDelta(BaseModel):
    """流式响应中的增量消息"""
    role: Optional[Literal["assistant"]] = Field(None, description="角色")
    content: Optional[str] = Field(None, description="内容增量")


class ChatCompletionChunkChoice(BaseModel):
    """流式响应中的选择"""
    index: int = Field(..., description="索引")
    delta: ChatCompletionDelta = Field(..., description="增量消息")
    finish_reason: Optional[Literal["stop", "length", "content_filter"]] = Field(
        None, description="完成原因"
    )


class ChatCompletionChunk(BaseModel):
    """Chat Completion 流式响应块"""
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}", description="响应ID")
    object: Literal["chat.completion.chunk"] = Field("chat.completion.chunk", description="对象类型")
    created: int = Field(default_factory=lambda: int(time.time()), description="创建时间戳")
    model: str = Field(..., description="模型名称")
    choices: List[ChatCompletionChunkChoice] = Field(..., description="选择列表")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "chatcmpl-abc123",
                "object": "chat.completion.chunk",
                "created": 1234567890,
                "model": "finnet-rag",
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": "根据"
                    },
                    "finish_reason": None
                }]
            }
        }


class ErrorResponse(BaseModel):
    """错误响应（OpenAI 格式）"""
    error: dict = Field(..., description="错误信息")

    class Config:
        json_schema_extra = {
            "example": {
                "error": {
                    "message": "Invalid request",
                    "type": "invalid_request_error",
                    "code": "invalid_request"
                }
            }
        }


class ModelInfo(BaseModel):
    """模型信息"""
    id: str = Field(..., description="模型ID")
    object: Literal["model"] = Field("model", description="对象类型")
    created: int = Field(default_factory=lambda: int(time.time()), description="创建时间戳")
    owned_by: str = Field("finnet", description="拥有者")


class ModelsListResponse(BaseModel):
    """模型列表响应"""
    object: Literal["list"] = Field("list", description="对象类型")
    data: List[ModelInfo] = Field(..., description="模型列表")

    class Config:
        json_schema_extra = {
            "example": {
                "object": "list",
                "data": [
                    {
                        "id": "finnet-rag",
                        "object": "model",
                        "created": 1677610602,
                        "owned_by": "finnet"
                    }
                ]
            }
        }
