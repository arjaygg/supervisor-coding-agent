import time
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Set
import re
import html
import urllib.parse
from supervisor_agent.config import settings
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    def __init__(self, app):
        super().__init__(app)
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self' ws: wss:; "
                "frame-ancestors 'none'"
            )
        }
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Add security headers
        for header, value in self.security_headers.items():
            response.headers[header] = value
        
        # Add cache control for sensitive endpoints
        if request.url.path.startswith("/api/v1/auth"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        
        return response


class InputValidationMiddleware(BaseHTTPMiddleware):
    """Validate and sanitize input to prevent injection attacks"""
    
    def __init__(self, app):
        super().__init__(app)
        
        # Patterns for detecting potential attacks
        self.sql_injection_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)",
            r"(-{2}|#|\*|/\*|\*/)",
            r"(\b(OR|AND)\s+\w+\s*=\s*\w+)",
            r"('|(\')|(\"|(\")))",
        ]
        
        self.xss_patterns = [
            r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe\b",
            r"<object\b",
            r"<embed\b",
        ]
        
        self.command_injection_patterns = [
            r"[;&|`$()]",
            r"\b(cat|ls|pwd|whoami|ps|netstat|grep|find|echo|rm|mkdir|chmod|chown)\b",
        ]
        
        # Compile patterns for better performance
        self.compiled_sql_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.sql_injection_patterns]
        self.compiled_xss_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.xss_patterns]
        self.compiled_cmd_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.command_injection_patterns]
    
    async def dispatch(self, request: Request, call_next):
        # Skip validation for certain endpoints if needed
        if not settings.security_enabled:
            return await call_next(request)
        
        # Skip validation for health checks and development endpoints
        health_endpoints = ["/api/v1/health", "/api/v1/ping", "/api/v1/healthz", 
                           "/api/v1/health/detailed", "/health", "/ping", "/healthz"]
        if request.url.path in health_endpoints:
            return await call_next(request)
        
        # Validate request method
        if request.method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}:
            logger.warning(f"Invalid HTTP method: {request.method}")
            return JSONResponse(
                status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
                content={"detail": "Method not allowed"}
            )
        
        # Validate headers
        try:
            await self._validate_headers(request)
        except HTTPException as e:
            logger.warning(f"Header validation failed: {e.detail}")
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
        
        # Validate query parameters
        try:
            await self._validate_query_params(request)
        except HTTPException as e:
            logger.warning(f"Query parameter validation failed: {e.detail}")
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
        
        # For POST/PUT/PATCH requests, validate body
        if request.method in {"POST", "PUT", "PATCH"}:
            try:
                await self._validate_request_body(request)
            except HTTPException as e:
                logger.warning(f"Request body validation failed: {e.detail}")
                return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
        
        return await call_next(request)
    
    async def _validate_headers(self, request: Request):
        """Validate request headers for malicious content"""
        suspicious_headers = []
        
        for name, value in request.headers.items():
            # Check for excessively long header values
            if len(value) > 8192:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Header {name} too long"
                )
            
            # Check for potential injection in headers
            if self._contains_malicious_patterns(value):
                suspicious_headers.append(name)
        
        if suspicious_headers:
            logger.warning(f"Suspicious headers detected: {suspicious_headers}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid header content detected"
            )
        
        # Validate User-Agent
        user_agent = request.headers.get("user-agent", "")
        if len(user_agent) > 512:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User-Agent header too long"
            )
    
    async def _validate_query_params(self, request: Request):
        """Validate query parameters"""
        for param, value in request.query_params.items():
            # Check parameter name
            if len(param) > 256 or not re.match(r'^[a-zA-Z0-9_\-\.]+$', param):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid parameter name: {param}"
                )
            
            # Check parameter value
            if isinstance(value, str):
                if len(value) > 4096:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Parameter {param} value too long"
                    )
                
                # Decode URL-encoded value for better detection
                try:
                    decoded_value = urllib.parse.unquote(value)
                    if self._contains_malicious_patterns(decoded_value):
                        logger.warning(f"Malicious pattern in parameter {param}: {value}")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid parameter content detected"
                        )
                except Exception:
                    # If decoding fails, check original value
                    if self._contains_malicious_patterns(value):
                        logger.warning(f"Malicious pattern in parameter {param}: {value}")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid parameter content detected"
                        )
    
    async def _validate_request_body(self, request: Request):
        """Validate request body for malicious content"""
        # Note: This is a basic check. For production, consider using
        # more sophisticated body parsing and validation
        content_type = request.headers.get("content-type", "")
        
        # Check content length
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length > 10 * 1024 * 1024:  # 10MB limit
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Request body too large"
                    )
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid Content-Length header"
                )
        
        # For JSON content, we'll let FastAPI handle parsing
        # and validate after parsing in request handlers
        
        # For form data, validate here
        if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            # FastAPI will parse this, so we'll validate in the endpoint handlers
            pass
    
    def _contains_malicious_patterns(self, text: str) -> bool:
        """Check if text contains malicious patterns"""
        if not text:
            return False
        
        text_lower = text.lower()
        
        # Check SQL injection patterns
        for pattern in self.compiled_sql_patterns:
            if pattern.search(text_lower):
                return True
        
        # Check XSS patterns
        for pattern in self.compiled_xss_patterns:
            if pattern.search(text_lower):
                return True
        
        # Check command injection patterns
        for pattern in self.compiled_cmd_patterns:
            if pattern.search(text_lower):
                return True
        
        return False


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log requests for security monitoring"""
    
    def __init__(self, app):
        super().__init__(app)
        self.sensitive_headers = {
            "authorization", "cookie", "x-api-key", 
            "x-auth-token", "x-csrf-token"
        }
        self.sensitive_paths = {
            "/api/v1/auth/login", "/api/v1/auth/register",
            "/api/v1/auth/change-password", "/api/v1/auth/reset-password"
        }
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log request
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Sanitize headers for logging
        logged_headers = {}
        for name, value in request.headers.items():
            if name.lower() in self.sensitive_headers:
                logged_headers[name] = "[REDACTED]"
            else:
                logged_headers[name] = value[:100]  # Truncate long headers
        
        request_info = {
            "method": request.method,
            "path": str(request.url.path),
            "query": str(request.url.query) if request.url.query else None,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "headers": logged_headers if request.url.path not in self.sensitive_paths else "[REDACTED]"
        }
        
        logger.info(f"Request started: {request_info}")
        
        # Process request
        try:
            response = await call_next(request)
            
            # Log response
            duration = time.time() - start_time
            logger.info(
                f"Request completed: {request.method} {request.url.path} "
                f"- Status: {response.status_code} - Duration: {duration:.3f}s"
            )
            
            # Log security events
            if response.status_code >= 400:
                logger.warning(
                    f"HTTP error response: {request.method} {request.url.path} "
                    f"- Status: {response.status_code} - Client: {client_ip}"
                )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"- Error: {str(e)} - Duration: {duration:.3f}s - Client: {client_ip}"
            )
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """Get real client IP considering reverse proxies"""
        # Check for real IP in headers (set by reverse proxy)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs, take the first one
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        return getattr(request.client, "host", "unknown")


def sanitize_input(text: str) -> str:
    """Sanitize input text to prevent XSS"""
    if not text:
        return text
    
    # HTML escape
    sanitized = html.escape(text)
    
    # Remove any remaining dangerous characters
    sanitized = re.sub(r'[<>"\']', '', sanitized)
    
    return sanitized


def validate_file_upload(filename: str, allowed_extensions: Set[str]) -> bool:
    """Validate file upload"""
    if not filename:
        return False
    
    # Check for directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        return False
    
    # Check extension
    extension = filename.lower().split('.')[-1] if '.' in filename else ''
    return extension in allowed_extensions


def is_safe_redirect_url(url: str, allowed_hosts: Set[str]) -> bool:
    """Check if redirect URL is safe"""
    if not url:
        return False
    
    # Prevent open redirects
    if url.startswith("//") or "://" in url:
        # Extract host from URL
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc in allowed_hosts
        except Exception:
            return False
    
    # Relative URLs are generally safe
    return url.startswith("/") and not url.startswith("//")