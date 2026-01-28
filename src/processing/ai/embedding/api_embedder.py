# -*- coding: utf-8 -*-
"""
API Embedding 服务
支持 OpenAI 兼容的 Embedding API 接口

支持自定义 URL、API Key 和 Model
"""

from typing import List, Optional
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.common.config import embedding_config
from src.common.logger import LoggerMixin


class APIEmbedder(LoggerMixin):
    """
    API Embedding 服务
    使用 OpenAI 兼容的 API 接口进行向量化
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None
    ):
        """
        初始化 API Embedder

        Args:
            api_url: API 地址（如 https://api.openai.com/v1/embeddings）
            api_key: API Key
            model: 模型名称（如 text-embedding-ada-002）
            timeout: 超时时间（秒）
            max_retries: 最大重试次数
        """
        self.api_url = api_url or embedding_config.EMBEDDING_API_URL
        self.api_key = api_key or embedding_config.EMBEDDING_API_KEY
        self.model = model or embedding_config.EMBEDDING_API_MODEL
        self.timeout = timeout or embedding_config.EMBEDDING_API_TIMEOUT
        self.max_retries = max_retries or embedding_config.EMBEDDING_API_MAX_RETRIES
        
        # 验证配置
        if not self.api_url:
            raise ValueError("EMBEDDING_API_URL 未配置，请设置 API 地址")
        if not self.api_key:
            raise ValueError("EMBEDDING_API_KEY 未配置，请设置 API Key")
        if not self.model:
            raise ValueError("EMBEDDING_API_MODEL 未配置，请设置模型名称")
        
        # 创建 HTTP 会话，配置重试策略
        self.session = requests.Session()
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # 设置默认 headers
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 向量维度（需要从 API 获取或配置）
        self.dimension = embedding_config.EMBEDDING_DIM
        
        self.logger.info(
            f"初始化 API Embedder: url={self.api_url}, model={self.model}"
        )
        
        # 测试连接（可选）
        try:
            self._test_connection()
        except Exception as e:
            self.logger.warning(f"API 连接测试失败: {e}，将在首次使用时重试")

    def _test_connection(self):
        """测试 API 连接"""
        test_text = "test"
        try:
            vector = self._call_api([test_text])
            if vector and len(vector) > 0:
                self.dimension = len(vector[0])
                self.logger.info(f"API 连接成功，向量维度: {self.dimension}")
        except Exception as e:
            self.logger.warning(f"API 连接测试失败: {e}")

    def _call_api(self, texts: List[str]) -> List[List[float]]:
        """
        调用 API 接口

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        payload = {
            "input": texts,
            "model": self.model
        }
        
        try:
            response = self.session.post(
                self.api_url,
                json=payload,
                headers=self.headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            # 检查 API 错误响应
            if isinstance(data, dict) and "error" in data:
                error_info = data["error"]
                error_msg = error_info.get("message", str(error_info))
                error_code = error_info.get("code", "unknown")
                raise ValueError(f"API 返回错误: {error_msg} (code: {error_code})")
            
            # 记录响应结构（用于调试）
            self.logger.debug(
                f"API 响应结构: keys={list(data.keys()) if isinstance(data, dict) else 'not a dict'}, "
                f"输入文本数={len(texts)}"
            )
            
            # 解析响应（OpenAI 格式）
            embeddings = None
            if "data" in data:
                embeddings = [item["embedding"] for item in data["data"]]
                self.logger.debug(f"从 'data' 字段解析: 找到 {len(embeddings)} 个向量")
            elif "embeddings" in data:
                embeddings = data["embeddings"]
                self.logger.debug(f"从 'embeddings' 字段解析: 找到 {len(embeddings)} 个向量")
            else:
                # 兼容其他格式
                if isinstance(data, list):
                    embeddings = data
                    self.logger.debug(f"响应是列表格式: 找到 {len(embeddings)} 个向量")
                else:
                    # 可能是单个对象
                    self.logger.warning(f"未知响应格式: {type(data)}, keys={list(data.keys()) if isinstance(data, dict) else 'N/A'}")
                    # 尝试查找 embedding 字段
                    if isinstance(data, dict) and "embedding" in data:
                        embeddings = [data["embedding"]]
                        self.logger.debug(f"从单个对象的 'embedding' 字段解析: 1 个向量")
                    else:
                        embeddings = [data] if not isinstance(data, list) else data
            
            # 验证返回的向量数量
            if embeddings is None:
                error_msg = f"无法解析 API 响应: {data}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
            
            if len(embeddings) != len(texts):
                error_msg = f"API 返回的向量数量不匹配: 期望={len(texts)}, 实际={len(embeddings)}"
                self.logger.error(error_msg)
                self.logger.error(f"API 响应数据 (前500字符): {str(data)[:500]}")
                # 如果是单个向量，可能是 API 只处理了第一个文本
                if len(embeddings) == 1:
                    self.logger.error(
                        f"⚠️  API 只返回了 1 个向量，可能是批量请求格式问题。"
                        f"检查 API 是否支持批量请求，或者需要逐个发送。"
                    )
                raise ValueError(error_msg)
            
            return embeddings
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API 调用失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"API 响应解析失败: {e}")
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
            embeddings = self._call_api([text])
            if embeddings and len(embeddings) > 0:
                return embeddings[0]
            else:
                raise ValueError("API 返回空向量")
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

        self.logger.debug(
            f"embed_batch: 输入文本数={len(texts)}, 有效文本数={len(valid_texts)}, "
            f"空文本数={len(texts) - len(valid_texts)}"
        )

        if not valid_texts:
            self.logger.warning("所有文本都为空，返回空列表")
            return []

        try:
            # 尝试批量调用 API，如果失败则降级为逐个调用
            batch_size = embedding_config.EMBEDDING_BATCH_SIZE
            all_embeddings = []
            use_individual_calls = False  # 是否使用逐个调用
            
            # 如果只有1个文本，直接单个调用
            if len(valid_texts) == 1:
                self.logger.debug("只有1个文本，使用单个调用")
                embeddings = self._call_api(valid_texts)
                all_embeddings.extend(embeddings)
            else:
                # 尝试批量调用
                try:
                    for i in range(0, len(valid_texts), batch_size):
                        batch = valid_texts[i:i + batch_size]
                        batch_num = i // batch_size + 1
                        self.logger.debug(f"处理批次 {batch_num}: {len(batch)} 个文本")
                        
                        try:
                            embeddings = self._call_api(batch)
                            if embeddings is None or len(embeddings) == 0:
                                raise ValueError(f"API 返回空向量列表（批次 {batch_num}）")
                            if len(embeddings) != len(batch):
                                # 如果批量请求失败（只返回1个向量），降级为逐个调用
                                if len(embeddings) == 1 and len(batch) > 1:
                                    self.logger.warning(
                                        f"⚠️  批量请求失败（返回 {len(embeddings)} 个向量，期望 {len(batch)} 个），"
                                        f"降级为逐个调用。API 可能不支持批量请求。"
                                    )
                                    use_individual_calls = True
                                    break
                                else:
                                    raise ValueError(
                                        f"API 返回向量数量不匹配: 期望={len(batch)}, 实际={len(embeddings)} "
                                        f"(批次 {batch_num})"
                                    )
                            all_embeddings.extend(embeddings)
                            self.logger.debug(f"批次 {batch_num} 成功: 返回 {len(embeddings)} 个向量")
                        except ValueError as e:
                            # 如果是向量数量不匹配且只返回1个，降级为逐个调用
                            error_str = str(e)
                            if "向量数量不匹配" in error_str:
                                # 检查是否有 embeddings 变量（可能在异常前已定义）
                                if 'embeddings' in locals() and len(embeddings) == 1:
                                    self.logger.warning(
                                        f"⚠️  批量请求失败，降级为逐个调用: {e}"
                                    )
                                    use_individual_calls = True
                                    break
                                else:
                                    # 向量数量不匹配但不是1个，或者 embeddings 未定义，直接抛出异常
                                    raise
                            else:
                                # 其他 ValueError（如 API 错误），直接抛出
                                raise
                        except Exception as e:
                            # 其他异常（如 API 连接错误），尝试逐个调用
                            self.logger.warning(
                                f"批量请求异常: {e}，尝试逐个调用..."
                            )
                            use_individual_calls = True
                            break
                        
                        # 避免请求过快
                        if i + batch_size < len(valid_texts):
                            time.sleep(0.1)  # 短暂延迟
                
                except Exception as e:
                    # 如果批量调用失败，尝试逐个调用
                    if not use_individual_calls:
                        self.logger.warning(
                            f"批量调用失败: {e}，尝试逐个调用..."
                        )
                        use_individual_calls = True
                
                # 如果批量调用失败，使用逐个调用
                if use_individual_calls:
                    processed_count = len(all_embeddings)
                    remaining_texts = valid_texts[processed_count:]
                    self.logger.info(
                        f"使用逐个调用模式处理剩余 {len(remaining_texts)} 个文本"
                        f"（已处理 {processed_count} 个）"
                    )
                    
                    # 记录失败的文本索引和错误信息
                    failed_indices = []
                    failed_errors = []
                    
                    for i, text in enumerate(remaining_texts, processed_count + 1):
                        try:
                            embeddings = self._call_api([text])
                            if embeddings and len(embeddings) > 0:
                                all_embeddings.append(embeddings[0])
                                if i % 10 == 0:
                                    self.logger.debug(f"已处理 {i}/{len(valid_texts)} 个文本")
                            else:
                                # 返回空向量，记录失败但继续处理
                                error_msg = f"文本 {i} 返回空向量"
                                self.logger.warning(f"⚠️  {error_msg}，插入零向量并继续处理")
                                all_embeddings.append([0.0] * self.dimension)
                                failed_indices.append(i)
                                failed_errors.append(error_msg)
                        except Exception as e:
                            # ✅ 改进：记录错误但继续处理，不抛出异常
                            error_msg = str(e)
                            self.logger.error(
                                f"文本 {i} 向量化失败: {e}，插入零向量并继续处理"
                            )
                            # 打印失败的文本内容（前200字符）
                            text_preview = text[:200] if text else ""
                            self.logger.error(
                                f"  失败文本内容（前200字符）:\n"
                                f"  {text_preview}\n"
                                f"  {'...' if len(text or '') > 200 else ''}"
                            )
                            # 插入零向量，保持列表长度一致
                            all_embeddings.append([0.0] * self.dimension)
                            failed_indices.append(i)
                            failed_errors.append(error_msg)
                        
                        # 避免请求过快
                        if i < len(valid_texts):
                            time.sleep(0.05)  # 短暂延迟
                    
                    # 如果有失败，记录警告但不抛出异常
                    if failed_indices:
                        self.logger.warning(
                            f"⚠️  逐个调用模式中，{len(failed_indices)} 个文本失败，"
                            f"已插入零向量。失败索引: {failed_indices}"
                        )
                        self.logger.warning(
                            f"失败文本索引和错误: {list(zip(failed_indices, failed_errors))}"
                        )
            
            self.logger.debug(
                f"所有批次完成: 收集到 {len(all_embeddings)} 个向量, "
                f"有效文本数={len(valid_texts)}"
            )
            
            # 如果有空文本，需要插入零向量
            if len(valid_indices) < len(texts):
                self.logger.debug(
                    f"有空文本: 输入={len(texts)}, 有效={len(valid_indices)}, "
                    f"需要插入 {len(texts) - len(valid_indices)} 个零向量"
                )
                full_result = []
                result_idx = 0
                for i in range(len(texts)):
                    if i in valid_indices:
                        if result_idx < len(all_embeddings):
                            full_result.append(all_embeddings[result_idx])
                            result_idx += 1
                        else:
                            self.logger.error(
                                f"索引越界: result_idx={result_idx}, "
                                f"all_embeddings长度={len(all_embeddings)}"
                            )
                            # 如果索引越界，插入零向量
                            full_result.append([0.0] * self.dimension)
                    else:
                        full_result.append([0.0] * self.dimension)
                
                self.logger.debug(f"最终结果: {len(full_result)} 个向量")
                return full_result
            
            self.logger.debug(f"无空文本，直接返回: {len(all_embeddings)} 个向量")
            return all_embeddings
            
        except Exception as e:
            self.logger.error(f"批量向量化失败: {e}", exc_info=True)
            raise

    def get_model_dim(self) -> int:
        """
        获取向量维度

        Returns:
            向量维度
        """
        return self.dimension

    def get_model_name(self) -> str:
        """
        获取模型名称

        Returns:
            模型名称
        """
        return self.model


# 全局 API Embedder 实例（单例模式）
_api_embedder: Optional[APIEmbedder] = None


def get_api_embedder(
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> APIEmbedder:
    """
    获取全局 API Embedder 实例（单例）

    Args:
        api_url: API 地址（可选）
        api_key: API Key（可选）
        model: 模型名称（可选）

    Returns:
        APIEmbedder 实例

    Example:
        >>> from src.processing.ai.embedding.api_embedder import get_api_embedder
        >>> embedder = get_api_embedder()
        >>> vector = embedder.embed_text("测试文本")
    """
    global _api_embedder
    if _api_embedder is None:
        _api_embedder = APIEmbedder(
            api_url=api_url,
            api_key=api_key,
            model=model
        )
    return _api_embedder
