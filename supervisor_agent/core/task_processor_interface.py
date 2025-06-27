from abc import ABC, abstractmethod
from typing import Protocol
from sqlalchemy.orm import Session


class TaskProcessor(Protocol):
    """Interface for task processing strategies"""
    
    async def queue_task(self, task_id: int, db: Session) -> None:
        """Queue a task for processing"""
        ...


class AsyncTaskProcessor:
    """Celery-based async task processor for production"""
    
    def __init__(self):
        self.name = "async"
    
    async def queue_task(self, task_id: int, db: Session) -> None:
        """Queue task using Celery"""
        from supervisor_agent.queue.tasks import process_single_task
        process_single_task.delay(task_id)


class SyncTaskProcessor:
    """Direct synchronous task processor for development"""
    
    def __init__(self):
        self.name = "sync"
    
    async def queue_task(self, task_id: int, db: Session) -> None:
        """Process task directly in background"""
        import asyncio
        from supervisor_agent.utils.logger import get_logger
        
        logger = get_logger(__name__)
        logger.info(f"Processing task {task_id} synchronously (development mode)")
        
        # Process in background to avoid blocking the API response
        asyncio.create_task(self._process_task_background(task_id))
    
    async def _process_task_background(self, task_id: int):
        """Process task in background without blocking"""
        from supervisor_agent.utils.logger import get_logger
        logger = get_logger(__name__)
        
        try:
            # Import the synchronous task processing function 
            from supervisor_agent.queue.tasks import process_single_task
            from supervisor_agent.db.database import SessionLocal, get_db
            from supervisor_agent.db import crud, schemas, models
            
            # Process the task directly (bypassing Celery)
            # Create a mock Celery task object to satisfy the function signature
            class MockTask:
                def retry(self, countdown=None):
                    raise Exception("Max retries exceeded in sync mode")
            
            mock_task = MockTask()
            
            # Get database session
            db_gen = get_db()
            db = next(db_gen)
            
            try:
                # Call the main task processing logic
                task = crud.TaskCRUD.get_task(db, task_id)
                if not task:
                    logger.error(f"Task {task_id} not found")
                    return
                
                # Update task status to in progress
                update_data = schemas.TaskUpdate(status=models.TaskStatus.IN_PROGRESS)
                crud.TaskCRUD.update_task(db, task_id, update_data)
                db.commit()
                
                # Get available agent and process
                from supervisor_agent.core.quota import quota_manager
                from supervisor_agent.core.memory import shared_memory
                from supervisor_agent.core.agent import agent_manager
                
                agent = quota_manager.get_available_agent(db)
                if not agent:
                    logger.warning(f"No available agents for task {task_id}")
                    update_data = schemas.TaskUpdate(
                        status=models.TaskStatus.FAILED,
                        error_message="No available agents"
                    )
                    crud.TaskCRUD.update_task(db, task_id, update_data)
                    db.commit()
                    return
                
                # Execute the task using Claude agent
                claude_agent = agent_manager.get_agent(agent.id)
                if not claude_agent:
                    logger.error(f"Agent {agent.id} not found in agent manager")
                    return
                
                # Get shared memory context
                memory_context = shared_memory.get_context_for_task(task.id)
                
                # Execute task
                result = await claude_agent.execute_task(task, memory_context, db)
                
                if result["success"]:
                    # Update task as completed
                    update_data = schemas.TaskUpdate(
                        status=models.TaskStatus.COMPLETED,
                        assigned_agent_id=agent.id,
                        result=result["result"]
                    )
                    crud.TaskCRUD.update_task(db, task_id, update_data)
                    
                    # Update quota usage
                    quota_manager.update_agent_usage(db, agent.id, 1)
                    
                    logger.info(f"Task {task_id} completed successfully")
                else:
                    # Update task as failed
                    update_data = schemas.TaskUpdate(
                        status=models.TaskStatus.FAILED,
                        assigned_agent_id=agent.id,
                        error_message=result.get("error", "Unknown error")
                    )
                    crud.TaskCRUD.update_task(db, task_id, update_data)
                    logger.error(f"Task {task_id} failed: {result.get('error', 'Unknown error')}")
                
                db.commit()
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to process task {task_id} in sync mode: {str(e)}")
            
            # Update task status to failed
            try:
                from supervisor_agent.db.database import SessionLocal
                from supervisor_agent.db import crud, schemas
                from supervisor_agent.db.enums import TaskStatus
                
                with SessionLocal() as task_db:
                    update_data = schemas.TaskUpdate(
                        status=TaskStatus.FAILED,
                        error_message=str(e)
                    )
                    crud.TaskCRUD.update_task(task_db, task_id, update_data)
                    task_db.commit()
            except Exception as update_error:
                logger.error(f"Failed to update task {task_id} status to failed: {str(update_error)}")


class TaskProcessorFactory:
    """Factory for creating appropriate task processors"""
    
    @staticmethod
    def create_processor() -> TaskProcessor:
        """Create processor based on configuration"""
        from supervisor_agent.config import settings
        from supervisor_agent.utils.logger import get_logger
        
        logger = get_logger(__name__)
        
        try:
            if settings.celery_required:
                logger.info("Using async task processor (Celery)")
                return AsyncTaskProcessor()
            else:
                logger.info("Using sync task processor (development mode)")
                return SyncTaskProcessor()
        except Exception as e:
            logger.warning(f"Failed to create async processor, falling back to sync: {str(e)}")
            return SyncTaskProcessor()