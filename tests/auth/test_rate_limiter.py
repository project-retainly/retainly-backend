from unittest.mock import Mock

import pytest
from fastapi import Request

from app.auth.contexts import AuthContext
from app.auth.rate_limiter import CompositeRateLimiter
from app.core.exceptions import AppException


class TestCompositeRateLimiter:
    """Test suite for CompositeRateLimiter with IP and User-based rate limiting"""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request with a test IP address"""
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "192.168.1.100"
        return request

    @pytest.fixture
    def mock_auth_context(self):
        """Create a mock authenticated context"""
        auth_cxt = Mock(spec=AuthContext)
        auth_cxt.user = Mock()
        auth_cxt.user.id = "test-user-123"
        return auth_cxt

    @pytest.fixture
    def rate_limiter(self):
        """Create a rate limiter with 5 requests per minute"""
        return CompositeRateLimiter(key_prefix="test", limit=5, minutes=1)

    # ==================== IP-BASED RATE LIMITING (Unauthenticated) ====================

    async def test_allows_request_within_ip_limit_unauthenticated(
        self, mock_request, rate_limiter, fake_redis_client
    ):
        """Test that requests within IP limit are allowed for unauthenticated users"""
        # Should succeed without raising exception
        result = await rate_limiter(mock_request, auth_cxt=None)
        assert result is True

        # Verify Redis key was created
        ip_key = "limiter:test:ip:192.168.1.100"
        count = await fake_redis_client.get(ip_key)
        assert int(count) == 1

    async def test_blocks_request_exceeding_ip_limit_unauthenticated(
        self, mock_request, rate_limiter, fake_redis_client
    ):
        """Test that requests exceeding IP limit are blocked for unauthenticated users"""
        # Make 5 successful requests
        for _ in range(5):
            await rate_limiter(mock_request, auth_cxt=None)

        # 6th request should fail
        with pytest.raises(AppException) as exc_info:
            await rate_limiter(mock_request, auth_cxt=None)

        # Check the exception was raised with correct error type
        exception = exc_info.value
        assert exception.status_code == 429
        assert "Retry-After" in exception.headers

    async def test_ip_limit_sets_expiry_on_first_request(
        self, mock_request, rate_limiter, fake_redis_client
    ):
        """Test that TTL is set correctly on the first request"""
        await rate_limiter(mock_request, auth_cxt=None)

        ip_key = "limiter:test:ip:192.168.1.100"
        ttl = await fake_redis_client.ttl(ip_key)

        # TTL should be set to 60 seconds (1 minute)
        assert 55 <= ttl <= 60  # Allow small variance

    async def test_ip_limit_handles_zombie_keys(
        self, mock_request, rate_limiter, fake_redis_client
    ):
        """Test that zombie keys (no TTL) are fixed automatically"""
        ip_key = "limiter:test:ip:192.168.1.100"

        # Simulate a zombie key: increment without expiry
        await fake_redis_client.incr(ip_key)
        await fake_redis_client.incr(ip_key)

        # Verify it's a zombie (TTL = -1)
        ttl = await fake_redis_client.ttl(ip_key)
        assert ttl == -1

        # Now call the rate limiter - it should fix the zombie
        await rate_limiter(mock_request, auth_cxt=None)

        # Verify TTL is now set
        ttl = await fake_redis_client.ttl(ip_key)
        assert ttl > 0

    async def test_different_ips_have_independent_limits(
        self, rate_limiter, fake_redis_client
    ):
        """Test that different IP addresses have independent rate limits"""
        # Create two different mock requests with different IPs
        request1 = Mock(spec=Request)
        request1.client = Mock()
        request1.client.host = "192.168.1.100"

        request2 = Mock(spec=Request)
        request2.client = Mock()
        request2.client.host = "192.168.1.200"

        # Exhaust limit for IP1
        for _ in range(5):
            await rate_limiter(request1, auth_cxt=None)

        # IP1 should be blocked
        with pytest.raises(AppException):
            await rate_limiter(request1, auth_cxt=None)

        # IP2 should still work
        result = await rate_limiter(request2, auth_cxt=None)
        assert result is True

    # ==================== USER-BASED RATE LIMITING (Authenticated) ====================

    async def test_allows_request_within_user_limit_authenticated(
        self, mock_request, mock_auth_context, rate_limiter, fake_redis_client
    ):
        """Test that requests within user limit are allowed for authenticated users"""
        result = await rate_limiter(mock_request, auth_cxt=mock_auth_context)
        assert result is True

        # Verify both IP and User keys were created
        ip_key = "limiter:test:ip:192.168.1.100"
        user_key = "limiter:test:user:test-user-123"

        assert await fake_redis_client.get(ip_key) == "1"
        assert await fake_redis_client.get(user_key) == "1"

    async def test_blocks_request_exceeding_user_limit_authenticated(
        self, mock_request, mock_auth_context, rate_limiter, fake_redis_client
    ):
        """Test that requests exceeding user limit are blocked"""
        # Make 5 successful requests
        for _ in range(5):
            await rate_limiter(mock_request, auth_cxt=mock_auth_context)

        # 6th request should fail
        with pytest.raises(AppException) as exc_info:
            await rate_limiter(mock_request, auth_cxt=mock_auth_context)

        exception = exc_info.value
        assert exception.status_code == 429

    async def test_user_limit_persists_across_different_ips(
        self, mock_auth_context, rate_limiter, fake_redis_client
    ):
        """Test that user rate limit applies even when switching IPs"""
        # Create requests from different IPs but same user
        request1 = Mock(spec=Request)
        request1.client = Mock()
        request1.client.host = "192.168.1.100"

        request2 = Mock(spec=Request)
        request2.client = Mock()
        request2.client.host = "192.168.1.200"

        # Make 3 requests from IP1
        for _ in range(3):
            await rate_limiter(request1, auth_cxt=mock_auth_context)

        # Make 2 requests from IP2 (total = 5)
        for _ in range(2):
            await rate_limiter(request2, auth_cxt=mock_auth_context)

        # 6th request from either IP should fail (user limit reached)
        with pytest.raises(AppException) as exc_info:
            await rate_limiter(request2, auth_cxt=mock_auth_context)

        exception = exc_info.value
        assert exception.status_code == 429

    async def test_different_users_have_independent_limits(
        self, rate_limiter, fake_redis_client
    ):
        """Test that different users have independent rate limits"""
        # Create two different auth contexts
        auth_cxt1 = Mock(spec=AuthContext)
        auth_cxt1.user = Mock()
        auth_cxt1.user.id = "user-1"

        auth_cxt2 = Mock(spec=AuthContext)
        auth_cxt2.user = Mock()
        auth_cxt2.user.id = "user-2"

        # Create requests from different IPs to avoid IP limit interference
        request1 = Mock(spec=Request)
        request1.client = Mock()
        request1.client.host = "192.168.1.100"

        request2 = Mock(spec=Request)
        request2.client = Mock()
        request2.client.host = "192.168.1.200"

        # Exhaust limit for user 1
        for _ in range(5):
            await rate_limiter(request1, auth_cxt=auth_cxt1)

        # User 1 should be blocked
        with pytest.raises(AppException):
            await rate_limiter(request1, auth_cxt=auth_cxt1)

        # User 2 should still work
        result = await rate_limiter(request2, auth_cxt=auth_cxt2)
        assert result is True

    # ==================== COMPOSITE BEHAVIOR (IP + USER) ====================

    async def test_blocks_when_ip_limit_exceeded_even_if_user_ok(
        self, rate_limiter, fake_redis_client
    ):
        """Test that IP limit blocks request even if user limit is not exceeded"""
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "192.168.1.100"

        # Create 3 different users from the same IP
        users = []
        for i in range(3):
            auth = Mock(spec=AuthContext)
            auth.user = Mock()
            auth.user.id = f"user-{i}"
            users.append(auth)

        # User 0 makes 2 requests (count = 2)
        await rate_limiter(request, auth_cxt=users[0])
        await rate_limiter(request, auth_cxt=users[0])

        # User 1 makes 2 requests (count = 4)
        await rate_limiter(request, auth_cxt=users[1])
        await rate_limiter(request, auth_cxt=users[1])

        # User 2 makes 1 request (count = 5, at limit)
        await rate_limiter(request, auth_cxt=users[2])

        # 6th request should fail due to IP limit (even though user 2 only made 1 request)
        with pytest.raises(AppException) as exc_info:
            await rate_limiter(request, auth_cxt=users[2])

        exception = exc_info.value
        assert exception.status_code == 429

    async def test_blocks_when_user_limit_exceeded_even_if_ip_ok(
        self, mock_auth_context, rate_limiter, fake_redis_client
    ):
        """Test that user limit blocks request even if IP limit is not exceeded"""
        # Same user from multiple IPs
        requests = []
        for i in range(3):
            req = Mock(spec=Request)
            req.client = Mock()
            req.client.host = f"192.168.1.{100 + i}"
            requests.append(req)

        # Make 2 requests from IP1 (count = 2)
        await rate_limiter(requests[0], auth_cxt=mock_auth_context)
        await rate_limiter(requests[0], auth_cxt=mock_auth_context)

        # Make 2 requests from IP2 (count = 4)
        await rate_limiter(requests[1], auth_cxt=mock_auth_context)
        await rate_limiter(requests[1], auth_cxt=mock_auth_context)

        # Make 1 request from IP3 (count = 5, at limit)
        await rate_limiter(requests[2], auth_cxt=mock_auth_context)

        # 6th request should fail due to user limit
        with pytest.raises(AppException) as exc_info:
            await rate_limiter(requests[2], auth_cxt=mock_auth_context)

        exception = exc_info.value
        assert exception.status_code == 429

    async def test_auth_context_with_no_user_only_checks_ip(
        self, mock_request, rate_limiter, fake_redis_client
    ):
        """Test that auth context without user object only checks IP limit"""
        # Auth context exists but user is None
        auth_cxt = Mock(spec=AuthContext)
        auth_cxt.user = None

        result = await rate_limiter(mock_request, auth_cxt=auth_cxt)
        assert result is True

        # Only IP key should exist
        ip_key = "limiter:test:ip:192.168.1.100"
        assert await fake_redis_client.exists(ip_key) == 1

        # No user key should be created
        keys = await fake_redis_client.keys("limiter:test:user:*")
        assert len(keys) == 0

    # ==================== RETRY-AFTER HEADER ====================

    async def test_retry_after_header_matches_window(
        self, mock_request, rate_limiter, fake_redis_client
    ):
        """Test that Retry-After header is set to the rate limit window"""
        # Exhaust limit
        for _ in range(5):
            await rate_limiter(mock_request, auth_cxt=None)

        # Next request should include Retry-After header
        with pytest.raises(AppException) as exc_info:
            await rate_limiter(mock_request, auth_cxt=None)

        assert exc_info.value.headers["Retry-After"] == "60"  # 1 minute = 60 seconds

    # ==================== CUSTOM CONFIGURATIONS ====================

    async def test_custom_key_prefix(self, mock_request, fake_redis_client):
        """Test that custom key prefix is used correctly"""
        limiter = CompositeRateLimiter(key_prefix="custom_endpoint", limit=3, minutes=5)

        await limiter(mock_request, auth_cxt=None)

        # Verify custom prefix is used
        ip_key = "limiter:custom_endpoint:ip:192.168.1.100"
        assert await fake_redis_client.exists(ip_key) == 1

    async def test_custom_limit_and_window(self, mock_request, fake_redis_client):
        """Test that custom limit and window settings work correctly"""
        # 10 requests per 5 minutes
        limiter = CompositeRateLimiter(key_prefix="test", limit=10, minutes=5)

        # Make 10 requests successfully
        for _ in range(10):
            await limiter(mock_request, auth_cxt=None)

        # 11th should fail
        with pytest.raises(AppException):
            await limiter(mock_request, auth_cxt=None)

        # Verify TTL is 5 minutes (300 seconds)
        ip_key = "limiter:test:ip:192.168.1.100"
        ttl = await fake_redis_client.ttl(ip_key)
        assert 295 <= ttl <= 300

    # ==================== EDGE CASES ====================

    async def test_handles_missing_client_host(self, rate_limiter, fake_redis_client):
        """Test graceful handling when request.client.host is None"""
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = None

        # Should still work (might use "None" as string or handle gracefully)
        # Adjust based on your actual implementation requirements
        result = await rate_limiter(request, auth_cxt=None)
        assert result is True

    async def test_concurrent_requests_accuracy(
        self, mock_auth_context, rate_limiter, fake_redis_client
    ):
        """Test that rate limiter handles concurrent requests correctly"""
        import asyncio

        # Use different IPs for each concurrent request to avoid IP limit
        async def make_request(ip_suffix):
            request = Mock(spec=Request)
            request.client = Mock()
            request.client.host = f"192.168.1.{ip_suffix}"
            return await rate_limiter(request, auth_cxt=mock_auth_context)

        # Simulate 6 concurrent requests from different IPs but same user
        tasks = [make_request(i) for i in range(100, 106)]

        # At least one should fail
        results = await asyncio.gather(*tasks, return_exceptions=True)

        exceptions = [r for r in results if isinstance(r, AppException)]
        successes = [r for r in results if r is True]

        # Should have 5 successes and 1+ failures
        assert len(successes) == 5
        assert len(exceptions) >= 1
        assert all(e.status_code == 429 for e in exceptions)

    async def test_rate_limit_resets_after_window_expires(
        self, mock_request, rate_limiter, fake_redis_client
    ):
        """Test that rate limit resets after the time window expires"""
        # Exhaust the limit
        for _ in range(5):
            await rate_limiter(mock_request, auth_cxt=None)

        # Should be blocked
        with pytest.raises(AppException):
            await rate_limiter(mock_request, auth_cxt=None)

        # Manually expire the key (simulate time passing)
        ip_key = "limiter:test:ip:192.168.1.100"
        await fake_redis_client.delete(ip_key)

        # Should work again
        result = await rate_limiter(mock_request, auth_cxt=None)
        assert result is True
