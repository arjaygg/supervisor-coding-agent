import asyncio
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from supervisor_agent.api.websocket import notify_task_update
from supervisor_agent.core.quota import quota_manager
from supervisor_agent.core.task_processor_interface import TaskProcessorFactory
from supervisor_agent.db import crud, schemas
from supervisor_agent.db.database import get_db
from supervisor_agent.db.enums import TaskStatus
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/tasks", response_model=schemas.TaskResponse)
async def create_task(
    task: schemas.TaskCreate, request: Request, db: Session = Depends(get_db)
):
    try:
        # Create task in database
        db_task = crud.TaskCRUD.create_task(db, task)

        # Create audit log
        audit_data = schemas.AuditLogCreate(
            event_type="TASK_CREATED",
            task_id=db_task.id,
            details={
                "task_type": task.type,
                "priority": task.priority,
                "payload_size": len(str(task.payload)),
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        crud.AuditLogCRUD.create_log(db, audit_data)

        # Queue task for processing using dependency injection
        processor = TaskProcessorFactory.create_processor()
        await processor.queue_task(db_task.id, db)

        # Send WebSocket notification
        asyncio.create_task(
            notify_task_update(
                {
                    "id": db_task.id,
                    "type": db_task.type,
                    "status": db_task.status,
                    "priority": db_task.priority,
                    "created_at": (
                        db_task.created_at.isoformat() if db_task.created_at else None
                    ),
                    "payload": db_task.payload,
                }
            )
        )

        logger.info(f"Created and queued task {db_task.id} of type {task.type}")

        return db_task

    except Exception as e:
        logger.error(f"Failed to create task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks", response_model=List[schemas.TaskResponse])
async def get_tasks(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    try:
        tasks = crud.TaskCRUD.get_tasks(db, skip=skip, limit=limit, status=status)
        return tasks

    except Exception as e:
        logger.error(f"Failed to get tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}", response_model=schemas.TaskResponse)
async def get_task(task_id: int, db: Session = Depends(get_db)):
    try:
        task = crud.TaskCRUD.get_task(db, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        return task

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/tasks/{task_id}/sessions", response_model=List[schemas.TaskSessionResponse]
)
async def get_task_sessions(task_id: int, db: Session = Depends(get_db)):
    try:
        # Verify task exists
        task = crud.TaskCRUD.get_task(db, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        sessions = crud.TaskSessionCRUD.get_task_sessions(db, task_id)
        return sessions

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sessions for task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/retry")
async def retry_task(task_id: int, db: Session = Depends(get_db)):
    try:
        task = crud.TaskCRUD.get_task(db, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if task.status not in [TaskStatus.FAILED, TaskStatus.COMPLETED]:
            raise HTTPException(
                status_code=400, detail=f"Cannot retry task with status {task.status}"
            )

        # Reset task status
        update_data = schemas.TaskUpdate(status=TaskStatus.PENDING, error_message=None)
        crud.TaskCRUD.update_task(db, task_id, update_data)

        # Queue for processing using dependency injection
        processor = TaskProcessorFactory.create_processor()
        await processor.queue_task(task_id, db)

        logger.info(f"Retrying task {task_id}")

        return {"message": "Task queued for retry", "task_id": task_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retry task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/stats/summary")
async def get_task_stats(db: Session = Depends(get_db)):
    try:
        # Get task counts by status
        all_tasks = crud.TaskCRUD.get_tasks(
            db, limit=10000
        )  # Get large batch for stats

        stats = {
            "total_tasks": len(all_tasks),
            "by_status": {},
            "by_type": {},
            "by_priority": {},
        }

        for task in all_tasks:
            # Count by status
            status = task.status
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

            # Count by type
            task_type = task.type
            stats["by_type"][task_type] = stats["by_type"].get(task_type, 0) + 1

            # Count by priority
            priority = task.priority
            stats["by_priority"][priority] = stats["by_priority"].get(priority, 0) + 1

        return stats

    except Exception as e:
        logger.error(f"Failed to get task stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/quota/status")
async def get_quota_status(db: Session = Depends(get_db)):
    try:
        quota_status = quota_manager.get_quota_status(db)
        return quota_status

    except Exception as e:
        logger.error(f"Failed to get quota status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents", response_model=List[schemas.AgentResponse])
async def get_agents(db: Session = Depends(get_db)):
    try:
        agents = crud.AgentCRUD.get_active_agents(db)
        return agents

    except Exception as e:
        logger.error(f"Failed to get agents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit-logs", response_model=List[schemas.AuditLogResponse])
async def get_audit_logs(
    skip: int = 0,
    limit: int = 100,
    event_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    try:
        logs = crud.AuditLogCRUD.get_logs(
            db, skip=skip, limit=limit, event_type=event_type
        )
        return logs

    except Exception as e:
        logger.error(f"Failed to get audit logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
