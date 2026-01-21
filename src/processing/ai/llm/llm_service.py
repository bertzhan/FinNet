# -*- coding: utf-8 -*-
"""
LLM 服务
提供统一的 LLM 调用接口，支持云端 API 和本地 LLM
"""

from typing import Optional, Iterator
import time
import requests
import json
from src.common.config import llm_config
from src.common.logger import get_logger, LoggerMixin


class LLMService(LoggerMixin):
    """
    LLM 服务
    统一的 LLM 调用接口，支持云端 API（OpenAI/DeepSeek）和本地 LLM（Ollama）
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        api_base: Optional[str] = None
    ):
        """
        初始化 LLM 服务

        Args:
            api_key: API 密钥，None 时从配置读取
            model: 模型名称，None 时从配置读取
            api_base: API 基础 URL，None 时从配置读取（必需）
        """
        # 确定使用云端还是本地 LLM
        if llm_config.CLOUD_LLM_ENABLED:
            self.mode = "cloud"
            self.api_key = api_key or llm_config.CLOUD_LLM_API_KEY
            self.model = model or llm_config.CLOUD_LLM_MODEL
            self.api_base = api_base or llm_config.CLOUD_LLM_API_BASE
            
            if not self.api_base:
                raise ValueError("云端 LLM 需要配置 CLOUD_LLM_API_BASE（API URL）")
            
            if not self.api_key:
                raise ValueError("云端 LLM 需要配置 CLOUD_LLM_API_KEY")
            
            # 从 URL 识别 provider（用于日志）
            self.provider = self._identify_provider_from_url(self.api_base)
        elif llm_config.LOCAL_LLM_ENABLED:
            self.mode = "local"
            self.provider = "ollama"
            self.api_key = None
            self.model = model or llm_config.LOCAL_LLM_MODEL
            self.api_base = api_base or llm_config.LOCAL_LLM_API_BASE
        else:
            raise ValueError("未启用任何 LLM 服务（CLOUD_LLM_ENABLED 和 LOCAL_LLM_ENABLED 都为 False）")

        self.logger.info(
            f"LLM 服务初始化: mode={self.mode}, api_base={self.api_base}, "
            f"model={self.model}, provider={self.provider}"
        )

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """
        生成文本

        Args:
            prompt: 提示词
            system_prompt: 系统提示词（可选）
            temperature: 温度参数（0-2）
            max_tokens: 最大生成长度

        Returns:
            生成的文本

        Example:
            >>> service = LLMService()
            >>> answer = service.generate(
            ...     prompt="什么是人工智能？",
            ...     system_prompt="你是一个专业的AI助手。",
            ...     temperature=0.7
            ... )
        """
        if self.mode == "cloud":
            return self._generate_cloud(prompt, system_prompt, temperature, max_tokens)
        else:
            return self._generate_local(prompt, system_prompt, temperature, max_tokens)

    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Iterator[str]:
        """
        流式生成文本（返回生成器）

        Args:
            prompt: 提示词
            system_prompt: 系统提示词（可选）
            temperature: 温度参数（0-2）
            max_tokens: 最大生成长度

        Yields:
            文本块（字符串）

        Example:
            >>> service = LLMService()
            >>> for chunk in service.generate_stream("什么是人工智能？"):
            ...     print(chunk, end="", flush=True)
        """
        if self.mode == "cloud":
            yield from self._generate_stream_cloud(prompt, system_prompt, temperature, max_tokens)
        else:
            yield from self._generate_stream_local(prompt, system_prompt, temperature, max_tokens)

    def _generate_cloud(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """使用云端 API 生成文本（统一使用 OpenAI 兼容格式）"""
        # 统一使用 OpenAI 兼容格式，支持大多数服务（OpenAI、DeepSeek、LocalAI、vLLM等）
        return self._generate_openai_compatible(prompt, system_prompt, temperature, max_tokens)

    def _generate_local(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """使用本地 LLM（Ollama）生成文本"""
        if self.provider != "ollama":
            raise ValueError(f"不支持的本地提供商: {self.provider}")

        # Ollama API 格式
        url = f"{self.api_base}/api/generate"
        
        # 构建消息
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }

        try:
            self.logger.debug(f"调用 Ollama API: {url}, model={self.model}")
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            
            result = response.json()
            generated_text = result.get("response", "")
            
            self.logger.debug(f"Ollama 生成完成: 长度={len(generated_text)}")
            return generated_text

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ollama API 调用失败: {e}", exc_info=True)
            raise

    def _generate_openai_compatible(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """使用 OpenAI 兼容格式 API 生成文本（支持 OpenAI、DeepSeek、LocalAI、vLLM 等）"""
        # 确保 URL 格式正确（去除末尾斜杠）
        base_url = self.api_base.rstrip('/')
        
        # 检查 base_url 是否已经包含 /v1/chat/completions 路径
        # 如果已经包含，直接使用；否则拼接
        if '/v1/chat/completions' in base_url.lower():
            url = base_url
        else:
            url = f"{base_url}/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            self.logger.debug(f"调用 LLM API: {url}, model={self.model}")
            response = requests.post(url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()
            
            result = response.json()
            
            # 调试：打印响应结构（仅在DEBUG级别）
            if self.logger.level <= 10:  # DEBUG
                self.logger.debug(f"API 响应结构: {list(result.keys())}")
                if "choices" in result:
                    self.logger.debug(f"choices 数量: {len(result.get('choices', []))}")
                    if len(result.get('choices', [])) > 0:
                        self.logger.debug(f"第一个 choice 结构: {list(result['choices'][0].keys())}")
            
            # 解析响应（兼容不同格式）
            generated_text = ""
            if "choices" in result and len(result["choices"]) > 0:
                choice = result["choices"][0]
                if "message" in choice:
                    message = choice["message"]
                    generated_text = message.get("content", "")
                    
                    # 检查 finish_reason，如果是 "length" 且 content 为空，可能是 max_tokens 太小
                    finish_reason = choice.get("finish_reason", "")
                    if not generated_text and finish_reason == "length":
                        # 检查是否有 reasoning 字段（推理模型）
                        if "reasoning" in message:
                            self.logger.warning(
                                f"模型返回了推理过程但没有内容，可能是 max_tokens ({max_tokens}) 太小。"
                                f"建议增加 max_tokens 或使用非推理模型。"
                            )
                        else:
                            self.logger.warning(
                                f"响应被截断（finish_reason=length），但 content 为空。"
                                f"建议增加 max_tokens（当前: {max_tokens}）"
                            )
                elif "text" in choice:
                    generated_text = choice["text"]
                elif "delta" in choice:
                    # 流式响应格式
                    generated_text = choice["delta"].get("content", "")
                else:
                    # 尝试直接获取content
                    generated_text = choice.get("content", "")
            elif "data" in result and len(result["data"]) > 0:
                # 某些API可能返回data字段
                generated_text = result["data"][0].get("content", "")
            elif "text" in result:
                # 某些API直接返回text字段
                generated_text = result["text"]
            else:
                # 打印完整响应用于调试
                self.logger.warning(f"未识别的响应格式，响应键: {list(result.keys())}")
                if self.logger.level <= 20:  # INFO or DEBUG
                    import json
                    self.logger.warning(f"完整响应: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}")
                generated_text = ""
            
            # 如果仍然为空，记录警告
            if not generated_text:
                self.logger.warning(
                    f"LLM 返回空内容。"
                    f"finish_reason: {result.get('choices', [{}])[0].get('finish_reason', 'unknown')}, "
                    f"max_tokens: {max_tokens}"
                )
            
            self.logger.debug(f"LLM 生成完成: 长度={len(generated_text)}")
            return generated_text

        except requests.exceptions.RequestException as e:
            self.logger.error(f"LLM API 调用失败: {e}", exc_info=True)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    self.logger.error(f"错误详情: {error_detail}")
                except:
                    self.logger.error(f"响应内容: {e.response.text}")
            raise

    def _generate_stream_cloud(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> Iterator[str]:
        """使用云端 API 流式生成文本（OpenAI 兼容格式）"""
        # 确保 URL 格式正确（去除末尾斜杠）
        base_url = self.api_base.rstrip('/')
        
        # 检查 base_url 是否已经包含 /v1/chat/completions 路径
        if '/v1/chat/completions' in base_url.lower():
            url = base_url
        else:
            url = f"{base_url}/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }

        try:
            self.logger.debug(f"调用 LLM API (流式): {url}, model={self.model}")
            response = requests.post(url, json=payload, headers=headers, timeout=120, stream=True)
            response.raise_for_status()
            
            # 解析 SSE 流式响应
            for line in response.iter_lines():
                if not line:
                    continue
                
                line_text = line.decode('utf-8')
                if line_text.startswith('data: '):
                    data_str = line_text[6:]  # 移除 "data: " 前缀
                    if data_str.strip() == '[DONE]':
                        break
                    
                    try:
                        data = json.loads(data_str)
                        # 提取内容增量
                        if "choices" in data and len(data["choices"]) > 0:
                            choice = data["choices"][0]
                            if "delta" in choice:
                                delta = choice["delta"]
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            elif "message" in choice:
                                # 某些 API 在流式响应中也使用 message
                                message = choice["message"]
                                content = message.get("content", "")
                                if content:
                                    yield content
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"解析流式响应失败: {e}, 数据: {data_str[:100]}")
                        continue

        except requests.exceptions.RequestException as e:
            self.logger.error(f"LLM API 流式调用失败: {e}", exc_info=True)
            # 如果流式失败，尝试非流式并模拟流式返回
            self.logger.warning("流式调用失败，回退到非流式并模拟流式响应")
            try:
                full_text = self._generate_openai_compatible(prompt, system_prompt, temperature, max_tokens)
                # 按字符或词块分块返回（模拟流式）
                chunk_size = 3  # 每次返回3个字符
                for i in range(0, len(full_text), chunk_size):
                    yield full_text[i:i + chunk_size]
            except Exception as fallback_error:
                self.logger.error(f"回退方案也失败: {fallback_error}", exc_info=True)
                raise

    def _generate_stream_local(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> Iterator[str]:
        """使用本地 LLM（Ollama）流式生成文本"""
        if self.provider != "ollama":
            # 如果不支持流式，回退到非流式并模拟
            self.logger.warning(f"本地提供商 {self.provider} 不支持流式，使用模拟流式")
            try:
                full_text = self._generate_local(prompt, system_prompt, temperature, max_tokens)
                chunk_size = 3
                for i in range(0, len(full_text), chunk_size):
                    yield full_text[i:i + chunk_size]
            except Exception as e:
                self.logger.error(f"模拟流式失败: {e}", exc_info=True)
                raise
            return

        # Ollama 流式 API
        url = f"{self.api_base}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }

        try:
            self.logger.debug(f"调用 Ollama API (流式): {url}, model={self.model}")
            response = requests.post(url, json=payload, timeout=120, stream=True)
            response.raise_for_status()
            
            # Ollama 流式响应格式：每行一个 JSON 对象
            for line in response.iter_lines():
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    if "response" in data:
                        content = data["response"]
                        if content:
                            yield content
                    if data.get("done", False):
                        break
                except json.JSONDecodeError as e:
                    self.logger.warning(f"解析 Ollama 流式响应失败: {e}, 数据: {line[:100]}")
                    continue

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ollama API 流式调用失败: {e}", exc_info=True)
            # 回退到非流式
            self.logger.warning("流式调用失败，回退到非流式并模拟流式响应")
            try:
                full_text = self._generate_local(prompt, system_prompt, temperature, max_tokens)
                chunk_size = 3
                for i in range(0, len(full_text), chunk_size):
                    yield full_text[i:i + chunk_size]
            except Exception as fallback_error:
                self.logger.error(f"回退方案也失败: {fallback_error}", exc_info=True)
                raise

    def _identify_provider_from_url(self, url: str) -> str:
        """
        从 URL 识别 provider（仅用于日志显示）
        
        Args:
            url: API URL
            
        Returns:
            provider 名称
        """
        url_lower = url.lower()
        if "openai.com" in url_lower:
            return "openai"
        elif "deepseek.com" in url_lower:
            return "deepseek"
        elif "dashscope" in url_lower or "aliyuncs.com" in url_lower:
            return "dashscope"
        elif "localhost" in url_lower or "127.0.0.1" in url_lower:
            return "local"
        else:
            return "custom"


# 全局服务实例（单例模式）
_llm_service: Optional[LLMService] = None


def get_llm_service(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    api_base: Optional[str] = None
) -> LLMService:
    """
    获取全局 LLM 服务实例（单例）

    Args:
        api_key: API 密钥（可选）
        model: 模型名称（可选）
        api_base: API 基础 URL（可选，云端 LLM 必需）

    Returns:
        LLM 服务实例

    Example:
        >>> from src.processing.ai.llm.llm_service import get_llm_service
        >>> service = get_llm_service()
        >>> answer = service.generate("什么是人工智能？")
    """
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService(
            api_key=api_key,
            model=model,
            api_base=api_base
        )
    return _llm_service
