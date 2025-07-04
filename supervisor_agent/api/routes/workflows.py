"""
Workflow Management API Routes

REST API endpoints for workflow orchestration including:
- Workflow CRUD operations
- Workflow execution management
- Schedule management
- Status monitoring

Follows FastAPI patterns and integrates with existing API structure.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from supervisor_agent.core.dag_resolver import DAGResolver
from supervisor_agent.core.workflow_engine import WorkflowEngine
from supervisor_agent.core.workflow_models import (
    ScheduleStatus,
    WorkflowDefinition,
)
from supervisor_agent.core.workflow_scheduler import WorkflowScheduler
from supervisor_agent.db.database import get_db
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)

# Initialize workflow components
dag_resolver = DAGResolver()
workflow_engine = WorkflowEngine(dag_resolver)
workflow_scheduler = WorkflowScheduler(workflow_engine)

router = APIRouter(prefix="/workflows", tags=["workflows"])



# Pydantic models for request/response
from pydantic import BaseModel, Field


class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., description="Workflow name")
    description: Optional[str] = Field(
        None, description="Workflow description"
    )
    tasks: List[Dict[str, Any]] = Field(
        ..., description="List of tasks in the workflow"
    )
    dependencies: List[Dict[str, Any]] = Field(
        default=[], description="Task dependencies"
    )
    variables: Optional[Dict[str, Any]] = Field(
        default={}, description="Workflow variables"
    )


class WorkflowExecuteRequest(BaseModel):
    context: Optional[Dict[str, Any]] = Field(
        default={}, description="Execution context"
    )
    triggered_by: Optional[str] = Field(
        None, description="Who/what triggered the execution"
    )


class ScheduleCreateRequest(BaseModel):
    workflow_id: str = Field(..., description="Workflow ID to schedule")
    name: str = Field(..., description="Schedule name")
    cron_expression: str = Field(..., description="Cron expression")
    timezone: str = Field(default="UTC", description="Timezone for schedule")


class ScheduleUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, description="Schedule name")
    cron_expression: Optional[str] = Field(None, description="Cron expression")
    timezone: Optional[str] = Field(None, description="Timezone")
    status: Optional[ScheduleStatus] = Field(
        None, description="Schedule status"
    )


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    definition: Dict[str, Any]
    created_by: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    is_active: bool
    version: int


class ExecutionResponse(BaseModel):
    execution_id: str
    workflow_id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    context: Dict[str, Any]
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    task_executions: Dict[str, Any]


# Workflow CRUD Operations
@router.post("/", response_model=Dict[str, str])
async def create_workflow(
    request: WorkflowCreateRequest, db: Session = Depends(get_db)
):
    """Create a new workflow definition"""

    try:
        workflow_def = WorkflowDefinition(
            name=request.name,
            description=request.description,
            tasks=request.tasks,
            dependencies=request.dependencies,
            variables=request.variables,
        )

        workflow_id = await workflow_engine.create_workflow(
            workflow_def=workflow_def,
            created_by="api_user",  # In production, get from authentication
        )

        return {
            "workflow_id": workflow_id,
            "message": "Workflow created successfully",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create workflow: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to create workflow"
        )


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str, db: Session = Depends(get_db)):
    """Get workflow definition by ID"""

    try:
        from supervisor_agent.core.workflow_models import Workflow

        workflow = (
            db.query(Workflow).filter(Workflow.id == workflow_id).first()
        )
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        return {
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "definition": workflow.definition,
            "created_by": workflow.created_by,
            "created_at": workflow.created_at.isoformat(),
            "updated_at": (
                workflow.updated_at.isoformat()
                if workflow.updated_at
                else None
            ),
            "is_active": workflow.is_active,
            "version": workflow.version,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get workflow")


@router.get("/")
async def list_workflows(
    active_only: bool = Query(
        True, description="Only return active workflows"
    ),
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of workflows to return"
    ),
    offset: int = Query(0, ge=0, description="Number of workflows to skip"),
    db: Session = Depends(get_db),
):
    """List workflows with pagination"""

    try:
        from supervisor_agent.core.workflow_models import Workflow

        query = db.query(Workflow)
        if active_only:
            query = query.filter(Workflow.is_active == True)

        total = query.count()
        workflows = query.offset(offset).limit(limit).all()

        return {
            "workflows": [
                {
                    "id": w.id,
                    "name": w.name,
                    "description": w.description,
                    "created_by": w.created_by,
                    "created_at": w.created_at.isoformat(),
                    "is_active": w.is_active,
                    "version": w.version,
                }
                for w in workflows
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(f"Failed to list workflows: {e}")
        raise HTTPException(status_code=500, detail="Failed to list workflows")


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str, db: Session = Depends(get_db)):
    """Delete a workflow (mark as inactive)"""

    try:
        from supervisor_agent.core.workflow_models import Workflow

        workflow = (
            db.query(Workflow).filter(Workflow.id == workflow_id).first()
        )
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Mark as inactive instead of deleting
        workflow.is_active = False
        workflow.updated_at = datetime.now(timezone.utc)
        db.commit()

        return {"message": "Workflow deactivated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete workflow {workflow_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to delete workflow"
        )


# Workflow Execution Operations
@router.post("/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: str,
    request: WorkflowExecuteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Execute a workflow"""

    try:
        execution_id = await workflow_engine.execute_workflow(
            workflow_id=workflow_id,
            context=request.context,
            triggered_by=request.triggered_by or "api_user",
        )

        return {
            "execution_id": execution_id,
            "workflow_id": workflow_id,
            "message": "Workflow execution started",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to execute workflow {workflow_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to execute workflow"
        )


@router.get("/{workflow_id}/executions/{execution_id}")
async def get_execution_status(
    workflow_id: str, execution_id: str, db: Session = Depends(get_db)
):
    """Get workflow execution status"""

    try:
        status = await workflow_engine.get_execution_status(execution_id)
        return status

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get execution status {execution_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get execution status"
        )


@router.post("/{workflow_id}/executions/{execution_id}/cancel")
async def cancel_execution(
    workflow_id: str, execution_id: str, db: Session = Depends(get_db)
):
    """Cancel a running workflow execution"""

    try:
        success = await workflow_engine.cancel_execution(execution_id)

        if success:
            return {"message": "Workflow execution cancelled successfully"}
        else:
            raise HTTPException(
                status_code=400, detail="Unable to cancel execution"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel execution {execution_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to cancel execution"
        )


@router.get("/{workflow_id}/executions")
async def list_executions(
    workflow_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(
        None, description="Filter by execution status"
    ),
    db: Session = Depends(get_db),
):
    """List workflow executions"""

    try:
        from supervisor_agent.core.workflow_models import WorkflowExecution

        query = db.query(WorkflowExecution).filter(
            WorkflowExecution.workflow_id == workflow_id
        )

        if status:
            query = query.filter(WorkflowExecution.status == status)

        total = query.count()
        executions = (
            query.order_by(WorkflowExecution.started_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "executions": [
                {
                    "execution_id": e.id,
                    "status": e.status.value,
                    "started_at": e.started_at.isoformat(),
                    "completed_at": (
                        e.completed_at.isoformat() if e.completed_at else None
                    ),
                    "triggered_by": e.triggered_by,
                    "error_message": e.error_message,
                }
                for e in executions
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(
            f"Failed to list executions for workflow {workflow_id}: {e}"
        )
        raise HTTPException(
            status_code=500, detail="Failed to list executions"
        )


# Schedule Management Operations
@router.post("/schedules")
async def create_schedule(
    request: ScheduleCreateRequest, db: Session = Depends(get_db)
):
    """Create a new workflow schedule"""

    try:
        schedule_id = await workflow_scheduler.create_schedule(
            workflow_id=request.workflow_id,
            name=request.name,
            cron_expression=request.cron_expression,
            timezone_str=request.timezone,
            created_by="api_user",
        )

        return {
            "schedule_id": schedule_id,
            "message": "Schedule created successfully",
        }

    except Exception as e:
        logger.error(f"Failed to create schedule: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/schedules/{schedule_id}")
async def get_schedule(schedule_id: str, db: Session = Depends(get_db)):
    """Get schedule details"""

    try:
        schedule = await workflow_scheduler.get_schedule(schedule_id)
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")

        return schedule

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get schedule")


@router.put("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    request: ScheduleUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update schedule configuration"""

    try:
        updates = {
            k: v for k, v in request.model_dump().items() if v is not None
        }

        success = await workflow_scheduler.update_schedule(
            schedule_id, **updates
        )

        if success:
            return {"message": "Schedule updated successfully"}
        else:
            raise HTTPException(status_code=404, detail="Schedule not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update schedule {schedule_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str, db: Session = Depends(get_db)):
    """Delete a schedule"""

    try:
        success = await workflow_scheduler.delete_schedule(schedule_id)

        if success:
            return {"message": "Schedule deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Schedule not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete schedule {schedule_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to delete schedule"
        )


@router.post("/schedules/{schedule_id}/pause")
async def pause_schedule(schedule_id: str, db: Session = Depends(get_db)):
    """Pause a schedule"""

    try:
        success = await workflow_scheduler.pause_schedule(schedule_id)

        if success:
            return {"message": "Schedule paused successfully"}
        else:
            raise HTTPException(status_code=404, detail="Schedule not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to pause schedule")


@router.post("/schedules/{schedule_id}/resume")
async def resume_schedule(schedule_id: str, db: Session = Depends(get_db)):
    """Resume a paused schedule"""

    try:
        success = await workflow_scheduler.resume_schedule(schedule_id)

        if success:
            return {"message": "Schedule resumed successfully"}
        else:
            raise HTTPException(status_code=404, detail="Schedule not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume schedule {schedule_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to resume schedule"
        )


@router.post("/schedules/{schedule_id}/trigger")
async def trigger_schedule(schedule_id: str, db: Session = Depends(get_db)):
    """Manually trigger a scheduled workflow"""

    try:
        execution_id = await workflow_scheduler.force_schedule_execution(
            schedule_id
        )

        return {
            "execution_id": execution_id,
            "message": "Scheduled workflow triggered successfully",
        }

    except Exception as e:
        logger.error(f"Failed to trigger schedule {schedule_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/schedules")
async def list_schedules(
    workflow_id: Optional[str] = Query(
        None, description="Filter by workflow ID"
    ),
    status: Optional[ScheduleStatus] = Query(
        None, description="Filter by status"
    ),
    db: Session = Depends(get_db),
):
    """List workflow schedules"""

    try:
        schedules = await workflow_scheduler.list_schedules(
            workflow_id, status
        )
        return {"schedules": schedules}

    except Exception as e:
        logger.error(f"Failed to list schedules: {e}")
        raise HTTPException(status_code=500, detail="Failed to list schedules")


# Workflow Validation and Testing
@router.post("/validate")
async def validate_workflow(request: WorkflowCreateRequest):
    """Validate workflow definition without creating it"""

    try:
        workflow_def = WorkflowDefinition(
            name=request.name,
            description=request.description,
            tasks=request.tasks,
            dependencies=request.dependencies,
            variables=request.variables,
        )

        validation_result = dag_resolver.validate_dag(workflow_def)

        return {
            "valid": validation_result.is_valid,
            "error_message": validation_result.error_message,
            "warnings": validation_result.warnings,
        }

    except Exception as e:
        logger.error(f"Failed to validate workflow: {e}")
        return {"valid": False, "error_message": str(e), "warnings": []}


# Health and Status Endpoints
@router.get("/health")
async def workflow_health():
    """Get workflow system health status"""

    try:
        from supervisor_agent.core.workflow_models import WorkflowExecution
        from supervisor_agent.db.database import SessionLocal

        with SessionLocal() as db:
            # Count active executions
            active_executions = (
                db.query(WorkflowExecution)
                .filter(WorkflowExecution.status.in_(["PENDING", "RUNNING"]))
                .count()
            )

            # Count total executions today
            today = datetime.now(timezone.utc).date()
            today_executions = (
                db.query(WorkflowExecution)
                .filter(WorkflowExecution.started_at >= today)
                .count()
            )

        return {
            "status": "healthy",
            "active_executions": active_executions,
            "executions_today": today_executions,
            "scheduler_running": workflow_scheduler._scheduler_running,
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


# Initialize scheduler on module load
@router.on_event("startup")
async def startup_event():
    """Start workflow scheduler on API startup"""
    await workflow_scheduler.start_scheduler()
    logger.info("Workflow scheduler started")


@router.on_event("shutdown")
async def shutdown_event():
    """Stop workflow scheduler on API shutdown"""
    await workflow_scheduler.stop_scheduler()
    logger.info("Workflow scheduler stopped")
