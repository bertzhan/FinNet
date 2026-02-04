# -*- coding: utf-8 -*-
"""
Embedding 模块
提供文本向量化服务
支持本地模型和 API 两种方式
"""

from .api_embedder import APIEmbedder, get_api_embedder
from .embedder_factory import EmbedderFactory, get_embedder_by_mode

# 延迟导入 vectorizer，避免循环依赖
def _lazy_import_vectorizer():
    """延迟导入 vectorizer"""
    try:
        from .vectorizer import Vectorizer, get_vectorizer
        return Vectorizer, get_vectorizer
    except ImportError:
        # 如果 pymilvus 未安装，返回 None
        return None, None

__all__ = [
    "APIEmbedder",
    "get_api_embedder",
    "EmbedderFactory",
    "get_embedder_by_mode",  # 统一接口
]
