# -*- coding: utf-8 -*-
"""
Embedder 工厂
根据配置自动选择本地模型或 API 方式
"""

from typing import Optional, Union, Any
from src.common.config import embedding_config
from src.common.logger import get_logger, LoggerMixin

# 延迟导入，避免循环依赖
try:
    from .bge_embedder import BGEEmbedder, get_embedder as get_local_embedder
except ImportError:
    BGEEmbedder = None
    get_local_embedder = None

try:
    from .api_embedder import APIEmbedder, get_api_embedder
except ImportError:
    APIEmbedder = None
    get_api_embedder = None


class EmbedderFactory:
    """Embedder 工厂类"""
    
    _logger = None
    
    @classmethod
    def _get_logger(cls):
        """获取 logger"""
        if cls._logger is None:
            cls._logger = get_logger(__name__)
        return cls._logger
    
    @staticmethod
    def get_embedder(
        mode: Optional[str] = None,
        **kwargs: Any
    ) -> Any:  # Union[BGEEmbedder, APIEmbedder]
        """
        根据模式获取 Embedder 实例

        Args:
            mode: 模式（'local' 或 'api'），None 时从配置读取
            **kwargs: 其他参数
                - 对于 local 模式：model_name, device
                - 对于 api 模式：api_url, api_key, model

        Returns:
            Embedder 实例（BGEEmbedder 或 APIEmbedder）

        Example:
            >>> from src.processing.ai.embedding.embedder_factory import EmbedderFactory
            >>> # 使用配置的模式
            >>> embedder = EmbedderFactory.get_embedder()
            >>> # 强制使用 API 模式
            >>> embedder = EmbedderFactory.get_embedder(mode='api')
            >>> # 使用自定义 API 配置
            >>> embedder = EmbedderFactory.get_embedder(
            ...     mode='api',
            ...     api_url='https://api.example.com/v1/embeddings',
            ...     api_key='your-key',
            ...     model='text-embedding-ada-002'
            ... )
        """
        mode = mode or embedding_config.EMBEDDING_MODE
        
        # 记录使用的模式
        logger = EmbedderFactory._get_logger()
        logger.info(f"🔧 Embedder 模式: {mode} (配置值: EMBEDDING_MODE={embedding_config.EMBEDDING_MODE})")
        
        if mode == "api":
            logger.info("📡 使用 API Embedder 模式")
            if APIEmbedder is None or get_api_embedder is None:
                raise ImportError("APIEmbedder 未可用，请检查依赖")
            
            api_url = kwargs.get("api_url")
            api_key = kwargs.get("api_key")
            model = kwargs.get("model")
            
            return get_api_embedder(
                api_url=api_url,
                api_key=api_key,
                model=model
            )
        
        elif mode == "local":
            logger.info("💻 使用本地模型 Embedder 模式")
            if BGEEmbedder is None or get_local_embedder is None:
                raise ImportError("BGEEmbedder 未可用，请检查 sentence-transformers 是否安装")
            
            model_name = kwargs.get("model_name")
            device = kwargs.get("device")
            
            return get_local_embedder(
                model_name=model_name,
                device=device
            )
        
        else:
            raise ValueError(f"不支持的模式: {mode}，支持的模式: 'local', 'api'")


# 便捷函数
def get_embedder_by_mode(
    mode: Optional[str] = None,
    **kwargs: Any
) -> Any:  # Union[BGEEmbedder, APIEmbedder]
    """
    根据模式获取 Embedder（便捷函数）

    Args:
        mode: 模式（'local' 或 'api'），None 时从配置读取
        **kwargs: 其他参数

    Returns:
        Embedder 实例

    Example:
        >>> from src.processing.ai.embedding.embedder_factory import get_embedder_by_mode
        >>> embedder = get_embedder_by_mode()  # 使用配置的模式
        >>> vector = embedder.embed_text("测试文本")
    """
    return EmbedderFactory.get_embedder(mode=mode, **kwargs)
