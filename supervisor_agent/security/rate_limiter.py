import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from fastapi import HTTPException, Request, status
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from supervisor_agent.config import settings
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RateLimitEntry:
    """Track rate limit state for a client"""

    count: int = 0
    window_start: float = field(default_factory=time.time)
    burst_count: int = 0
    burst_window_start: float = field(default_factory=time.time)


class TokenBucketRateLimiter:
    """Token bucket rate limiter with burst support"""

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_limit: int = 120,
        window_duration: int = 60,
        burst_window: int = 10,
    ):
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit
        self.window_duration = window_duration
        self.burst_window = burst_window
        self.clients: Dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._lock = asyncio.Lock()

    async def is_allowed(self, client_id: str) -> Tuple[bool, Dict[str, any]]:
        """Check if request is allowed and return rate limit info"""
        async with self._lock:
            now = time.time()
            entry = self.clients[client_id]

            # Reset window if expired
            if now - entry.window_start >= self.window_duration:
                entry.count = 0
                entry.window_start = now

            # Reset burst window if expired
            if now - entry.burst_window_start >= self.burst_window:
                entry.burst_count = 0
                entry.burst_window_start = now

            # Check burst limit first
            if entry.burst_count >= self.burst_limit:
                return False, {
                    "error": "burst_limit_exceeded",
                    "burst_limit": self.burst_limit,
                    "burst_window": self.burst_window,
                    "retry_after": self.burst_window - (now - entry.burst_window_start),
                }

            # Check rate limit
            if entry.count >= self.requests_per_minute:
                return False, {
                    "error": "rate_limit_exceeded",
                    "rate_limit": self.requests_per_minute,
                    "window_duration": self.window_duration,
                    "retry_after": self.window_duration - (now - entry.window_start),
                }

            # Allow request
            entry.count += 1
            entry.burst_count += 1

            return True, {
                "remaining": self.requests_per_minute - entry.count,
                "reset_time": entry.window_start + self.window_duration,
                "burst_remaining": self.burst_limit - entry.burst_count,
            }

    async def cleanup_expired_entries(self):
        """Remove expired entries to prevent memory leaks"""
        async with self._lock:
            now = time.time()
            expired_clients = []

            for client_id, entry in self.clients.items():
                if (
                    now - entry.window_start > self.window_duration * 2
                    and now - entry.burst_window_start > self.burst_window * 2
                ):
                    expired_clients.append(client_id)

            for client_id in expired_clients:
                del self.clients[client_id]

            if expired_clients:
                logger.debug(
                    f"Cleaned up {len(expired_clients)} expired rate limit entries"
                )


