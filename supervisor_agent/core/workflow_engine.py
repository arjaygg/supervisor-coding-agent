"""
Workflow Orchestration Engine

Manages workflow execution, task coordination, and state management.
Integrates with existing task processing infrastructure while adding
orchestration capabilities.

Follows SOLID principles and integrates with existing architecture.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Callable
from contextlib import asynccontextmanager

from sqlalchemy.orm import Session

from supervisor_agent.core.workflow_models import (
    Workflow, WorkflowExecution, WorkflowTaskExecution,
    WorkflowDefinition, WorkflowResult, WorkflowContext,
    ExecutionPlan, WorkflowStatus
)
from supervisor_agent.core.dag_resolver import DAGResolver, ValidationResult
from supervisor_agent.core.task_processor_interface import TaskProcessorFactory
from supervisor_agent.db.models import Task
from supervisor_agent.db.enums import TaskStatus, TaskType
from supervisor_agent.db.database import SessionLocal
from supervisor_agent.db import crud, schemas
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class WorkflowExecutionError(Exception):
    """Raised when workflow execution fails"""
    pass


class WorkflowEngine:
    """
    Workflow orchestration engine that manages complex task workflows.
    
    Integrates with existing task processing infrastructure while adding
    orchestration, dependency management, and parallel execution capabilities.
    """
    
    def __init__(self, dag_resolver: DAGResolver = None):
        self.dag_resolver = dag_resolver or DAGResolver()
        self.task_processor = TaskProcessorFactory.create_processor()
        self._active_executions: Dict[str, 'WorkflowExecutor'] = {}
    
    async def create_workflow(self, workflow_def: WorkflowDefinition, 
                            created_by: str = None) -> str:
        """Create a new workflow definition"""
        
        logger.info(f"Creating workflow: {workflow_def.name}")
        
        # Validate workflow definition
        validation_result = self.dag_resolver.validate_dag(workflow_def)
        if not validation_result.is_valid:
            raise ValueError(f"Invalid workflow definition: {validation_result.error_message}")
        
        # Generate workflow ID
        workflow_id = str(uuid.uuid4())
        
        # Store workflow in database
        with SessionLocal() as db:
            db_workflow = Workflow(
                id=workflow_id,
                name=workflow_def.name,
                description=workflow_def.description,
                definition=workflow_def.to_dict(),
                created_by=created_by,
                is_active=True,
                version=1
            )
            db.add(db_workflow)
            db.commit()
            
            logger.info(f"Workflow created with ID: {workflow_id}")
            return workflow_id
    
    async def execute_workflow(self, workflow_id: str, context: Dict[str, Any] = None,
                             triggered_by: str = None) -> str:
        """Execute a workflow and return execution ID"""
        
        logger.info(f"Starting workflow execution: {workflow_id}")
        
        with SessionLocal() as db:
            # Get workflow definition
            db_workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
            if not db_workflow:
                raise ValueError(f"Workflow not found: {workflow_id}")
            
            if not db_workflow.is_active:
                raise ValueError(f"Workflow is not active: {workflow_id}")
            
            # Create execution record
            execution_id = str(uuid.uuid4())
            db_execution = WorkflowExecution(
                id=execution_id,
                workflow_id=workflow_id,
                status=WorkflowStatus.PENDING,
                context=context or {},
                triggered_by=triggered_by
            )
            db.add(db_execution)
            db.commit()
            
            # Start execution in background
            executor = WorkflowExecutor(
                execution_id=execution_id,
                workflow_def=WorkflowDefinition(**db_workflow.definition),
                context=WorkflowContext(
                    workflow_execution_id=execution_id,
                    variables=context or {}
                ),
                dag_resolver=self.dag_resolver,
                task_processor=self.task_processor
            )
            
            self._active_executions[execution_id] = executor
            
            # Execute asynchronously
            asyncio.create_task(self._run_workflow_execution(executor))
            
            logger.info(f"Workflow execution started: {execution_id}")
            return execution_id
    
    async def get_execution_status(self, execution_id: str) -> Dict[str, Any]:
        """Get workflow execution status"""
        
        with SessionLocal() as db:
            db_execution = db.query(WorkflowExecution).filter(
                WorkflowExecution.id == execution_id
            ).first()
            
            if not db_execution:
                raise ValueError(f"Workflow execution not found: {execution_id}")
            
            # Get task execution details
            task_executions = db.query(WorkflowTaskExecution).filter(
                WorkflowTaskExecution.workflow_execution_id == execution_id
            ).all()
            
            task_status = {}
            for task_exec in task_executions:
                task_status[task_exec.task_name] = {
                    "status": task_exec.status.value,
                    "started_at": task_exec.started_at.isoformat() if task_exec.started_at else None,
                    "completed_at": task_exec.completed_at.isoformat() if task_exec.completed_at else None,
                    "error_message": task_exec.error_message,
                    "retry_count": task_exec.retry_count
                }
            
            return {
                "execution_id": execution_id,
                "workflow_id": db_execution.workflow_id,
                "status": db_execution.status.value,
                "started_at": db_execution.started_at.isoformat(),
                "completed_at": db_execution.completed_at.isoformat() if db_execution.completed_at else None,
                "context": db_execution.context,
                "result": db_execution.result,
                "error_message": db_execution.error_message,
                "task_executions": task_status
            }
    
    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a running workflow execution"""
        
        logger.info(f"Cancelling workflow execution: {execution_id}")
        
        # Cancel active executor
        if execution_id in self._active_executions:
            executor = self._active_executions[execution_id]
            await executor.cancel()
            del self._active_executions[execution_id]
        
        # Update database status
        with SessionLocal() as db:
            db_execution = db.query(WorkflowExecution).filter(
                WorkflowExecution.id == execution_id
            ).first()
            
            if db_execution and db_execution.status in [WorkflowStatus.PENDING, WorkflowStatus.RUNNING]:
                db_execution.status = WorkflowStatus.CANCELLED
                db_execution.completed_at = datetime.now(timezone.utc)
                db.commit()
                
                logger.info(f"Workflow execution cancelled: {execution_id}")
                return True
        
        return False
    
    async def _run_workflow_execution(self, executor: 'WorkflowExecutor'):
        """Run workflow execution with error handling"""
        
        try:
            result = await executor.execute()
            
            # Update execution status
            with SessionLocal() as db:
                db_execution = db.query(WorkflowExecution).filter(
                    WorkflowExecution.id == executor.execution_id
                ).first()
                
                if db_execution:
                    db_execution.status = result.status
                    db_execution.completed_at = datetime.now(timezone.utc)
                    db_execution.result = result.to_dict()
                    if result.error_message:
                        db_execution.error_message = result.error_message
                    db.commit()
            
            logger.info(f"Workflow execution completed: {executor.execution_id}")
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {executor.execution_id}: {e}")
            
            # Update execution status to failed
            with SessionLocal() as db:
                db_execution = db.query(WorkflowExecution).filter(
                    WorkflowExecution.id == executor.execution_id
                ).first()
                
                if db_execution:
                    db_execution.status = WorkflowStatus.FAILED
                    db_execution.completed_at = datetime.now(timezone.utc)
                    db_execution.error_message = str(e)
                    db.commit()
        
        finally:
            # Clean up active executions
            if executor.execution_id in self._active_executions:
                del self._active_executions[executor.execution_id]


