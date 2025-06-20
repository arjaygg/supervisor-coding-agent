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
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum
from supervisor_agent.db.database import Base


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

    # Relationships
    agent = relationship("Agent", back_populates="tasks")
    sessions = relationship("TaskSession", back_populates="task")


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


# Import workflow models to ensure they're included in Base metadata
from supervisor_agent.core.workflow_models import (
    Workflow,
    WorkflowExecution, 
    WorkflowTaskExecution,
    TaskDependency,
    WorkflowSchedule
)
