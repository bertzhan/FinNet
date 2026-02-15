# -*- coding: utf-8 -*-
"""
共享HTTP客户端（支持连接池和HTTP/2）
适配自 SEC-Filings-ETL/utils/http_client.py
"""
import httpx
from typing import Optional

from src.common.logger import get_logger
from src.common.config import sec_config

logger = get_logger(__name__)


class SharedHTTPClient:
    """
    单例HTTP客户端，支持连接池和HTTP/2

    优势：
    - 连接复用减少延迟
    - HTTP/2多路复用提高吞吐量
    - 连接池限制防止资源耗尽
    """

    _instance: Optional[httpx.Client] = None
    _async_instance: Optional[httpx.AsyncClient] = None

    @classmethod
    def get_client(cls) -> httpx.Client:
        """
        获取或创建共享的同步HTTP客户端

        Returns:
            共享的 httpx.Client 实例
        """
        if cls._instance is None:
            timeout = httpx.Timeout(
                connect=sec_config.SEC_TIMEOUT,
                read=60.0,
                write=30.0,
                pool=5.0
            )

            limits = httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=30.0
            )

            # 检查 SEC_USER_AGENT 是否配置
            user_agent = sec_config.SEC_USER_AGENT
            if not user_agent or user_agent == "":
                logger.warning(
                    "SEC_USER_AGENT未配置，使用默认值。"
                    "请在.env中设置SEC_USER_AGENT=YourCompany email@domain.com"
                )
                user_agent = "FinNet Research noreply@example.com"

            cls._instance = httpx.Client(
                timeout=timeout,
                limits=limits,
                http2=True,
                follow_redirects=True,
                headers={"User-Agent": user_agent}
            )

            logger.info(
                "共享HTTP客户端已初始化",
                extra={
                    "http2": True,
                    "max_connections": 100,
                    "max_keepalive": 20
                }
            )

        return cls._instance

    @classmethod
    def get_async_client(cls) -> httpx.AsyncClient:
        """
        获取或创建共享的异步HTTP客户端

        Returns:
            共享的 httpx.AsyncClient 实例
        """
        if cls._async_instance is None:
            timeout = httpx.Timeout(
                connect=sec_config.SEC_TIMEOUT,
                read=60.0,
                write=30.0,
                pool=5.0
            )

            limits = httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=30.0
            )

            user_agent = sec_config.SEC_USER_AGENT
            if not user_agent or user_agent == "":
                logger.warning(
                    "SEC_USER_AGENT未配置，使用默认值。"
                    "请在.env中设置SEC_USER_AGENT=YourCompany email@domain.com"
                )
                user_agent = "FinNet Research noreply@example.com"

            cls._async_instance = httpx.AsyncClient(
                timeout=timeout,
                limits=limits,
                http2=True,
                follow_redirects=True,
                headers={"User-Agent": user_agent}
            )

            logger.info(
                "共享异步HTTP客户端已初始化",
                extra={
                    "http2": True,
                    "max_connections": 100,
                    "max_keepalive": 20
                }
            )

        return cls._async_instance

    @classmethod
    def close_all(cls):
        """关闭所有共享客户端（应用关闭时调用）"""
        if cls._instance:
            cls._instance.close()
            cls._instance = None
            logger.info("共享HTTP客户端已关闭")

        if cls._async_instance:
            import asyncio
            asyncio.run(cls._async_instance.aclose())
            cls._async_instance = None
            logger.info("共享异步HTTP客户端已关闭")


def get_http_client() -> httpx.Client:
    """便捷函数：获取共享HTTP客户端"""
    return SharedHTTPClient.get_client()


def get_async_http_client() -> httpx.AsyncClient:
    """便捷函数：获取共享异步HTTP客户端"""
    return SharedHTTPClient.get_async_client()
