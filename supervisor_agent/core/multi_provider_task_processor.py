"""
Multi-Provider Task Processor

Enhanced task processor that integrates with the multi-provider architecture.
Extends the existing IntelligentTaskProcessor with provider coordination,
sophisticated routing logic, and cross-provider optimization.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from supervisor_agent.api.websocket import (
    notify_quota_update,
    notify_system_event,
)
from supervisor_agent.core.intelligent_task_processor import (
    IntelligentTaskProcessor,
)
from supervisor_agent.core.multi_provider_subscription_intelligence import (
    MultiProviderSubscriptionIntelligence,
)
from supervisor_agent.core.provider_coordinator import (
    ExecutionContext,
    ProviderCoordinator,
    TaskAffinityStrategy,
)
from supervisor_agent.db.crud import ProviderUsageCRUD, TaskCRUD
from supervisor_agent.db.enums import TaskStatus, TaskType
from supervisor_agent.db.models import Task
from supervisor_agent.providers.base_provider import (
    AIProvider,
    ProviderError,
    ProviderResponse,
)
from supervisor_agent.providers.provider_registry import (
    LoadBalancingStrategy,
    ProviderRegistry,
)

logger = logging.getLogger(__name__)


class TaskPriority(str, Enum):
    """Task priority levels for routing decisions"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class RoutingStrategy(str, Enum):
    """Task routing strategies"""

    OPTIMAL = "optimal"  # Balance all factors
    FASTEST = "fastest"  # Minimize response time
    CHEAPEST = "cheapest"  # Minimize cost
    MOST_RELIABLE = "most_reliable"  # Maximize success rate
    LOAD_BALANCED = "load_balanced"  # Distribute load evenly


class TaskBatch:
    """Represents a batch of related tasks for optimization"""

    def __init__(self, tasks: List[Task], batch_type: str = "general"):
        self.tasks = tasks
        self.batch_type = batch_type
        self.created_at = datetime.now(timezone.utc)
        self.total_estimated_cost = 0.0
        self.preferred_provider: Optional[str] = None

    @property
    def task_count(self) -> int:
        return len(self.tasks)

    @property
    def batch_id(self) -> str:
        return f"batch_{int(self.created_at.timestamp())}_{self.task_count}"


