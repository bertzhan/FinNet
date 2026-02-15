"""
Shared HTTP client with connection pooling and HTTP/2 support.
"""
import httpx
import structlog
from typing import Optional

from config.settings import settings

logger = structlog.get_logger()


class SharedHTTPClient:
    """
    Singleton HTTP client with connection pooling and HTTP/2.

    Benefits:
    - Connection reuse reduces latency
    - HTTP/2 multiplexing improves throughput
    - Connection pool limits prevent resource exhaustion
    """

    _instance: Optional[httpx.Client] = None
    _async_instance: Optional[httpx.AsyncClient] = None

    @classmethod
    def get_client(cls) -> httpx.Client:
        """
        Get or create the shared synchronous HTTP client.

        Returns:
            Shared httpx.Client instance
        """
        if cls._instance is None:
            timeout = httpx.Timeout(
                connect=settings.sec_timeout,
                read=60.0,
                write=30.0,
                pool=5.0
            )

            limits = httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=30.0
            )

            cls._instance = httpx.Client(
                timeout=timeout,
                limits=limits,
                http2=True,
                follow_redirects=True,
                headers={"User-Agent": settings.sec_user_agent}
            )

            logger.info(
                "shared_http_client_initialized",
                http2=True,
                max_connections=100,
                max_keepalive=20
            )

        return cls._instance

    @classmethod
    def get_async_client(cls) -> httpx.AsyncClient:
        """
        Get or create the shared asynchronous HTTP client.

        Returns:
            Shared httpx.AsyncClient instance
        """
        if cls._async_instance is None:
            timeout = httpx.Timeout(
                connect=settings.sec_timeout,
                read=60.0,
                write=30.0,
                pool=5.0
            )

            limits = httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=30.0
            )

            cls._async_instance = httpx.AsyncClient(
                timeout=timeout,
                limits=limits,
                http2=True,
                follow_redirects=True,
                headers={"User-Agent": settings.sec_user_agent}
            )

            logger.info(
                "shared_async_http_client_initialized",
                http2=True,
                max_connections=100,
                max_keepalive=20
            )

        return cls._async_instance

    @classmethod
    def close_all(cls):
        """Close all shared clients. Call this on application shutdown."""
        if cls._instance:
            cls._instance.close()
            cls._instance = None
            logger.info("shared_http_client_closed")

        if cls._async_instance:
            import asyncio
            asyncio.run(cls._async_instance.aclose())
            cls._async_instance = None
            logger.info("shared_async_http_client_closed")


def get_http_client() -> httpx.Client:
    """Convenience function to get the shared HTTP client."""
    return SharedHTTPClient.get_client()


def get_async_http_client() -> httpx.AsyncClient:
    """Convenience function to get the shared async HTTP client."""
    return SharedHTTPClient.get_async_client()
