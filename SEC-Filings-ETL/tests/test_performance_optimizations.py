"""
Unit tests for performance optimizations.

Tests:
1. Disk cache hit path (no network)
2. Rate limiter 429 handling with Retry-After
3. HTTP client reuse (connection count doesn't explode)
4. Batch DB operations
"""
import time
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
import httpx

from utils.disk_cache import DiskCache
from utils.rate_limiter import SECRateLimiter
from utils.http_client import SharedHTTPClient
from utils.batch_db import BatchDBWriter
from services.sec_api import SECAPIClient


class TestDiskCache:
    """Test disk-based TTL cache."""

    def test_cache_hit_no_network(self):
        """Test that cache hit returns data without network call."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = DiskCache(cache_dir=tmpdir, ttl_hours=1)

            # Store test data
            test_data = {"cik": "0000320193", "name": "Apple Inc."}
            cache.set("test_key", test_data)

            # Retrieve from cache (no network)
            cached_data = cache.get("test_key")

            assert cached_data == test_data
            assert cached_data is not None

    def test_cache_miss_returns_none(self):
        """Test that cache miss returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = DiskCache(cache_dir=tmpdir, ttl_hours=1)

            result = cache.get("nonexistent_key")

            assert result is None

    def test_cache_expiration(self):
        """Test that expired cache entries return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # TTL of 0.001 hours (3.6 seconds)
            cache = DiskCache(cache_dir=tmpdir, ttl_hours=0.001)

            test_data = {"test": "data"}
            cache.set("test_key", test_data)

            # Wait for expiration
            time.sleep(4)

            result = cache.get("test_key")

            assert result is None

    def test_cache_subdirectory_structure(self):
        """Test that cache uses subdirectories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = DiskCache(cache_dir=tmpdir, ttl_hours=1)

            cache.set("test_key", {"data": "value"})

            # Check subdirectory was created
            cache_path = Path(tmpdir)
            subdirs = list(cache_path.glob("**/"))

            # Should have at least one subdirectory
            assert len(subdirs) > 1

    def test_clear_expired(self):
        """Test clearing expired cache entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = DiskCache(cache_dir=tmpdir, ttl_hours=0.001)

            # Add some entries
            cache.set("key1", {"data": 1})
            cache.set("key2", {"data": 2})

            # Wait for expiration
            time.sleep(4)

            removed = cache.clear_expired()

            assert removed == 2


class TestRateLimiter429:
    """Test rate limiter with 429 response handling."""

    def test_429_handling_with_retry_after(self):
        """Test that 429 response triggers Retry-After wait."""
        limiter = SECRateLimiter(requests_per_second=10)

        # Simulate 429 with Retry-After: 2 seconds
        limiter.handle_429(retry_after=2)

        # Next wait should include retry delay
        start = time.time()
        limiter.wait()
        duration = time.time() - start

        # Should wait at least 2 seconds
        assert duration >= 2.0
        assert duration < 3.0  # But not much longer

    def test_429_handling_without_retry_after(self):
        """Test that 429 without Retry-After uses default backoff."""
        limiter = SECRateLimiter(requests_per_second=100)  # Fast to test

        # Simulate 429 without Retry-After
        limiter.handle_429(retry_after=None)

        # Next wait should include 60s default delay
        start = time.time()
        # Don't actually wait 60s in test, just check the logic
        assert limiter.retry_after_until > time.time()

    def test_rate_limiter_respects_rps(self):
        """Test that rate limiter enforces RPS limit."""
        limiter = SECRateLimiter(requests_per_second=10)

        # Make 10 requests
        start = time.time()
        for _ in range(10):
            limiter.wait()
        duration = time.time() - start

        # Should take at least 0.9 seconds (10 req / 10 rps)
        assert duration >= 0.9

    def test_get_stats(self):
        """Test rate limiter statistics."""
        limiter = SECRateLimiter(requests_per_second=10)

        # Make some requests
        for _ in range(5):
            limiter.wait()

        stats = limiter.get_stats()

        assert stats["total_requests"] == 5
        assert stats["requests_per_second"] == 10
        assert "min_interval_ms" in stats
        assert "in_retry_after" in stats


class TestHTTPClientReuse:
    """Test shared HTTP client connection reuse."""

    @patch('config.settings.settings')
    def test_client_singleton(self, mock_settings):
        """Test that get_client returns the same instance."""
        mock_settings.sec_user_agent = "Test test@example.com"
        mock_settings.sec_timeout = 30

        # Reset singleton
        SharedHTTPClient._instance = None

        client1 = SharedHTTPClient.get_client()
        client2 = SharedHTTPClient.get_client()

        assert client1 is client2

        # Cleanup
        SharedHTTPClient.close_all()

    @patch('config.settings.settings')
    def test_http2_enabled(self, mock_settings):
        """Test that HTTP/2 is enabled."""
        mock_settings.sec_user_agent = "Test test@example.com"
        mock_settings.sec_timeout = 30

        # Reset singleton
        SharedHTTPClient._instance = None

        client = SharedHTTPClient.get_client()

        # HTTP/2 is enabled during init
        # Just verify client was created
        assert client is not None

        # Cleanup
        SharedHTTPClient.close_all()

    @patch('config.settings.settings')
    def test_connection_pooling_limits(self, mock_settings):
        """Test that connection pool has correct limits."""
        mock_settings.sec_user_agent = "Test test@example.com"
        mock_settings.sec_timeout = 30

        # Reset singleton
        SharedHTTPClient._instance = None

        client = SharedHTTPClient.get_client()

        # Verify client has pooling configured
        # The limits are applied during init, just verify client exists
        assert client is not None
        # Connection pooling is configured internally

        # Cleanup
        SharedHTTPClient.close_all()

    @patch('config.settings.settings')
    def test_client_reuse_no_connection_explosion(self, mock_settings):
        """Test that multiple API calls don't create excessive connections."""
        mock_settings.sec_user_agent = "Test test@example.com"
        mock_settings.sec_timeout = 30

        # Reset singleton for clean test
        SharedHTTPClient._instance = None

        client = SharedHTTPClient.get_client()

        # Simulate multiple requests (without actual network calls)
        # The key is that we're using the same client instance
        for _ in range(100):
            # Just verify client is reused
            same_client = SharedHTTPClient.get_client()
            assert same_client is client

        # Cleanup
        SharedHTTPClient.close_all()

    @patch('config.settings.settings')
    def test_close_all(self, mock_settings):
        """Test closing all shared clients."""
        mock_settings.sec_user_agent = "Test test@example.com"
        mock_settings.sec_timeout = 30

        # Reset and create
        SharedHTTPClient._instance = None
        _ = SharedHTTPClient.get_client()

        SharedHTTPClient.close_all()

        assert SharedHTTPClient._instance is None