class MultiProviderTaskProcessor:
    """
    Advanced task processor with multi-provider coordination and intelligent routing.

    Extends IntelligentTaskProcessor with:
    - Provider selection and coordination
    - Cross-provider load balancing
    - Cost optimization
    - Automatic failover and retry logic
    - Task affinity and batching
    """

    def __init__(
        self,
        provider_registry: ProviderRegistry,
        provider_coordinator: ProviderCoordinator,
        subscription_intelligence: MultiProviderSubscriptionIntelligence,
        default_routing_strategy: RoutingStrategy = RoutingStrategy.OPTIMAL,
        max_retry_attempts: int = 3,
        failover_enabled: bool = True,
        batch_optimization_enabled: bool = True,
    ):
        # Initialize base processor
        self.base_processor = IntelligentTaskProcessor()

        # Multi-provider components
        self.provider_registry = provider_registry
        self.provider_coordinator = provider_coordinator
        self.subscription_intelligence = subscription_intelligence

        # Configuration
        self.default_routing_strategy = default_routing_strategy
        self.max_retry_attempts = max_retry_attempts
        self.failover_enabled = failover_enabled
        self.batch_optimization_enabled = batch_optimization_enabled

        # Performance tracking
        self.processing_stats = {
            "total_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "retry_tasks": 0,
            "cache_hits": 0,
            "provider_switches": 0,
            "batch_optimizations": 0,
            "total_cost_usd": 0.0,
            "average_response_time": 0.0,
            "provider_distribution": {},
        }

        # Task queues for batching
        self._task_queues: Dict[str, List[Task]] = {}
        self._batch_timers: Dict[str, asyncio.Task] = {}
        self._processing_tasks: Dict[str, asyncio.Task] = {}

        logger.info(
            f"Multi-Provider Task Processor initialized with strategy: {default_routing_strategy}"
        )

    async def process_task(
        self,
        task: Task,
        agent_processor: Callable[[Task, Dict[str, Any]], Dict[str, Any]],
        context: Optional[ExecutionContext] = None,
        routing_strategy: Optional[RoutingStrategy] = None,
        shared_memory: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a single task with multi-provider coordination

        Args:
            task: Task to process
            agent_processor: Function to process task with agent
            context: Execution context with preferences and constraints
            routing_strategy: Override for routing strategy
            shared_memory: Shared context between tasks

        Returns:
            Task execution result
        """
        start_time = time.time()
        self.processing_stats["total_tasks"] += 1

        try:
            # Use provided context or create default
            if context is None:
                context = ExecutionContext(
                    priority=self._determine_task_priority(task),
                    metadata={"task_type": str(task.type)},
                )

            # Use provided strategy or default
            strategy = routing_strategy or self.default_routing_strategy

            logger.info(f"Processing task {task.id} with strategy {strategy}")

            # Check for cached result first
            cached_result = await self._check_task_cache(task, shared_memory)
            if cached_result:
                self.processing_stats["cache_hits"] += 1
                logger.info(f"Task {task.id} resolved from cache")
                return cached_result

            # Apply routing strategy to adjust context
            context = await self._apply_routing_strategy(strategy, task, context)

            # Select optimal provider
            selected_provider_id = await self.provider_coordinator.select_provider(
                task, context
            )
            if not selected_provider_id:
                raise ProviderError("No suitable provider available for task")

            logger.info(f"Selected provider {selected_provider_id} for task {task.id}")

            # Execute task with provider
            result = await self._execute_task_with_provider(
                task,
                selected_provider_id,
                agent_processor,
                context,
                shared_memory,
            )

            # Update statistics
            execution_time = time.time() - start_time
            await self._update_processing_stats(
                selected_provider_id, result, execution_time
            )

            return result

        except Exception as e:
            # Handle failures with retry/failover logic
            logger.error(f"Task {task.id} processing failed: {str(e)}")

            if self.failover_enabled:
                return await self._handle_task_failure(
                    task,
                    agent_processor,
                    context,
                    shared_memory,
                    str(e),
                    start_time,
                )
            else:
                self.processing_stats["failed_tasks"] += 1
                return {
                    "success": False,
                    "error": str(e),
                    "execution_time": time.time() - start_time,
                    "provider_id": None,
                }

    async def process_task_batch(
        self,
        tasks: List[Task],
        agent_processor: Callable[[Task, Dict[str, Any]], Dict[str, Any]],
        context: Optional[ExecutionContext] = None,
        max_concurrent: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Process multiple tasks with batch optimization

        Args:
            tasks: List of tasks to process
            agent_processor: Function to process individual tasks
            context: Shared execution context
            max_concurrent: Maximum concurrent task executions

        Returns:
            List of task execution results
        """
        if not tasks:
            return []

        logger.info(f"Processing batch of {len(tasks)} tasks")

        # Create task batch for optimization
        task_batch = TaskBatch(tasks, "user_batch")

        # Optimize batch if enabled
        if self.batch_optimization_enabled:
            optimized_batches = await self._optimize_task_batch(task_batch, context)
        else:
            optimized_batches = [task_batch]

        # Process optimized batches
        all_results = []

        for batch in optimized_batches:
            # Create semaphore for concurrency control
            semaphore = asyncio.Semaphore(max_concurrent)

            async def process_single_task(task: Task) -> Dict[str, Any]:
                async with semaphore:
                    return await self.process_task(task, agent_processor, context)

            # Execute tasks concurrently within batch
            batch_results = await asyncio.gather(
                *[process_single_task(task) for task in batch.tasks],
                return_exceptions=True,
            )

            # Handle any exceptions
            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    batch_results[i] = {
                        "success": False,
                        "error": str(result),
                        "task_id": batch.tasks[i].id,
                        "execution_time": 0.0,
                    }

            all_results.extend(batch_results)

        self.processing_stats["batch_optimizations"] += 1
        logger.info(f"Completed batch processing: {len(all_results)} results")

        return all_results

    async def get_processing_stats(self) -> Dict[str, Any]:
        """Get comprehensive processing statistics"""
        stats = self.processing_stats.copy()

        # Add derived metrics
        if stats["total_tasks"] > 0:
            stats["success_rate"] = stats["successful_tasks"] / stats["total_tasks"]
            stats["cache_hit_rate"] = stats["cache_hits"] / stats["total_tasks"]
        else:
            stats["success_rate"] = 0.0
            stats["cache_hit_rate"] = 0.0

        # Add provider statistics
        provider_stats = {}
        for provider_id in self.provider_registry.providers.keys():
            provider_stats[provider_id] = {
                "usage_count": stats["provider_distribution"].get(provider_id, 0),
                "quota_status": await self.subscription_intelligence.get_quota_status(
                    provider_id
                ),
            }

        stats["provider_stats"] = provider_stats

        # Add current system status
        stats["system_status"] = {
            "active_providers": len(
                [
                    p
                    for p in self.provider_registry.providers.keys()
                    if await self._is_provider_available(p)
                ]
            ),
            "total_providers": len(self.provider_registry.providers),
            "pending_batches": len(self._task_queues),
            "processing_tasks": len(self._processing_tasks),
        }

        return stats

    async def _check_task_cache(
        self, task: Task, shared_memory: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Check if task result is available in cache"""
        try:
            # Create request data for cache lookup
            request_data = {
                "task_type": str(task.type),
                "payload": task.payload,
                "shared_memory": shared_memory or {},
            }

            # Check multi-provider cache
            optimal_provider = (
                await self.subscription_intelligence.get_optimal_provider(request_data)
            )

            if optimal_provider == "cache":
                # Cache hit - return cached result
                return {
                    "success": True,
                    "result": "Cached response",  # In real implementation, return actual cached result
                    "cached": True,
                    "execution_time": 0.001,
                    "provider_id": "cache",
                }

        except Exception as e:
            logger.debug(f"Cache check failed: {str(e)}")

        return None

    async def _apply_routing_strategy(
        self, strategy: RoutingStrategy, task: Task, context: ExecutionContext
    ) -> ExecutionContext:
        """Apply routing strategy to modify execution context"""
        if strategy == RoutingStrategy.FASTEST:
            # Prioritize speed over cost
            context.max_cost_usd = None  # Remove cost constraints
            context.require_capabilities = ["fast_response"]

        elif strategy == RoutingStrategy.CHEAPEST:
            # Prioritize cost optimization
            context.max_cost_usd = 0.10  # Low cost threshold

        elif strategy == RoutingStrategy.MOST_RELIABLE:
            # Prioritize reliability
            context.require_capabilities = ["high_reliability"]

        elif strategy == RoutingStrategy.LOAD_BALANCED:
            # Ensure even distribution
            # This would be handled by the provider coordinator's load balancing
            pass

        # OPTIMAL strategy uses default context without modifications

        return context

    async def _execute_task_with_provider(
        self,
        task: Task,
        provider_id: str,
        agent_processor: Callable,
        context: ExecutionContext,
        shared_memory: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute task with specified provider"""
        provider = self.provider_registry.get_provider(provider_id)
        if not provider:
            raise ProviderError(f"Provider {provider_id} not found")

        start_time = time.time()

        try:
            # Execute task with provider
            response = await provider.execute_task(task, shared_memory or {})

            if not response.success:
                raise ProviderError(
                    f"Provider execution failed: {response.error_message}"
                )

            execution_time = time.time() - start_time

            # Track the request
            await self.subscription_intelligence.track_request(
                provider_id=provider_id,
                request_data={
                    "task_type": str(task.type),
                    "payload": task.payload,
                },
                response=response.result,
                execution_time=execution_time,
                cost_usd=(
                    float(response.cost_estimate.total_cost_usd)
                    if response.cost_estimate
                    else 0.0
                ),
                success=True,
            )

            # Update task affinity tracking
            self.provider_coordinator.task_affinity_tracker.record_assignment(
                task, provider_id
            )
            self.provider_coordinator.task_affinity_tracker.record_performance(
                provider_id, True, execution_time
            )

            result = {
                "success": True,
                "result": response.result,
                "execution_time": execution_time,
                "provider_id": provider_id,
                "cost_usd": (
                    float(response.cost_estimate.total_cost_usd)
                    if response.cost_estimate
                    else 0.0
                ),
                "tokens_used": response.tokens_used,
                "metadata": response.metadata,
            }

            logger.debug(
                f"Task {task.id} executed successfully with provider {provider_id}"
            )
            return result

        except Exception as e:
            execution_time = time.time() - start_time

            # Track failed request
            await self.subscription_intelligence.track_request(
                provider_id=provider_id,
                request_data={
                    "task_type": str(task.type),
                    "payload": task.payload,
                },
                response=None,
                execution_time=execution_time,
                cost_usd=0.0,
                success=False,
            )

            # Update performance tracking
            self.provider_coordinator.task_affinity_tracker.record_performance(
                provider_id, False, execution_time
            )

            raise e

    async def _handle_task_failure(
        self,
        task: Task,
        agent_processor: Callable,
        context: ExecutionContext,
        shared_memory: Optional[Dict[str, Any]],
        error_message: str,
        start_time: float,
    ) -> Dict[str, Any]:
        """Handle task failure with retry and failover logic"""
        retry_count = getattr(task, "retry_count", 0)

        if retry_count < self.max_retry_attempts:
            logger.info(
                f"Retrying task {task.id} (attempt {retry_count + 1}/{self.max_retry_attempts})"
            )

            # Get backup provider
            try:
                failed_provider_id = (
                    context.exclude_providers[-1] if context.exclude_providers else None
                )
                backup_provider_id = (
                    await self.provider_coordinator.select_backup_provider(
                        task, failed_provider_id or "unknown", context
                    )
                )

                if backup_provider_id:
                    # Retry with backup provider
                    task.retry_count = retry_count + 1
                    self.processing_stats["retry_tasks"] += 1
                    self.processing_stats["provider_switches"] += 1

                    return await self._execute_task_with_provider(
                        task,
                        backup_provider_id,
                        agent_processor,
                        context,
                        shared_memory,
                    )

            except Exception as retry_error:
                logger.error(f"Retry failed for task {task.id}: {str(retry_error)}")

        # All retries exhausted or no backup available
        self.processing_stats["failed_tasks"] += 1
        execution_time = time.time() - start_time

        return {
            "success": False,
            "error": error_message,
            "execution_time": execution_time,
            "retry_count": retry_count,
            "provider_id": None,
        }

    async def _optimize_task_batch(
        self, task_batch: TaskBatch, context: Optional[ExecutionContext]
    ) -> List[TaskBatch]:
        """Optimize task batch for efficient processing"""
        try:
            # Group tasks by type for better batching
            task_groups = {}
            for task in task_batch.tasks:
                task_type = str(task.type)
                if task_type not in task_groups:
                    task_groups[task_type] = []
                task_groups[task_type].append(task)

            # Create optimized batches
            optimized_batches = []
            for task_type, tasks in task_groups.items():
                # Further split large groups to respect provider limits
                batch_size = 5  # Configurable batch size
                for i in range(0, len(tasks), batch_size):
                    batch_tasks = tasks[i : i + batch_size]
                    optimized_batch = TaskBatch(batch_tasks, f"optimized_{task_type}")
                    optimized_batches.append(optimized_batch)

            logger.debug(
                f"Optimized {len(task_batch.tasks)} tasks into {len(optimized_batches)} batches"
            )
            return optimized_batches

        except Exception as e:
            logger.warning(f"Batch optimization failed: {str(e)}, using original batch")
            return [task_batch]

    def _determine_task_priority(self, task: Task) -> int:
        """Determine task priority based on task properties"""
        # Simple priority logic - can be enhanced based on requirements
        priority_map = {
            TaskType.BUG_FIX: 8,  # High priority
            TaskType.PR_REVIEW: 6,  # Medium-high priority
            TaskType.FEATURE: 5,  # Normal priority
            TaskType.REFACTOR: 4,  # Medium-low priority
            TaskType.CODE_ANALYSIS: 3,  # Low priority
        }

        return priority_map.get(task.type, 5)  # Default to normal priority

    async def _update_processing_stats(
        self, provider_id: str, result: Dict[str, Any], execution_time: float
    ) -> None:
        """Update processing statistics"""
        if result.get("success", False):
            self.processing_stats["successful_tasks"] += 1
        else:
            self.processing_stats["failed_tasks"] += 1

        # Update provider distribution
        if provider_id not in self.processing_stats["provider_distribution"]:
            self.processing_stats["provider_distribution"][provider_id] = 0
        self.processing_stats["provider_distribution"][provider_id] += 1

        # Update cost tracking
        cost = result.get("cost_usd", 0.0)
        self.processing_stats["total_cost_usd"] += cost

        # Update average response time
        current_avg = self.processing_stats["average_response_time"]
        total_tasks = self.processing_stats["total_tasks"]

        if total_tasks > 1:
            self.processing_stats["average_response_time"] = (
                current_avg * (total_tasks - 1) + execution_time
            ) / total_tasks
        else:
            self.processing_stats["average_response_time"] = execution_time

    async def _is_provider_available(self, provider_id: str) -> bool:
        """Check if provider is currently available"""
        try:
            quota_status = await self.subscription_intelligence.get_quota_status(
                provider_id
            )
            return bool(
                quota_status
                and quota_status[provider_id]
                and quota_status[provider_id].is_available
            )
        except Exception:
            return False
