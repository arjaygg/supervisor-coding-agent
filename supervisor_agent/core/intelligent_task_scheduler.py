"""
Intelligent Task Scheduler

Advanced task scheduling with quota-aware priority management:
- Priority-based queue management with dynamic reordering
- Context-aware task scheduling based on quota availability
- Task complexity estimation for optimal batching
- Dynamic task deferral based on subscription limits
- Intelligent resource allocation and cost optimization
- Dependency graph management for task ordering
- Adaptive scheduling based on historical performance
"""

import asyncio
import heapq
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from sqlalchemy.orm import Session

from supervisor_agent.core.advanced_usage_predictor import AdvancedUsagePredictor
from supervisor_agent.core.claude_code_subscription_monitor import claude_code_monitor
from supervisor_agent.core.proactive_quota_monitor import quota_monitor
from supervisor_agent.db import crud
from supervisor_agent.db.database import get_db
from supervisor_agent.db.enums import TaskStatus, TaskType
from supervisor_agent.db.models import Task
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class TaskPriority(int, Enum):
    """Task priority levels"""

    CRITICAL = 1  # Critical tasks (security, bugs)
    HIGH = 2  # High priority features
    MEDIUM = 3  # Standard tasks
    LOW = 4  # Background tasks
    DEFERRED = 5  # Deferred due to quota


class SchedulingStrategy(str, Enum):
    """Task scheduling strategies"""

    PRIORITY_FIRST = "priority_first"  # Strict priority ordering
    QUOTA_AWARE = "quota_aware"  # Quota-conscious scheduling
    COST_OPTIMIZED = "cost_optimized"  # Minimize subscription costs
    PERFORMANCE_OPTIMIZED = "performance_optimized"  # Maximize throughput
    ADAPTIVE = "adaptive"  # ML-based adaptive scheduling


@dataclass
class TaskMetadata:
    """Enhanced task metadata for scheduling"""

    task_id: int
    task_type: TaskType
    priority: TaskPriority
    estimated_tokens: int
    estimated_duration_minutes: float
    dependencies: List[int]  # Task IDs this task depends on
    deadline: Optional[datetime]
    cost_estimate: float
    retry_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    scheduled_at: Optional[datetime] = None
    complexity_score: float = 1.0  # 0-1 scale
    can_be_batched: bool = True
    provider_preference: Optional[str] = None


@dataclass
class SchedulingContext:
    """Current scheduling context"""

    available_quota_percentage: float
    predicted_quota_exhaustion: Optional[datetime]
    current_queue_size: int
    average_processing_time: float
    provider_health_scores: Dict[str, float]
    active_batch_size: int
    cost_budget_remaining: float


@dataclass
class SchedulingDecision:
    """Result of scheduling decision"""

    action: str  # "schedule", "defer", "batch", "reject"
    task_ids: List[int]
    provider_id: Optional[str]
    scheduled_time: datetime
    reasoning: str
    estimated_completion: datetime
    confidence_score: float


