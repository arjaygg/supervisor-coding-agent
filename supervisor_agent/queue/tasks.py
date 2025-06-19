import asyncio
import json
from datetime import datetime, timezone
from typing import List, Dict, Any
from celery import current_task
from sqlalchemy.orm import Session
from supervisor_agent.queue.celery_app import celery_app
from supervisor_agent.db.database import get_db
from supervisor_agent.db import models, schemas, crud
from supervisor_agent.core.agent import agent_manager
from supervisor_agent.core.memory import shared_memory
from supervisor_agent.core.quota import quota_manager
from supervisor_agent.core.batcher import task_batcher
from supervisor_agent.core.notifier import notification_manager
from supervisor_agent.config import settings
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


@celery_app.task(bind=True, max_retries=settings.max_retries)
def process_single_task(self, task_id: int):
    """Process a single task"""
    db = next(get_db())

    try:
        task = crud.TaskCRUD.get_task(db, task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return {"error": "Task not found"}

        # Update task status to in progress
        update_data = schemas.TaskUpdate(status=models.TaskStatus.IN_PROGRESS)
        crud.TaskCRUD.update_task(db, task_id, update_data)

        # Get available agent
        agent = quota_manager.get_available_agent(db)
        if not agent:
            logger.warning(f"No available agents for task {task_id}")

            # Check if all agents are saturated
            if quota_manager.are_all_agents_saturated(db):
                asyncio.run(
                    notification_manager.send_quota_exhausted_alert(
                        quota_manager.get_quota_status(db)
                    )
                )

            # Retry task later
            raise self.retry(countdown=300)  # Retry in 5 minutes

        # Assign agent to task
        update_data = schemas.TaskUpdate(assigned_agent_id=agent.id)
        crud.TaskCRUD.update_task(db, task_id, update_data)

        # Get shared memory context
        context = shared_memory.get_task_context(task)

        # Execute task
        agent_wrapper = agent_manager.get_agent(agent.id)
        if not agent_wrapper:
            raise Exception(f"Agent wrapper not found for {agent.id}")

        # Estimate quota usage
        payload_size = len(json.dumps(task.payload))
        estimated_messages = quota_manager.estimate_messages_from_task(
            task.type, payload_size
        )

        # Consume quota
        if not quota_manager.consume_quota(db, agent.id, estimated_messages):
            raise Exception(f"Failed to consume quota for agent {agent.id}")

        # Execute the task
        result = asyncio.run(agent_wrapper.execute_task(task, context))

        if result["success"]:
            # Store successful result
            session_data = schemas.TaskSessionCreate(
                task_id=task_id,
                prompt=result["prompt"],
                response=result["result"],
                result=result,
                execution_time_seconds=result["execution_time"],
            )
            crud.TaskSessionCRUD.create_session(db, session_data)

            # Update task status
            update_data = schemas.TaskUpdate(status=models.TaskStatus.COMPLETED)
            crud.TaskCRUD.update_task(db, task_id, update_data)

            # Store result in shared memory
            shared_memory.store_task_result(task, result)

            logger.info(f"Task {task_id} completed successfully")

            # Create audit log
            audit_data = schemas.AuditLogCreate(
                event_type="TASK_COMPLETED",
                agent_id=agent.id,
                task_id=task_id,
                details={"execution_time": result["execution_time"], "success": True},
            )
            crud.AuditLogCRUD.create_log(db, audit_data)

            return {"success": True, "task_id": task_id, "result": result}

        else:
            # Handle failure
            error_message = result.get("error", "Unknown error")

            # Store failed session
            session_data = schemas.TaskSessionCreate(
                task_id=task_id,
                prompt=result.get("prompt", ""),
                response=error_message,
                result=result,
                execution_time_seconds=result.get("execution_time", 0),
            )
            crud.TaskSessionCRUD.create_session(db, session_data)

            # Update task
            task.retry_count += 1
            if task.retry_count >= settings.max_retries:
                update_data = schemas.TaskUpdate(
                    status=models.TaskStatus.FAILED, error_message=error_message
                )
                crud.TaskCRUD.update_task(db, task_id, update_data)

                # Send failure notification
                asyncio.run(
                    notification_manager.send_task_failure_alert(
                        task_id, task.type, error_message, task.retry_count
                    )
                )

                logger.error(f"Task {task_id} failed after {task.retry_count} retries")
            else:
                update_data = schemas.TaskUpdate(
                    status=models.TaskStatus.RETRY, error_message=error_message
                )
                crud.TaskCRUD.update_task(db, task_id, update_data)

                # Retry the task
                raise self.retry(countdown=60 * task.retry_count)  # Exponential backoff

            # Create audit log
            audit_data = schemas.AuditLogCreate(
                event_type="TASK_FAILED",
                agent_id=agent.id,
                task_id=task_id,
                details={
                    "error": error_message,
                    "retry_count": task.retry_count,
                    "execution_time": result.get("execution_time", 0),
                },
            )
            crud.AuditLogCRUD.create_log(db, audit_data)

            return {"success": False, "error": error_message, "task_id": task_id}

    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}", exc_info=True)

        # Update task status to failed
        update_data = schemas.TaskUpdate(
            status=models.TaskStatus.FAILED, error_message=str(e)
        )
        crud.TaskCRUD.update_task(db, task_id, update_data)

        # Create audit log
        audit_data = schemas.AuditLogCreate(
            event_type="TASK_ERROR",
            task_id=task_id,
            details={"error": str(e), "traceback": str(e)},
        )
        crud.AuditLogCRUD.create_log(db, audit_data)

        return {"success": False, "error": str(e), "task_id": task_id}

    finally:
        db.close()


