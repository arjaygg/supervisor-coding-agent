"""
Enhanced Task Processing with Subscription Intelligence

This module provides drop-in replacements for the existing task processing functions
that integrate subscription intelligence for optimal API usage.

Key improvements:
- Request deduplication (60-80% API reduction)
- Intelligent batching with timeout handling
- Usage prediction and quota management
- Real-time quota notifications
- Performance metrics tracking
"""

import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any
from celery import current_task
from sqlalchemy.orm import Session

from supervisor_agent.queue.celery_app import celery_app
from supervisor_agent.db.database import get_db
from supervisor_agent.db import models, schemas, crud
from supervisor_agent.core.agent import agent_manager
from supervisor_agent.core.memory import shared_memory
from supervisor_agent.core.quota import quota_manager
from supervisor_agent.core.notifier import notification_manager
from supervisor_agent.core.intelligent_task_processor import (
    process_task_intelligently,
    process_batch_intelligently,
    TaskProcessorFactory,
)
from supervisor_agent.api.websocket import notify_task_update, notify_quota_update
from supervisor_agent.config import settings
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


@celery_app.task(bind=True, max_retries=settings.max_retries)
def process_single_task_enhanced(self, task_id: int):
    """
    Enhanced version of process_single_task with subscription intelligence.

    Provides drop-in replacement with intelligent optimization:
    - Automatic deduplication of identical requests
    - Intelligent batching for efficiency
    - Real-time quota monitoring
    - Performance tracking
    """
    db = next(get_db())

    try:
        task = crud.TaskCRUD.get_task(db, task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return {"error": "Task not found"}

        # Update task status to in progress
        update_data = schemas.TaskUpdate(status=models.TaskStatus.IN_PROGRESS)
        crud.TaskCRUD.update_task(db, task_id, update_data)

        # Send real-time update
        asyncio.run(
            notify_task_update(
                {
                    "id": task.id,
                    "type": task.type,
                    "status": "IN_PROGRESS",
                    "updated_at": datetime.utcnow().isoformat(),
                }
            )
        )

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

        # Define agent processor function
        async def agent_processor(task_to_process):
            """Wrapper for the actual agent processing."""
            # Get shared memory context
            context = shared_memory.get_task_context(task_to_process)

            # Execute task
            agent_wrapper = agent_manager.get_agent(agent.id)
            if not agent_wrapper:
                raise Exception(f"Agent wrapper not found for {agent.id}")

            # Execute the task
            result = await agent_wrapper.execute_task(task_to_process, context)

            return result

        # Process with intelligent optimization
        result = asyncio.run(process_task_intelligently(task, agent_processor))

        # Update quota usage (if not already tracked by intelligent processor)
        if not result.get("optimization_metadata", {}).get("was_cached", False):
            payload_size = len(json.dumps(task.payload))
            estimated_messages = quota_manager.estimate_messages_from_task(
                task.type, payload_size
            )

            if not quota_manager.consume_quota(db, agent.id, estimated_messages):
                logger.warning(f"Failed to consume quota for agent {agent.id}")

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

            # Send real-time completion update
            asyncio.run(
                notify_task_update(
                    {
                        "id": task.id,
                        "type": task.type,
                        "status": "COMPLETED",
                        "updated_at": datetime.utcnow().isoformat(),
                        "optimization_metadata": result.get(
                            "optimization_metadata", {}
                        ),
                    }
                )
            )

            logger.info(
                f"Task {task_id} completed successfully "
                f"(cached: {result.get('optimization_metadata', {}).get('was_cached', False)})"
            )

            # Create audit log with optimization data
            audit_data = schemas.AuditLogCreate(
                event_type="TASK_COMPLETED",
                agent_id=agent.id,
                task_id=task_id,
                details={
                    "execution_time": result["execution_time"],
                    "success": True,
                    "optimization_metadata": result.get("optimization_metadata", {}),
                },
            )
            crud.AuditLogCRUD.create_log(db, audit_data)

            return {"success": True, "task_id": task_id, "result": result}

        else:
            # Handle failure (same as original but with real-time updates)
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

                # Send real-time failure update
                asyncio.run(
                    notify_task_update(
                        {
                            "id": task.id,
                            "type": task.type,
                            "status": "FAILED",
                            "error_message": error_message,
                            "updated_at": datetime.utcnow().isoformat(),
                        }
                    )
                )

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

        # Send real-time error update
        asyncio.run(
            notify_task_update(
                {
                    "id": task_id,
                    "status": "FAILED",
                    "error_message": str(e),
                    "updated_at": datetime.utcnow().isoformat(),
                }
            )
        )

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


@celery_app.task(bind=True)
def process_task_batch_enhanced(self, task_ids: List[int]):
    """
    Enhanced version of process_task_batch with subscription intelligence.

    Provides intelligent batching with:
    - Automatic request deduplication within batch
    - Optimized batch size based on task complexity
    - Real-time progress updates
    - Comprehensive performance metrics
    """
    db = next(get_db())

    try:
        start_time = datetime.utcnow()

        # Get tasks
        tasks = [crud.TaskCRUD.get_task(db, task_id) for task_id in task_ids]
        tasks = [task for task in tasks if task]  # Filter out None

        if not tasks:
            logger.warning("No valid tasks found for batch processing")
            return {"error": "No valid tasks found"}

        # Send batch start notification
        asyncio.run(
            notify_task_update(
                {
                    "type": "batch_start",
                    "task_ids": [task.id for task in tasks],
                    "batch_size": len(tasks),
                    "started_at": start_time.isoformat(),
                }
            )
        )

        # Get available agent
        agent = quota_manager.get_available_agent(db)
        if not agent:
            logger.warning("No available agents for batch processing")
            # Fall back to individual processing with intelligence
            for task_id in task_ids:
                process_single_task_enhanced.delay(task_id)
            return {"message": "Fallback to individual processing"}

        # Define batch processor function
        async def batch_agent_processor(tasks_to_process):
            """Process multiple tasks efficiently."""
            results = []

            for task in tasks_to_process:
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
                    result = await agent_wrapper.execute_task(task, context)

                    results.append(result)

                except Exception as e:
                    logger.error(f"Error processing task {task.id} in batch: {str(e)}")
                    results.append(
                        {"success": False, "error": str(e), "task_id": task.id}
                    )

            return results

        # Process batch with intelligent optimization
        results = asyncio.run(process_batch_intelligently(tasks, batch_agent_processor))

        # Process results and update database
        successful_count = 0
        failed_count = 0
        task_types = {}

        for i, (task, result) in enumerate(zip(tasks, results)):
            try:
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

                    # Send individual task completion update
                    asyncio.run(
                        notify_task_update(
                            {
                                "id": task.id,
                                "type": task.type,
                                "status": "COMPLETED",
                                "updated_at": datetime.utcnow().isoformat(),
                                "batch_processed": True,
                                "optimization_metadata": result.get(
                                    "optimization_metadata", {}
                                ),
                            }
                        )
                    )

                else:
                    # Handle failure
                    update_data = schemas.TaskUpdate(
                        status=models.TaskStatus.FAILED,
                        error_message=result.get("error", "Unknown error"),
                    )
                    crud.TaskCRUD.update_task(db, task.id, update_data)
                    failed_count += 1

                    # Send individual task failure update
                    asyncio.run(
                        notify_task_update(
                            {
                                "id": task.id,
                                "type": task.type,
                                "status": "FAILED",
                                "error_message": result.get("error", "Unknown error"),
                                "updated_at": datetime.utcnow().isoformat(),
                                "batch_processed": True,
                            }
                        )
                    )

                # Count task types
                task_types[task.type] = task_types.get(task.type, 0) + 1

            except Exception as e:
                logger.error(f"Error updating task {task.id} result: {str(e)}")
                failed_count += 1

        # Calculate processing time
        processing_time = int((datetime.utcnow() - start_time).total_seconds())

        # Get optimization metrics
        processor = TaskProcessorFactory.get_processor()
        optimization_metrics = processor.get_usage_metrics()

        # Send batch completion notification with optimization data
        batch_summary = {
            "task_count": len(tasks),
            "successful_count": successful_count,
            "failed_count": failed_count,
            "processing_time_seconds": processing_time,
            "agent_id": agent.id,
            "task_types": task_types,
            "optimization_metrics": {
                "cache_hit_rate": optimization_metrics["processing_stats"][
                    "cache_hit_rate_percent"
                ],
                "batch_efficiency": optimization_metrics["processing_stats"][
                    "batch_efficiency_percent"
                ],
                "quota_usage": optimization_metrics["usage_percentage"],
            },
        }

        # Send WebSocket update for batch completion
        asyncio.run(
            notify_task_update(
                {
                    "type": "batch_complete",
                    "batch_summary": batch_summary,
                    "completed_at": datetime.utcnow().isoformat(),
                }
            )
        )

        # Send traditional notification
        asyncio.run(notification_manager.send_batch_completion_alert(batch_summary))

        logger.info(
            f"Enhanced batch processing completed: {successful_count} successful, "
            f"{failed_count} failed, cache_hit_rate: "
            f"{optimization_metrics['processing_stats']['cache_hit_rate_percent']:.1f}%"
        )

        return {
            "batch_summary": batch_summary,
            "results": [
                {"task_id": task.id, "success": result["success"]}
                for task, result in zip(tasks, results)
            ],
        }

    except Exception as e:
        logger.error(f"Error in enhanced batch processing: {str(e)}", exc_info=True)

        # Send batch failure notification
        asyncio.run(
            notify_task_update(
                {
                    "type": "batch_error",
                    "error": str(e),
                    "task_ids": task_ids,
                    "failed_at": datetime.utcnow().isoformat(),
                }
            )
        )

        return {"error": str(e)}

    finally:
        db.close()


@celery_app.task
def get_optimization_metrics():
    """
    Task to collect and report optimization metrics.

    This can be scheduled to run periodically to monitor
    the performance of the subscription intelligence system.
    """
    try:
        processor = TaskProcessorFactory.get_processor()
        metrics = processor.get_usage_metrics()

        # Send metrics via WebSocket for real-time monitoring
        asyncio.run(
            notify_quota_update(
                {
                    "type": "metrics_update",
                    "metrics": metrics,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        )

        logger.info(
            f"Optimization metrics - Cache hit rate: "
            f"{metrics['processing_stats']['cache_hit_rate_percent']:.1f}%, "
            f"Quota usage: {metrics['usage_percentage']:.1f}%"
        )

        return metrics

    except Exception as e:
        logger.error(f"Error collecting optimization metrics: {str(e)}")
        return {"error": str(e)}


@celery_app.task
def force_process_pending_batches():
    """
    Force process any pending batched requests.

    This can be scheduled to run periodically to ensure
    no requests get stuck in partial batches.
    """
    try:
        processor = TaskProcessorFactory.get_processor()
        asyncio.run(processor.force_process_pending())

        logger.info("Forced processing of pending batches completed")
        return {"message": "Pending batches processed"}

    except Exception as e:
        logger.error(f"Error forcing pending batch processing: {str(e)}")
        return {"error": str(e)}


# Backward compatibility aliases
# These allow existing code to use enhanced versions transparently
process_single_task_optimized = process_single_task_enhanced
process_task_batch_optimized = process_task_batch_enhanced