class SecurityRateLimiter:
    """Security-focused rate limiter with enhanced protections"""

    def __init__(self):
        self.enabled = settings.rate_limit_enabled
        self.general_limiter = TokenBucketRateLimiter(
            requests_per_minute=settings.rate_limit_requests_per_minute,
            burst_limit=settings.rate_limit_burst,
        )

        # Stricter limits for auth endpoints
        self.auth_limiter = TokenBucketRateLimiter(
            requests_per_minute=10,  # More restrictive for auth
            burst_limit=20,
            window_duration=60,
            burst_window=10,
        )

        # Very strict for failed attempts
        self.failure_limiter = TokenBucketRateLimiter(
            requests_per_minute=3,
            burst_limit=5,
            window_duration=300,  # 5 minutes
            burst_window=60,
        )

        # Track suspicious IPs
        self.suspicious_ips: Dict[str, float] = {}
        self.blocked_ips: Dict[str, float] = {}

    def get_client_identifier(self, request: Request) -> str:
        """Get client identifier for rate limiting"""
        # Try to get real IP from headers (for reverse proxy setups)
        real_ip = (
            request.headers.get("X-Real-IP")
            or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or getattr(request.client, "host", "unknown")
        )

        # For authenticated requests, also consider user ID
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user:{user_id}:{real_ip}"

        return f"ip:{real_ip}"

    async def check_rate_limit(
        self, request: Request, endpoint_type: str = "general"
    ) -> Optional[HTTPException]:
        """Check rate limit and return exception if exceeded"""
        if not self.enabled:
            return None

        client_id = self.get_client_identifier(request)
        ip = client_id.split(":")[-1]  # Extract IP

        # Check if IP is blocked
        if ip in self.blocked_ips:
            block_time = self.blocked_ips[ip]
            if time.time() - block_time < 3600:  # 1 hour block
                logger.warning(f"Blocked IP attempted access: {ip}")
                return HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="IP temporarily blocked due to suspicious activity",
                )
            else:
                # Unblock after timeout
                del self.blocked_ips[ip]

        # Select appropriate limiter
        if endpoint_type == "auth":
            limiter = self.auth_limiter
        elif endpoint_type == "failure":
            limiter = self.failure_limiter
        else:
            limiter = self.general_limiter

        allowed, info = await limiter.is_allowed(client_id)

        if not allowed:
            # Track repeated violations
            if ip not in self.suspicious_ips:
                self.suspicious_ips[ip] = time.time()
            else:
                # If same IP has multiple violations, consider blocking
                if time.time() - self.suspicious_ips[ip] < 300:  # 5 minutes
                    self.blocked_ips[ip] = time.time()
                    logger.warning(
                        f"IP blocked for repeated rate limit violations: {ip}"
                    )

            logger.warning(f"Rate limit exceeded for {client_id}: {info}")

            headers = {}
            if "retry_after" in info:
                headers["Retry-After"] = str(int(info["retry_after"]))

            return HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {info.get('error', 'unknown')}",
                headers=headers,
            )

        # Add rate limit headers to response
        request.state.rate_limit_headers = {
            "X-RateLimit-Remaining": str(info.get("remaining", 0)),
            "X-RateLimit-Reset": str(int(info.get("reset_time", 0))),
            "X-RateLimit-Limit": str(limiter.requests_per_minute),
        }

        return None

    async def record_auth_failure(self, request: Request):
        """Record authentication failure for enhanced monitoring"""
        client_id = self.get_client_identifier(request)
        await self.failure_limiter.is_allowed(client_id)

        logger.warning(f"Authentication failure recorded for {client_id}")

    async def cleanup(self):
        """Cleanup expired entries"""
        await self.general_limiter.cleanup_expired_entries()
        await self.auth_limiter.cleanup_expired_entries()
        await self.failure_limiter.cleanup_expired_entries()

        # Cleanup suspicious/blocked IPs
        now = time.time()
        expired_suspicious = [
            ip
            for ip, timestamp in self.suspicious_ips.items()
            if now - timestamp > 3600  # 1 hour
        ]
        for ip in expired_suspicious:
            del self.suspicious_ips[ip]

        expired_blocked = [
            ip
            for ip, timestamp in self.blocked_ips.items()
            if now - timestamp > 3600  # 1 hour
        ]
        for ip in expired_blocked:
            del self.blocked_ips[ip]


# Global rate limiter instance
security_rate_limiter = SecurityRateLimiter()


# Slowapi integration for basic rate limiting
limiter = Limiter(key_func=get_remote_address)


async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware"""
    # Determine endpoint type
    endpoint_type = "general"
    if request.url.path.startswith("/api/v1/auth"):
        endpoint_type = "auth"

    # Check rate limit
    rate_limit_error = await security_rate_limiter.check_rate_limit(
        request, endpoint_type
    )

    if rate_limit_error:
        raise rate_limit_error

    # Process request
    response = await call_next(request)

    # Add rate limit headers
    if hasattr(request.state, "rate_limit_headers"):
        for header, value in request.state.rate_limit_headers.items():
            response.headers[header] = value

    return response


# Background task for cleanup
async def rate_limiter_cleanup_task():
    """Background task to clean up expired rate limit entries"""
    while True:
        try:
            await security_rate_limiter.cleanup()
            await asyncio.sleep(300)  # Clean up every 5 minutes
        except Exception as e:
            logger.error(f"Rate limiter cleanup failed: {str(e)}")
            await asyncio.sleep(60)  # Retry in 1 minute
