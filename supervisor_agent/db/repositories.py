"""
Specific repositories using the generic base repository pattern.
Provides specialized CRUD operations while eliminating code duplication.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, desc

from supervisor_agent.db import models, schemas
from supervisor_agent.db.base_repository import (
    BaseRepository, TimestampMixin, StatusMixin, PriorityMixin
)


class TaskRepository(BaseRepository[models.Task, schemas.TaskCreate, schemas.TaskUpdate], 
                     TimestampMixin, StatusMixin, PriorityMixin):
    """Repository for Task operations with specialized methods."""
    
    def __init__(self):
        super().__init__(models.Task)
    
    def get_pending_tasks(self, db: Session, limit: int = 10) -> List[models.Task]:
        """Get pending tasks ordered by priority and creation time."""
        return (
            db.query(self.model)
            .filter(self.model.status == models.TaskStatus.PENDING)
            .order_by(self.model.priority.desc(), self.model.created_at)
            .limit(limit)
            .all()
        )
    
    def get_similar_tasks(
        self, 
        db: Session, 
        task_type: str, 
        hours_back: int = 24
    ) -> List[models.Task]:
        """Get similar tasks within a time window."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        return (
            db.query(self.model)
            .filter(and_(
                self.model.type == task_type, 
                self.model.created_at >= cutoff_time
            ))
            .all()
        )
    
    def get_tasks_by_status(
        self, 
        db: Session, 
        status: Optional[str] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[models.Task]:
        """Get tasks with optional status filtering."""
        query = db.query(self.model)
        if status:
            query = query.filter(self.model.status == status)
        return (
            query.order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )


class TaskSessionRepository(BaseRepository[models.TaskSession, schemas.TaskSessionCreate, schemas.TaskSessionUpdate]):
    """Repository for TaskSession operations."""
    
    def __init__(self):
        super().__init__(models.TaskSession)
    
    def get_task_sessions(self, db: Session, task_id: int) -> List[models.TaskSession]:
        """Get all sessions for a specific task."""
        return (
            db.query(self.model)
            .filter(self.model.task_id == task_id)
            .order_by(self.model.created_at)
            .all()
        )


class AgentRepository(BaseRepository[models.Agent, schemas.AgentCreate, schemas.AgentUpdate],
                      StatusMixin):
    """Repository for Agent operations with availability checks."""
    
    def __init__(self):
        super().__init__(models.Agent)
    
    def get_active_agents(self, db: Session) -> List[models.Agent]:
        """Get all active agents."""
        return self.get_active(db, active_field='is_active')
    
    def get_available_agents(self, db: Session) -> List[models.Agent]:
        """Get agents that are available for new tasks."""
        now = datetime.now(timezone.utc)
        return (
            db.query(self.model)
            .filter(and_(
                self.model.is_active == True,
                self.model.quota_used < self.model.quota_limit,
                self.model.quota_reset_at > now,
            ))
            .all()
        )


class AuditLogRepository(BaseRepository[models.AuditLog, schemas.AuditLogCreate, schemas.AuditLogUpdate],
                         TimestampMixin):
    """Repository for AuditLog operations with event filtering."""
    
    def __init__(self):
        super().__init__(models.AuditLog)
    
    def get_logs_by_event(
        self, 
        db: Session, 
        event_type: Optional[str] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[models.AuditLog]:
        """Get audit logs with optional event type filtering."""
        query = db.query(self.model)
        if event_type:
            query = query.filter(self.model.event_type == event_type)
        return (
            query.order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )


class CostTrackingRepository(BaseRepository[models.CostTrackingEntry, schemas.CostTrackingCreate, schemas.CostTrackingUpdate],
                             TimestampMixin):
    """Repository for CostTracking operations with aggregation methods."""
    
    def __init__(self):
        super().__init__(models.CostTrackingEntry)
    
    def get_cost_by_agent(
        self, 
        db: Session, 
        agent_id: str,
        hours_back: int = 24
    ) -> List[models.CostTrackingEntry]:
        """Get cost tracking entries for a specific agent."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        return (
            db.query(self.model)
            .filter(and_(
                self.model.agent_id == agent_id,
                self.model.created_at >= cutoff_time
            ))
            .order_by(desc(self.model.created_at))
            .all()
        )


class ProviderRepository(BaseRepository[models.Provider, schemas.ProviderCreate, schemas.ProviderUpdate],
                         StatusMixin):
    """Repository for Provider operations with health and status management."""
    
    def __init__(self):
        super().__init__(models.Provider)
    
    def get_healthy_providers(self, db: Session) -> List[models.Provider]:
        """Get providers that are currently healthy."""
        return (
            db.query(self.model)
            .filter(self.model.health_status.in_(['healthy', 'degraded']))
            .all()
        )
    
    def get_providers_by_type(
        self, 
        db: Session, 
        provider_type: str
    ) -> List[models.Provider]:
        """Get providers by type."""
        return self.get_multi_by_field(db, 'provider_type', provider_type)


# Create repository instances for easy import
task_repository = TaskRepository()
task_session_repository = TaskSessionRepository()
agent_repository = AgentRepository()
audit_log_repository = AuditLogRepository()
cost_tracking_repository = CostTrackingRepository()
provider_repository = ProviderRepository()


# Backward compatibility - create wrapper classes that match the old CRUD interface
class TaskCRUD:
    """Backward compatibility wrapper for TaskRepository."""
    
    @staticmethod
    def create_task(db: Session, task: schemas.TaskCreate) -> models.Task:
        return task_repository.create(db, task)
    
    @staticmethod
    def get_task(db: Session, task_id: int) -> Optional[models.Task]:
        return task_repository.get(db, task_id)
    
    @staticmethod
    def get_tasks(
        db: Session, skip: int = 0, limit: int = 100, status: Optional[str] = None
    ) -> List[models.Task]:
        return task_repository.get_tasks_by_status(db, status, skip, limit)
    
    @staticmethod
    def update_task(
        db: Session, task_id: int, task_update: schemas.TaskUpdate
    ) -> Optional[models.Task]:
        return task_repository.update_by_id(db, id=task_id, obj_in=task_update)
    
    @staticmethod
    def get_pending_tasks(db: Session, limit: int = 10) -> List[models.Task]:
        return task_repository.get_pending_tasks(db, limit)
    
    @staticmethod
    def get_similar_tasks(
        db: Session, task_type: str, hours_back: int = 24
    ) -> List[models.Task]:
        return task_repository.get_similar_tasks(db, task_type, hours_back)


class TaskSessionCRUD:
    """Backward compatibility wrapper for TaskSessionRepository."""
    
    @staticmethod
    def create_session(
        db: Session, session: schemas.TaskSessionCreate
    ) -> models.TaskSession:
        return task_session_repository.create(db, session)
    
    @staticmethod
    def get_task_sessions(db: Session, task_id: int) -> List[models.TaskSession]:
        return task_session_repository.get_task_sessions(db, task_id)


class AgentCRUD:
    """Backward compatibility wrapper for AgentRepository."""
    
    @staticmethod
    def create_agent(db: Session, agent: schemas.AgentCreate) -> models.Agent:
        return agent_repository.create(db, agent)
    
    @staticmethod
    def get_agent(db: Session, agent_id: str) -> Optional[models.Agent]:
        return agent_repository.get(db, agent_id)
    
    @staticmethod
    def get_active_agents(db: Session) -> List[models.Agent]:
        return agent_repository.get_active_agents(db)
    
    @staticmethod
    def update_agent(
        db: Session, agent_id: str, agent_update: schemas.AgentUpdate
    ) -> Optional[models.Agent]:
        return agent_repository.update_by_id(db, id=agent_id, obj_in=agent_update)
    
    @staticmethod
    def get_available_agents(db: Session) -> List[models.Agent]:
        return agent_repository.get_available_agents(db)


class AuditLogCRUD:
    """Backward compatibility wrapper for AuditLogRepository."""
    
    @staticmethod
    def create_log(db: Session, log: schemas.AuditLogCreate) -> models.AuditLog:
        return audit_log_repository.create(db, log)
    
    @staticmethod
    def get_logs(
        db: Session, skip: int = 0, limit: int = 100, event_type: Optional[str] = None
    ) -> List[models.AuditLog]:
        return audit_log_repository.get_logs_by_event(db, event_type, skip, limit)


class ProviderCRUD:
    """Backward compatibility wrapper for ProviderRepository."""
    
    @staticmethod
    def create_provider(db: Session, provider: schemas.ProviderCreate) -> models.Provider:
        return provider_repository.create(db, provider)
    
    @staticmethod
    def get_provider(db: Session, provider_id: int) -> Optional[models.Provider]:
        return provider_repository.get(db, provider_id)
    
    @staticmethod
    def get_providers(
        db: Session, skip: int = 0, limit: int = 100
    ) -> List[models.Provider]:
        return provider_repository.get_multi(db, skip=skip, limit=limit)
    
    @staticmethod
    def update_provider(
        db: Session, provider_id: int, provider_update: schemas.ProviderUpdate
    ) -> Optional[models.Provider]:
        return provider_repository.update_by_id(db, id=provider_id, obj_in=provider_update)
    
    @staticmethod
    def get_healthy_providers(db: Session) -> List[models.Provider]:
        return provider_repository.get_healthy_providers(db)
    
    @staticmethod
    def get_providers_by_type(
        db: Session, provider_type: str
    ) -> List[models.Provider]:
        return provider_repository.get_providers_by_type(db, provider_type)


class ProviderUsageCRUD:
    """Backward compatibility wrapper for provider usage operations."""
    
    @staticmethod
    def create_usage_log(db: Session, usage: schemas.CostTrackingCreate) -> models.CostTrackingEntry:
        return cost_tracking_repository.create(db, usage)
    
    @staticmethod
    def get_usage_by_agent(
        db: Session, agent_id: str, hours_back: int = 24
    ) -> List[models.CostTrackingEntry]:
        return cost_tracking_repository.get_cost_by_agent(db, agent_id, hours_back)