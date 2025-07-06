import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import jwt
from passlib.context import CryptContext

from supervisor_agent.auth.schemas import TokenType, UserResponse
from supervisor_agent.config import settings
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class JWTHandler:
    def __init__(self):
        self.secret_key = settings.jwt_secret_key
        self.algorithm = settings.jwt_algorithm
        self.access_token_expire_minutes = settings.jwt_access_token_expire_minutes
        self.refresh_token_expire_days = settings.jwt_refresh_token_expire_days

    def create_access_token(
        self,
        user_id: str,
        username: str,
        roles: List[str],
        permissions: List[str],
        expires_delta: Optional[timedelta] = None,
    ) -> tuple[str, str]:
        """Create JWT access token and return (token, jti)"""
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=self.access_token_expire_minutes
            )

        jti = secrets.token_urlsafe(32)

        payload = {
            "sub": user_id,
            "username": username,
            "roles": roles,
            "permissions": permissions,
            "type": TokenType.ACCESS.value,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "jti": jti,
        }

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token, jti

    def create_refresh_token(
        self,
        user_id: str,
        username: str,
        expires_delta: Optional[timedelta] = None,
    ) -> tuple[str, str]:
        """Create JWT refresh token and return (token, jti)"""
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                days=self.refresh_token_expire_days
            )

        jti = secrets.token_urlsafe(32)

        payload = {
            "sub": user_id,
            "username": username,
            "type": TokenType.REFRESH.value,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "jti": jti,
        }

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token, jti

    def verify_token(
        self, token: str, token_type: Optional[TokenType] = None
    ) -> Optional[Dict[str, Any]]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Check token type if specified
            if token_type and payload.get("type") != token_type.value:
                logger.warning(
                    f"Token type mismatch: expected {token_type.value}, got {payload.get('type')}"
                )
                return None

            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {str(e)}")
            return None

    def get_token_jti(self, token: str) -> Optional[str]:
        """Extract JTI from token without full verification"""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": False},
            )
            return payload.get("jti")
        except jwt.InvalidTokenError:
            return None

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(plain_password, hashed_password)

    def generate_api_key(self) -> tuple[str, str, str]:
        """Generate API key and return (full_key, prefix, hashed_key)"""
        # Generate a secure random key
        key = secrets.token_urlsafe(32)
        prefix = key[:8]  # First 8 characters for identification
        hashed_key = self.hash_password(key)

        return key, prefix, hashed_key

    def verify_api_key(self, key: str, hashed_key: str) -> bool:
        """Verify API key against hash"""
        return self.verify_password(key, hashed_key)


# Global JWT handler instance
jwt_handler = JWTHandler()


def create_token_pair(user: UserResponse) -> Dict[str, Any]:
    """Create access and refresh token pair for user"""
    # Extract role names and permissions
    role_names = [role.name for role in user.roles]
    permissions = []
    for role in user.roles:
        permissions.extend([perm.name for perm in role.permissions])

    # Remove duplicates
    permissions = list(set(permissions))

    # Create tokens
    access_token, access_jti = jwt_handler.create_access_token(
        user_id=user.id,
        username=user.username,
        roles=role_names,
        permissions=permissions,
    )

    refresh_token, refresh_jti = jwt_handler.create_refresh_token(
        user_id=user.id, username=user.username
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "access_jti": access_jti,
        "refresh_jti": refresh_jti,
        "expires_in": jwt_handler.access_token_expire_minutes * 60,
        "token_type": "bearer",
    }