@celery_app.task
def batch_and_process_tasks():
    """Periodic task to batch and process pending tasks"""
    db = next(get_db())

    try:
        logger.info("Starting batch processing of tasks")

        # Get batchable tasks
        batches = task_batcher.get_batchable_tasks(db)

        if not batches:
            logger.info("No tasks to batch")
            return {"message": "No tasks to batch"}

        processed_batches = 0
        total_tasks = 0

        for batch in batches:
            if not batch:
                continue

            # Check if we can process this batch
            if not task_batcher.can_batch_tasks(batch):
                logger.warning(
                    f"Cannot batch {len(batch)} tasks, processing individually"
                )
                for task in batch:
                    process_single_task.delay(task.id)
                continue

            # Optimize batch order
            optimized_batch = task_batcher.optimize_batch_order(batch)

            # Mark batch as queued
            task_batcher.mark_batch_as_queued(db, optimized_batch)

            # Process batch
            process_task_batch.delay([task.id for task in optimized_batch])

            processed_batches += 1
            total_tasks += len(optimized_batch)

        logger.info(
            f"Processed {processed_batches} batches with {total_tasks} total tasks"
        )

        return {"processed_batches": processed_batches, "total_tasks": total_tasks}

    except Exception as e:
        logger.error(f"Error in batch processing: {str(e)}", exc_info=True)
        return {"error": str(e)}

    finally:
        db.close()


