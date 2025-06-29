from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from supervisor_agent.db.enums import (
    ChatThreadStatus,
    MessageRole,
    MessageType,
    NotificationType,
    TaskStatus,
    TaskType,
)


class TaskCreate(BaseModel):
    type: TaskType
    payload: Dict[str, Any]
    priority: Optional[int] = 5


class TaskUpdate(BaseModel):
    status: Optional[TaskStatus] = None
    assigned_agent_id: Optional[str] = None
    error_message: Optional[str] = None


class TaskResponse(BaseModel):
    id: int
    type: str
    status: str
    payload: Dict[str, Any]
    priority: int
    created_at: datetime
    updated_at: Optional[datetime]
    assigned_agent_id: Optional[str]
    retry_count: int
    error_message: Optional[str]

    model_config = {"from_attributes": True}


class TaskSessionCreate(BaseModel):
    task_id: int
    prompt: str
    response: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    execution_time_seconds: Optional[int] = None


class TaskSessionResponse(BaseModel):
    id: int
    task_id: int
    prompt: str
    response: Optional[str]
    result: Optional[Dict[str, Any]]
    created_at: datetime
    execution_time_seconds: Optional[int]

    model_config = {"from_attributes": True}


class AgentCreate(BaseModel):
    id: str
    api_key: str
    quota_limit: int
    quota_reset_at: datetime


class AgentUpdate(BaseModel):
    quota_used: Optional[int] = None
    is_active: Optional[bool] = None
    last_used_at: Optional[datetime] = None


class AgentResponse(BaseModel):
    id: str
    quota_used: int
    quota_limit: int
    quota_reset_at: datetime
    is_active: bool
    last_used_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogCreate(BaseModel):
    event_type: str
    agent_id: Optional[str] = None
    task_id: Optional[int] = None
    prompt_hash: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class AuditLogResponse(BaseModel):
    id: int
    event_type: str
    agent_id: Optional[str]
    task_id: Optional[int]
    prompt_hash: Optional[str]
    details: Optional[Dict[str, Any]]
    timestamp: datetime
    ip_address: Optional[str]
    user_agent: Optional[str]

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str = "1.0.0"
    database: bool
    redis: bool
    agents_active: int


class CostTrackingEntryCreate(BaseModel):
    task_id: int
    agent_id: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: str
    model_used: Optional[str] = None
    execution_time_ms: int

    model_config = {"protected_namespaces": ()}


class CostTrackingEntryResponse(BaseModel):
    id: int
    task_id: int
    agent_id: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: str
    model_used: Optional[str]
    execution_time_ms: int
    timestamp: datetime

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class UsageMetricsCreate(BaseModel):
    metric_type: str
    metric_key: str
    total_requests: int
    total_tokens: int
    total_cost_usd: str
    avg_response_time_ms: int
    success_rate: str


class UsageMetricsResponse(BaseModel):
    id: int
    metric_type: str
    metric_key: str
    total_requests: int
    total_tokens: int
    total_cost_usd: str
    avg_response_time_ms: int
    success_rate: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class CostSummaryResponse(BaseModel):
    total_cost_usd: str
    total_tokens: int
    total_requests: int
    avg_cost_per_request: str
    avg_tokens_per_request: float
    cost_by_agent: Dict[str, str]
    cost_by_task_type: Dict[str, str]
    daily_breakdown: List[Dict[str, Any]]


class UsageAnalyticsResponse(BaseModel):
    time_period: str
    summary: CostSummaryResponse
    trends: Dict[str, List[Dict[str, Any]]]
    top_agents: List[Dict[str, Any]]
    cost_efficiency: Dict[str, Any]


# Chat System Schemas
class ChatThreadCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    initial_message: Optional[str] = None


class ChatThreadUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[ChatThreadStatus] = None


class ChatThreadResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    status: ChatThreadStatus
    created_at: datetime
    updated_at: Optional[datetime]
    user_id: Optional[str]
    thread_metadata: Dict[str, Any] = Field(default_factory=dict)
    unread_count: Optional[int] = 0
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ChatMessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
    message_type: MessageType = MessageType.TEXT
    parent_message_id: Optional[UUID] = None
    metadata: Optional[Dict[str, Any]] = None


class ChatMessageResponse(BaseModel):
    id: UUID
    thread_id: UUID
    role: MessageRole
    content: str
    message_type: MessageType
    message_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    edited_at: Optional[datetime]
    parent_message_id: Optional[UUID]

    model_config = {"from_attributes": True}


class ChatMessagesListResponse(BaseModel):
    messages: List[ChatMessageResponse]
    has_more: bool
    total_count: int


class ChatNotificationCreate(BaseModel):
    thread_id: UUID
    type: NotificationType
    title: str = Field(..., min_length=1, max_length=255)
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ChatNotificationResponse(BaseModel):
    id: UUID
    thread_id: UUID
    type: NotificationType
    title: str
    message: Optional[str]
    is_read: bool
    created_at: datetime
    notification_metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class ChatThreadListResponse(BaseModel):
    threads: List[ChatThreadResponse]
    total_count: int


class TaskCreateFromChat(BaseModel):
    content: str
    thread_id: UUID
    message_id: Optional[UUID] = None
    task_type: Optional[TaskType] = None
    priority: Optional[int] = 5
