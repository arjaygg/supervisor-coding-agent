from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user" 
    VIEWER = "viewer"
    API_USER = "api_user"


class Permission(BaseModel):
    id: str
    name: str
    resource: str
    action: str
    description: Optional[str] = None


class Role(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    permissions: List[Permission] = []
    is_system_role: bool = False


class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: Optional[str] = None
    roles: List[str] = []


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    roles: Optional[List[str]] = None


class UserResponse(UserBase):
    id: str
    is_active: bool
    is_verified: bool
    oauth_provider: Optional[str] = None
    roles: List[Role] = []
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    username: str = Field(..., description="Username or email")
    password: str = Field(..., min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class OAuthTokenRequest(BaseModel):
    provider: str = Field(..., description="OAuth provider (google, github)")
    code: str = Field(..., description="Authorization code from OAuth provider")
    redirect_uri: Optional[str] = None


class APIKeyCreate(BaseModel):
    name: str = Field(..., description="Human-readable name for the API key")
    expires_at: Optional[datetime] = None
    scopes: Optional[List[str]] = None


class APIKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    is_active: bool
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    scopes: Optional[List[str]] = None
    created_at: datetime


class APIKeyWithSecret(APIKeyResponse):
    key: str  # Only returned on creation


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class SecurityAuditLogResponse(BaseModel):
    id: int
    user_id: Optional[str] = None
    action: str
    resource: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: List[str] = []


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None


class PermissionCreate(BaseModel):
    name: str
    resource: str
    action: str
    description: Optional[str] = None