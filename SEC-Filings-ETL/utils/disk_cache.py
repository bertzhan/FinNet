"""
Disk-based TTL cache for SEC API responses.

Reduces SEC API calls by caching company submissions data on disk.
"""
import json
import hashlib
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any
import structlog

from config.settings import settings

logger = structlog.get_logger()


class DiskCache:
    """
    Disk-based cache with TTL (Time-To-Live) support.

    Cache entries are stored as JSON files with metadata including
    creation time for TTL validation.
    """

    def __init__(self, cache_dir: str = ".cache/sec_api", ttl_hours: int = 12):
        """
        Initialize disk cache.

        Args:
            cache_dir: Directory to store cache files
            ttl_hours: Time-to-live in hours
        """
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_hours * 3600
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "disk_cache_initialized",
            cache_dir=str(self.cache_dir),
            ttl_hours=ttl_hours
        )

    def _get_cache_key(self, key: str) -> str:
        """
        Generate cache file key from string.

        Args:
            key: Cache key (e.g., "submissions:0000320193")

        Returns:
            SHA256 hash of the key
        """
        return hashlib.sha256(key.encode()).hexdigest()

    def _get_cache_path(self, key: str) -> Path:
        """
        Get cache file path for a key.

        Args:
            key: Cache key

        Returns:
            Path to cache file
        """
        cache_key = self._get_cache_key(key)
        # Use subdirectories to avoid too many files in one directory
        subdir = cache_key[:2]
        cache_path = self.cache_dir / subdir / f"{cache_key}.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        return cache_path

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get value from cache if it exists and is not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            logger.debug("cache_miss", key=key, reason="not_found")
            return None

        try:
            with open(cache_path, 'r') as f:
                cached_data = json.load(f)

            created_at = cached_data.get('created_at', 0)
            current_time = time.time()
            age_seconds = current_time - created_at

            if age_seconds > self.ttl_seconds:
                logger.debug(
                    "cache_miss",
                    key=key,
                    reason="expired",
                    age_hours=age_seconds / 3600
                )
                # Delete expired cache file
                cache_path.unlink()
                return None

            logger.debug(
                "cache_hit",
                key=key,
                age_hours=age_seconds / 3600
            )
            return cached_data.get('value')

        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning(
                "cache_read_error",
                key=key,
                error=str(e)
            )
            return None

    def set(self, key: str, value: Dict[str, Any]) -> bool:
        """
        Store value in cache with current timestamp.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)

        Returns:
            True if successful, False otherwise
        """
        cache_path = self._get_cache_path(key)

        try:
            cached_data = {
                'created_at': time.time(),
                'value': value
            }

            with open(cache_path, 'w') as f:
                json.dump(cached_data, f, separators=(',', ':'))

            logger.debug("cache_write", key=key)
            return True

        except (OSError, TypeError) as e:
            logger.error(
                "cache_write_error",
                key=key,
                error=str(e)
            )
            return False

    def clear_expired(self) -> int:
        """
        Remove all expired cache entries.

        Returns:
            Number of entries removed
        """
        removed_count = 0
        current_time = time.time()

        for cache_file in self.cache_dir.rglob("*.json"):
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)

                created_at = cached_data.get('created_at', 0)
                age_seconds = current_time - created_at

                if age_seconds > self.ttl_seconds:
                    cache_file.unlink()
                    removed_count += 1

            except (json.JSONDecodeError, KeyError, OSError):
                # Remove corrupted cache files
                try:
                    cache_file.unlink()
                    removed_count += 1
                except OSError:
                    pass

        logger.info("cache_expired_cleared", removed_count=removed_count)
        return removed_count

    def clear_all(self) -> int:
        """
        Remove all cache entries.

        Returns:
            Number of entries removed
        """
        removed_count = 0

        for cache_file in self.cache_dir.rglob("*.json"):
            try:
                cache_file.unlink()
                removed_count += 1
            except OSError:
                pass

        logger.info("cache_all_cleared", removed_count=removed_count)
        return removed_count


# Global cache instance
_global_cache: Optional[DiskCache] = None


def get_cache() -> DiskCache:
    """Get or create the global disk cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = DiskCache(ttl_hours=settings.sec_cache_ttl_hours)
    return _global_cache
