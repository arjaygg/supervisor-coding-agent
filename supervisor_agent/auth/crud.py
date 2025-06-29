from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from supervisor_agent.auth.jwt_handler import jwt_handler
from supervisor_agent.auth.models import (APIKey, Permission, Role,
                                          SecurityAuditLog, User, UserSession,
                                          role_permissions, user_roles)
from supervisor_agent.auth.schemas import (APIKeyCreate, PermissionCreate,
                                           RoleCreate, RoleUpdate, UserCreate,
                                           UserUpdate)
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class UserCRUD:
    @staticmethod
    def get_user(db: Session, user_id: str) -> Optional[User]:
        return (
            db.query(User)
            .options(joinedload(User.roles).joinedload(Role.permissions))
            .filter(User.id == user_id)
            .first()
        )

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        return (
            db.query(User)
            .options(joinedload(User.roles).joinedload(Role.permissions))
            .filter(User.email == email)
            .first()
        )

    @staticmethod
    def get_user_by_username(db: Session, username: str) -> Optional[User]:
        return (
            db.query(User)
            .options(joinedload(User.roles).joinedload(Role.permissions))
            .filter(User.username == username)
            .first()
        )

    @staticmethod
    def get_user_by_username_or_email(db: Session, identifier: str) -> Optional[User]:
        return (
            db.query(User)
            .options(joinedload(User.roles).joinedload(Role.permissions))
            .filter(or_(User.username == identifier, User.email == identifier))
            .first()
        )

    @staticmethod
    def get_users(
        db: Session, skip: int = 0, limit: int = 100, is_active: Optional[bool] = None
    ) -> List[User]:
        query = db.query(User).options(
            joinedload(User.roles).joinedload(Role.permissions)
        )

        if is_active is not None:
            query = query.filter(User.is_active == is_active)

        return query.offset(skip).limit(limit).all()

    @staticmethod
    def create_user(db: Session, user: UserCreate) -> User:
        # Hash password if provided
        hashed_password = None
        if user.password:
            hashed_password = jwt_handler.hash_password(user.password)

        db_user = User(
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            hashed_password=hashed_password,
        )

        db.add(db_user)
        db.flush()  # Get the user ID

        # Add roles if specified
        if user.roles:
            roles = db.query(Role).filter(Role.name.in_(user.roles)).all()
            db_user.roles = roles

        db.commit()
        db.refresh(db_user)
        return db_user

    @staticmethod
    def update_user(
        db: Session, user_id: str, user_update: UserUpdate
    ) -> Optional[User]:
        db_user = UserCRUD.get_user(db, user_id)
        if not db_user:
            return None

        # Update fields
        update_data = user_update.model_dump(exclude_unset=True)

        # Handle roles separately
        if "roles" in update_data:
            role_names = update_data.pop("roles")
            roles = db.query(Role).filter(Role.name.in_(role_names)).all()
            db_user.roles = roles

        # Update other fields
        for field, value in update_data.items():
            setattr(db_user, field, value)

        db.commit()
        db.refresh(db_user)
        return db_user

    @staticmethod
    def delete_user(db: Session, user_id: str) -> bool:
        db_user = UserCRUD.get_user(db, user_id)
        if not db_user:
            return False

        # Soft delete by deactivating
        db_user.is_active = False
        db.commit()
        return True

    @staticmethod
    def change_password(db: Session, user_id: str, new_password: str) -> bool:
        db_user = UserCRUD.get_user(db, user_id)
        if not db_user:
            return False

        db_user.hashed_password = jwt_handler.hash_password(new_password)
        db.commit()
        return True

    @staticmethod
    def update_last_login(db: Session, user_id: str):
        db_user = UserCRUD.get_user(db, user_id)
        if db_user:
            db_user.last_login = datetime.now(timezone.utc)
            db.commit()


