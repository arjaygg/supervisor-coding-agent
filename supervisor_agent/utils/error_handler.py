"""
Centralized error handling utilities.
Eliminates DRY violations in error handling patterns.
"""
import logging
from typing import Dict, Any, Callable, Optional
from datetime import datetime, timezone
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class ErrorHandler:
    """Centralized error handling utility."""
    
    @staticmethod
    def handle_cost_tracking_error(task_id: int, error: Exception) -> None:
        """Handle cost tracking errors with consistent logging."""
        logger.warning(f"Failed to track cost for task {task_id}: {str(error)}")
    
    @staticmethod
    def handle_task_execution_error(
        task_id: int, 
        error: Exception, 
        execution_time_ms: int = 0,
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle task execution errors with consistent format."""
        logger.error(f"Task {task_id} failed: {str(error)}")
        
        return {
            "success": False,
            "error": str(error),
            "execution_time_ms": execution_time_ms,
            "prompt": prompt,
            "task_id": task_id
        }
    
    @staticmethod
    async def with_cost_tracking(
        task_id: int, 
        cost_tracker,
        db_session,
        agent_id: str,
        prompt: str,
        response: str,
        execution_time_ms: int,
        context: Dict[str, Any],
        operation: Callable
    ) -> None:
        """Execute cost tracking with error handling."""
        try:
            await operation()
        except Exception as cost_error:
            ErrorHandler.handle_cost_tracking_error(task_id, cost_error)
    
    @staticmethod
    def track_execution_cost(
        cost_tracker,
        db_session,
        task_id: int,
        agent_id: str,
        prompt: str,
        response: str,
        execution_time_ms: int,
        context: Dict[str, Any]
    ) -> None:
        """Track execution cost with error handling."""
        try:
            cost_tracker.track_task_execution(
                db=db_session,
                task_id=task_id,
                agent_id=agent_id,
                prompt=prompt,
                response=response,
                execution_time_ms=execution_time_ms,
                context=context,
            )
        except Exception as cost_error:
            ErrorHandler.handle_cost_tracking_error(task_id, cost_error)
    
    @staticmethod
    def calculate_execution_time(start_time: datetime) -> tuple[int, int]:
        """Calculate execution time in seconds and milliseconds."""
        end_time = datetime.now(timezone.utc)
        execution_time = int((end_time - start_time).total_seconds())
        execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
        return execution_time, execution_time_ms
    
    @staticmethod
    def create_success_response(
        result: str,
        execution_time: int,
        execution_time_ms: int,
        prompt: str
    ) -> Dict[str, Any]:
        """Create a standardized success response."""
        return {
            "success": True,
            "result": result,
            "execution_time": execution_time,
            "execution_time_ms": execution_time_ms,
            "prompt": prompt,
        }
    
    @staticmethod
    def create_error_response(
        error: Exception,
        execution_time: int,
        execution_time_ms: int,
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a standardized error response."""
        return {
            "success": False,
            "error": str(error),
            "execution_time": execution_time,
            "execution_time_ms": execution_time_ms,
            "prompt": prompt,
        }