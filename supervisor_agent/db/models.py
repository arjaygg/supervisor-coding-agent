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
from enum import Enum
import uuid
from supervisor_agent.db.database import Base


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


class TaskType(str, Enum):
    PR_REVIEW = "PR_REVIEW"
    ISSUE_SUMMARY = "ISSUE_SUMMARY"
    CODE_ANALYSIS = "CODE_ANALYSIS"
    REFACTOR = "REFACTOR"
    BUG_FIX = "BUG_FIX"
    FEATURE = "FEATURE"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRY = "RETRY"


class ChatThreadStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    COMPLETED = "COMPLETED"


class MessageRole(str, Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class MessageType(str, Enum):
    TEXT = "TEXT"
    TASK_BREAKDOWN = "TASK_BREAKDOWN"
    PROGRESS = "PROGRESS"
    NOTIFICATION = "NOTIFICATION"
    ERROR = "ERROR"


class NotificationType(str, Enum):
    TASK_COMPLETE = "TASK_COMPLETE"
    TASK_FAILED = "TASK_FAILED"
    AGENT_UPDATE = "AGENT_UPDATE"
    SYSTEM_ALERT = "SYSTEM_ALERT"


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
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    chat_thread_id = Column(GUID(), ForeignKey("chat_threads.id"), nullable=True)
    source_message_id = Column(GUID(), ForeignKey("chat_messages.id"), nullable=True)

    # Relationships
    agent = relationship("Agent", back_populates="tasks")
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