class IntelligentTaskScheduler:
    """Advanced task scheduler with quota awareness and ML optimization"""

    def __init__(
        self,
        max_queue_size: int = 1000,
        default_batch_size: int = 5,
        quota_warning_threshold: float = 80.0,
        quota_emergency_threshold: float = 95.0,
        scheduling_interval_seconds: int = 30,
    ):
        self.max_queue_size = max_queue_size
        self.default_batch_size = default_batch_size
        self.quota_warning_threshold = quota_warning_threshold
        self.quota_emergency_threshold = quota_emergency_threshold
        self.scheduling_interval_seconds = scheduling_interval_seconds

        # Task queues by priority
        self.priority_queues: Dict[TaskPriority, List[TaskMetadata]] = {
            priority: [] for priority in TaskPriority
        }

        # Task metadata storage
        self.task_metadata: Dict[int, TaskMetadata] = {}
        self.dependency_graph: Dict[int, Set[int]] = defaultdict(set)
        self.batch_candidates: Dict[str, List[int]] = defaultdict(
            list
        )  # task_type -> task_ids

        # Scheduling state
        self.is_scheduling: bool = False
        self.scheduling_task: Optional[asyncio.Task] = None
        self.last_scheduling_run: Optional[datetime] = None

        # Performance tracking
        self.scheduling_stats = {
            "tasks_scheduled": 0,
            "tasks_deferred": 0,
            "tasks_batched": 0,
            "average_queue_time": 0.0,
            "scheduling_efficiency": 0.0,
        }

        # ML components
        self.usage_predictor = AdvancedUsagePredictor()

        # Strategy configuration
        self.current_strategy = SchedulingStrategy.ADAPTIVE
        self.strategy_weights = {
            "priority": 0.4,
            "quota": 0.3,
            "cost": 0.2,
            "performance": 0.1,
        }

        logger.info("Intelligent task scheduler initialized")

    async def start_scheduling(self) -> None:
        """Start the intelligent scheduling loop"""
        if self.is_scheduling:
            logger.warning("Task scheduling already started")
            return

        self.is_scheduling = True
        self.scheduling_task = asyncio.create_task(self._scheduling_loop())

        logger.info("Started intelligent task scheduling")

    async def stop_scheduling(self) -> None:
        """Stop task scheduling"""
        self.is_scheduling = False

        if self.scheduling_task:
            self.scheduling_task.cancel()
            try:
                await self.scheduling_task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped intelligent task scheduling")

    async def submit_task(
        self,
        task: Task,
        priority: Optional[TaskPriority] = None,
        dependencies: Optional[List[int]] = None,
        deadline: Optional[datetime] = None,
        provider_preference: Optional[str] = None,
    ) -> bool:
        """Submit a task for intelligent scheduling"""
        try:
            # Auto-detect priority if not specified
            if priority is None:
                priority = self._auto_detect_priority(task)

            # Estimate task complexity and resource usage
            estimated_tokens = self._estimate_task_tokens(task)
            estimated_duration = self._estimate_task_duration(task)
            complexity_score = self._calculate_complexity_score(task)
            cost_estimate = self._estimate_task_cost(task)

            # Create task metadata
            metadata = TaskMetadata(
                task_id=task.id,
                task_type=task.type,
                priority=priority,
                estimated_tokens=estimated_tokens,
                estimated_duration_minutes=estimated_duration,
                dependencies=dependencies or [],
                deadline=deadline,
                cost_estimate=cost_estimate,
                complexity_score=complexity_score,
                can_be_batched=self._can_task_be_batched(task),
                provider_preference=provider_preference,
            )

            # Store metadata
            self.task_metadata[task.id] = metadata

            # Update dependency graph
            if dependencies:
                for dep_id in dependencies:
                    self.dependency_graph[task.id].add(dep_id)

            # Add to appropriate priority queue
            heapq.heappush(
                self.priority_queues[priority],
                (self._calculate_scheduling_score(metadata), time.time(), metadata),
            )

            # Add to batch candidates if batchable
            if metadata.can_be_batched:
                self.batch_candidates[task.type].append(task.id)

            logger.info(
                f"Submitted task {task.id} ({task.type}) with priority {priority.name}, "
                f"estimated {estimated_tokens} tokens, {estimated_duration:.1f} min"
            )

            return True

        except Exception as e:
            logger.error(f"Error submitting task {task.id}: {e}")
            return False

    async def schedule_next_tasks(self) -> List[SchedulingDecision]:
        """Schedule the next batch of tasks based on current context"""
        try:
            # Get current scheduling context
            context = await self._get_scheduling_context()

            # Apply scheduling strategy
            decisions = await self._apply_scheduling_strategy(context)

            # Execute scheduling decisions
            executed_decisions = []
            for decision in decisions:
                success = await self._execute_scheduling_decision(decision)
                if success:
                    executed_decisions.append(decision)

            # Update statistics
            self._update_scheduling_stats(executed_decisions)

            return executed_decisions

        except Exception as e:
            logger.error(f"Error in schedule_next_tasks: {e}")
            return []

    async def rebalance_queues(self) -> None:
        """Rebalance task queues based on current quota status"""
        try:
            # Check Claude Code subscription status
            claude_status = await claude_code_monitor.check_claude_code_status()

            # Check general quota status
            quota_status = await quota_monitor.check_quota_status("claude-cli-primary")

            # Determine if we need to rebalance
            needs_rebalancing = (
                not claude_status.is_available
                or claude_status.usage_percentage > self.quota_warning_threshold
            )

            if not needs_rebalancing:
                return

            logger.info("Rebalancing task queues due to quota constraints")

            # Move low priority tasks to deferred queue
            for priority in [TaskPriority.LOW, TaskPriority.MEDIUM]:
                queue = self.priority_queues[priority]
                while queue:
                    _, timestamp, metadata = heapq.heappop(queue)

                    # Move to deferred queue
                    metadata.priority = TaskPriority.DEFERRED
                    heapq.heappush(
                        self.priority_queues[TaskPriority.DEFERRED],
                        (
                            self._calculate_scheduling_score(metadata),
                            timestamp,
                            metadata,
                        ),
                    )

                    # Defer the actual task
                    await claude_code_monitor.defer_work(
                        work_id=f"task_{metadata.task_id}",
                        work_type="task_processing",
                        payload={"task_id": metadata.task_id},
                        priority=metadata.priority.value,
                    )

            self.scheduling_stats["tasks_deferred"] += 1

        except Exception as e:
            logger.error(f"Error rebalancing queues: {e}")

    async def get_scheduling_status(self) -> Dict[str, Any]:
        """Get comprehensive scheduling status"""
        try:
            status = {
                "is_scheduling": self.is_scheduling,
                "current_strategy": self.current_strategy,
                "last_scheduling_run": (
                    self.last_scheduling_run.isoformat()
                    if self.last_scheduling_run
                    else None
                ),
                "queue_sizes": {},
                "batch_candidates": {},
                "scheduling_stats": self.scheduling_stats.copy(),
                "context": None,
                "next_scheduled_tasks": [],
            }

            # Queue sizes by priority
            for priority, queue in self.priority_queues.items():
                status["queue_sizes"][priority.name] = len(queue)

            # Batch candidates count
            for task_type, candidates in self.batch_candidates.items():
                status["batch_candidates"][task_type] = len(candidates)

            # Current scheduling context
            context = await self._get_scheduling_context()
            status["context"] = {
                "available_quota_percentage": context.available_quota_percentage,
                "current_queue_size": context.current_queue_size,
                "average_processing_time": context.average_processing_time,
                "active_batch_size": context.active_batch_size,
            }

            # Next tasks to be scheduled
            next_tasks = await self._peek_next_tasks(5)
            status["next_scheduled_tasks"] = [
                {
                    "task_id": metadata.task_id,
                    "task_type": metadata.task_type,
                    "priority": metadata.priority.name,
                    "estimated_tokens": metadata.estimated_tokens,
                    "complexity_score": metadata.complexity_score,
                }
                for metadata in next_tasks
            ]

            return status

        except Exception as e:
            logger.error(f"Error getting scheduling status: {e}")
            return {"error": str(e)}

    # Private methods

    async def _scheduling_loop(self) -> None:
        """Main scheduling loop"""
        logger.info("Started task scheduling loop")

        while self.is_scheduling:
            try:
                self.last_scheduling_run = datetime.now(timezone.utc)

                # Schedule next batch of tasks
                decisions = await self.schedule_next_tasks()

                # Rebalance queues if needed
                await self.rebalance_queues()

                # Cleanup completed tasks
                await self._cleanup_completed_tasks()

                # Optimize batch candidates
                await self._optimize_batch_candidates()

            except Exception as e:
                logger.error(f"Error in scheduling loop: {e}")

            # Wait for next scheduling cycle
            await asyncio.sleep(self.scheduling_interval_seconds)

        logger.info("Exited task scheduling loop")

    async def _get_scheduling_context(self) -> SchedulingContext:
        """Get current scheduling context"""
        try:
            # Get Claude Code status
            claude_status = await claude_code_monitor.check_claude_code_status()

            # Calculate total queue size
            total_queue_size = sum(
                len(queue) for queue in self.priority_queues.values()
            )

            # Estimate average processing time
            avg_processing_time = 5.0  # Default 5 minutes
            if self.scheduling_stats["tasks_scheduled"] > 0:
                # Would calculate from actual task history
                avg_processing_time = self.scheduling_stats.get(
                    "average_queue_time", 5.0
                )

            # Get provider health scores
            provider_health = {"claude-cli-primary": 1.0}  # Default
            try:
                quota_status = await quota_monitor.check_quota_status(
                    "claude-cli-primary"
                )
                if quota_status:
                    health_score = 1.0 - (
                        quota_status["claude-cli-primary"].usage_percentage / 100.0
                    )
                    provider_health["claude-cli-primary"] = max(0.0, health_score)
            except:
                pass

            return SchedulingContext(
                available_quota_percentage=100.0 - claude_status.usage_percentage,
                predicted_quota_exhaustion=None,  # Would come from predictor
                current_queue_size=total_queue_size,
                average_processing_time=avg_processing_time,
                provider_health_scores=provider_health,
                active_batch_size=self.default_batch_size,
                cost_budget_remaining=1000.0,  # Default budget
            )

        except Exception as e:
            logger.error(f"Error getting scheduling context: {e}")
            # Return safe defaults
            return SchedulingContext(
                available_quota_percentage=50.0,
                predicted_quota_exhaustion=None,
                current_queue_size=0,
                average_processing_time=5.0,
                provider_health_scores={"claude-cli-primary": 0.5},
                active_batch_size=self.default_batch_size,
                cost_budget_remaining=1000.0,
            )

    async def _apply_scheduling_strategy(
        self, context: SchedulingContext
    ) -> List[SchedulingDecision]:
        """Apply the current scheduling strategy"""
        decisions = []

        try:
            if self.current_strategy == SchedulingStrategy.ADAPTIVE:
                decisions = await self._adaptive_scheduling(context)
            elif self.current_strategy == SchedulingStrategy.PRIORITY_FIRST:
                decisions = await self._priority_first_scheduling(context)
            elif self.current_strategy == SchedulingStrategy.QUOTA_AWARE:
                decisions = await self._quota_aware_scheduling(context)
            elif self.current_strategy == SchedulingStrategy.COST_OPTIMIZED:
                decisions = await self._cost_optimized_scheduling(context)
            elif self.current_strategy == SchedulingStrategy.PERFORMANCE_OPTIMIZED:
                decisions = await self._performance_optimized_scheduling(context)
            else:
                # Default to adaptive
                decisions = await self._adaptive_scheduling(context)

        except Exception as e:
            logger.error(
                f"Error applying scheduling strategy {self.current_strategy}: {e}"
            )

        return decisions

    async def _adaptive_scheduling(
        self, context: SchedulingContext
    ) -> List[SchedulingDecision]:
        """Adaptive scheduling using ML and heuristics"""
        decisions = []

        # Determine scheduling approach based on context
        if context.available_quota_percentage < 20:
            # Emergency mode - only critical tasks
            decisions.extend(await self._emergency_scheduling(context))
        elif context.available_quota_percentage < 50:
            # Conservative mode - high priority only
            decisions.extend(await self._conservative_scheduling(context))
        else:
            # Normal mode - all priorities with batching
            decisions.extend(await self._normal_scheduling(context))

        return decisions

    async def _emergency_scheduling(
        self, context: SchedulingContext
    ) -> List[SchedulingDecision]:
        """Emergency scheduling - only critical tasks"""
        decisions = []

        # Only schedule critical tasks
        critical_queue = self.priority_queues[TaskPriority.CRITICAL]
        if critical_queue:
            _, timestamp, metadata = heapq.heappop(critical_queue)

            decision = SchedulingDecision(
                action="schedule",
                task_ids=[metadata.task_id],
                provider_id="claude-cli-primary",
                scheduled_time=datetime.now(timezone.utc),
                reasoning="Emergency mode: only critical tasks allowed",
                estimated_completion=datetime.now(timezone.utc)
                + timedelta(minutes=metadata.estimated_duration_minutes),
                confidence_score=0.9,
            )
            decisions.append(decision)

        return decisions

    async def _conservative_scheduling(
        self, context: SchedulingContext
    ) -> List[SchedulingDecision]:
        """Conservative scheduling - high priority tasks only"""
        decisions = []

        # Schedule high and critical priority tasks
        for priority in [TaskPriority.CRITICAL, TaskPriority.HIGH]:
            queue = self.priority_queues[priority]
            if queue and len(decisions) < 2:  # Limit to 2 tasks
                _, timestamp, metadata = heapq.heappop(queue)

                decision = SchedulingDecision(
                    action="schedule",
                    task_ids=[metadata.task_id],
                    provider_id="claude-cli-primary",
                    scheduled_time=datetime.now(timezone.utc),
                    reasoning=f"Conservative mode: {priority.name} priority task",
                    estimated_completion=datetime.now(timezone.utc)
                    + timedelta(minutes=metadata.estimated_duration_minutes),
                    confidence_score=0.8,
                )
                decisions.append(decision)

        return decisions

    async def _normal_scheduling(
        self, context: SchedulingContext
    ) -> List[SchedulingDecision]:
        """Normal scheduling with batching and optimization"""
        decisions = []

        # Check for batch opportunities first
        batch_decision = await self._try_batch_scheduling(context)
        if batch_decision:
            decisions.append(batch_decision)

        # Schedule individual tasks by priority
        for priority in [TaskPriority.CRITICAL, TaskPriority.HIGH, TaskPriority.MEDIUM]:
            queue = self.priority_queues[priority]
            scheduled_count = 0

            while queue and scheduled_count < 3:  # Limit per priority
                _, timestamp, metadata = heapq.heappop(queue)

                # Check dependencies
                if await self._check_dependencies_satisfied(metadata):
                    decision = SchedulingDecision(
                        action="schedule",
                        task_ids=[metadata.task_id],
                        provider_id="claude-cli-primary",
                        scheduled_time=datetime.now(timezone.utc),
                        reasoning=f"Normal mode: {priority.name} priority task",
                        estimated_completion=datetime.now(timezone.utc)
                        + timedelta(minutes=metadata.estimated_duration_minutes),
                        confidence_score=0.7,
                    )
                    decisions.append(decision)
                    scheduled_count += 1
                else:
                    # Put back in queue - dependencies not satisfied
                    heapq.heappush(
                        queue,
                        (
                            self._calculate_scheduling_score(metadata),
                            timestamp,
                            metadata,
                        ),
                    )

        return decisions

    async def _try_batch_scheduling(
        self, context: SchedulingContext
    ) -> Optional[SchedulingDecision]:
        """Try to create a batch of similar tasks"""
        for task_type, candidates in self.batch_candidates.items():
            if len(candidates) >= 3:  # Minimum batch size
                # Select best candidates for batching
                batch_tasks = []
                total_tokens = 0

                for task_id in candidates[: self.default_batch_size]:
                    metadata = self.task_metadata.get(task_id)
                    if metadata and await self._check_dependencies_satisfied(metadata):
                        batch_tasks.append(task_id)
                        total_tokens += metadata.estimated_tokens

                        # Remove from batch candidates
                        self.batch_candidates[task_type].remove(task_id)

                        # Remove from individual queues
                        self._remove_from_priority_queue(metadata)

                if len(batch_tasks) >= 2:  # Valid batch
                    return SchedulingDecision(
                        action="batch",
                        task_ids=batch_tasks,
                        provider_id="claude-cli-primary",
                        scheduled_time=datetime.now(timezone.utc),
                        reasoning=f"Batch processing {len(batch_tasks)} {task_type} tasks",
                        estimated_completion=datetime.now(timezone.utc)
                        + timedelta(minutes=10),
                        confidence_score=0.8,
                    )

        return None

    async def _execute_scheduling_decision(self, decision: SchedulingDecision) -> bool:
        """Execute a scheduling decision"""
        try:
            if decision.action == "schedule":
                # Schedule individual task
                for task_id in decision.task_ids:
                    from supervisor_agent.queue.enhanced_tasks import (
                        process_single_task_enhanced,
                    )

                    process_single_task_enhanced.delay(task_id)

                    # Update metadata
                    if task_id in self.task_metadata:
                        self.task_metadata[task_id].scheduled_at = (
                            decision.scheduled_time
                        )

            elif decision.action == "batch":
                # Schedule batch processing
                from supervisor_agent.queue.enhanced_tasks import (
                    process_task_batch_enhanced,
                )

                process_task_batch_enhanced.delay(decision.task_ids)

                # Update metadata for all tasks
                for task_id in decision.task_ids:
                    if task_id in self.task_metadata:
                        self.task_metadata[task_id].scheduled_at = (
                            decision.scheduled_time
                        )

            elif decision.action == "defer":
                # Defer tasks
                for task_id in decision.task_ids:
                    await claude_code_monitor.defer_work(
                        work_id=f"task_{task_id}",
                        work_type="task_processing",
                        payload={"task_id": task_id},
                        priority=(
                            self.task_metadata[task_id].priority.value
                            if task_id in self.task_metadata
                            else 3
                        ),
                    )

            logger.info(
                f"Executed scheduling decision: {decision.action} for tasks {decision.task_ids}"
            )
            return True

        except Exception as e:
            logger.error(f"Error executing scheduling decision: {e}")
            return False

    def _auto_detect_priority(self, task: Task) -> TaskPriority:
        """Auto-detect task priority based on type and content"""
        if task.type in [TaskType.SECURITY_ISSUE, TaskType.CRITICAL_BUG_FIX]:
            return TaskPriority.CRITICAL
        elif task.type in [TaskType.BUG_FIX, TaskType.PR_REVIEW]:
            return TaskPriority.HIGH
        elif task.type in [TaskType.FEATURE, TaskType.CODE_ANALYSIS]:
            return TaskPriority.MEDIUM
        else:
            return TaskPriority.LOW

    def _estimate_task_tokens(self, task: Task) -> int:
        """Estimate token usage for a task"""
        base_tokens = 500  # Base token usage

        # Adjust based on task type
        type_multipliers = {
            TaskType.FEATURE: 2.0,
            TaskType.REFACTOR: 1.8,
            TaskType.CODE_ANALYSIS: 1.5,
            TaskType.BUG_FIX: 1.2,
            TaskType.PR_REVIEW: 1.0,
        }

        multiplier = type_multipliers.get(task.type, 1.0)

        # Adjust based on payload size
        payload_size = len(str(task.payload)) if task.payload else 0
        size_factor = 1.0 + (payload_size / 10000)  # +1 factor per 10KB

        return int(base_tokens * multiplier * size_factor)

    def _estimate_task_duration(self, task: Task) -> float:
        """Estimate task duration in minutes"""
        base_duration = 3.0  # 3 minutes base

        # Adjust based on task type
        type_durations = {
            TaskType.FEATURE: 8.0,
            TaskType.REFACTOR: 6.0,
            TaskType.CODE_ANALYSIS: 4.0,
            TaskType.BUG_FIX: 5.0,
            TaskType.PR_REVIEW: 3.0,
        }

        return type_durations.get(task.type, base_duration)

    def _calculate_complexity_score(self, task: Task) -> float:
        """Calculate task complexity score (0-1)"""
        # Simple heuristic based on payload size and type
        payload_size = len(str(task.payload)) if task.payload else 0

        # Base complexity by type
        type_complexity = {
            TaskType.FEATURE: 0.8,
            TaskType.REFACTOR: 0.7,
            TaskType.CODE_ANALYSIS: 0.5,
            TaskType.BUG_FIX: 0.6,
            TaskType.PR_REVIEW: 0.3,
        }

        base_complexity = type_complexity.get(task.type, 0.5)

        # Adjust for payload size
        size_factor = min(0.3, payload_size / 50000)  # Max 0.3 bonus for large payloads

        return min(1.0, base_complexity + size_factor)

    def _estimate_task_cost(self, task: Task) -> float:
        """Estimate task cost in USD"""
        estimated_tokens = self._estimate_task_tokens(task)
        cost_per_token = 0.00001  # Approximate Claude pricing
        return estimated_tokens * cost_per_token

    def _can_task_be_batched(self, task: Task) -> bool:
        """Determine if task can be included in a batch"""
        # Simple heuristic - similar task types can be batched
        batchable_types = {
            TaskType.PR_REVIEW,
            TaskType.CODE_ANALYSIS,
            TaskType.ISSUE_SUMMARY,
        }
        return task.type in batchable_types

    def _calculate_scheduling_score(self, metadata: TaskMetadata) -> float:
        """Calculate scheduling score (lower = higher priority)"""
        # Base score from priority (lower number = higher priority)
        base_score = metadata.priority.value

        # Adjust for deadline urgency
        if metadata.deadline:
            time_to_deadline = (
                metadata.deadline - datetime.now(timezone.utc)
            ).total_seconds() / 3600
            if time_to_deadline < 24:  # Less than 24 hours
                base_score -= (24 - time_to_deadline) / 24  # Boost priority

        # Adjust for age (older tasks get higher priority)
        age_hours = (
            datetime.now(timezone.utc) - metadata.created_at
        ).total_seconds() / 3600
        age_boost = min(1.0, age_hours / 24)  # Max 1 point boost for day-old tasks
        base_score -= age_boost

        return base_score

    async def _check_dependencies_satisfied(self, metadata: TaskMetadata) -> bool:
        """Check if task dependencies are satisfied"""
        if not metadata.dependencies:
            return True

        # Check if all dependency tasks are completed
        db = next(get_db())
        try:
            for dep_id in metadata.dependencies:
                dep_task = crud.TaskCRUD.get_task(db, dep_id)
                if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                    return False
            return True
        except Exception as e:
            logger.warning(
                f"Error checking dependencies for task {metadata.task_id}: {e}"
            )
            return True  # Assume satisfied on error
        finally:
            db.close()

    def _remove_from_priority_queue(self, metadata: TaskMetadata) -> None:
        """Remove task from its priority queue"""
        queue = self.priority_queues[metadata.priority]
        # Note: This is inefficient for heapq, but works for small queues
        # In production, would use a more sophisticated data structure
        new_queue = []
        for score, timestamp, queued_metadata in queue:
            if queued_metadata.task_id != metadata.task_id:
                new_queue.append((score, timestamp, queued_metadata))

        # Replace queue
        self.priority_queues[metadata.priority] = new_queue
        heapq.heapify(self.priority_queues[metadata.priority])

    async def _peek_next_tasks(self, count: int) -> List[TaskMetadata]:
        """Peek at next tasks to be scheduled"""
        next_tasks = []

        for priority in TaskPriority:
            queue = self.priority_queues[priority]
            for score, timestamp, metadata in sorted(queue)[:count]:
                next_tasks.append(metadata)
                if len(next_tasks) >= count:
                    break
            if len(next_tasks) >= count:
                break

        return next_tasks

    async def _cleanup_completed_tasks(self) -> None:
        """Clean up metadata for completed tasks"""
        db = next(get_db())
        try:
            # Get completed task IDs
            completed_task_ids = []
            for task_id in list(self.task_metadata.keys()):
                task = crud.TaskCRUD.get_task(db, task_id)
                if task and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    completed_task_ids.append(task_id)

            # Remove from metadata and queues
            for task_id in completed_task_ids:
                if task_id in self.task_metadata:
                    metadata = self.task_metadata[task_id]
                    self._remove_from_priority_queue(metadata)
                    del self.task_metadata[task_id]

                # Remove from batch candidates
                for task_type, candidates in self.batch_candidates.items():
                    if task_id in candidates:
                        candidates.remove(task_id)

            if completed_task_ids:
                logger.debug(f"Cleaned up {len(completed_task_ids)} completed tasks")

        except Exception as e:
            logger.error(f"Error cleaning up completed tasks: {e}")
        finally:
            db.close()

    async def _optimize_batch_candidates(self) -> None:
        """Optimize batch candidate lists"""
        # Remove candidates that are too old or no longer batchable
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=2)

        for task_type, candidates in list(self.batch_candidates.items()):
            valid_candidates = []

            for task_id in candidates:
                metadata = self.task_metadata.get(task_id)
                if metadata and metadata.created_at > cutoff_time:
                    valid_candidates.append(task_id)

            if valid_candidates:
                self.batch_candidates[task_type] = valid_candidates
            else:
                del self.batch_candidates[task_type]

    def _update_scheduling_stats(self, decisions: List[SchedulingDecision]) -> None:
        """Update scheduling statistics"""
        for decision in decisions:
            if decision.action == "schedule":
                self.scheduling_stats["tasks_scheduled"] += len(decision.task_ids)
            elif decision.action == "defer":
                self.scheduling_stats["tasks_deferred"] += len(decision.task_ids)
            elif decision.action == "batch":
                self.scheduling_stats["tasks_batched"] += len(decision.task_ids)

        # Update efficiency metric
        total_decisions = sum(
            [
                self.scheduling_stats["tasks_scheduled"],
                self.scheduling_stats["tasks_deferred"],
                self.scheduling_stats["tasks_batched"],
            ]
        )

        if total_decisions > 0:
            efficiency = (
                self.scheduling_stats["tasks_scheduled"]
                + self.scheduling_stats["tasks_batched"]
            ) / total_decisions
            self.scheduling_stats["scheduling_efficiency"] = efficiency

    # Additional strategy implementations
    async def _priority_first_scheduling(
        self, context: SchedulingContext
    ) -> List[SchedulingDecision]:
        """Strict priority-based scheduling"""
        decisions = []
        # Implementation similar to normal scheduling but purely priority-based
        return decisions

    async def _quota_aware_scheduling(
        self, context: SchedulingContext
    ) -> List[SchedulingDecision]:
        """Quota-conscious scheduling"""
        decisions = []
        # Implementation that heavily weights quota availability
        return decisions

    async def _cost_optimized_scheduling(
        self, context: SchedulingContext
    ) -> List[SchedulingDecision]:
        """Cost-optimized scheduling"""
        decisions = []
        # Implementation that minimizes costs
        return decisions

    async def _performance_optimized_scheduling(
        self, context: SchedulingContext
    ) -> List[SchedulingDecision]:
        """Performance-optimized scheduling for maximum throughput"""
        decisions = []
        # Implementation that maximizes task throughput
        return decisions


# Global scheduler instance
task_scheduler = IntelligentTaskScheduler()
