from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from supervisor_agent.db.models import TaskType, TaskStatus


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
    
    class Config:
        orm_mode = True


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
    
    class Config:
        orm_mode = True


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
    
    class Config:
        orm_mode = True


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
    
    class Config:
        orm_mode = True


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str = "1.0.0"
    database: bool
    redis: bool
    agents_active: int