from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from supervisor_agent.db import models, schemas


class TaskCRUD:
    @staticmethod
    def create_task(db: Session, task: schemas.TaskCreate) -> models.Task:
        db_task = models.Task(
            type=task.type,
            payload=task.payload,
            priority=task.priority
        )
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        return db_task
    
    @staticmethod
    def get_task(db: Session, task_id: int) -> Optional[models.Task]:
        return db.query(models.Task).filter(models.Task.id == task_id).first()
    
    @staticmethod
    def get_tasks(db: Session, skip: int = 0, limit: int = 100, status: Optional[str] = None) -> List[models.Task]:
        query = db.query(models.Task)
        if status:
            query = query.filter(models.Task.status == status)
        return query.order_by(desc(models.Task.created_at)).offset(skip).limit(limit).all()
    
    @staticmethod
    def update_task(db: Session, task_id: int, task_update: schemas.TaskUpdate) -> Optional[models.Task]:
        db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
        if db_task:
            update_data = task_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_task, field, value)
            db.commit()
            db.refresh(db_task)
        return db_task
    
    @staticmethod
    def get_pending_tasks(db: Session, limit: int = 10) -> List[models.Task]:
        return db.query(models.Task).filter(
            models.Task.status == models.TaskStatus.PENDING
        ).order_by(models.Task.priority.desc(), models.Task.created_at).limit(limit).all()
    
    @staticmethod
    def get_similar_tasks(db: Session, task_type: str, hours_back: int = 24) -> List[models.Task]:
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        return db.query(models.Task).filter(
            and_(
                models.Task.type == task_type,
                models.Task.created_at >= cutoff_time
            )
        ).all()


class TaskSessionCRUD:
    @staticmethod
    def create_session(db: Session, session: schemas.TaskSessionCreate) -> models.TaskSession:
        db_session = models.TaskSession(**session.dict())
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        return db_session
    
    @staticmethod
    def get_task_sessions(db: Session, task_id: int) -> List[models.TaskSession]:
        return db.query(models.TaskSession).filter(
            models.TaskSession.task_id == task_id
        ).order_by(models.TaskSession.created_at).all()


class AgentCRUD:
    @staticmethod
    def create_agent(db: Session, agent: schemas.AgentCreate) -> models.Agent:
        db_agent = models.Agent(**agent.dict())
        db.add(db_agent)
        db.commit()
        db.refresh(db_agent)
        return db_agent
    
    @staticmethod
    def get_agent(db: Session, agent_id: str) -> Optional[models.Agent]:
        return db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    
    @staticmethod
    def get_active_agents(db: Session) -> List[models.Agent]:
        return db.query(models.Agent).filter(models.Agent.is_active == True).all()
    
    @staticmethod
    def update_agent(db: Session, agent_id: str, agent_update: schemas.AgentUpdate) -> Optional[models.Agent]:
        db_agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
        if db_agent:
            update_data = agent_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_agent, field, value)
            db.commit()
            db.refresh(db_agent)
        return db_agent
    
    @staticmethod
    def get_available_agents(db: Session) -> List[models.Agent]:
        now = datetime.utcnow()
        return db.query(models.Agent).filter(
            and_(
                models.Agent.is_active == True,
                models.Agent.quota_used < models.Agent.quota_limit,
                models.Agent.quota_reset_at > now
            )
        ).all()


class AuditLogCRUD:
    @staticmethod
    def create_log(db: Session, log: schemas.AuditLogCreate) -> models.AuditLog:
        db_log = models.AuditLog(**log.dict())
        db.add(db_log)
        db.commit()
        db.refresh(db_log)
        return db_log
    
    @staticmethod
    def get_logs(db: Session, skip: int = 0, limit: int = 100, event_type: Optional[str] = None) -> List[models.AuditLog]:
        query = db.query(models.AuditLog)
        if event_type:
            query = query.filter(models.AuditLog.event_type == event_type)
        return query.order_by(desc(models.AuditLog.timestamp)).offset(skip).limit(limit).all()