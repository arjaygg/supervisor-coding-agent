"""
Task execution service using dependency injection.
Implements Single Responsibility Principle by focusing only on task execution.
"""
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from supervisor_agent.db.models import Task
from supervisor_agent.core.prompt_builder import PromptBuilder
from supervisor_agent.core.cli_manager import CLIManager, CLIValidationError, CLIExecutionError
from supervisor_agent.core.mock_response_generator import MockResponseGenerator
from supervisor_agent.core.cost_tracker import cost_tracker
from supervisor_agent.utils.error_handler import ErrorHandler
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class TaskExecutor:
    """Focused task executor using dependency injection."""
    
    def __init__(
        self,
        agent_id: str,
        cli_manager: CLIManager,
        prompt_builder: PromptBuilder,
        mock_generator: MockResponseGenerator
    ):
        self.agent_id = agent_id
        self.cli_manager = cli_manager
        self.prompt_builder = prompt_builder
        self.mock_generator = mock_generator
    
    async def execute_task(
        self,
        task: Task,
        shared_memory: Dict[str, Any],
        db_session=None
    ) -> Dict[str, Any]:
        """Execute a task with proper separation of concerns."""
        start_time = datetime.now(timezone.utc)
        prompt = None
        result = None
        
        try:
            # Build prompt using dedicated builder
            prompt = self._build_task_prompt(task, shared_memory)
            
            logger.info(f"Executing task {task.id} with agent {self.agent_id}")
            
            # Execute task using CLI manager
            result = await self._execute_with_cli(prompt)
            
            # Calculate execution time
            execution_time, execution_time_ms = ErrorHandler.calculate_execution_time(start_time)
            
            # Track cost if database session is provided
            if db_session:
                ErrorHandler.track_execution_cost(
                    cost_tracker=cost_tracker,
                    db_session=db_session,
                    task_id=task.id,
                    agent_id=self.agent_id,
                    prompt=prompt,
                    response=result,
                    execution_time_ms=execution_time_ms,
                    context=shared_memory
                )
            
            return ErrorHandler.create_success_response(
                result=result,
                execution_time=execution_time,
                execution_time_ms=execution_time_ms,
                prompt=prompt
            )
        
        except Exception as e:
            # Calculate execution time for error case
            execution_time, execution_time_ms = ErrorHandler.calculate_execution_time(start_time)
            
            logger.error(f"Task {task.id} failed with agent {self.agent_id}: {str(e)}")
            
            # Track failed execution cost if database session is provided
            if db_session and prompt:
                ErrorHandler.track_execution_cost(
                    cost_tracker=cost_tracker,
                    db_session=db_session,
                    task_id=task.id,
                    agent_id=self.agent_id,
                    prompt=prompt,
                    response="",  # Empty response for failed tasks
                    execution_time_ms=execution_time_ms,
                    context=shared_memory
                )
            
            return ErrorHandler.create_error_response(
                error=e,
                execution_time=execution_time,
                execution_time_ms=execution_time_ms,
                prompt=prompt
            )
    
    def _build_task_prompt(self, task: Task, shared_memory: Dict[str, Any]) -> str:
        """Build prompt using the dedicated prompt builder."""
        if task.type is None:
            raise ValueError("Task type cannot be None")
        
        return self.prompt_builder.build_prompt(
            task_type=task.type,
            payload=task.payload,
            shared_memory=shared_memory
        )
    
    async def _execute_with_cli(self, prompt: str) -> str:
        """Execute prompt using CLI manager with fallback to mock responses."""
        try:
            return await self.cli_manager.execute_cli(prompt)
        except (CLIValidationError, CLIExecutionError) as e:
            logger.warning(f"CLI execution failed, using mock response: {str(e)}")
            return self.mock_generator.generate_response(prompt)