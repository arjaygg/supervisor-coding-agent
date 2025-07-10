from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from supervisor_agent.db import models, schemas
from supervisor_agent.db.enums import (
    ChatThreadStatus,
    MessageRole,
    MessageType,
    ProviderStatus,
    ProviderType,
)


class TaskCRUD:
    @staticmethod
    def create_task(db: Session, task: schemas.TaskCreate) -> models.Task:
        db_task = models.Task(
            type=task.type, payload=task.payload, priority=task.priority
        )
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        return db_task

    @staticmethod
    def get_task(db: Session, task_id: int) -> Optional[models.Task]:
        return db.query(models.Task).filter(models.Task.id == task_id).first()

    @staticmethod
    def get_tasks(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
    ) -> List[models.Task]:
        query = db.query(models.Task)
        if status:
            query = query.filter(models.Task.status == status)
        return (
            query.order_by(desc(models.Task.created_at)).offset(skip).limit(limit).all()
        )

    @staticmethod
    def update_task(
        db: Session, task_id: int, task_update: schemas.TaskUpdate
    ) -> Optional[models.Task]:
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
        return (
            db.query(models.Task)
            .filter(models.Task.status == models.TaskStatus.PENDING)
            .order_by(models.Task.priority.desc(), models.Task.created_at)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_similar_tasks(
        db: Session, task_type: str, hours_back: int = 24
    ) -> List[models.Task]:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        return (
            db.query(models.Task)
            .filter(
                and_(
                    models.Task.type == task_type,
                    models.Task.created_at >= cutoff_time,
                )
            )
            .all()
        )


class TaskSessionCRUD:
    @staticmethod
    def create_session(
        db: Session, session: schemas.TaskSessionCreate
    ) -> models.TaskSession:
        db_session = models.TaskSession(**session.model_dump())
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        return db_session

    @staticmethod
    def get_task_sessions(db: Session, task_id: int) -> List[models.TaskSession]:
        return (
            db.query(models.TaskSession)
            .filter(models.TaskSession.task_id == task_id)
            .order_by(models.TaskSession.created_at)
            .all()
        )


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
    def update_agent(
        db: Session, agent_id: str, agent_update: schemas.AgentUpdate
    ) -> Optional[models.Agent]:
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
        now = datetime.now(timezone.utc)
        return (
            db.query(models.Agent)
            .filter(
                and_(
                    models.Agent.is_active == True,
                    models.Agent.quota_used < models.Agent.quota_limit,
                    models.Agent.quota_reset_at > now,
                )
            )
            .all()
        )


class AuditLogCRUD:
    @staticmethod
    def create_log(db: Session, log: schemas.AuditLogCreate) -> models.AuditLog:
        db_log = models.AuditLog(**log.model_dump())
        db.add(db_log)
        db.commit()
        db.refresh(db_log)
        return db_log

    @staticmethod
    def get_logs(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        event_type: Optional[str] = None,
    ) -> List[models.AuditLog]:
        query = db.query(models.AuditLog)
        if event_type:
            query = query.filter(models.AuditLog.event_type == event_type)
        return (
            query.order_by(desc(models.AuditLog.timestamp))
            .offset(skip)
            .limit(limit)
            .all()
        )


class CostTrackingCRUD:
    @staticmethod
    def create_cost_entry(
        db: Session, entry: schemas.CostTrackingEntryCreate
    ) -> models.CostTrackingEntry:
        db_entry = models.CostTrackingEntry(**entry.model_dump())
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)
        return db_entry

    @staticmethod
    def get_cost_entries(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        task_id: Optional[int] = None,
        agent_id: Optional[str] = None,
    ) -> List[models.CostTrackingEntry]:
        query = db.query(models.CostTrackingEntry)
        if task_id:
            query = query.filter(models.CostTrackingEntry.task_id == task_id)
        if agent_id:
            query = query.filter(models.CostTrackingEntry.agent_id == agent_id)
        return (
            query.order_by(desc(models.CostTrackingEntry.timestamp))
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_cost_summary(
        db: Session,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
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
                "daily_breakdown": [],
            }

        # Calculate totals
        total_cost = sum(float(entry.estimated_cost_usd) for entry in entries)
        total_tokens = sum(entry.total_tokens for entry in entries)
        total_requests = len(entries)

        # Calculate averages
        avg_cost_per_request = total_cost / total_requests if total_requests > 0 else 0
        avg_tokens_per_request = (
            total_tokens / total_requests if total_requests > 0 else 0
        )

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
            task_entries = task_entries.filter(
                models.CostTrackingEntry.timestamp >= start_date
            )
        if end_date:
            task_entries = task_entries.filter(
                models.CostTrackingEntry.timestamp <= end_date
            )

        for cost_entry, task in task_entries.all():
            task_type_cost = cost_by_task_type.get(task.type, 0)
            cost_by_task_type[task.type] = task_type_cost + float(
                cost_entry.estimated_cost_usd
            )

        cost_by_task_type = {k: f"{v:.4f}" for k, v in cost_by_task_type.items()}

        # Daily breakdown (last 30 days)
        from sqlalchemy import Float, func

        daily_data = db.query(
            func.date(models.CostTrackingEntry.timestamp).label("date"),
            func.count(models.CostTrackingEntry.id).label("requests"),
            func.sum(models.CostTrackingEntry.total_tokens).label("tokens"),
            func.sum(
                func.cast(models.CostTrackingEntry.estimated_cost_usd, Float)
            ).label("cost"),
        ).group_by(func.date(models.CostTrackingEntry.timestamp))

        if start_date:
            daily_data = daily_data.filter(
                models.CostTrackingEntry.timestamp >= start_date
            )
        if end_date:
            daily_data = daily_data.filter(
                models.CostTrackingEntry.timestamp <= end_date
            )

        daily_breakdown = []
        for row in daily_data.all():
            daily_breakdown.append(
                {
                    "date": row.date.isoformat() if row.date else None,
                    "requests": row.requests or 0,
                    "tokens": row.tokens or 0,
                    "cost": f"{row.cost:.4f}" if row.cost else "0.0000",
                }
            )

        return {
            "total_cost_usd": f"{total_cost:.4f}",
            "total_tokens": total_tokens,
            "total_requests": total_requests,
            "avg_cost_per_request": f"{avg_cost_per_request:.4f}",
            "avg_tokens_per_request": avg_tokens_per_request,
            "cost_by_agent": cost_by_agent,
            "cost_by_task_type": cost_by_task_type,
            "daily_breakdown": daily_breakdown,
        }


class UsageMetricsCRUD:
    @staticmethod
    def create_metric(
        db: Session, metric: schemas.UsageMetricsCreate
    ) -> models.UsageMetrics:
        db_metric = models.UsageMetrics(**metric.model_dump())
        db.add(db_metric)
        db.commit()
        db.refresh(db_metric)
        return db_metric

    @staticmethod
    def get_metrics(
        db: Session,
        metric_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[models.UsageMetrics]:
        query = db.query(models.UsageMetrics)
        if metric_type:
            query = query.filter(models.UsageMetrics.metric_type == metric_type)
        return (
            query.order_by(desc(models.UsageMetrics.timestamp))
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def upsert_metric(
        db: Session,
        metric_type: str,
        metric_key: str,
        update_data: Dict[str, Any],
    ) -> models.UsageMetrics:
        """Update existing metric or create new one"""
        existing = (
            db.query(models.UsageMetrics)
            .filter(
                models.UsageMetrics.metric_type == metric_type,
                models.UsageMetrics.metric_key == metric_key,
            )
            .first()
        )

        if existing:
            for key, value in update_data.items():
                setattr(existing, key, value)
            db.commit()
            db.refresh(existing)
            return existing
        else:
            new_metric = models.UsageMetrics(
                metric_type=metric_type, metric_key=metric_key, **update_data
            )
            db.add(new_metric)
            db.commit()
            db.refresh(new_metric)
            return new_metric


class ChatThreadCRUD:
    @staticmethod
    def create_thread(
        db: Session,
        thread: schemas.ChatThreadCreate,
        user_id: Optional[str] = None,
    ) -> models.ChatThread:
        db_thread = models.ChatThread(
            title=thread.title,
            description=thread.description,
            user_id=user_id,
            thread_metadata={},
        )
        db.add(db_thread)
        db.flush()  # Flush to get the ID

        # Add initial message if provided
        if thread.initial_message:
            initial_msg = models.ChatMessage(
                thread_id=db_thread.id,
                role=MessageRole.USER,
                content=thread.initial_message,
                message_type=MessageType.TEXT,
                message_metadata={},
            )
            db.add(initial_msg)

        db.commit()
        db.refresh(db_thread)
        return db_thread

    @staticmethod
    def get_thread(db: Session, thread_id: UUID) -> Optional[models.ChatThread]:
        return (
            db.query(models.ChatThread)
            .filter(models.ChatThread.id == thread_id)
            .first()
        )

    @staticmethod
    def get_threads(
        db: Session,
        skip: int = 0,
        limit: int = 20,
        status: Optional[models.ChatThreadStatus] = None,
        user_id: Optional[str] = None,
    ) -> List[models.ChatThread]:
        query = db.query(models.ChatThread)

        if status:
            query = query.filter(models.ChatThread.status == status)
        if user_id:
            query = query.filter(models.ChatThread.user_id == user_id)

        return (
            query.order_by(desc(models.ChatThread.updated_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def update_thread(
        db: Session, thread_id: UUID, thread_update: schemas.ChatThreadUpdate
    ) -> Optional[models.ChatThread]:
        db_thread = (
            db.query(models.ChatThread)
            .filter(models.ChatThread.id == thread_id)
            .first()
        )
        if db_thread:
            update_data = thread_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_thread, field, value)
            db_thread.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(db_thread)
        return db_thread

    @staticmethod
    def delete_thread(db: Session, thread_id: UUID) -> bool:
        db_thread = (
            db.query(models.ChatThread)
            .filter(models.ChatThread.id == thread_id)
            .first()
        )
        if db_thread:
            db.delete(db_thread)
            db.commit()
            return True
        return False

    @staticmethod
    def get_threads_with_stats(
        db: Session,
        skip: int = 0,
        limit: int = 20,
        status: Optional[models.ChatThreadStatus] = None,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get threads with message count and unread notifications"""
        query = (
            db.query(
                models.ChatThread,
                func.count(models.ChatMessage.id).label("message_count"),
                func.count(models.ChatNotification.id.distinct())
                .filter(models.ChatNotification.is_read == False)
                .label("unread_count"),
                func.max(models.ChatMessage.created_at).label("last_message_at"),
            )
            .outerjoin(
                models.ChatMessage,
                models.ChatThread.id == models.ChatMessage.thread_id,
            )
            .outerjoin(
                models.ChatNotification,
                models.ChatThread.id == models.ChatNotification.thread_id,
            )
            .group_by(models.ChatThread.id)
        )

        if status:
            query = query.filter(models.ChatThread.status == status)
        if user_id:
            query = query.filter(models.ChatThread.user_id == user_id)

        results = (
            query.order_by(desc(models.ChatThread.updated_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

        threads = []
        for thread, message_count, unread_count, last_message_at in results:
            thread_dict = {
                "id": thread.id,
                "title": thread.title,
                "description": thread.description,
                "status": thread.status,
                "created_at": thread.created_at,
                "updated_at": thread.updated_at,
                "user_id": thread.user_id,
                "metadata": thread.thread_metadata,
                "message_count": message_count or 0,
                "unread_count": unread_count or 0,
                "last_message_at": last_message_at,
            }
            threads.append(thread_dict)

        return threads

    @staticmethod
    def get_threads_by_ids(db: Session, thread_ids: List[UUID]) -> List[models.ChatThread]:
        """Get threads by a list of IDs"""
        return (
            db.query(models.ChatThread)
            .filter(models.ChatThread.id.in_(thread_ids))
            .all()
        )


class ChatMessageCRUD:
    @staticmethod
    def create_message(
        db: Session,
        thread_id: UUID,
        message: schemas.ChatMessageCreate,
        role: models.MessageRole,
    ) -> models.ChatMessage:
        db_message = models.ChatMessage(
            thread_id=thread_id,
            role=role,
            content=message.content,
            message_type=message.message_type,
            parent_message_id=message.parent_message_id,
            message_metadata=message.metadata or {},
        )
        db.add(db_message)

        # Update thread's updated_at timestamp
        db.query(models.ChatThread).filter(models.ChatThread.id == thread_id).update(
            {"updated_at": datetime.now(timezone.utc)}
        )

        db.commit()
        db.refresh(db_message)
        return db_message

    @staticmethod
    def get_message(db: Session, message_id: UUID) -> Optional[models.ChatMessage]:
        return (
            db.query(models.ChatMessage)
            .filter(models.ChatMessage.id == message_id)
            .first()
        )

    @staticmethod
    def get_messages(
        db: Session,
        thread_id: UUID,
        skip: int = 0,
        limit: int = 50,
        before: Optional[UUID] = None,
    ) -> List[models.ChatMessage]:
        query = db.query(models.ChatMessage).filter(
            models.ChatMessage.thread_id == thread_id
        )

        if before:
            # Get messages before a specific message (for pagination)
            before_message = (
                db.query(models.ChatMessage)
                .filter(models.ChatMessage.id == before)
                .first()
            )
            if before_message:
                query = query.filter(
                    models.ChatMessage.created_at < before_message.created_at
                )

        return (
            query.order_by(desc(models.ChatMessage.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def update_message(
        db: Session, message_id: UUID, content: str
    ) -> Optional[models.ChatMessage]:
        db_message = (
            db.query(models.ChatMessage)
            .filter(models.ChatMessage.id == message_id)
            .first()
        )
        if db_message:
            db_message.content = content
            db_message.edited_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(db_message)
        return db_message

    @staticmethod
    def delete_message(db: Session, message_id: UUID) -> bool:
        db_message = (
            db.query(models.ChatMessage)
            .filter(models.ChatMessage.id == message_id)
            .first()
        )
        if db_message:
            db.delete(db_message)
            db.commit()
            return True
        return False

    @staticmethod
    def get_messages_count(db: Session, thread_id: UUID) -> int:
        return (
            db.query(models.ChatMessage)
            .filter(models.ChatMessage.thread_id == thread_id)
            .count()
        )

    @staticmethod
    def search_messages(
        db: Session,
        query: str,
        role: Optional[str] = None,
        message_type: Optional[str] = None,
        date_filter: Optional[datetime] = None,
        thread_ids: Optional[List[UUID]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[models.ChatMessage]:
        """
        Search messages with full-text search and filters
        """
        db_query = db.query(models.ChatMessage)

        # Full-text search on content
        if query.strip():
            # Use ILIKE for case-insensitive search (PostgreSQL) or LIKE for SQLite
            search_terms = query.lower().split()
            for term in search_terms:
                db_query = db_query.filter(
                    func.lower(models.ChatMessage.content).contains(term)
                )

        # Role filter
        if role and role != "all":
            try:
                role_enum = MessageRole(role)
                db_query = db_query.filter(models.ChatMessage.role == role_enum)
            except ValueError:
                pass  # Invalid role, ignore filter

        # Message type filter
        if message_type and message_type != "all":
            try:
                type_enum = MessageType(message_type)
                db_query = db_query.filter(models.ChatMessage.message_type == type_enum)
            except ValueError:
                pass  # Invalid message type, ignore filter

        # Date filter
        if date_filter:
            db_query = db_query.filter(models.ChatMessage.created_at >= date_filter)

        # Thread IDs filter
        if thread_ids:
            db_query = db_query.filter(models.ChatMessage.thread_id.in_(thread_ids))

        # Order by relevance (newer messages first for now, could be enhanced with proper scoring)
        db_query = db_query.order_by(desc(models.ChatMessage.created_at))

        # Apply pagination
        return db_query.offset(offset).limit(limit).all()


class ChatNotificationCRUD:
    @staticmethod
    def create_notification(
        db: Session, notification: schemas.ChatNotificationCreate
    ) -> models.ChatNotification:
        db_notification = models.ChatNotification(
            thread_id=notification.thread_id,
            type=notification.type,
            title=notification.title,
            message=notification.message,
            notification_metadata=notification.metadata or {},
        )
        db.add(db_notification)
        db.commit()
        db.refresh(db_notification)
        return db_notification

    @staticmethod
    def get_notifications(
        db: Session,
        thread_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 50,
        unread_only: bool = False,
    ) -> List[models.ChatNotification]:
        query = db.query(models.ChatNotification)

        if thread_id:
            query = query.filter(models.ChatNotification.thread_id == thread_id)
        if unread_only:
            query = query.filter(models.ChatNotification.is_read == False)

        return (
            query.order_by(desc(models.ChatNotification.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def mark_notification_read(db: Session, notification_id: UUID) -> bool:
        db_notification = (
            db.query(models.ChatNotification)
            .filter(models.ChatNotification.id == notification_id)
            .first()
        )
        if db_notification:
            db_notification.is_read = True
            db.commit()
            return True
        return False

    @staticmethod
    def mark_thread_notifications_read(db: Session, thread_id: UUID) -> int:
        """Mark all notifications in a thread as read. Returns count of updated notifications."""
        updated_count = (
            db.query(models.ChatNotification)
            .filter(
                models.ChatNotification.thread_id == thread_id,
                models.ChatNotification.is_read == False,
            )
            .update({"is_read": True})
        )
        db.commit()
        return updated_count

    @staticmethod
    def get_unread_count(db: Session, thread_id: Optional[UUID] = None) -> int:
        query = db.query(models.ChatNotification).filter(
            models.ChatNotification.is_read == False
        )
        if thread_id:
            query = query.filter(models.ChatNotification.thread_id == thread_id)
        return query.count()


class ProviderCRUD:
    @staticmethod
    def create_provider(db: Session, provider_data: Dict[str, Any]) -> models.Provider:
        """Create a new provider."""
        db_provider = models.Provider(**provider_data)
        db.add(db_provider)
        db.commit()
        db.refresh(db_provider)
        return db_provider

    @staticmethod
    def get_provider(db: Session, provider_id: str) -> Optional[models.Provider]:
        """Get a provider by ID."""
        return (
            db.query(models.Provider).filter(models.Provider.id == provider_id).first()
        )

    @staticmethod
    def get_providers(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        provider_type: Optional[ProviderType] = None,
        status: Optional[ProviderStatus] = None,
        enabled_only: bool = False,
    ) -> List[models.Provider]:
        """Get providers with optional filtering."""
        query = db.query(models.Provider)

        if provider_type:
            query = query.filter(models.Provider.type == provider_type)
        if status:
            query = query.filter(models.Provider.status == status)
        if enabled_only:
            query = query.filter(models.Provider.is_enabled == True)

        return (
            query.order_by(
                models.Provider.priority.asc(),
                models.Provider.created_at.desc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_available_providers(
        db: Session, task_type: Optional[str] = None
    ) -> List[models.Provider]:
        """Get providers that are enabled and have healthy status."""
        query = db.query(models.Provider).filter(
            models.Provider.is_enabled == True,
            models.Provider.status.in_(
                [ProviderStatus.ACTIVE, ProviderStatus.DEGRADED]
            ),
        )

        # If task_type is provided, filter by capabilities
        if task_type:
            # Use JSON path query to check if task_type is in supported_tasks array
            query = query.filter(
                func.json_extract_path_text(
                    models.Provider.capabilities, "supported_tasks"
                ).contains(task_type)
            )

        return query.order_by(models.Provider.priority.asc()).all()

    @staticmethod
    def update_provider(
        db: Session, provider_id: str, update_data: Dict[str, Any]
    ) -> Optional[models.Provider]:
        """Update a provider."""
        db_provider = (
            db.query(models.Provider).filter(models.Provider.id == provider_id).first()
        )
        if db_provider:
            for field, value in update_data.items():
                setattr(db_provider, field, value)
            db_provider.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(db_provider)
        return db_provider

    @staticmethod
    def update_provider_health(
        db: Session, provider_id: str, health_data: Dict[str, Any]
    ) -> Optional[models.Provider]:
        """Update provider health status."""
        db_provider = (
            db.query(models.Provider).filter(models.Provider.id == provider_id).first()
        )
        if db_provider:
            db_provider.health_status = health_data
            db_provider.last_health_check = datetime.now(timezone.utc)
            db.commit()
            db.refresh(db_provider)
        return db_provider

    @staticmethod
    def delete_provider(db: Session, provider_id: str) -> bool:
        """Delete a provider and all associated usage records."""
        db_provider = (
            db.query(models.Provider).filter(models.Provider.id == provider_id).first()
        )
        if db_provider:
            db.delete(db_provider)
            db.commit()
            return True
        return False

    @staticmethod
    def get_provider_stats(
        db: Session, provider_id: str, days: int = 30
    ) -> Dict[str, Any]:
        """Get usage statistics for a provider."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Get usage statistics
        usage_stats = (
            db.query(
                func.count(models.ProviderUsage.id).label("total_requests"),
                func.sum(models.ProviderUsage.tokens_used).label("total_tokens"),
                func.sum(func.cast(models.ProviderUsage.cost_usd, db.Integer)).label(
                    "total_cost"
                ),
                func.avg(models.ProviderUsage.execution_time_ms).label(
                    "avg_response_time"
                ),
                func.count(models.ProviderUsage.id)
                .filter(models.ProviderUsage.success == True)
                .label("successful_requests"),
            )
            .filter(
                models.ProviderUsage.provider_id == provider_id,
                models.ProviderUsage.timestamp >= cutoff_date,
            )
            .first()
        )

        total_requests = usage_stats.total_requests or 0
        successful_requests = usage_stats.successful_requests or 0
        success_rate = (
            (successful_requests / total_requests * 100)
            if total_requests > 0
            else 100.0
        )

        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": total_requests - successful_requests,
            "success_rate": round(success_rate, 2),
            "total_tokens": usage_stats.total_tokens or 0,
            "total_cost_usd": f"{float(usage_stats.total_cost or 0):.4f}",
            "avg_response_time_ms": round(float(usage_stats.avg_response_time or 0), 2),
            "period_days": days,
        }


class ProviderUsageCRUD:
    @staticmethod
    def create_usage_entry(
        db: Session, usage_data: Dict[str, Any]
    ) -> models.ProviderUsage:
        """Create a provider usage entry."""
        db_usage = models.ProviderUsage(**usage_data)
        db.add(db_usage)
        db.commit()
        db.refresh(db_usage)
        return db_usage

    @staticmethod
    def get_usage_entries(
        db: Session,
        provider_id: Optional[str] = None,
        task_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[models.ProviderUsage]:
        """Get usage entries with optional filtering."""
        query = db.query(models.ProviderUsage)

        if provider_id:
            query = query.filter(models.ProviderUsage.provider_id == provider_id)
        if task_id:
            query = query.filter(models.ProviderUsage.task_id == task_id)
        if start_date:
            query = query.filter(models.ProviderUsage.timestamp >= start_date)
        if end_date:
            query = query.filter(models.ProviderUsage.timestamp <= end_date)

        return (
            query.order_by(desc(models.ProviderUsage.timestamp))
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_provider_daily_usage(
        db: Session, provider_id: str, days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get daily usage breakdown for a provider."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        daily_stats = (
            db.query(
                func.date(models.ProviderUsage.timestamp).label("date"),
                func.count(models.ProviderUsage.id).label("requests"),
                func.sum(models.ProviderUsage.tokens_used).label("tokens"),
                func.sum(func.cast(models.ProviderUsage.cost_usd, db.Float)).label(
                    "cost"
                ),
                func.count(models.ProviderUsage.id)
                .filter(models.ProviderUsage.success == True)
                .label("successful"),
            )
            .filter(
                models.ProviderUsage.provider_id == provider_id,
                models.ProviderUsage.timestamp >= cutoff_date,
            )
            .group_by(func.date(models.ProviderUsage.timestamp))
            .order_by(func.date(models.ProviderUsage.timestamp))
            .all()
        )

        results = []
        for stat in daily_stats:
            success_rate = (
                (stat.successful / stat.requests * 100) if stat.requests > 0 else 0
            )
            results.append(
                {
                    "date": stat.date.isoformat(),
                    "requests": stat.requests,
                    "successful_requests": stat.successful,
                    "success_rate": round(success_rate, 2),
                    "tokens_used": stat.tokens or 0,
                    "cost_usd": f"{float(stat.cost or 0):.4f}",
                }
            )

        return results

    @staticmethod
    def get_usage_summary(
        db: Session,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get overall usage summary across all providers."""
        query = db.query(
            models.ProviderUsage.provider_id,
            func.count(models.ProviderUsage.id).label("requests"),
            func.sum(models.ProviderUsage.tokens_used).label("tokens"),
            func.sum(func.cast(models.ProviderUsage.cost_usd, db.Float)).label("cost"),
            func.count(models.ProviderUsage.id)
            .filter(models.ProviderUsage.success == True)
            .label("successful"),
        )

        if start_date:
            query = query.filter(models.ProviderUsage.timestamp >= start_date)
        if end_date:
            query = query.filter(models.ProviderUsage.timestamp <= end_date)

        results = query.group_by(models.ProviderUsage.provider_id).all()

        provider_summary = {}
        total_requests = 0
        total_tokens = 0
        total_cost = 0.0
        total_successful = 0

        for result in results:
            requests = result.requests
            tokens = result.tokens or 0
            cost = float(result.cost or 0)
            successful = result.successful

            provider_summary[result.provider_id] = {
                "requests": requests,
                "successful_requests": successful,
                "success_rate": round(
                    (successful / requests * 100) if requests > 0 else 0, 2
                ),
                "tokens_used": tokens,
                "cost_usd": f"{cost:.4f}",
            }

            total_requests += requests
            total_tokens += tokens
            total_cost += cost
            total_successful += successful

        overall_success_rate = (
            (total_successful / total_requests * 100) if total_requests > 0 else 0
        )

        return {
            "total_requests": total_requests,
            "total_successful_requests": total_successful,
            "overall_success_rate": round(overall_success_rate, 2),
            "total_tokens_used": total_tokens,
            "total_cost_usd": f"{total_cost:.4f}",
            "provider_breakdown": provider_summary,
        }


# Organization CRUD Operations

class FolderCRUD:
    @staticmethod
    def create_folder(
        db: Session, folder: schemas.FolderCreate, user_id: Optional[str] = None
    ) -> models.Folder:
        """Create a new folder."""
        db_folder = models.Folder(
            name=folder.name,
            description=folder.description,
            color=folder.color,
            icon=folder.icon,
            parent_id=folder.parent_id,
            position=folder.position,
            user_id=user_id,
        )
        db.add(db_folder)
        db.commit()
        db.refresh(db_folder)
        return db_folder

    @staticmethod
    def get_folder(db: Session, folder_id: UUID) -> Optional[models.Folder]:
        """Get a folder by ID."""
        return db.query(models.Folder).filter(models.Folder.id == folder_id).first()

    @staticmethod
    def get_folders(
        db: Session,
        user_id: Optional[str] = None,
        parent_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[models.Folder]:
        """Get folders with optional filtering."""
        query = db.query(models.Folder)
        
        if user_id:
            query = query.filter(models.Folder.user_id == user_id)
        if parent_id:
            query = query.filter(models.Folder.parent_id == parent_id)
        else:
            # If no parent_id specified, get root folders (parent_id is None)
            query = query.filter(models.Folder.parent_id.is_(None))
        
        return (
            query.order_by(models.Folder.position, models.Folder.name)
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def update_folder(
        db: Session, folder_id: UUID, folder_update: schemas.FolderUpdate
    ) -> Optional[models.Folder]:
        """Update a folder."""
        db_folder = db.query(models.Folder).filter(models.Folder.id == folder_id).first()
        if not db_folder:
            return None
        
        update_data = folder_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_folder, field, value)
        
        db.commit()
        db.refresh(db_folder)
        return db_folder

    @staticmethod
    def delete_folder(db: Session, folder_id: UUID) -> bool:
        """Delete a folder and move its conversations to parent or root."""
        db_folder = db.query(models.Folder).filter(models.Folder.id == folder_id).first()
        if not db_folder:
            return False
        
        # Move conversations to parent folder or root (None)
        db.query(models.ChatThread).filter(
            models.ChatThread.folder_id == folder_id
        ).update({models.ChatThread.folder_id: db_folder.parent_id})
        
        # Move subfolders to parent folder or root
        db.query(models.Folder).filter(
            models.Folder.parent_id == folder_id
        ).update({models.Folder.parent_id: db_folder.parent_id})
        
        db.delete(db_folder)
        db.commit()
        return True

    @staticmethod
    def get_folder_conversation_count(db: Session, folder_id: UUID) -> int:
        """Get the number of conversations in a folder."""
        return (
            db.query(models.ChatThread)
            .filter(models.ChatThread.folder_id == folder_id)
            .count()
        )


class TagCRUD:
    @staticmethod
    def create_tag(
        db: Session, tag: schemas.TagCreate, user_id: Optional[str] = None
    ) -> models.Tag:
        """Create a new tag."""
        db_tag = models.Tag(
            name=tag.name,
            description=tag.description,
            color=tag.color,
            user_id=user_id,
        )
        db.add(db_tag)
        db.commit()
        db.refresh(db_tag)
        return db_tag

    @staticmethod
    def get_tag(db: Session, tag_id: UUID) -> Optional[models.Tag]:
        """Get a tag by ID."""
        return db.query(models.Tag).filter(models.Tag.id == tag_id).first()

    @staticmethod
    def get_tag_by_name(db: Session, name: str, user_id: Optional[str] = None) -> Optional[models.Tag]:
        """Get a tag by name."""
        query = db.query(models.Tag).filter(models.Tag.name == name)
        if user_id:
            query = query.filter(models.Tag.user_id == user_id)
        return query.first()

    @staticmethod
    def get_tags(
        db: Session,
        user_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[models.Tag]:
        """Get tags with optional filtering."""
        query = db.query(models.Tag)
        
        if user_id:
            query = query.filter(models.Tag.user_id == user_id)
        
        return (
            query.order_by(desc(models.Tag.usage_count), models.Tag.name)
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def update_tag(
        db: Session, tag_id: UUID, tag_update: schemas.TagUpdate
    ) -> Optional[models.Tag]:
        """Update a tag."""
        db_tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
        if not db_tag:
            return None
        
        update_data = tag_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_tag, field, value)
        
        db.commit()
        db.refresh(db_tag)
        return db_tag

    @staticmethod
    def delete_tag(db: Session, tag_id: UUID) -> bool:
        """Delete a tag and remove it from all conversations."""
        db_tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
        if not db_tag:
            return False
        
        # Remove tag from all conversations
        for conversation in db_tag.conversations:
            conversation.tags.remove(db_tag)
        
        db.delete(db_tag)
        db.commit()
        return True

    @staticmethod
    def increment_usage_count(db: Session, tag_id: UUID) -> None:
        """Increment the usage count for a tag."""
        db.query(models.Tag).filter(models.Tag.id == tag_id).update(
            {models.Tag.usage_count: models.Tag.usage_count + 1}
        )
        db.commit()

    @staticmethod
    def get_popular_tags(
        db: Session, user_id: Optional[str] = None, limit: int = 10
    ) -> List[models.Tag]:
        """Get the most popular tags by usage count."""
        query = db.query(models.Tag)
        
        if user_id:
            query = query.filter(models.Tag.user_id == user_id)
        
        return (
            query.filter(models.Tag.usage_count > 0)
            .order_by(desc(models.Tag.usage_count))
            .limit(limit)
            .all()
        )


class FavoriteCRUD:
    @staticmethod
    def create_favorite(
        db: Session, favorite: schemas.FavoriteCreate, user_id: Optional[str] = None
    ) -> models.Favorite:
        """Create a new favorite."""
        db_favorite = models.Favorite(
            conversation_id=favorite.conversation_id,
            category=favorite.category,
            notes=favorite.notes,
            user_id=user_id,
        )
        db.add(db_favorite)
        db.commit()
        db.refresh(db_favorite)
        return db_favorite

    @staticmethod
    def get_favorite(db: Session, favorite_id: UUID) -> Optional[models.Favorite]:
        """Get a favorite by ID."""
        return db.query(models.Favorite).filter(models.Favorite.id == favorite_id).first()

    @staticmethod
    def get_favorite_by_conversation(
        db: Session, conversation_id: UUID, user_id: Optional[str] = None
    ) -> Optional[models.Favorite]:
        """Get a favorite by conversation ID."""
        query = db.query(models.Favorite).filter(
            models.Favorite.conversation_id == conversation_id
        )
        if user_id:
            query = query.filter(models.Favorite.user_id == user_id)
        return query.first()

    @staticmethod
    def get_favorites(
        db: Session,
        user_id: Optional[str] = None,
        category: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[models.Favorite]:
        """Get favorites with optional filtering."""
        query = db.query(models.Favorite)
        
        if user_id:
            query = query.filter(models.Favorite.user_id == user_id)
        if category:
            query = query.filter(models.Favorite.category == category)
        
        return (
            query.order_by(desc(models.Favorite.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def update_favorite(
        db: Session, favorite_id: UUID, favorite_update: schemas.FavoriteUpdate
    ) -> Optional[models.Favorite]:
        """Update a favorite."""
        db_favorite = db.query(models.Favorite).filter(models.Favorite.id == favorite_id).first()
        if not db_favorite:
            return None
        
        update_data = favorite_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_favorite, field, value)
        
        db.commit()
        db.refresh(db_favorite)
        return db_favorite

    @staticmethod
    def delete_favorite(db: Session, favorite_id: UUID) -> bool:
        """Delete a favorite."""
        db_favorite = db.query(models.Favorite).filter(models.Favorite.id == favorite_id).first()
        if not db_favorite:
            return False
        
        db.delete(db_favorite)
        db.commit()
        return True

    @staticmethod
    def is_conversation_favorited(
        db: Session, conversation_id: UUID, user_id: Optional[str] = None
    ) -> bool:
        """Check if a conversation is favorited by a user."""
        query = db.query(models.Favorite).filter(
            models.Favorite.conversation_id == conversation_id
        )
        if user_id:
            query = query.filter(models.Favorite.user_id == user_id)
        return query.first() is not None


class ConversationOrganizationCRUD:
    @staticmethod
    def update_conversation_organization(
        db: Session, 
        conversation_id: UUID, 
        organization_update: schemas.ConversationOrganizationUpdate
    ) -> Optional[models.ChatThread]:
        """Update conversation organization (folder, tags, pinning, priority)."""
        db_conversation = (
            db.query(models.ChatThread)
            .filter(models.ChatThread.id == conversation_id)
            .first()
        )
        if not db_conversation:
            return None
        
        # Update basic organization fields
        update_data = organization_update.model_dump(exclude_unset=True, exclude={'tag_ids'})
        for field, value in update_data.items():
            setattr(db_conversation, field, value)
        
        # Handle tag updates
        if organization_update.tag_ids is not None:
            # Clear existing tags
            db_conversation.tags.clear()
            
            # Add new tags
            if organization_update.tag_ids:
                new_tags = (
                    db.query(models.Tag)
                    .filter(models.Tag.id.in_(organization_update.tag_ids))
                    .all()
                )
                for tag in new_tags:
                    db_conversation.tags.append(tag)
                    # Increment usage count for each tag
                    TagCRUD.increment_usage_count(db, tag.id)
        
        db.commit()
        db.refresh(db_conversation)
        return db_conversation

    @staticmethod
    def get_organized_conversations(
        db: Session,
        filter_request: schemas.ConversationFilterRequest,
        user_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[models.ChatThread]:
        """Get conversations with organization filters applied."""
        query = db.query(models.ChatThread)
        
        # User filter
        if user_id:
            query = query.filter(models.ChatThread.user_id == user_id)
        
        # Organization filters
        if filter_request.folder_id is not None:
            query = query.filter(models.ChatThread.folder_id == filter_request.folder_id)
        
        if filter_request.is_pinned is not None:
            query = query.filter(models.ChatThread.is_pinned == filter_request.is_pinned)
        
        if filter_request.priority is not None:
            query = query.filter(models.ChatThread.priority == filter_request.priority)
        
        if filter_request.status:
            query = query.filter(models.ChatThread.status == filter_request.status)
        
        if filter_request.search_query:
            search_term = f"%{filter_request.search_query}%"
            query = query.filter(
                or_(
                    models.ChatThread.title.ilike(search_term),
                    models.ChatThread.description.ilike(search_term),
                )
            )
        
        if filter_request.date_from:
            query = query.filter(models.ChatThread.created_at >= filter_request.date_from)
        
        if filter_request.date_to:
            query = query.filter(models.ChatThread.created_at <= filter_request.date_to)
        
        # Tag filter (requires join)
        if filter_request.tag_ids:
            query = query.join(models.ChatThread.tags).filter(
                models.Tag.id.in_(filter_request.tag_ids)
            )
        
        # Favorite filter (requires subquery)
        if filter_request.is_favorited is not None:
            favorite_subquery = db.query(models.Favorite.conversation_id)
            if user_id:
                favorite_subquery = favorite_subquery.filter(models.Favorite.user_id == user_id)
            
            if filter_request.is_favorited:
                query = query.filter(models.ChatThread.id.in_(favorite_subquery))
            else:
                query = query.filter(~models.ChatThread.id.in_(favorite_subquery))
        
        # Order by priority, pinned status, then updated date
        query = query.order_by(
            desc(models.ChatThread.priority),
            desc(models.ChatThread.is_pinned),
            desc(models.ChatThread.updated_at)
        )
        
        return query.offset(skip).limit(limit).all()

    @staticmethod
    def get_organization_stats(
        db: Session, user_id: Optional[str] = None
    ) -> schemas.OrganizationStatsResponse:
        """Get organization statistics."""
        # Base query for user's conversations
        conversation_query = db.query(models.ChatThread)
        if user_id:
            conversation_query = conversation_query.filter(models.ChatThread.user_id == user_id)
        
        # Total counts
        total_conversations = conversation_query.count()
        
        folder_query = db.query(models.Folder)
        if user_id:
            folder_query = folder_query.filter(models.Folder.user_id == user_id)
        total_folders = folder_query.count()
        
        tag_query = db.query(models.Tag)
        if user_id:
            tag_query = tag_query.filter(models.Tag.user_id == user_id)
        total_tags = tag_query.count()
        
        favorite_query = db.query(models.Favorite)
        if user_id:
            favorite_query = favorite_query.filter(models.Favorite.user_id == user_id)
        total_favorites = favorite_query.count()
        
        # Conversations by folder
        folder_stats = (
            db.query(
                models.Folder.name.label("folder_name"),
                func.count(models.ChatThread.id).label("conversation_count")
            )
            .outerjoin(models.ChatThread, models.Folder.id == models.ChatThread.folder_id)
        )
        if user_id:
            folder_stats = folder_stats.filter(models.Folder.user_id == user_id)
        
        conversations_by_folder = {
            stat.folder_name: stat.conversation_count 
            for stat in folder_stats.group_by(models.Folder.name).all()
        }
        
        # Conversations by tag
        tag_stats = (
            db.query(
                models.Tag.name.label("tag_name"),
                func.count(models.ChatThread.id).label("conversation_count")
            )
            .join(models.conversation_tags, models.Tag.id == models.conversation_tags.c.tag_id)
            .join(models.ChatThread, models.ChatThread.id == models.conversation_tags.c.conversation_id)
        )
        if user_id:
            tag_stats = tag_stats.filter(models.Tag.user_id == user_id)
        
        conversations_by_tag = {
            stat.tag_name: stat.conversation_count 
            for stat in tag_stats.group_by(models.Tag.name).all()
        }
        
        # Special counts
        pinned_conversations = conversation_query.filter(models.ChatThread.is_pinned == True).count()
        high_priority_conversations = conversation_query.filter(models.ChatThread.priority == 1).count()
        
        return schemas.OrganizationStatsResponse(
            total_conversations=total_conversations,
            total_folders=total_folders,
            total_tags=total_tags,
            total_favorites=total_favorites,
            conversations_by_folder=conversations_by_folder,
            conversations_by_tag=conversations_by_tag,
            pinned_conversations=pinned_conversations,
            high_priority_conversations=high_priority_conversations,
        )
