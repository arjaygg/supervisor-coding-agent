"""
Workflow Orchestration Models

New models for advanced task management including DAG-based dependencies,
workflow orchestration, and scheduling capabilities.

Follows SOLID principles with clear interface segregation.
"""

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
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from supervisor_agent.db.database import Base


class WorkflowStatus(str, Enum):
    """Workflow execution status"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"


class DependencyCondition(str, Enum):
    """Task dependency conditions"""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    COMPLETION = "COMPLETION"  # Success or failure
    CUSTOM = "CUSTOM"  # Custom condition expression


class ScheduleStatus(str, Enum):
    """Schedule status"""
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DISABLED = "DISABLED"


# Database Models
class Workflow(Base):
    """Workflow definition"""
    __tablename__ = "workflows"

    id = Column(String, primary_key=True, index=True)  # UUID
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    definition = Column(JSON, nullable=False)  # Workflow DAG definition
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    version = Column(Integer, default=1)

    # Relationships
    executions = relationship("WorkflowExecution", back_populates="workflow", cascade="all, delete-orphan")
    schedules = relationship("WorkflowSchedule", back_populates="workflow", cascade="all, delete-orphan")


class WorkflowExecution(Base):
    """Workflow execution instance"""
    __tablename__ = "workflow_executions"

    id = Column(String, primary_key=True, index=True)  # UUID
    workflow_id = Column(String, ForeignKey("workflows.id"), nullable=False)
    status = Column(SQLEnum(WorkflowStatus), default=WorkflowStatus.PENDING)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    context = Column(JSON, default=dict)  # Workflow variables and context
    result = Column(JSON, nullable=True)  # Final execution result
    error_message = Column(Text, nullable=True)
    triggered_by = Column(String(255), nullable=True)  # User, schedule, or system
    
    # Relationships
    workflow = relationship("Workflow", back_populates="executions")
    task_executions = relationship("WorkflowTaskExecution", back_populates="workflow_execution", cascade="all, delete-orphan")


class WorkflowTaskExecution(Base):
    """Individual task execution within a workflow"""
    __tablename__ = "workflow_task_executions"

    id = Column(String, primary_key=True, index=True)  # UUID
    workflow_execution_id = Column(String, ForeignKey("workflow_executions.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    task_name = Column(String(255), nullable=False)  # Task name within workflow
    status = Column(SQLEnum(WorkflowStatus), default=WorkflowStatus.PENDING)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    execution_order = Column(Integer, nullable=False)  # Order in workflow
    
    # Relationships
    workflow_execution = relationship("WorkflowExecution", back_populates="task_executions")


class TaskDependency(Base):
    """Task dependency relationships"""
    __tablename__ = "task_dependencies"

    id = Column(String, primary_key=True, index=True)  # UUID
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    depends_on_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    condition_type = Column(SQLEnum(DependencyCondition), default=DependencyCondition.SUCCESS)
    condition_value = Column(Text, nullable=True)  # Custom condition expression
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint('task_id', 'depends_on_task_id', name='unique_task_dependency'),
    )


class WorkflowSchedule(Base):
    """Workflow scheduling configuration"""
    __tablename__ = "workflow_schedules"

    id = Column(String, primary_key=True, index=True)  # UUID
    workflow_id = Column(String, ForeignKey("workflows.id"), nullable=False)
    name = Column(String(255), nullable=False)
    cron_expression = Column(String(100), nullable=False)
    timezone = Column(String(50), default="UTC")
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(SQLEnum(ScheduleStatus), default=ScheduleStatus.ACTIVE)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    workflow = relationship("Workflow", back_populates="schedules")


# Data Transfer Objects (DTOs)
@dataclass
class WorkflowDefinition:
    """Workflow definition structure"""
    name: str
    description: Optional[str]
    tasks: List[Dict[str, Any]]
    dependencies: List[Dict[str, Any]]
    variables: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "tasks": self.tasks,
            "dependencies": self.dependencies,
            "variables": self.variables or {}
        }


@dataclass
class TaskDefinition:
    """Task definition within a workflow"""
    id: str
    name: str
    type: str
    config: Dict[str, Any]
    dependencies: List[str] = None
    conditions: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "config": self.config,
            "dependencies": self.dependencies or [],
            "conditions": self.conditions or {}
        }


@dataclass
class DependencyDefinition:
    """Task dependency definition"""
    task_id: str
    depends_on: str
    condition: DependencyCondition = DependencyCondition.SUCCESS
    condition_value: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "depends_on": self.depends_on,
            "condition": self.condition.value,
            "condition_value": self.condition_value
        }


@dataclass
class WorkflowContext:
    """Workflow execution context"""
    workflow_execution_id: str
    variables: Dict[str, Any]
    task_results: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_execution_id": self.workflow_execution_id,
            "variables": self.variables,
            "task_results": self.task_results or {}
        }


@dataclass
class ExecutionPlan:
    """DAG execution plan"""
    execution_order: List[List[str]]  # Groups of tasks that can run in parallel
    task_map: Dict[str, TaskDefinition]
    dependency_map: Dict[str, List[str]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_order": self.execution_order,
            "task_map": {k: v.to_dict() for k, v in self.task_map.items()},
            "dependency_map": self.dependency_map
        }


@dataclass
class WorkflowResult:
    """Workflow execution result"""
    workflow_execution_id: str
    status: WorkflowStatus
    task_results: Dict[str, Any]
    error_message: Optional[str] = None
    execution_time_seconds: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_execution_id": self.workflow_execution_id,
            "status": self.status.value,
            "task_results": self.task_results,
            "error_message": self.error_message,
            "execution_time_seconds": self.execution_time_seconds
        }