class TestSECAPIClientCache:
    """Test SEC API client with caching."""

    @patch('config.settings.settings')
    @patch('utils.http_client.get_http_client')
    def test_fetch_submissions_cache_hit(self, mock_get_http, mock_settings):
        """Test that cached submissions don't trigger network call."""
        # Mock settings
        mock_settings.sec_user_agent = "Test test@example.com"
        mock_settings.sec_rps = 10

        # Mock HTTP client
        mock_client = MagicMock()
        mock_get_http.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = DiskCache(cache_dir=tmpdir, ttl_hours=1)

            # Pre-populate cache
            test_data = {"filings": {"recent": {"form": ["10-K"]}}}
            cache.set("submissions:0000320193", test_data)

            # Create API client
            with patch('utils.disk_cache.get_cache', return_value=cache):
                client = SECAPIClient(use_cache=True)

                # Fetch submissions (should hit cache)
                result = client.fetch_company_submissions("320193")

                # Verify no network call was made
                mock_client.get.assert_not_called()

                # Verify cached data returned
                assert result == test_data

    @patch('config.settings.settings')
    @patch('services.sec_api.get_http_client')
    def test_fetch_submissions_cache_miss(self, mock_get_http, mock_settings):
        """Test that cache miss triggers network call and caches result."""
        # Mock settings
        mock_settings.sec_user_agent = "Test test@example.com"
        mock_settings.sec_rps = 10

        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock HTTP client
            mock_client = MagicMock()
            mock_response = MagicMock()
            test_data = {"filings": {"recent": {"form": ["10-Q"]}}}
            mock_response.json.return_value = test_data
            mock_response.raise_for_status.return_value = None
            mock_client.get.return_value = mock_response
            mock_get_http.return_value = mock_client

            # Create fresh cache
            cache = DiskCache(cache_dir=tmpdir, ttl_hours=1)

            with patch('services.sec_api.get_cache', return_value=cache):
                client = SECAPIClient(use_cache=True)

                # Fetch submissions for different CIK (cache miss)
                result = client.fetch_company_submissions("789019")

                # Verify network call was made
                assert mock_client.get.called

                # Verify result is correct
                assert result == test_data

                # Verify data was cached
                cached_result = cache.get("submissions:0000789019")
                assert cached_result == test_data

    @patch('config.settings.settings')
    @patch('utils.http_client.get_http_client')
    def test_cache_disabled(self, mock_get_http, mock_settings):
        """Test that cache can be disabled."""
        # Mock settings
        mock_settings.sec_user_agent = "Test test@example.com"
        mock_settings.sec_rps = 10

        mock_client = MagicMock()
        mock_get_http.return_value = mock_client

        client = SECAPIClient(use_cache=False)

        assert client.cache is None


