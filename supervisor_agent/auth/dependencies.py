import json
from datetime import datetime, timezone
from typing import List, Optional, Union

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from supervisor_agent.auth.jwt_handler import jwt_handler
from supervisor_agent.auth.models import (APIKey, SecurityAuditLog, User,
                                          UserSession)
from supervisor_agent.auth.schemas import TokenType, UserResponse
from supervisor_agent.db.database import get_db
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)


class AuthenticationError(HTTPException):
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthorizationError(HTTPException):
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


def log_security_event(
    db: Session,
    action: str,
    user_id: Optional[str] = None,
    resource: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    success: bool = True,
):
    """Log security events for audit trail"""
    try:
        audit_log = SecurityAuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            details=json.dumps(details) if details else None,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
        )
        db.add(audit_log)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log security event: {str(e)}")


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Get current authenticated user from JWT token or API key"""

    if not credentials:
        # Check for API key in headers
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return await authenticate_api_key(request, api_key, db)

        log_security_event(
            db,
            "authentication_failed",
            details={"reason": "no_credentials"},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            success=False,
        )
        raise AuthenticationError("Authentication credentials required")

    return await authenticate_jwt_token(request, credentials.credentials, db)


async def authenticate_jwt_token(request: Request, token: str, db: Session) -> User:
    """Authenticate user with JWT token"""
    # Verify token
    payload = jwt_handler.verify_token(token, TokenType.ACCESS)
    if not payload:
        log_security_event(
            db,
            "token_verification_failed",
            details={"reason": "invalid_token"},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            success=False,
        )
        raise AuthenticationError("Invalid or expired token")

    user_id = payload.get("sub")
    jti = payload.get("jti")

    if not user_id or not jti:
        log_security_event(
            db,
            "token_verification_failed",
            details={"reason": "invalid_payload"},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            success=False,
        )
        raise AuthenticationError("Invalid token payload")

    # Check if session exists and is active
    session = (
        db.query(UserSession)
        .filter(UserSession.token_jti == jti, UserSession.is_active == True)
        .first()
    )

    if not session:
        log_security_event(
            db,
            "session_not_found",
            user_id=user_id,
            details={"jti": jti},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            success=False,
        )
        raise AuthenticationError("Session not found or expired")

    # Get user
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        log_security_event(
            db,
            "user_not_found",
            user_id=user_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            success=False,
        )
        raise AuthenticationError("User not found or inactive")

    # Update session last used
    session.last_used = datetime.now(timezone.utc)
    db.commit()

    return user


async def authenticate_api_key(request: Request, api_key: str, db: Session) -> User:
    """Authenticate user with API key"""
    # Extract prefix for lookup
    if len(api_key) < 8:
        log_security_event(
            db,
            "api_key_invalid",
            details={"reason": "too_short"},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            success=False,
        )
        raise AuthenticationError("Invalid API key format")

    key_prefix = api_key[:8]

    # Find API key in database
    api_key_record = (
        db.query(APIKey)
        .filter(APIKey.key_prefix == key_prefix, APIKey.is_active == True)
        .first()
    )

    if not api_key_record:
        log_security_event(
            db,
            "api_key_not_found",
            details={"prefix": key_prefix},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            success=False,
        )
        raise AuthenticationError("Invalid API key")

    # Verify key
    if not jwt_handler.verify_api_key(api_key, api_key_record.hashed_key):
        log_security_event(
            db,
            "api_key_verification_failed",
            user_id=api_key_record.user_id,
            details={"prefix": key_prefix},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            success=False,
        )
        raise AuthenticationError("Invalid API key")

    # Check expiration
    if api_key_record.expires_at and api_key_record.expires_at < datetime.now(
        timezone.utc
    ):
        log_security_event(
            db,
            "api_key_expired",
            user_id=api_key_record.user_id,
            details={"prefix": key_prefix},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            success=False,
        )
        raise AuthenticationError("API key has expired")

    # Get user
    user = (
        db.query(User)
        .filter(User.id == api_key_record.user_id, User.is_active == True)
        .first()
    )

    if not user:
        log_security_event(
            db,
            "api_key_user_not_found",
            user_id=api_key_record.user_id,
            details={"prefix": key_prefix},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            success=False,
        )
        raise AuthenticationError("User not found or inactive")

    # Update last used
    api_key_record.last_used = datetime.now(timezone.utc)
    db.commit()

    log_security_event(
        db,
        "api_key_authentication_success",
        user_id=user.id,
        details={"prefix": key_prefix},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        success=True,
    )

    return user


def require_permissions(permissions: Union[List[str], str]):
    """Decorator to require specific permissions"""
    if isinstance(permissions, str):
        permissions = [permissions]

    def permission_dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        # Get user permissions
        user_permissions = set()
        for role in current_user.roles:
            for permission in role.permissions:
                user_permissions.add(permission.name)

        # Check if user has required permissions
        missing_permissions = set(permissions) - user_permissions

        if missing_permissions:
            log_security_event(
                db,
                "permission_denied",
                user_id=current_user.id,
                details={
                    "required_permissions": permissions,
                    "missing_permissions": list(missing_permissions),
                },
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                success=False,
            )
            raise AuthorizationError(
                f"Missing permissions: {', '.join(missing_permissions)}"
            )

        return current_user

    return permission_dependency


def require_roles(roles: Union[List[str], str]):
    """Decorator to require specific roles"""
    if isinstance(roles, str):
        roles = [roles]

    def role_dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        # Get user roles
        user_roles = {role.name for role in current_user.roles}

        # Check if user has any of the required roles
        if not any(role in user_roles for role in roles):
            log_security_event(
                db,
                "role_access_denied",
                user_id=current_user.id,
                details={"required_roles": roles, "user_roles": list(user_roles)},
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                success=False,
            )
            raise AuthorizationError(f"Required roles: {', '.join(roles)}")

        return current_user

    return role_dependency


# Convenience functions for common permission checks
def require_admin(current_user: User = Depends(require_roles("admin"))):
    return current_user


def require_user_or_admin(
    current_user: User = Depends(require_roles(["user", "admin"]))
):
    return current_user


# Optional authentication (for public endpoints that can benefit from auth)
async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Get current user if authenticated, None otherwise"""
    try:
        return await get_current_user(request, credentials, db)
    except HTTPException:
        return None
