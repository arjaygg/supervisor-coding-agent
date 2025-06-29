from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    JSON,
    ForeignKey,
    Boolean,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import TypeDecorator, CHAR
import uuid
from supervisor_agent.db.database import Base
from supervisor_agent.db.enums import (
    TaskType,
    TaskStatus,
    ChatThreadStatus,
    MessageRole,
    MessageType,
    NotificationType,
    ProviderType,
    ProviderStatus,
)


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise uses CHAR(32), storing as stringified hex values.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(value)
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            return value

    @staticmethod
    def _uuid_value(value):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value



class Provider(Base):
    __tablename__ = "providers"

    id = Column(String, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    type = Column(SQLEnum(ProviderType), nullable=False)
    status = Column(SQLEnum(ProviderStatus), default=ProviderStatus.ACTIVE)
    priority = Column(Integer, default=5)
    config = Column(JSON, nullable=False, default=dict)
    capabilities = Column(JSON, nullable=False, default=dict)
    max_concurrent_requests = Column(Integer, default=10)
    rate_limit_per_minute = Column(Integer, default=60)
    rate_limit_per_hour = Column(Integer, default=1000)
    rate_limit_per_day = Column(Integer, default=10000)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    health_status = Column(JSON, nullable=True, default=dict)
    provider_metadata = Column("metadata", JSON, default=dict)

    # Relationships
    tasks = relationship("Task", back_populates="provider")
    usage_entries = relationship("ProviderUsage", back_populates="provider", cascade="all, delete-orphan")

    # Indexes for performance
    __table_args__ = (
        Index('ix_providers_type_status', 'type', 'status'),
        Index('ix_providers_priority_enabled', 'priority', 'is_enabled'),
    )


class ProviderUsage(Base):
    __tablename__ = "provider_usage"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(String, ForeignKey("providers.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    request_id = Column(String, nullable=True)  # For tracking individual requests
    tokens_used = Column(Integer, nullable=False, default=0)
    cost_usd = Column(String, nullable=False, default="0.00")  # Store as string for precision
    execution_time_ms = Column(Integer, nullable=False, default=0)
    model_used = Column(String, nullable=True)
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    usage_metadata = Column("metadata", JSON, default=dict)

    # Relationships
    provider = relationship("Provider", back_populates="usage_entries")
    task = relationship("Task", backref="provider_usage_entries")

    # Indexes for efficient queries
    __table_args__ = (
        Index('ix_provider_usage_provider_timestamp', 'provider_id', 'timestamp'),
        Index('ix_provider_usage_task_provider', 'task_id', 'provider_id'),
        Index('ix_provider_usage_success_timestamp', 'success', 'timestamp'),
    )


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(SQLEnum(TaskType), nullable=False)
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)
    payload = Column(JSON, nullable=False)
    priority = Column(Integer, default=5)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    assigned_agent_id = Column(String, ForeignKey("agents.id"), nullable=True)
    assigned_provider_id = Column(String, ForeignKey("providers.id"), nullable=True)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    chat_thread_id = Column(GUID(), ForeignKey("chat_threads.id"), nullable=True)
    source_message_id = Column(GUID(), ForeignKey("chat_messages.id"), nullable=True)

    # Relationships
    agent = relationship("Agent", back_populates="tasks")
    provider = relationship("Provider", back_populates="tasks")
    sessions = relationship("TaskSession", back_populates="task")
    chat_thread = relationship("ChatThread", back_populates="tasks")
    source_message = relationship("ChatMessage", foreign_keys=[source_message_id])


class TaskSession(Base):
    __tablename__ = "task_sessions"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    execution_time_seconds = Column(Integer, nullable=True)

    # Relationships
    task = relationship("Task", back_populates="sessions")


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, index=True)
    api_key = Column(String, nullable=False)
    quota_used = Column(Integer, default=0)
    quota_limit = Column(Integer, nullable=False)
    quota_reset_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tasks = relationship("Task", back_populates="agent")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, nullable=False)
    agent_id = Column(String, nullable=True)
    task_id = Column(Integer, nullable=True)
    prompt_hash = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)


