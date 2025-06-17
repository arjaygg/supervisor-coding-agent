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
        db_session = models.TaskSession(**session.model_dump())
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
        db_agent = models.Agent(**agent.model_dump())
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
        db_log = models.AuditLog(**log.model_dump())
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


class CostTrackingCRUD:
    @staticmethod
    def create_cost_entry(db: Session, entry: schemas.CostTrackingEntryCreate) -> models.CostTrackingEntry:
        db_entry = models.CostTrackingEntry(**entry.model_dump())
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)
        return db_entry
    
    @staticmethod
    def get_cost_entries(db: Session, skip: int = 0, limit: int = 100, 
                        task_id: Optional[int] = None, agent_id: Optional[str] = None) -> List[models.CostTrackingEntry]:
        query = db.query(models.CostTrackingEntry)
        if task_id:
            query = query.filter(models.CostTrackingEntry.task_id == task_id)
        if agent_id:
            query = query.filter(models.CostTrackingEntry.agent_id == agent_id)
        return query.order_by(desc(models.CostTrackingEntry.timestamp)).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_cost_summary(db: Session, start_date: Optional[datetime] = None, 
                        end_date: Optional[datetime] = None) -> Dict[str, Any]:
        query = db.query(models.CostTrackingEntry)
        
        if start_date:
            query = query.filter(models.CostTrackingEntry.timestamp >= start_date)
        if end_date:
            query = query.filter(models.CostTrackingEntry.timestamp <= end_date)
        
        entries = query.all()
        
        if not entries:
            return {
                "total_cost_usd": "0.00",
                "total_tokens": 0,
                "total_requests": 0,
                "avg_cost_per_request": "0.00",
                "avg_tokens_per_request": 0.0,
                "cost_by_agent": {},
                "cost_by_task_type": {},
                "daily_breakdown": []
            }
        
        # Calculate totals
        total_cost = sum(float(entry.estimated_cost_usd) for entry in entries)
        total_tokens = sum(entry.total_tokens for entry in entries)
        total_requests = len(entries)
        
        # Calculate averages
        avg_cost_per_request = total_cost / total_requests if total_requests > 0 else 0
        avg_tokens_per_request = total_tokens / total_requests if total_requests > 0 else 0
        
        # Cost by agent
        cost_by_agent = {}
        for entry in entries:
            agent_cost = cost_by_agent.get(entry.agent_id, 0)
            cost_by_agent[entry.agent_id] = agent_cost + float(entry.estimated_cost_usd)
        
        # Convert to strings for precision
        cost_by_agent = {k: f"{v:.4f}" for k, v in cost_by_agent.items()}
        
        # Cost by task type (need to join with tasks table)
        cost_by_task_type = {}
        task_entries = db.query(models.CostTrackingEntry, models.Task).join(
            models.Task, models.CostTrackingEntry.task_id == models.Task.id
        )
        
        if start_date:
            task_entries = task_entries.filter(models.CostTrackingEntry.timestamp >= start_date)
        if end_date:
            task_entries = task_entries.filter(models.CostTrackingEntry.timestamp <= end_date)
        
        for cost_entry, task in task_entries.all():
            task_type_cost = cost_by_task_type.get(task.type, 0)
            cost_by_task_type[task.type] = task_type_cost + float(cost_entry.estimated_cost_usd)
        
        cost_by_task_type = {k: f"{v:.4f}" for k, v in cost_by_task_type.items()}
        
        # Daily breakdown (last 30 days)
        from sqlalchemy import func, Float
        daily_data = db.query(
            func.date(models.CostTrackingEntry.timestamp).label('date'),
            func.count(models.CostTrackingEntry.id).label('requests'),
            func.sum(models.CostTrackingEntry.total_tokens).label('tokens'),
            func.sum(func.cast(models.CostTrackingEntry.estimated_cost_usd, Float)).label('cost')
        ).group_by(func.date(models.CostTrackingEntry.timestamp))
        
        if start_date:
            daily_data = daily_data.filter(models.CostTrackingEntry.timestamp >= start_date)
        if end_date:
            daily_data = daily_data.filter(models.CostTrackingEntry.timestamp <= end_date)
        
        daily_breakdown = []
        for row in daily_data.all():
            daily_breakdown.append({
                "date": row.date.isoformat() if row.date else None,
                "requests": row.requests or 0,
                "tokens": row.tokens or 0,
                "cost": f"{row.cost:.4f}" if row.cost else "0.0000"
            })
        
        return {
            "total_cost_usd": f"{total_cost:.4f}",
            "total_tokens": total_tokens,
            "total_requests": total_requests,
            "avg_cost_per_request": f"{avg_cost_per_request:.4f}",
            "avg_tokens_per_request": avg_tokens_per_request,
            "cost_by_agent": cost_by_agent,
            "cost_by_task_type": cost_by_task_type,
            "daily_breakdown": daily_breakdown
        }


class UsageMetricsCRUD:
    @staticmethod
    def create_metric(db: Session, metric: schemas.UsageMetricsCreate) -> models.UsageMetrics:
        db_metric = models.UsageMetrics(**metric.model_dump())
        db.add(db_metric)
        db.commit()
        db.refresh(db_metric)
        return db_metric
    
    @staticmethod
    def get_metrics(db: Session, metric_type: Optional[str] = None, 
                   skip: int = 0, limit: int = 100) -> List[models.UsageMetrics]:
        query = db.query(models.UsageMetrics)
        if metric_type:
            query = query.filter(models.UsageMetrics.metric_type == metric_type)
        return query.order_by(desc(models.UsageMetrics.timestamp)).offset(skip).limit(limit).all()
    
    @staticmethod
    def upsert_metric(db: Session, metric_type: str, metric_key: str, 
                     update_data: Dict[str, Any]) -> models.UsageMetrics:
        """Update existing metric or create new one"""
        existing = db.query(models.UsageMetrics).filter(
            models.UsageMetrics.metric_type == metric_type,
            models.UsageMetrics.metric_key == metric_key
        ).first()
        
        if existing:
            for key, value in update_data.items():
                setattr(existing, key, value)
            db.commit()
            db.refresh(existing)
            return existing
        else:
            new_metric = models.UsageMetrics(
                metric_type=metric_type,
                metric_key=metric_key,
                **update_data
            )
            db.add(new_metric)
            db.commit()
            db.refresh(new_metric)
            return new_metric