class WorkflowExecutor:
    """
    Executes individual workflow instances.
    
    Handles task coordination, dependency resolution, and parallel execution.
    """
    
    def __init__(self, execution_id: str, workflow_def: WorkflowDefinition,
                 context: WorkflowContext, dag_resolver: DAGResolver,
                 task_processor):
        self.execution_id = execution_id
        self.workflow_def = workflow_def
        self.context = context
        self.dag_resolver = dag_resolver
        self.task_processor = task_processor
        self._cancelled = False
        self._task_results: Dict[str, Any] = {}
        self._active_tasks: Dict[str, asyncio.Task] = {}
    
    async def execute(self) -> WorkflowResult:
        """Execute the workflow"""
        
        logger.info(f"Executing workflow: {self.execution_id}")
        start_time = datetime.now(timezone.utc)
        
        try:
            # Update status to running
            await self._update_execution_status(WorkflowStatus.RUNNING)
            
            # Create execution plan
            execution_plan = self.dag_resolver.create_execution_plan(self.workflow_def)
            
            # Execute tasks according to plan
            await self._execute_plan(execution_plan)
            
            # Check final status
            if self._cancelled:
                status = WorkflowStatus.CANCELLED
                error_message = "Workflow execution was cancelled"
            elif self._has_failed_tasks():
                status = WorkflowStatus.FAILED
                error_message = "One or more tasks failed"
            else:
                status = WorkflowStatus.COMPLETED
                error_message = None
            
            end_time = datetime.now(timezone.utc)
            execution_time = int((end_time - start_time).total_seconds())
            
            return WorkflowResult(
                workflow_execution_id=self.execution_id,
                status=status,
                task_results=self._task_results,
                error_message=error_message,
                execution_time_seconds=execution_time
            )
            
        except Exception as e:
            logger.error(f"Workflow execution error: {self.execution_id}: {e}")
            await self._update_execution_status(WorkflowStatus.FAILED)
            
            end_time = datetime.now(timezone.utc)
            execution_time = int((end_time - start_time).total_seconds())
            
            return WorkflowResult(
                workflow_execution_id=self.execution_id,
                status=WorkflowStatus.FAILED,
                task_results=self._task_results,
                error_message=str(e),
                execution_time_seconds=execution_time
            )
    
    async def cancel(self):
        """Cancel workflow execution"""
        self._cancelled = True
        
        # Cancel all active tasks
        for task in self._active_tasks.values():
            task.cancel()
        
        await self._update_execution_status(WorkflowStatus.CANCELLED)
    
    async def _execute_plan(self, execution_plan: ExecutionPlan):
        """Execute tasks according to execution plan"""
        
        for parallel_group in execution_plan.execution_order:
            if self._cancelled:
                break
            
            # Execute all tasks in parallel group
            group_tasks = []
            for task_id in parallel_group:
                task_def = execution_plan.task_map[task_id]
                task_coro = self._execute_task(task_def)
                group_tasks.append(task_coro)
            
            # Wait for all tasks in group to complete
            if group_tasks:
                await asyncio.gather(*group_tasks, return_exceptions=True)
    
    async def _execute_task(self, task_def) -> Dict[str, Any]:
        """Execute individual task"""
        
        if self._cancelled:
            return {"status": "CANCELLED", "success": False}
        
        logger.info(f"Executing task: {task_def.name} (ID: {task_def.id})")
        
        try:
            # Create task record
            task_record = await self._create_task_record(task_def)
            
            # Create workflow task execution record
            await self._create_task_execution_record(task_def, task_record.id)
            
            # Process task using existing infrastructure
            await self.task_processor.queue_task(task_record.id, SessionLocal())
            
            # Wait for task completion with polling
            result = await self._wait_for_task_completion(task_record.id, task_def.name)
            
            # Store result
            self._task_results[task_def.id] = result
            
            # Update task execution record
            await self._update_task_execution_result(task_def.name, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Task execution failed: {task_def.name}: {e}")
            error_result = {
                "status": "FAILED",
                "success": False,
                "error": str(e)
            }
            self._task_results[task_def.id] = error_result
            await self._update_task_execution_result(task_def.name, error_result)
            return error_result
    
    async def _create_task_record(self, task_def) -> Task:
        """Create task record in database"""
        
        with SessionLocal() as db:
            # Map workflow task type to system task type
            task_type = self._map_task_type(task_def.type)
            
            # Create task
            task_create = schemas.TaskCreate(
                type=task_type,
                payload=task_def.config,
                priority=task_def.config.get("priority", 5)
            )
            
            task_record = crud.TaskCRUD.create_task(db, task_create)
            db.commit()
            
            return task_record
    
    async def _create_task_execution_record(self, task_def, task_id: int):
        """Create workflow task execution record"""
        
        with SessionLocal() as db:
            execution_record = WorkflowTaskExecution(
                id=str(uuid.uuid4()),
                workflow_execution_id=self.execution_id,
                task_id=task_id,
                task_name=task_def.name,
                status=WorkflowStatus.PENDING,
                execution_order=0  # This should be set based on execution plan
            )
            db.add(execution_record)
            db.commit()
    
    async def _wait_for_task_completion(self, task_id: int, task_name: str, 
                                      timeout: int = 300) -> Dict[str, Any]:
        """Wait for task completion with polling"""
        
        start_time = datetime.now(timezone.utc)
        
        while True:
            if self._cancelled:
                return {"status": "CANCELLED", "success": False}
            
            # Check timeout
            if (datetime.now(timezone.utc) - start_time).total_seconds() > timeout:
                return {"status": "TIMEOUT", "success": False, "error": "Task execution timeout"}
            
            # Check task status
            with SessionLocal() as db:
                task = crud.TaskCRUD.get_task(db, task_id)
                if not task:
                    return {"status": "NOT_FOUND", "success": False}
                
                if task.status == TaskStatus.COMPLETED:
                    return {
                        "status": "COMPLETED",
                        "success": True,
                        "result": task.result if hasattr(task, 'result') else {}
                    }
                elif task.status == TaskStatus.FAILED:
                    return {
                        "status": "FAILED",
                        "success": False,
                        "error": task.error_message or "Task failed"
                    }
            
            # Wait before next check
            await asyncio.sleep(2)
    
    async def _update_task_execution_result(self, task_name: str, result: Dict[str, Any]):
        """Update workflow task execution result"""
        
        with SessionLocal() as db:
            execution_record = db.query(WorkflowTaskExecution).filter(
                WorkflowTaskExecution.workflow_execution_id == self.execution_id,
                WorkflowTaskExecution.task_name == task_name
            ).first()
            
            if execution_record:
                execution_record.status = WorkflowStatus.COMPLETED if result.get("success") else WorkflowStatus.FAILED
                execution_record.completed_at = datetime.now(timezone.utc)
                execution_record.result = result
                if not result.get("success"):
                    execution_record.error_message = result.get("error", "Task failed")
                db.commit()
    
    async def _update_execution_status(self, status: WorkflowStatus):
        """Update workflow execution status"""
        
        with SessionLocal() as db:
            db_execution = db.query(WorkflowExecution).filter(
                WorkflowExecution.id == self.execution_id
            ).first()
            
            if db_execution:
                db_execution.status = status
                if status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED]:
                    db_execution.completed_at = datetime.now(timezone.utc)
                db.commit()
    
    def _map_task_type(self, workflow_task_type: str) -> TaskType:
        """Map workflow task type to system task type"""
        
        type_mapping = {
            "PR_REVIEW": TaskType.PR_REVIEW,
            "ISSUE_SUMMARY": TaskType.ISSUE_SUMMARY,
            "CODE_ANALYSIS": TaskType.CODE_ANALYSIS,
            "REFACTOR": TaskType.REFACTOR,
            "BUG_FIX": TaskType.BUG_FIX,
            "FEATURE": TaskType.FEATURE
        }
        
        return type_mapping.get(workflow_task_type, TaskType.CODE_ANALYSIS)
    
    def _has_failed_tasks(self) -> bool:
        """Check if any tasks failed"""
        return any(not result.get("success", False) for result in self._task_results.values())