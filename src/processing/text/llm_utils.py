#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 调用工具，用于 title_level_detector 等模块
支持 OpenRouter (https://openrouter.ai/api/v1) 及 OpenAI 兼容 API
"""

import json
import logging
import os
import re
import time
from typing import Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import openai
except ImportError:
    openai = None

try:
    import tiktoken
except ImportError:
    tiktoken = None

# OpenRouter 配置（.env 中设置 OPENROUTER_API_KEY、OPENROUTER_MODEL）
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("CLOUD_LLM_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL") or os.getenv("CLOUD_LLM_MODEL", "openai/gpt-4o-mini")

# OpenAI 兼容（备用）
CHATGPT_API_KEY = os.getenv("CHATGPT_API_KEY") or os.getenv("OPENAI_API_KEY")
DEFAULT_MODEL = OPENROUTER_MODEL or "gpt-4o-mini"


def count_tokens(text: str, model: Optional[str] = None) -> int:
    """估算文本的 token 数量"""
    if not text:
        return 0
    if tiktoken is None:
        return len(text) // 4
    try:
        enc = tiktoken.encoding_for_model(model or DEFAULT_MODEL)
        return len(enc.encode(text))
    except Exception:
        return len(text) // 4


def chat_completion(
    prompt: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    chat_history: Optional[list] = None,
    base_url: Optional[str] = None,
) -> str:
    """
    调用 LLM Chat Completions API（OpenRouter 或 OpenAI 兼容）

    .env 配置示例：
        OPENROUTER_API_KEY=sk-or-v1-xxx
        OPENROUTER_MODEL=openai/gpt-4o-mini

    Args:
        prompt: 用户提示
        model: 模型名称，默认从 OPENROUTER_MODEL 读取
        api_key: API 密钥，默认从 OPENROUTER_API_KEY 读取
        chat_history: 可选的历史消息列表
        base_url: API 地址，默认 OpenRouter

    Returns:
        assistant 回复内容
    """
    if openai is None:
        raise ImportError("请安装 openai: pip install openai")

    key = api_key or OPENROUTER_API_KEY or CHATGPT_API_KEY
    if not key:
        raise ValueError(
            "未设置 API Key，请在 .env 中配置 OPENROUTER_API_KEY 或 CHATGPT_API_KEY"
        )

    url = base_url or OPENROUTER_API_BASE
    client = openai.OpenAI(api_key=key, base_url=url.rstrip("/"))
    model = model or OPENROUTER_MODEL or DEFAULT_MODEL
    max_retries = 5

    for attempt in range(max_retries):
        try:
            if chat_history:
                messages = list(chat_history)
                messages.append({"role": "user", "content": prompt})
            else:
                messages = [{"role": "user", "content": prompt}]

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logging.warning(f"API 调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise


def extract_json(content: str) -> Any:
    """
    从 LLM 回复中提取 JSON，支持 ```json ... ``` 包裹

    Args:
        content: 原始回复文本

    Returns:
        解析后的 JSON 对象（dict 或 list），失败返回空 list
    """
    if not content or not content.strip():
        return []

    # 尝试提取 ```json ... ``` 块
    start_marker = "```json"
    start_idx = content.find(start_marker)
    if start_idx != -1:
        start_idx += len(start_marker)
        end_idx = content.find("```", start_idx)
        if end_idx != -1:
            content = content[start_idx:end_idx]

    content = content.strip()

    # 清理常见问题
    content = content.replace("None", "null")
    content = content.replace("'", '"')

    # 移除尾随逗号
    content = re.sub(r",\s*]", "]", content)
    content = re.sub(r",\s*}", "}", content)

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logging.error(f"JSON 解析失败: {e}")
        return []
