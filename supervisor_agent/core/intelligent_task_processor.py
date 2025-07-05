"""
Intelligent Task Processor

Integrates Subscription Intelligence with existing task processing pipeline.
Provides optimized task execution with deduplication, batching, and quota management.

Follows evolutionary architecture principles with minimal disruption to existing code.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from supervisor_agent.api.websocket import (
    notify_quota_update,
    notify_system_event,
)
from supervisor_agent.core.subscription_intelligence import (
    SubscriptionIntelligence,
)
from supervisor_agent.db.enums import TaskStatus
from supervisor_agent.db.models import Task
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class IntelligentTaskProcessor:
    """
    Enhanced task processor that integrates subscription intelligence.

    This acts as a wrapper around the existing task processing logic,
    adding intelligent optimization without breaking existing functionality.
    """

    def __init__(
        self,
        daily_limit: int = 50000,
        batch_size: int = 5,
        cache_ttl_seconds: int = 300,
        batch_timeout_seconds: float = 2.0,
    ):
        self.subscription_intelligence = SubscriptionIntelligence(
            daily_limit=daily_limit,
            batch_size=batch_size,
            cache_ttl_seconds=cache_ttl_seconds,
            batch_timeout_seconds=batch_timeout_seconds,
        )

        # Performance tracking
        self.processing_stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "batched_requests": 0,
            "individual_requests": 0,
            "quota_warnings": 0,
        }

        logger.info(
            f"Intelligent Task Processor initialized: "
            f"daily_limit={daily_limit}, batch_size={batch_size}"
        )

    async def process_task(
        self, task: Task, agent_processor: Callable
    ) -> Dict[str, Any]:
        """
        Process a single task with intelligent optimization.

        Args:
            task: The task to process
            agent_processor: Function that actually processes the task

        Returns:
            Processing result with optimization metadata
        """
        self.processing_stats["total_requests"] += 1

        try:
            # Convert task to request format for subscription intelligence
            request = self._task_to_request(task)

            # Check quota and send warnings if needed
            await self._check_quota_warnings()

            # Process through subscription intelligence
            async def wrapped_processor(requests):
                if len(requests) == 1:
                    # Single task processing
                    self.processing_stats["individual_requests"] += 1
                    return await agent_processor(requests[0])
                else:
                    # Batch processing
                    self.processing_stats["batched_requests"] += len(requests)
                    # Convert requests back to tasks for batch processing
                    tasks = [self._request_to_task(req) for req in requests]
                    return await agent_processor(tasks)

            # Use subscription intelligence to optimize processing
            result = await self.subscription_intelligence.process_request(
                request, wrapped_processor
            )

            # Track cache hits
            from supervisor_agent.core.subscription_intelligence import (
                RequestHash,
            )

            request_hash = RequestHash.generate(request)
            if (
                request_hash
                in self.subscription_intelligence.deduplicator.cache
            ):
                cache_entry = (
                    self.subscription_intelligence.deduplicator.cache[
                        request_hash
                    ]
                )
                if cache_entry.hit_count > 0:
                    self.processing_stats["cache_hits"] += 1

            # Add optimization metadata
            result["optimization_metadata"] = {
                "was_cached": result.get("was_cached", False),
                "processing_time": result.get("processing_time", 0),
                "tokens_estimated": self.subscription_intelligence.estimate_token_usage(
                    request
                ),
                "batch_processed": (
                    len(request) > 1 if isinstance(request, list) else False
                ),
            }

            logger.debug(
                f"Task {task.id} processed: "
                f"cached={result['optimization_metadata']['was_cached']}, "
                f"tokens_est={result['optimization_metadata']['tokens_estimated']}"
            )

            return result

        except Exception as e:
            logger.error(
                f"Error in intelligent task processing for task {task.id}: {e}"
            )

            # Fall back to direct processing on optimization errors
            logger.warning(
                f"Falling back to direct processing for task {task.id}"
            )
            return await agent_processor(task)

    async def process_batch(
        self, tasks: List[Task], agent_processor: Callable
    ) -> List[Dict[str, Any]]:
        """
        Process a batch of tasks with intelligent optimization.

        Args:
            tasks: List of tasks to process
            agent_processor: Function that processes the batch

        Returns:
            List of processing results
        """
        if not tasks:
            return []

        try:
            # Group tasks by whether they should be batched
            batchable_tasks = []
            individual_tasks = []

            for task in tasks:
                if self.should_batch_task(task):
                    batchable_tasks.append(task)
                else:
                    individual_tasks.append(task)

            results = []

            # Process individual tasks
            for task in individual_tasks:
                result = await self.process_task(task, agent_processor)
                results.append(result)

            # Process batchable tasks as a group
            if batchable_tasks:
                batch_requests = [
                    self._task_to_request(task) for task in batchable_tasks
                ]

                async def batch_processor(requests):
                    # Convert back to tasks for agent processor
                    batch_tasks = [
                        self._request_to_task(req) for req in requests
                    ]
                    return await agent_processor(batch_tasks)

                # Process through subscription intelligence
                batch_results = []
                for request in batch_requests:
                    result = (
                        await self.subscription_intelligence.process_request(
                            request, batch_processor
                        )
                    )
                    batch_results.append(result)

                results.extend(batch_results)

            logger.info(
                f"Batch processed: {len(individual_tasks)} individual, "
                f"{len(batchable_tasks)} batched tasks"
            )

            return results

        except Exception as e:
            logger.error(f"Error in batch processing: {e}")

            # Fall back to processing all individually
            results = []
            for task in tasks:
                try:
                    result = await agent_processor(task)
                    results.append(result)
                except Exception as task_error:
                    logger.error(
                        f"Error processing task {task.id}: {task_error}"
                    )
                    results.append(
                        {
                            "success": False,
                            "error": str(task_error),
                            "task_id": task.id,
                        }
                    )

            return results

    def should_batch_task(self, task: Task) -> bool:
        """
        Determine if a task should be batched.

        Uses the same logic as subscription intelligence but operates on Task objects.
        """
        try:
            request = self._task_to_request(task)
            return self.subscription_intelligence.should_batch_request(request)
        except Exception as e:
            logger.warning(
                f"Error determining batch eligibility for task {task.id}: {e}"
            )
            return False

    def get_usage_metrics(self) -> Dict[str, Any]:
        """Get comprehensive usage and performance metrics."""
        base_metrics = self.subscription_intelligence.get_usage_stats()

        # Add our processing stats
        cache_hit_rate = (
            self.processing_stats["cache_hits"]
            / max(self.processing_stats["total_requests"], 1)
        ) * 100

        batch_efficiency = (
            self.processing_stats["batched_requests"]
            / max(self.processing_stats["total_requests"], 1)
        ) * 100

        return {
            **base_metrics,
            "processing_stats": {
                **self.processing_stats,
                "cache_hit_rate_percent": round(cache_hit_rate, 1),
                "batch_efficiency_percent": round(batch_efficiency, 1),
            },
        }

    async def force_process_pending(self):
        """Force process any pending batched tasks."""
        await self.subscription_intelligence.force_process_pending()

    async def shutdown(self):
        """Graceful shutdown of the processor."""
        logger.info("Shutting down Intelligent Task Processor")
        await self.subscription_intelligence.shutdown()

    def _task_to_request(self, task: Task) -> Dict[str, Any]:
        """Convert a Task object to a request format for subscription intelligence."""
        return {
            "task_id": task.id,
            "type": task.type,
            "payload": task.payload,
            "priority": task.priority,
            "status": task.status,
        }

    def _request_to_task(self, request: Dict[str, Any]) -> Task:
        """Convert a request back to a Task object (for compatibility)."""
        # This is a simplified conversion - in practice you might need
        # to retrieve the full task from database
        task = Task()
        task.id = request.get("task_id")
        task.type = request.get("type")
        task.payload = request.get("payload", {})
        task.priority = request.get("priority", 5)
        task.status = request.get("status", TaskStatus.PENDING)
        return task

    async def _check_quota_warnings(self):
        """Check quota usage and send warnings if needed."""
        usage_stats = self.subscription_intelligence.get_usage_stats()
        usage_percentage = usage_stats["usage_percentage"]

        # Send warnings at 75%, 90%, and 95%
        warning_thresholds = [75, 90, 95]

        for threshold in warning_thresholds:
            if usage_percentage >= threshold:
                self.processing_stats["quota_warnings"] += 1

                # Send WebSocket notification
                await notify_quota_update(
                    {
                        "current_usage": usage_stats["current_usage"],
                        "daily_limit": usage_stats["daily_limit"],
                        "usage_percentage": usage_percentage,
                        "warning_level": threshold,
                        "time_until_reset_hours": usage_stats[
                            "time_until_reset_hours"
                        ],
                    }
                )

                # Send system event for high usage
                if usage_percentage >= 90:
                    await notify_system_event(
                        event_type="quota_warning",
                        message=f"API quota at {usage_percentage:.1f}% of daily limit",
                        details=usage_stats,
                    )

                break  # Only send one warning per check


class TaskProcessorFactory:
    """Factory for creating and managing intelligent task processors."""

    _instance: Optional[IntelligentTaskProcessor] = None

    @classmethod
    def get_processor(
        cls,
        daily_limit: int = 50000,
        batch_size: int = 5,
        cache_ttl_seconds: int = 300,
    ) -> IntelligentTaskProcessor:
        """Get or create a singleton task processor instance."""
        if cls._instance is None:
            cls._instance = IntelligentTaskProcessor(
                daily_limit=daily_limit,
                batch_size=batch_size,
                cache_ttl_seconds=cache_ttl_seconds,
            )

        return cls._instance

    @classmethod
    async def shutdown_processor(cls):
        """Shutdown the current processor instance."""
        if cls._instance:
            await cls._instance.shutdown()
            cls._instance = None


# Global instance for easy access
intelligent_processor = TaskProcessorFactory.get_processor()


async def process_task_intelligently(
    task: Task, agent_processor: Callable
) -> Dict[str, Any]:
    """
    Convenience function for processing a single task with intelligence.

    This can be used as a drop-in replacement for direct agent processing.
    """
    processor = TaskProcessorFactory.get_processor()
    return await processor.process_task(task, agent_processor)


async def process_batch_intelligently(
    tasks: List[Task], agent_processor: Callable
) -> List[Dict[str, Any]]:
    """
    Convenience function for processing a batch of tasks with intelligence.

    This can be used as a drop-in replacement for direct batch processing.
    """
    processor = TaskProcessorFactory.get_processor()
    return await processor.process_batch(tasks, agent_processor)