class CostTrackingEntry(Base):
    __tablename__ = "cost_tracking"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    estimated_cost_usd = Column(
        String, nullable=False, default="0.00"
    )  # Store as string for precision
    model_used = Column(String, nullable=True)
    execution_time_ms = Column(Integer, nullable=False, default=0)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    task = relationship("Task", backref="cost_entries")
    agent = relationship("Agent", backref="cost_entries")


class UsageMetrics(Base):
    __tablename__ = "usage_metrics"

    id = Column(Integer, primary_key=True, index=True)
    metric_type = Column(String, nullable=False)  # 'daily', 'hourly', 'agent'
    metric_key = Column(String, nullable=False)  # date, hour, agent_id
    total_requests = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    total_cost_usd = Column(String, nullable=False, default="0.00")
    avg_response_time_ms = Column(Integer, nullable=False, default=0)
    success_rate = Column(
        String, nullable=False, default="100.00"
    )  # Percentage as string
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Composite index for efficient queries
    __table_args__ = {"extend_existing": True}


class ChatThread(Base):
    __tablename__ = "chat_threads"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SQLEnum(ChatThreadStatus), default=ChatThreadStatus.ACTIVE)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    user_id = Column(String(255), nullable=True)  # for future multi-user support
    thread_metadata = Column("metadata", JSON, default=dict)

    # Relationships
    messages = relationship("ChatMessage", back_populates="thread", cascade="all, delete-orphan", order_by="ChatMessage.created_at")
    tasks = relationship("Task", back_populates="chat_thread")
    notifications = relationship("ChatNotification", back_populates="thread", cascade="all, delete-orphan")

    # Indexes for performance
    __table_args__ = (
        Index('ix_chat_threads_status_updated', 'status', 'updated_at'),
        Index('ix_chat_threads_user_status', 'user_id', 'status'),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    thread_id = Column(GUID(), ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False)
    role = Column(SQLEnum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    message_type = Column(SQLEnum(MessageType), default=MessageType.TEXT)
    message_metadata = Column("metadata", JSON, default=dict)  # for storing task refs, progress data, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    edited_at = Column(DateTime(timezone=True), nullable=True)
    parent_message_id = Column(GUID(), ForeignKey("chat_messages.id"), nullable=True)

    # Relationships
    thread = relationship("ChatThread", back_populates="messages")
    parent_message = relationship("ChatMessage", remote_side=[id])
    child_messages = relationship("ChatMessage", remote_side=[parent_message_id], overlaps="parent_message")

    # Indexes for performance
    __table_args__ = (
        Index('ix_chat_messages_thread_created', 'thread_id', 'created_at'),
        Index('ix_chat_messages_role_type', 'role', 'message_type'),
    )


class ChatNotification(Base):
    __tablename__ = "chat_notifications"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    thread_id = Column(GUID(), ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False)
    type = Column(SQLEnum(NotificationType), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    notification_metadata = Column("metadata", JSON, default=dict)

    # Relationships
    thread = relationship("ChatThread", back_populates="notifications")

    # Indexes for performance
    __table_args__ = (
        Index('ix_chat_notifications_thread_unread', 'thread_id', 'is_read'),
        Index('ix_chat_notifications_type_created', 'type', 'created_at'),
    )


# Import workflow models to ensure they're included in Base metadata
from supervisor_agent.core.workflow_models import (
    Workflow,
    WorkflowExecution, 
    WorkflowTaskExecution,
    TaskDependency,
    WorkflowSchedule
)

# Import analytics models to ensure they're included in Base metadata
from supervisor_agent.core.analytics_models import (
    MetricEntry,
    Dashboard,
    AnalyticsCache,
    AlertRule
)
