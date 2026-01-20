# -*- coding: utf-8 -*-
"""
BGE Embedding 服务
支持 BGE-large-zh-v1.5 和 BCE-embedding-base 模型

按照 plan.md 设计：
- 封装 Embedding 模型
- 支持批量向量化
- 支持 CPU/GPU 设备选择
"""

from typing import List, Optional
from sentence_transformers import SentenceTransformer

from src.common.config import embedding_config
from src.common.logger import LoggerMixin


class BGEEmbedder(LoggerMixin):
    """
    BGE Embedding 服务
    封装 BGE/BCE 模型的向量化功能
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None
    ):
        """
        初始化 BGE Embedder

        Args:
            model_name: 模型名称（默认从配置读取）
            device: 设备类型（cpu/cuda，默认从配置读取）
        """
        self.model_name = model_name or embedding_config.EMBEDDING_MODEL
        self.device = device or embedding_config.EMBEDDING_DEVICE
        
        # 根据模型名称选择实际模型路径
        if "bge-large" in self.model_name.lower():
            model_path = embedding_config.BGE_MODEL_PATH
        elif "bce" in self.model_name.lower():
            model_path = embedding_config.BCE_MODEL_PATH
        else:
            # 默认使用 BGE
            model_path = embedding_config.BGE_MODEL_PATH
        
        self.logger.info(f"初始化 Embedding 模型: {model_path}, device={self.device}")
        
        # 加载模型
        try:
            self.model = SentenceTransformer(
                model_path,
                device=self.device
            )
            self.dimension = self.model.get_sentence_embedding_dimension()
            self.logger.info(f"模型加载成功: dimension={self.dimension}")
        except Exception as e:
            self.logger.error(f"模型加载失败: {e}", exc_info=True)
            raise

    def embed_text(self, text: str) -> List[float]:
        """
        单个文本向量化

        Args:
            text: 待向量化的文本

        Returns:
            向量列表（浮点数列表）
        """
        if not text or not text.strip():
            self.logger.warning("空文本，返回零向量")
            return [0.0] * self.dimension

        try:
            embedding = self.model.encode(
                text,
                batch_size=1,
                normalize_embeddings=True,  # 归一化向量
                show_progress_bar=False
            )
            return embedding.tolist()[0]
        except Exception as e:
            self.logger.error(f"向量化失败: {e}", exc_info=True)
            raise

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量向量化

        Args:
            texts: 待向量化的文本列表

        Returns:
            向量列表（每个文本对应一个向量）
        """
        if not texts:
            return []

        # 过滤空文本
        valid_texts = []
        valid_indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                valid_texts.append(text)
                valid_indices.append(i)
            else:
                self.logger.warning(f"跳过空文本（索引 {i}）")

        if not valid_texts:
            self.logger.warning("所有文本都为空，返回空列表")
            return []

        try:
            embeddings = self.model.encode(
                valid_texts,
                batch_size=embedding_config.EMBEDDING_BATCH_SIZE,
                normalize_embeddings=True,  # 归一化向量
                show_progress_bar=False
            )
            
            # 转换为列表格式
            result = embeddings.tolist()
            
            # 如果有空文本，需要插入零向量
            if len(valid_indices) < len(texts):
                full_result = []
                result_idx = 0
                for i in range(len(texts)):
                    if i in valid_indices:
                        full_result.append(result[result_idx])
                        result_idx += 1
                    else:
                        full_result.append([0.0] * self.dimension)
                return full_result
            
            return result
        except Exception as e:
            self.logger.error(f"批量向量化失败: {e}", exc_info=True)
            raise

    def get_model_dim(self) -> int:
        """
        获取向量维度

        Returns:
            向量维度（BGE: 1024, BCE: 768）
        """
        return self.dimension

    def get_model_name(self) -> str:
        """
        获取模型名称

        Returns:
            模型名称
        """
        return self.model_name


# 全局 Embedder 实例（单例模式）
_embedder: Optional[BGEEmbedder] = None


def get_embedder(
    model_name: Optional[str] = None,
    device: Optional[str] = None
) -> BGEEmbedder:
    """
    获取全局 Embedder 实例（单例）

    Args:
        model_name: 模型名称（可选）
        device: 设备类型（可选）

    Returns:
        BGEEmbedder 实例

    Example:
        >>> from src.processing.ai.embedding.bge_embedder import get_embedder
        >>> embedder = get_embedder()
        >>> vector = embedder.embed_text("测试文本")
    """
    global _embedder
    if _embedder is None:
        _embedder = BGEEmbedder(model_name=model_name, device=device)
    return _embedder