@celery_app.task(bind=True)
def process_task_batch(self, task_ids: List[int]):
    """Process a batch of tasks"""
    db = next(get_db())

    try:
        start_time = datetime.now(timezone.utc)

        # Get tasks
        tasks = [crud.TaskCRUD.get_task(db, task_id) for task_id in task_ids]
        tasks = [task for task in tasks if task]  # Filter out None

        if not tasks:
            logger.warning("No valid tasks found for batch processing")
            return {"error": "No valid tasks found"}

        # Get available agent
        agent = quota_manager.get_available_agent(db)
        if not agent:
            logger.warning("No available agents for batch processing")
            # Fall back to individual processing
            for task_id in task_ids:
                process_single_task.delay(task_id)
            return {"message": "Fallback to individual processing"}

        # Process each task in the batch
        results = []
        successful_count = 0
        failed_count = 0
        task_types = {}

        for task in tasks:
            try:
                # Update task status
                update_data = schemas.TaskUpdate(
                    status=models.TaskStatus.IN_PROGRESS, assigned_agent_id=agent.id
                )
                crud.TaskCRUD.update_task(db, task.id, update_data)

                # Get context
                context = shared_memory.get_task_context(task)

                # Execute task
                agent_wrapper = agent_manager.get_agent(agent.id)
                result = asyncio.run(agent_wrapper.execute_task(task, context))

                if result["success"]:
                    # Store successful result
                    session_data = schemas.TaskSessionCreate(
                        task_id=task.id,
                        prompt=result["prompt"],
                        response=result["result"],
                        result=result,
                        execution_time_seconds=result["execution_time"],
                    )
                    crud.TaskSessionCRUD.create_session(db, session_data)

                    update_data = schemas.TaskUpdate(status=models.TaskStatus.COMPLETED)
                    crud.TaskCRUD.update_task(db, task.id, update_data)

                    shared_memory.store_task_result(task, result)
                    successful_count += 1
                else:
                    # Handle failure
                    update_data = schemas.TaskUpdate(
                        status=models.TaskStatus.FAILED,
                        error_message=result.get("error", "Unknown error"),
                    )
                    crud.TaskCRUD.update_task(db, task.id, update_data)
                    failed_count += 1

                # Count task types
                task_types[task.type] = task_types.get(task.type, 0) + 1
                results.append({"task_id": task.id, "success": result["success"]})

            except Exception as e:
                logger.error(f"Error processing task {task.id} in batch: {str(e)}")
                update_data = schemas.TaskUpdate(
                    status=models.TaskStatus.FAILED, error_message=str(e)
                )
                crud.TaskCRUD.update_task(db, task.id, update_data)
                failed_count += 1
                results.append({"task_id": task.id, "success": False, "error": str(e)})

        # Calculate processing time
        processing_time = int((datetime.now(timezone.utc) - start_time).total_seconds())

        # Send batch completion notification
        batch_summary = {
            "task_count": len(tasks),
            "successful_count": successful_count,
            "failed_count": failed_count,
            "processing_time_seconds": processing_time,
            "agent_id": agent.id,
            "task_types": task_types,
        }

        asyncio.run(notification_manager.send_batch_completion_alert(batch_summary))

        logger.info(
            f"Batch processing completed: {successful_count} successful, {failed_count} failed"
        )

        return {"batch_summary": batch_summary, "results": results}

    except Exception as e:
        logger.error(f"Error in batch processing: {str(e)}", exc_info=True)
        return {"error": str(e)}

    finally:
        db.close()


@celery_app.task
def cleanup_expired_cache():
    """Cleanup expired cache entries"""
    try:
        shared_memory.clear_expired_cache()
        logger.info("Cache cleanup completed")
        return {"message": "Cache cleanup completed"}

    except Exception as e:
        logger.error(f"Error in cache cleanup: {str(e)}")
        return {"error": str(e)}


@celery_app.task
def health_check_task():
    """Periodic health check task"""
    db = next(get_db())

    try:
        # Basic health checks
        health_issues = []

        # Check database connectivity
        try:
            from sqlalchemy import text
            db.execute(text("SELECT 1"))
        except Exception as e:
            health_issues.append(f"Database connectivity issue: {str(e)}")

        # Check Redis connectivity
        try:
            import redis

            redis_client = redis.from_url(settings.redis_url)
            redis_client.ping()
        except Exception as e:
            health_issues.append(f"Redis connectivity issue: {str(e)}")

        # Check agent availability
        try:
            quota_status = quota_manager.get_quota_status(db)
            if quota_status["available_agents"] == 0:
                health_issues.append("No agents available for task processing")
        except Exception as e:
            health_issues.append(f"Agent status check failed: {str(e)}")

        # Send alert if issues found
        if health_issues:
            health_status = {
                "status": "degraded",
                "issues": health_issues,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            asyncio.run(notification_manager.send_system_health_alert(health_status))

        return {
            "status": "healthy" if not health_issues else "degraded",
            "issues": health_issues,
        }

    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        return {"error": str(e)}

    finally:
        db.close()
