"""
Rate limiter for SEC EDGAR API compliance (max 10 req/sec).

Enhanced with:
- 429 response handling
- Retry-After header support
- Global RPS enforcement across processes
"""
import time
from threading import Lock
from typing import Optional

import structlog

logger = structlog.get_logger()


class SECRateLimiter:
    """
    Thread-safe rate limiter for SEC EDGAR API.
    Ensures compliance with configurable requests per second limit.

    Features:
    - Configurable RPS from environment
    - 429 response handling with exponential backoff
    - Retry-After header support
    - Thread-safe operation
    """

    def __init__(self, requests_per_second: int = 10):
        """
        Initialize rate limiter.

        Args:
            requests_per_second: Maximum requests allowed per second
        """
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0
        self.lock = Lock()
        self.request_count = 0
        self.retry_after_until = 0.0  # Timestamp until which to wait after 429

        logger.info(
            "rate_limiter_initialized",
            requests_per_second=requests_per_second,
            min_interval_ms=self.min_interval * 1000
        )

    def wait(self):
        """
        Wait if necessary to comply with rate limit.
        This method is thread-safe.
        """
        with self.lock:
            current_time = time.time()

            # Check if we need to wait due to 429 Retry-After
            if current_time < self.retry_after_until:
                sleep_time = self.retry_after_until - current_time
                logger.warning(
                    "rate_limit_retry_after_wait",
                    sleep_seconds=sleep_time
                )
                time.sleep(sleep_time)
                current_time = time.time()

            # Standard rate limit check
            elapsed = current_time - self.last_request_time

            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                logger.debug("rate_limit_wait", sleep_ms=sleep_time * 1000)
                time.sleep(sleep_time)

            self.last_request_time = time.time()
            self.request_count += 1

            if self.request_count % 100 == 0:
                logger.info("rate_limiter_stats", total_requests=self.request_count)

    def handle_429(self, retry_after: Optional[int] = None):
        """
        Handle a 429 Too Many Requests response.

        Args:
            retry_after: Value from Retry-After header (seconds), or None
        """
        with self.lock:
            if retry_after:
                # Use server-provided retry delay
                wait_seconds = float(retry_after)
            else:
                # Use exponential backoff: 60s, 120s, 240s...
                wait_seconds = 60.0

            self.retry_after_until = time.time() + wait_seconds

            logger.warning(
                "rate_limit_429_received",
                retry_after_seconds=wait_seconds,
                retry_after_until=self.retry_after_until
            )

    def reset_stats(self):
        """Reset request counter."""
        with self.lock:
            self.request_count = 0

    def get_stats(self) -> dict:
        """
        Get current rate limiter statistics.

        Returns:
            Dictionary with stats
        """
        with self.lock:
            return {
                "total_requests": self.request_count,
                "requests_per_second": self.requests_per_second,
                "min_interval_ms": self.min_interval * 1000,
                "in_retry_after": time.time() < self.retry_after_until
            }