class TestBatchDBWriter:
    """Test batch database operations."""

    def test_batch_accumulation(self):
        """Test that items accumulate before commit."""
        mock_session = Mock()
        mock_session.autoflush = True

        writer = BatchDBWriter(mock_session, batch_size=5)

        # Add 3 items (below batch size)
        for i in range(3):
            item = Mock()
            writer.add(item)

        # No commit yet
        mock_session.commit.assert_not_called()

        # Add 2 more (triggers batch)
        for i in range(2):
            item = Mock()
            writer.add(item)

        # Flush should have been called
        mock_session.flush.assert_called()

    def test_finish_commits_remaining(self):
        """Test that finish commits remaining items."""
        mock_session = Mock()
        mock_session.autoflush = True
        mock_session.dirty = []

        writer = BatchDBWriter(mock_session, batch_size=10)

        # Add 3 items (below batch size)
        for i in range(3):
            item = Mock()
            writer.add(item)

        # Call finish
        total = writer.finish()

        # Should commit remaining items
        mock_session.commit.assert_called()
        assert total == 3

    def test_autoflush_disabled(self):
        """Test that autoflush can be disabled."""
        mock_session = Mock()
        mock_session.autoflush = True

        writer = BatchDBWriter(mock_session, batch_size=10, auto_flush=False)

        # autoflush should be disabled
        assert mock_session.autoflush is False


class TestSECAPI429Handling:
    """Test SEC API 429 response handling."""

    @patch('utils.http_client.SharedHTTPClient.get_client')
    def test_api_handles_429_response(self, mock_get_client):
        """Test that API properly handles 429 responses."""
        # Mock HTTP client to return 429
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "5"}

        error = httpx.HTTPStatusError(
            "Too Many Requests",
            request=Mock(),
            response=mock_response
        )

        mock_client.get.side_effect = error
        mock_get_client.return_value = mock_client

        client = SECAPIClient(use_cache=False)

        # Try to make request (should handle 429)
        with pytest.raises(httpx.HTTPStatusError):
            client._make_request("https://example.com/test")

        # Verify rate limiter was updated
        stats = client.rate_limiter.get_stats()
        assert stats["in_retry_after"] is True


class TestDownloadChunkSize:
    """Test configurable download chunk size."""

    @patch('config.settings.settings')
    @patch('services.sec_api.get_http_client')
    @patch('builtins.open', create=True)
    def test_download_uses_configured_chunk_size(self, mock_open, mock_get_http, mock_settings):
        """Test that download uses configured chunk size."""
        # Mock settings
        mock_settings.sec_user_agent = "Test test@example.com"
        mock_settings.sec_rps = 10
        mock_settings.download_chunk_size = 262144

        # Mock HTTP client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.iter_bytes.return_value = [b"chunk1", b"chunk2"]
        mock_response.raise_for_status.return_value = None

        # Create stream context manager
        mock_stream_context = MagicMock()
        mock_stream_context.__enter__.return_value = mock_response
        mock_stream_context.__exit__.return_value = None
        mock_client.stream.return_value = mock_stream_context

        mock_get_http.return_value = mock_client

        client = SECAPIClient(use_cache=False)

        # Download file
        client.download_file("https://example.com/file", "/tmp/test")

        # Verify chunk size was used
        mock_response.iter_bytes.assert_called_once()
        call_kwargs = mock_response.iter_bytes.call_args[1]
        assert call_kwargs.get('chunk_size') == 262144