class RoleCRUD:
    @staticmethod
    def get_role(db: Session, role_id: str) -> Optional[Role]:
        return (
            db.query(Role)
            .options(joinedload(Role.permissions))
            .filter(Role.id == role_id)
            .first()
        )

    @staticmethod
    def get_role_by_name(db: Session, name: str) -> Optional[Role]:
        return (
            db.query(Role)
            .options(joinedload(Role.permissions))
            .filter(Role.name == name)
            .first()
        )

    @staticmethod
    def get_roles(db: Session, skip: int = 0, limit: int = 100) -> List[Role]:
        return (
            db.query(Role)
            .options(joinedload(Role.permissions))
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def create_role(db: Session, role: RoleCreate) -> Role:
        db_role = Role(name=role.name, description=role.description)

        db.add(db_role)
        db.flush()

        # Add permissions if specified
        if role.permissions:
            permissions = (
                db.query(Permission).filter(Permission.name.in_(role.permissions)).all()
            )
            db_role.permissions = permissions

        db.commit()
        db.refresh(db_role)
        return db_role

    @staticmethod
    def update_role(
        db: Session, role_id: str, role_update: RoleUpdate
    ) -> Optional[Role]:
        db_role = RoleCRUD.get_role(db, role_id)
        if not db_role or db_role.is_system_role:
            return None

        update_data = role_update.model_dump(exclude_unset=True)

        # Handle permissions separately
        if "permissions" in update_data:
            permission_names = update_data.pop("permissions")
            permissions = (
                db.query(Permission).filter(Permission.name.in_(permission_names)).all()
            )
            db_role.permissions = permissions

        # Update other fields
        for field, value in update_data.items():
            setattr(db_role, field, value)

        db.commit()
        db.refresh(db_role)
        return db_role

    @staticmethod
    def delete_role(db: Session, role_id: str) -> bool:
        db_role = RoleCRUD.get_role(db, role_id)
        if not db_role or db_role.is_system_role:
            return False

        db.delete(db_role)
        db.commit()
        return True


class PermissionCRUD:
    @staticmethod
    def get_permission(db: Session, permission_id: str) -> Optional[Permission]:
        return db.query(Permission).filter(Permission.id == permission_id).first()

    @staticmethod
    def get_permission_by_name(db: Session, name: str) -> Optional[Permission]:
        return db.query(Permission).filter(Permission.name == name).first()

    @staticmethod
    def get_permissions(
        db: Session, skip: int = 0, limit: int = 100
    ) -> List[Permission]:
        return db.query(Permission).offset(skip).limit(limit).all()

    @staticmethod
    def create_permission(db: Session, permission: PermissionCreate) -> Permission:
        db_permission = Permission(
            name=permission.name,
            resource=permission.resource,
            action=permission.action,
            description=permission.description,
        )

        db.add(db_permission)
        db.commit()
        db.refresh(db_permission)
        return db_permission

    @staticmethod
    def delete_permission(db: Session, permission_id: str) -> bool:
        db_permission = PermissionCRUD.get_permission(db, permission_id)
        if not db_permission:
            return False

        db.delete(db_permission)
        db.commit()
        return True


class SessionCRUD:
    @staticmethod
    def create_session(
        db: Session,
        user_id: str,
        access_jti: str,
        refresh_jti: str,
        expires_at: datetime,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UserSession:
        session = UserSession(
            user_id=user_id,
            token_jti=access_jti,
            refresh_token_jti=refresh_jti,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def get_session_by_jti(db: Session, jti: str) -> Optional[UserSession]:
        return (
            db.query(UserSession)
            .filter(UserSession.token_jti == jti, UserSession.is_active == True)
            .first()
        )

    @staticmethod
    def get_session_by_refresh_jti(
        db: Session, refresh_jti: str
    ) -> Optional[UserSession]:
        return (
            db.query(UserSession)
            .filter(
                UserSession.refresh_token_jti == refresh_jti,
                UserSession.is_active == True,
            )
            .first()
        )

    @staticmethod
    def deactivate_session(db: Session, jti: str) -> bool:
        session = SessionCRUD.get_session_by_jti(db, jti)
        if not session:
            return False

        session.is_active = False
        db.commit()
        return True

    @staticmethod
    def deactivate_user_sessions(db: Session, user_id: str) -> int:
        """Deactivate all sessions for a user"""
        count = (
            db.query(UserSession)
            .filter(UserSession.user_id == user_id, UserSession.is_active == True)
            .update({"is_active": False})
        )

        db.commit()
        return count

    @staticmethod
    def cleanup_expired_sessions(db: Session) -> int:
        """Remove expired sessions"""
        now = datetime.now(timezone.utc)
        count = db.query(UserSession).filter(UserSession.expires_at < now).delete()

        db.commit()
        return count


class APIKeyCRUD:
    @staticmethod
    def create_api_key(
        db: Session, user_id: str, api_key_create: APIKeyCreate
    ) -> tuple[APIKey, str]:
        # Generate API key
        full_key, prefix, hashed_key = jwt_handler.generate_api_key()

        api_key = APIKey(
            user_id=user_id,
            name=api_key_create.name,
            key_prefix=prefix,
            hashed_key=hashed_key,
            expires_at=api_key_create.expires_at,
            scopes=api_key_create.scopes,
        )

        db.add(api_key)
        db.commit()
        db.refresh(api_key)

        return api_key, full_key

    @staticmethod
    def get_api_keys(db: Session, user_id: str) -> List[APIKey]:
        return (
            db.query(APIKey)
            .filter(APIKey.user_id == user_id, APIKey.is_active == True)
            .all()
        )

    @staticmethod
    def get_api_key(db: Session, api_key_id: str) -> Optional[APIKey]:
        return db.query(APIKey).filter(APIKey.id == api_key_id).first()

    @staticmethod
    def delete_api_key(db: Session, api_key_id: str, user_id: str) -> bool:
        api_key = (
            db.query(APIKey)
            .filter(APIKey.id == api_key_id, APIKey.user_id == user_id)
            .first()
        )

        if not api_key:
            return False

        api_key.is_active = False
        db.commit()
        return True


def initialize_default_permissions(db: Session):
    """Initialize default permissions for the system"""
    default_permissions = [
        # Task permissions
        ("tasks:create", "tasks", "create", "Create new tasks"),
        ("tasks:read", "tasks", "read", "View tasks"),
        ("tasks:update", "tasks", "update", "Update tasks"),
        ("tasks:delete", "tasks", "delete", "Delete tasks"),
        ("tasks:execute", "tasks", "execute", "Execute tasks"),
        # Workflow permissions
        ("workflows:create", "workflows", "create", "Create workflows"),
        ("workflows:read", "workflows", "read", "View workflows"),
        ("workflows:update", "workflows", "update", "Update workflows"),
        ("workflows:delete", "workflows", "delete", "Delete workflows"),
        ("workflows:execute", "workflows", "execute", "Execute workflows"),
        # Analytics permissions
        ("analytics:read", "analytics", "read", "View analytics"),
        ("analytics:export", "analytics", "export", "Export analytics data"),
        # Provider permissions
        ("providers:read", "providers", "read", "View providers"),
        ("providers:manage", "providers", "manage", "Manage providers"),
        # Admin permissions
        ("users:create", "users", "create", "Create users"),
        ("users:read", "users", "read", "View users"),
        ("users:update", "users", "update", "Update users"),
        ("users:delete", "users", "delete", "Delete users"),
        ("roles:manage", "roles", "manage", "Manage roles and permissions"),
        ("system:admin", "system", "admin", "System administration"),
    ]

    for name, resource, action, description in default_permissions:
        if not PermissionCRUD.get_permission_by_name(db, name):
            PermissionCRUD.create_permission(
                db,
                PermissionCreate(
                    name=name, resource=resource, action=action, description=description
                ),
            )

    logger.info("Default permissions initialized")


def initialize_default_roles(db: Session):
    """Initialize default roles for the system"""
    # Admin role with all permissions
    admin_permissions = [
        "tasks:create",
        "tasks:read",
        "tasks:update",
        "tasks:delete",
        "tasks:execute",
        "workflows:create",
        "workflows:read",
        "workflows:update",
        "workflows:delete",
        "workflows:execute",
        "analytics:read",
        "analytics:export",
        "providers:read",
        "providers:manage",
        "users:create",
        "users:read",
        "users:update",
        "users:delete",
        "roles:manage",
        "system:admin",
    ]

    # Regular user role
    user_permissions = [
        "tasks:create",
        "tasks:read",
        "tasks:update",
        "tasks:execute",
        "workflows:create",
        "workflows:read",
        "workflows:update",
        "workflows:execute",
        "analytics:read",
        "providers:read",
    ]

    # Viewer role (read-only)
    viewer_permissions = [
        "tasks:read",
        "workflows:read",
        "analytics:read",
        "providers:read",
    ]

    # API user role (for service-to-service)
    api_user_permissions = [
        "tasks:create",
        "tasks:read",
        "tasks:update",
        "tasks:execute",
        "workflows:create",
        "workflows:read",
        "workflows:update",
        "workflows:execute",
    ]

    roles_to_create = [
        ("admin", "System Administrator", admin_permissions, True),
        ("user", "Regular User", user_permissions, True),
        ("viewer", "Read-only Viewer", viewer_permissions, True),
        ("api_user", "API Service User", api_user_permissions, True),
    ]

    for name, description, permissions, is_system in roles_to_create:
        if not RoleCRUD.get_role_by_name(db, name):
            role = RoleCRUD.create_role(
                db,
                RoleCreate(name=name, description=description, permissions=permissions),
            )
            role.is_system_role = is_system
            db.commit()

    logger.info("Default roles initialized")
