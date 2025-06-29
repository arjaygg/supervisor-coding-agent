from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from supervisor_agent.auth.crud import (
    APIKeyCRUD,
    PermissionCRUD,
    RoleCRUD,
    SessionCRUD,
    UserCRUD,
    initialize_default_permissions,
    initialize_default_roles,
)
from supervisor_agent.auth.dependencies import (
    get_current_user,
    log_security_event,
    require_admin,
    require_permissions,
    require_user_or_admin,
)
from supervisor_agent.auth.jwt_handler import create_token_pair, jwt_handler
from supervisor_agent.auth.models import SecurityAuditLog, User
from supervisor_agent.auth.schemas import (
    APIKeyCreate,
    APIKeyResponse,
    APIKeyWithSecret,
    LoginRequest,
    PasswordChangeRequest,
    Permission,
    PermissionCreate,
    RefreshTokenRequest,
    Role,
    RoleCreate,
    RoleUpdate,
    SecurityAuditLogResponse,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from supervisor_agent.db.database import get_db
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse)
async def register(
    request: Request, user_create: UserCreate, db: Session = Depends(get_db)
):
    """Register a new user"""
    # Check if user already exists
    if UserCRUD.get_user_by_email(db, user_create.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    if UserCRUD.get_user_by_username(db, user_create.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken"
        )

    # Create user with default 'user' role if no roles specified
    if not user_create.roles:
        user_create.roles = ["user"]

    user = UserCRUD.create_user(db, user_create)

    log_security_event(
        db,
        "user_registered",
        user_id=user.id,
        details={"email": user.email, "username": user.username},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Login with username/email and password"""
    # Find user by username or email
    user = UserCRUD.get_user_by_username_or_email(db, form_data.username)

    if not user or not user.hashed_password:
        log_security_event(
            db,
            "login_failed",
            details={"username": form_data.username, "reason": "user_not_found"},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            success=False,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    # Verify password
    if not jwt_handler.verify_password(form_data.password, user.hashed_password):
        log_security_event(
            db,
            "login_failed",
            user_id=user.id,
            details={"username": form_data.username, "reason": "invalid_password"},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            success=False,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    if not user.is_active:
        log_security_event(
            db,
            "login_failed",
            user_id=user.id,
            details={"username": form_data.username, "reason": "user_inactive"},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            success=False,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is inactive"
        )

    # Create token pair
    user_response = UserResponse.model_validate(user)
    token_data = create_token_pair(user_response)

    # Create session
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=jwt_handler.refresh_token_expire_days
    )
    SessionCRUD.create_session(
        db,
        user_id=user.id,
        access_jti=token_data["access_jti"],
        refresh_jti=token_data["refresh_jti"],
        expires_at=expires_at,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    # Update last login
    UserCRUD.update_last_login(db, user.id)

    log_security_event(
        db,
        "login_success",
        user_id=user.id,
        details={"username": form_data.username},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return TokenResponse(
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        token_type=token_data["token_type"],
        expires_in=token_data["expires_in"],
        user=user_response,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    refresh_request: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    """Refresh access token using refresh token"""
    # Verify refresh token
    payload = jwt_handler.verify_token(refresh_request.refresh_token)
    if not payload:
        log_security_event(
            db,
            "token_refresh_failed",
            details={"reason": "invalid_token"},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            success=False,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    user_id = payload.get("sub")
    refresh_jti = payload.get("jti")

    # Check session
    session = SessionCRUD.get_session_by_refresh_jti(db, refresh_jti)
    if not session:
        log_security_event(
            db,
            "token_refresh_failed",
            user_id=user_id,
            details={"reason": "session_not_found"},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            success=False,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session not found"
        )

    # Get user
    user = UserCRUD.get_user(db, user_id)
    if not user or not user.is_active:
        log_security_event(
            db,
            "token_refresh_failed",
            user_id=user_id,
            details={"reason": "user_not_found_or_inactive"},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            success=False,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Create new token pair
    user_response = UserResponse.model_validate(user)
    token_data = create_token_pair(user_response)

    # Update session with new tokens
    session.token_jti = token_data["access_jti"]
    session.refresh_token_jti = token_data["refresh_jti"]
    session.last_used = datetime.now(timezone.utc)
    db.commit()

    log_security_event(
        db,
        "token_refresh_success",
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return TokenResponse(
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        token_type=token_data["token_type"],
        expires_in=token_data["expires_in"],
        user=user_response,
    )


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Logout current user"""
    # Get token from request
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    if token:
        jti = jwt_handler.get_token_jti(token)
        if jti:
            SessionCRUD.deactivate_session(db, jti)

    log_security_event(
        db,
        "logout",
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return {"message": "Successfully logged out"}


@router.post("/logout-all")
async def logout_all(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Logout from all devices"""
    count = SessionCRUD.deactivate_user_sessions(db, current_user.id)

    log_security_event(
        db,
        "logout_all",
        user_id=current_user.id,
        details={"sessions_deactivated": count},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return {"message": f"Successfully logged out from {count} sessions"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    request: Request,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update current user information"""
    # Users can't change their own roles
    if hasattr(user_update, "roles") and user_update.roles is not None:
        user_update.roles = None

    updated_user = UserCRUD.update_user(db, current_user.id, user_update)

    log_security_event(
        db,
        "user_updated",
        user_id=current_user.id,
        details={
            "updated_fields": list(user_update.model_dump(exclude_unset=True).keys())
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return UserResponse.model_validate(updated_user)


@router.post("/change-password")
async def change_password(
    request: Request,
    password_change: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change user password"""
    if not current_user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no password set (OAuth user)",
        )

    # Verify current password
    if not jwt_handler.verify_password(
        password_change.current_password, current_user.hashed_password
    ):
        log_security_event(
            db,
            "password_change_failed",
            user_id=current_user.id,
            details={"reason": "invalid_current_password"},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            success=False,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Change password
    UserCRUD.change_password(db, current_user.id, password_change.new_password)

    # Logout from other sessions for security
    SessionCRUD.deactivate_user_sessions(db, current_user.id)

    log_security_event(
        db,
        "password_changed",
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return {"message": "Password changed successfully"}


# API Key management
@router.post("/api-keys", response_model=APIKeyWithSecret)
async def create_api_key(
    request: Request,
    api_key_create: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new API key"""
    api_key, full_key = APIKeyCRUD.create_api_key(db, current_user.id, api_key_create)

    log_security_event(
        db,
        "api_key_created",
        user_id=current_user.id,
        details={"api_key_name": api_key_create.name, "prefix": api_key.key_prefix},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    response = APIKeyWithSecret.model_validate(api_key)
    response.key = full_key
    return response


@router.get("/api-keys", response_model=List[APIKeyResponse])
async def get_api_keys(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get user's API keys"""
    api_keys = APIKeyCRUD.get_api_keys(db, current_user.id)
    return [APIKeyResponse.model_validate(key) for key in api_keys]


@router.delete("/api-keys/{api_key_id}")
async def delete_api_key(
    request: Request,
    api_key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an API key"""
    success = APIKeyCRUD.delete_api_key(db, api_key_id, current_user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
        )

    log_security_event(
        db,
        "api_key_deleted",
        user_id=current_user.id,
        details={"api_key_id": api_key_id},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return {"message": "API key deleted successfully"}


# Admin endpoints
@router.get("/users", response_model=List[UserResponse])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    current_user: User = Depends(require_permissions("users:read")),
    db: Session = Depends(get_db),
):
    """Get users (admin only)"""
    users = UserCRUD.get_users(db, skip=skip, limit=limit, is_active=is_active)
    return [UserResponse.model_validate(user) for user in users]


@router.post("/users", response_model=UserResponse)
async def create_user_admin(
    request: Request,
    user_create: UserCreate,
    current_user: User = Depends(require_permissions("users:create")),
    db: Session = Depends(get_db),
):
    """Create user (admin only)"""
    # Check if user already exists
    if UserCRUD.get_user_by_email(db, user_create.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    if UserCRUD.get_user_by_username(db, user_create.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken"
        )

    user = UserCRUD.create_user(db, user_create)

    log_security_event(
        db,
        "user_created_by_admin",
        user_id=current_user.id,
        details={"created_user_id": user.id, "email": user.email},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return UserResponse.model_validate(user)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user_admin(
    request: Request,
    user_id: str,
    user_update: UserUpdate,
    current_user: User = Depends(require_permissions("users:update")),
    db: Session = Depends(get_db),
):
    """Update user (admin only)"""
    updated_user = UserCRUD.update_user(db, user_id, user_update)

    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    log_security_event(
        db,
        "user_updated_by_admin",
        user_id=current_user.id,
        details={
            "updated_user_id": user_id,
            "updated_fields": list(user_update.model_dump(exclude_unset=True).keys()),
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return UserResponse.model_validate(updated_user)


@router.delete("/users/{user_id}")
async def delete_user_admin(
    request: Request,
    user_id: str,
    current_user: User = Depends(require_permissions("users:delete")),
    db: Session = Depends(get_db),
):
    """Delete user (admin only)"""
    success = UserCRUD.delete_user(db, user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    log_security_event(
        db,
        "user_deleted_by_admin",
        user_id=current_user.id,
        details={"deleted_user_id": user_id},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return {"message": "User deleted successfully"}


# Role management
@router.get("/roles", response_model=List[Role])
async def get_roles(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_permissions("roles:manage")),
    db: Session = Depends(get_db),
):
    """Get roles (admin only)"""
    roles = RoleCRUD.get_roles(db, skip=skip, limit=limit)
    return [Role.model_validate(role) for role in roles]


@router.post("/roles", response_model=Role)
async def create_role(
    request: Request,
    role_create: RoleCreate,
    current_user: User = Depends(require_permissions("roles:manage")),
    db: Session = Depends(get_db),
):
    """Create role (admin only)"""
    if RoleCRUD.get_role_by_name(db, role_create.name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Role name already exists"
        )

    role = RoleCRUD.create_role(db, role_create)

    log_security_event(
        db,
        "role_created",
        user_id=current_user.id,
        details={"role_name": role_create.name},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return Role.model_validate(role)


@router.get("/permissions", response_model=List[Permission])
async def get_permissions(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_permissions("roles:manage")),
    db: Session = Depends(get_db),
):
    """Get permissions (admin only)"""
    permissions = PermissionCRUD.get_permissions(db, skip=skip, limit=limit)
    return [Permission.model_validate(perm) for perm in permissions]


@router.get("/audit-logs", response_model=List[SecurityAuditLogResponse])
async def get_audit_logs(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_permissions("system:admin")),
    db: Session = Depends(get_db),
):
    """Get security audit logs (admin only)"""
    logs = (
        db.query(SecurityAuditLog)
        .order_by(SecurityAuditLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [SecurityAuditLogResponse.model_validate(log) for log in logs]


@router.post("/initialize-defaults")
async def initialize_defaults(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Initialize default permissions and roles"""
    initialize_default_permissions(db)
    initialize_default_roles(db)

    log_security_event(
        db,
        "defaults_initialized",
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return {"message": "Default permissions and roles initialized"}
