# supervisor_agent/orchestration/dynamic_task_scheduler.py
"""
Dynamic Task Scheduler

This module provides real-time task scheduling with AI-powered optimization,
dynamic resource allocation, and adaptive priority management. It integrates
with the workflow engine for intelligent task distribution and execution.
"""

import asyncio
import heapq
import json
import math
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import structlog

from supervisor_agent.intelligence.workflow_synthesizer import (
    ClaudeAgentWrapper,
)
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)
structured_logger = structlog.get_logger(__name__)


class TaskPriority(Enum):
    """Task priority levels for scheduling."""

    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


class SchedulingStrategy(Enum):
    """Task scheduling strategies."""

    FIFO = "first_in_first_out"
    PRIORITY = "priority_based"
    SHORTEST_JOB_FIRST = "shortest_job_first"
    FAIR_SHARE = "fair_share"
    AI_OPTIMIZED = "ai_optimized"
    ADAPTIVE = "adaptive"


class ResourceType(Enum):
    """Types of resources that can be allocated."""

    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    GPU = "gpu"
    AGENT_SLOTS = "agent_slots"


@dataclass
class ResourceRequirement:
    """Resource requirement specification for tasks."""

    resource_type: ResourceType
    amount: float
    max_amount: Optional[float] = None
    preferred_amount: Optional[float] = None
    is_required: bool = True


@dataclass
class ResourceAllocation:
    """Allocated resources for task execution."""

    task_id: str
    allocations: Dict[ResourceType, float]
    allocated_at: datetime
    expires_at: Optional[datetime] = None
    allocation_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class ScheduledTask:
    """Task scheduled for execution with metadata."""

    task_id: str
    workflow_id: str
    execution_id: str
    task_name: str
    task_type: str
    priority: TaskPriority
    resource_requirements: List[ResourceRequirement]
    estimated_duration: int  # minutes
    deadline: Optional[datetime] = None
    dependencies: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class AgentCapacity:
    """Agent capacity and availability information."""

    agent_id: str
    agent_type: str
    capabilities: List[str]
    max_concurrent_tasks: int
    current_tasks: int
    available_resources: Dict[ResourceType, float]
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SchedulingContext:
    """Context information for scheduling decisions."""

    current_load: Dict[str, float]
    resource_availability: Dict[ResourceType, float]
    agent_capacities: Dict[str, AgentCapacity]
    performance_history: Dict[str, List[float]]
    system_constraints: Dict[str, Any]
    optimization_goals: List[str]


class DynamicTaskScheduler:
    """
    AI-powered dynamic task scheduler with real-time optimization,
    adaptive priority management, and intelligent resource allocation.
    """

    def __init__(self, claude_agent: ClaudeAgentWrapper):
        self.claude_agent = claude_agent

        # Task scheduling
        self.task_queue: List[Tuple[float, ScheduledTask]] = []  # Priority queue
        self.running_tasks: Dict[str, ScheduledTask] = {}
        self.completed_tasks: Dict[str, ScheduledTask] = {}
        self.failed_tasks: Dict[str, ScheduledTask] = {}

        # Resource management
        self.resource_pool: Dict[ResourceType, float] = {
            ResourceType.CPU: 100.0,
            ResourceType.MEMORY: 100.0,
            ResourceType.STORAGE: 100.0,
            ResourceType.NETWORK: 100.0,
            ResourceType.GPU: 10.0,
            ResourceType.AGENT_SLOTS: 20.0,
        }
        self.allocated_resources: Dict[str, ResourceAllocation] = {}
        self.resource_usage_history: Dict[ResourceType, deque] = {
            rt: deque(maxlen=100) for rt in ResourceType
        }

        # Agent management
        self.agent_capacities: Dict[str, AgentCapacity] = {}
        self.agent_assignments: Dict[str, List[str]] = defaultdict(list)

        # Scheduling configuration
        self.scheduling_strategy = SchedulingStrategy.AI_OPTIMIZED
        self.optimization_interval = 60  # seconds
        self.max_queue_size = 1000
        self.load_balancing_threshold = 0.8

        # Performance tracking
        self.scheduling_metrics: Dict[str, Any] = defaultdict(dict)
        self.optimization_history: deque = deque(maxlen=100)

        # AI-powered optimization
        self.ai_optimizer = SchedulingOptimizer(claude_agent)
        self.adaptive_controller = AdaptiveSchedulingController()
        self.load_predictor = LoadPredictor()

        # Background tasks
        self._optimization_task = None
        self._monitoring_task = None
        self._running = False

        self.logger = structured_logger.bind(component="dynamic_task_scheduler")

    async def start(self):
        """Start the dynamic task scheduler."""

        if self._running:
            return

        self._running = True

        # Start background optimization and monitoring
        self._optimization_task = asyncio.create_task(self._optimization_loop())
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())

        self.logger.info("Dynamic task scheduler started")

    async def stop(self):
        """Stop the dynamic task scheduler."""

        self._running = False

        # Cancel background tasks
        if self._optimization_task:
            self._optimization_task.cancel()
        if self._monitoring_task:
            self._monitoring_task.cancel()

        self.logger.info("Dynamic task scheduler stopped")

    async def schedule_task(self, task: ScheduledTask) -> str:
        """Schedule a task for execution with AI-powered optimization."""

        try:
            if len(self.task_queue) >= self.max_queue_size:
                raise RuntimeError("Task queue is full")

            # Validate task
            validation_result = await self._validate_task(task)
            if not validation_result["valid"]:
                raise ValueError(f"Invalid task: {validation_result['errors']}")

            # AI-powered priority optimization
            optimized_priority = await self._optimize_task_priority(task)
            task.priority = optimized_priority

            # Calculate scheduling score
            scheduling_score = await self._calculate_scheduling_score(task)

            # Add to priority queue
            heapq.heappush(self.task_queue, (scheduling_score, task))
            task.scheduled_at = datetime.now(timezone.utc)

            self.logger.info(
                "Task scheduled",
                task_id=task.task_id,
                priority=task.priority.value,
                scheduling_score=scheduling_score,
                queue_size=len(self.task_queue),
            )

            # Trigger immediate scheduling evaluation
            asyncio.create_task(self._evaluate_immediate_scheduling())

            return task.task_id

        except Exception as e:
            self.logger.error(
                "Task scheduling failed", task_id=task.task_id, error=str(e)
            )
            raise

    async def _validate_task(self, task: ScheduledTask) -> Dict[str, Any]:
        """Validate task for scheduling compatibility."""

        validation_prompt = f"""
        Validate this task for scheduling feasibility and resource compatibility:
        
        Task Details: {json.dumps({
            "task_id": task.task_id,
            "task_name": task.task_name,
            "task_type": task.task_type,
            "priority": task.priority.value,
            "estimated_duration": task.estimated_duration,
            "resource_requirements": [{
                "resource_type": req.resource_type.value,
                "amount": req.amount,
                "is_required": req.is_required
            } for req in task.resource_requirements],
            "dependencies": task.dependencies,
            "deadline": task.deadline.isoformat() if task.deadline else None
        }, indent=2)}
        
        Current System State: {json.dumps({
            "available_resources": {rt.value: amount for rt, amount in self.resource_pool.items()},
            "queue_size": len(self.task_queue),
            "running_tasks": len(self.running_tasks),
            "agent_capacity": len(self.agent_capacities)
        }, indent=2)}
        
        Check for:
        1. Resource requirement feasibility given current availability
        2. Dependency consistency and circular dependency detection
        3. Deadline achievability based on current queue and estimated duration
        4. Task type compatibility with available agent capabilities
        5. Resource allocation conflicts with running tasks
        6. Parameter validity and completeness
        7. Priority level appropriateness for task characteristics
        8. Estimated duration reasonableness
        
        Provide validation result in JSON format with:
        - valid: boolean indicating if task can be scheduled
        - errors: list of critical issues preventing scheduling
        - warnings: list of potential concerns or suboptimal conditions
        - recommendations: suggested improvements or adjustments
        - resource_feasibility: assessment of resource requirement feasibility
        - scheduling_complexity: predicted complexity of scheduling this task
        - optimization_suggestions: ways to improve task schedulability
        
        Focus on identifying issues that could cause scheduling failures or poor performance.
        """

        result = await self.claude_agent.execute_task(
            {"type": "task_validation", "prompt": validation_prompt},
            shared_memory={"task_context": task.__dict__},
        )

        try:
            return json.loads(result["result"])
        except (json.JSONDecodeError, KeyError):
            return {
                "valid": True,  # Assume valid if AI validation fails
                "errors": [],
                "warnings": ["AI validation unavailable"],
                "recommendations": [],
            }

    async def _optimize_task_priority(self, task: ScheduledTask) -> TaskPriority:
        """Use AI to optimize task priority based on context."""

        priority_optimization_prompt = f"""
        Optimize task priority for dynamic scheduling based on system context:
        
        Task Information: {json.dumps({
            "task_name": task.task_name,
            "task_type": task.task_type,
            "current_priority": task.priority.value,
            "estimated_duration": task.estimated_duration,
            "deadline": task.deadline.isoformat() if task.deadline else None,
            "dependencies": task.dependencies,
            "workflow_id": task.workflow_id
        }, indent=2)}
        
        System Context: {json.dumps({
            "queue_length": len(self.task_queue),
            "running_tasks": len(self.running_tasks),
            "system_load": self._calculate_current_load(),
            "resource_utilization": self._calculate_resource_utilization(),
            "average_wait_time": self._calculate_average_wait_time()
        }, indent=2)}
        
        Consider factors:
        1. Task deadline urgency vs current queue state
        2. Resource requirements vs system capacity
        3. Dependency blocking potential for other tasks
        4. Workflow criticality and business impact
        5. System load balancing requirements
        6. Historical performance patterns for similar tasks
        7. Resource efficiency and optimization goals
        8. Overall system throughput impact
        
        Determine optimal priority level considering:
        - CRITICAL (1): Mission-critical, deadline-sensitive, or blocking many tasks
        - HIGH (2): Important business tasks with near-term deadlines
        - NORMAL (3): Standard workflow tasks with reasonable timelines
        - LOW (4): Non-urgent tasks that can be delayed
        - BACKGROUND (5): Maintenance or optimization tasks
        
        Provide priority recommendation in JSON format with:
        - recommended_priority: integer priority level (1-5)
        - reasoning: explanation for priority recommendation
        - impact_analysis: how this priority affects system performance
        - alternative_priorities: other viable priority options with trade-offs
        - scheduling_implications: expected impact on queue and execution timing
        
        Focus on optimal system throughput while respecting business priorities.
        """

        result = await self.claude_agent.execute_task(
            {"type": "priority_optimization", "prompt": priority_optimization_prompt},
            shared_memory={"scheduling_context": self._get_scheduling_context()},
        )

        try:
            optimization = json.loads(result["result"])
            priority_value = optimization.get(
                "recommended_priority", task.priority.value
            )
            return TaskPriority(priority_value)
        except (json.JSONDecodeError, KeyError, ValueError):
            return task.priority  # Return original priority if optimization fails

    async def _calculate_scheduling_score(self, task: ScheduledTask) -> float:
        """Calculate scheduling score for priority queue ordering."""

        # Base score from priority (lower number = higher priority)
        priority_score = task.priority.value

        # Deadline urgency factor
        urgency_factor = 0.0
        if task.deadline:
            time_to_deadline = (
                task.deadline - datetime.now(timezone.utc)
            ).total_seconds() / 3600  # hours
            if time_to_deadline > 0:
                urgency_factor = max(
                    0, 10 / time_to_deadline
                )  # More urgent = lower score
            else:
                urgency_factor = -100  # Past deadline = highest priority

        # Resource efficiency factor
        resource_efficiency = self._calculate_resource_efficiency(task)

        # Dependency factor (tasks that unblock others get higher priority)
        dependency_factor = self._calculate_dependency_factor(task)

        # Combine factors (lower score = higher priority)
        final_score = (
            priority_score + urgency_factor - resource_efficiency - dependency_factor
        )

        return final_score

    def _calculate_resource_efficiency(self, task: ScheduledTask) -> float:
        """Calculate resource efficiency score for the task."""

        if not task.resource_requirements:
            return 0.0

        efficiency_score = 0.0
        for req in task.resource_requirements:
            available = self.resource_pool.get(req.resource_type, 0.0)
            if available > 0:
                utilization = req.amount / available
                # Prefer tasks that use resources efficiently
                efficiency_score += min(utilization, 1.0)

        return efficiency_score / len(task.resource_requirements)

    def _calculate_dependency_factor(self, task: ScheduledTask) -> float:
        """Calculate dependency factor - how many other tasks this might unblock."""

        # Count tasks in queue that depend on this task
        dependent_tasks = 0
        for _, queued_task in self.task_queue:
            if task.task_id in queued_task.dependencies:
                dependent_tasks += 1

        # Higher factor for tasks that unblock more tasks
        return dependent_tasks * 0.5

    async def _evaluate_immediate_scheduling(self):
        """Evaluate if any queued tasks can be scheduled immediately."""

        if not self.task_queue:
            return

        # Check available resources and agent capacity
        available_resources = self._calculate_available_resources()
        available_agents = self._get_available_agents()

        # Try to schedule top priority tasks
        tasks_to_schedule = []

        while (
            self.task_queue and len(tasks_to_schedule) < 5
        ):  # Limit immediate scheduling
            score, task = heapq.heappop(self.task_queue)

            # Check if task can be scheduled now
            if await self._can_schedule_task(
                task, available_resources, available_agents
            ):
                tasks_to_schedule.append(task)

                # Update available resources
                for req in task.resource_requirements:
                    if req.resource_type in available_resources:
                        available_resources[req.resource_type] -= req.amount
            else:
                # Put task back in queue
                heapq.heappush(self.task_queue, (score, task))
                break

        # Schedule selected tasks
        for task in tasks_to_schedule:
            await self._execute_task(task)

    async def _can_schedule_task(
        self,
        task: ScheduledTask,
        available_resources: Dict[ResourceType, float],
        available_agents: List[str],
    ) -> bool:
        """Check if a task can be scheduled with current resources."""

        # Check resource requirements
        for req in task.resource_requirements:
            if req.is_required:
                available = available_resources.get(req.resource_type, 0.0)
                if available < req.amount:
                    return False

        # Check agent availability
        if not available_agents:
            return False

        # Check dependencies
        for dep_id in task.dependencies:
            if dep_id not in self.completed_tasks:
                return False

        return True

    async def _execute_task(self, task: ScheduledTask):
        """Execute a scheduled task."""

        try:
            # Allocate resources
            allocation = await self._allocate_resources(task)

            # Assign to agent
            agent_id = await self._assign_agent(task)

            # Mark as running
            task.started_at = datetime.now(timezone.utc)
            self.running_tasks[task.task_id] = task

            self.logger.info(
                "Task execution started",
                task_id=task.task_id,
                agent_id=agent_id,
                allocation_id=allocation.allocation_id,
            )

            # Start execution (placeholder - in real implementation would delegate to agent)
            asyncio.create_task(self._simulate_task_execution(task, allocation))

        except Exception as e:
            self.logger.error(
                "Task execution failed to start", task_id=task.task_id, error=str(e)
            )

            # Move to failed tasks
            self.failed_tasks[task.task_id] = task

    async def _allocate_resources(self, task: ScheduledTask) -> ResourceAllocation:
        """Allocate resources for task execution."""

        allocations = {}

        for req in task.resource_requirements:
            if req.is_required:
                if self.resource_pool[req.resource_type] >= req.amount:
                    allocations[req.resource_type] = req.amount
                    self.resource_pool[req.resource_type] -= req.amount
                else:
                    raise RuntimeError(
                        f"Insufficient {req.resource_type.value} resources"
                    )

        allocation = ResourceAllocation(
            task_id=task.task_id,
            allocations=allocations,
            allocated_at=datetime.now(timezone.utc),
        )

        self.allocated_resources[allocation.allocation_id] = allocation
        return allocation

    async def _assign_agent(self, task: ScheduledTask) -> str:
        """Assign an available agent to execute the task."""

        available_agents = self._get_available_agents()

        if not available_agents:
            raise RuntimeError("No available agents")

        # Simple assignment to first available agent
        # In a real implementation, this would use more sophisticated matching
        agent_id = available_agents[0]
        self.agent_assignments[agent_id].append(task.task_id)

        return agent_id

    async def _simulate_task_execution(
        self, task: ScheduledTask, allocation: ResourceAllocation
    ):
        """Simulate task execution (placeholder for real execution)."""

        try:
            # Simulate execution time
            execution_time = task.estimated_duration * 60  # Convert to seconds
            await asyncio.sleep(min(execution_time, 10))  # Cap simulation time

            # Mark as completed
            task.completed_at = datetime.now(timezone.utc)

            # Move from running to completed
            if task.task_id in self.running_tasks:
                del self.running_tasks[task.task_id]
            self.completed_tasks[task.task_id] = task

            # Release resources
            await self._release_resources(allocation)

            self.logger.info(
                "Task execution completed",
                task_id=task.task_id,
                duration_seconds=(task.completed_at - task.started_at).total_seconds(),
            )

        except Exception as e:
            self.logger.error(
                "Task execution failed", task_id=task.task_id, error=str(e)
            )

            # Move to failed tasks
            if task.task_id in self.running_tasks:
                del self.running_tasks[task.task_id]
            self.failed_tasks[task.task_id] = task

            # Release resources
            await self._release_resources(allocation)

    async def _release_resources(self, allocation: ResourceAllocation):
        """Release allocated resources back to the pool."""

        for resource_type, amount in allocation.allocations.items():
            self.resource_pool[resource_type] += amount

        # Remove allocation record
        if allocation.allocation_id in self.allocated_resources:
            del self.allocated_resources[allocation.allocation_id]

    async def _optimization_loop(self):
        """Background optimization loop for scheduling performance."""

        while self._running:
            try:
                await asyncio.sleep(self.optimization_interval)

                if not self._running:
                    break

                # Perform AI-powered optimization
                await self._optimize_scheduling()

            except Exception as e:
                self.logger.error("Optimization loop error", error=str(e))

    async def _monitoring_loop(self):
        """Background monitoring loop for system metrics."""

        while self._running:
            try:
                await asyncio.sleep(30)  # Monitor every 30 seconds

                if not self._running:
                    break

                # Update metrics
                await self._update_performance_metrics()

            except Exception as e:
                self.logger.error("Monitoring loop error", error=str(e))

    async def _optimize_scheduling(self):
        """Perform AI-powered scheduling optimization."""

        if not self.task_queue:
            return

        context = self._get_scheduling_context()
        optimization = await self.ai_optimizer.optimize_schedule(
            self.task_queue, context
        )

        if optimization.get("reorder_required", False):
            # Re-prioritize queue based on optimization
            await self._reorder_task_queue(optimization.get("new_priorities", {}))

    def _get_scheduling_context(self) -> SchedulingContext:
        """Get current scheduling context for optimization."""

        return SchedulingContext(
            current_load=self._calculate_current_load(),
            resource_availability=self._calculate_available_resources(),
            agent_capacities=self.agent_capacities,
            performance_history=self._get_performance_history(),
            system_constraints=self._get_system_constraints(),
            optimization_goals=["throughput", "latency", "resource_efficiency"],
        )

    async def _reorder_task_queue(self, new_priorities: Dict[str, float]):
        """Reorder task queue based on new priorities."""

        # Extract all tasks from queue
        tasks = []
        while self.task_queue:
            score, task = heapq.heappop(self.task_queue)
            tasks.append(task)

        # Re-add with new priorities
        for task in tasks:
            new_score = new_priorities.get(
                task.task_id, await self._calculate_scheduling_score(task)
            )
            heapq.heappush(self.task_queue, (new_score, task))

    # Helper methods

    def _calculate_current_load(self) -> Dict[str, float]:
        """Calculate current system load metrics."""
        return {
            "queue_utilization": len(self.task_queue) / self.max_queue_size,
            "resource_utilization": sum(
                (total - available) / total
                for total, available in [
                    (100, self.resource_pool[rt]) for rt in ResourceType
                ]
            )
            / len(ResourceType),
            "agent_utilization": len(self.running_tasks)
            / max(len(self.agent_capacities), 1),
        }

    def _calculate_available_resources(self) -> Dict[ResourceType, float]:
        """Calculate currently available resources."""
        return self.resource_pool.copy()

    def _calculate_resource_utilization(self) -> Dict[str, float]:
        """Calculate resource utilization percentages."""
        return {
            rt.value: (100.0 - amount) / 100.0
            for rt, amount in self.resource_pool.items()
        }

    def _calculate_average_wait_time(self) -> float:
        """Calculate average wait time for tasks in queue."""
        if not self.task_queue:
            return 0.0

        current_time = datetime.now(timezone.utc)
        total_wait_time = sum(
            (current_time - task.created_at).total_seconds() / 60  # minutes
            for _, task in self.task_queue
        )

        return total_wait_time / len(self.task_queue)

    def _get_available_agents(self) -> List[str]:
        """Get list of available agent IDs."""
        available = []
        for agent_id, capacity in self.agent_capacities.items():
            if capacity.current_tasks < capacity.max_concurrent_tasks:
                available.append(agent_id)
        return available

    def _get_performance_history(self) -> Dict[str, List[float]]:
        """Get performance history for optimization."""
        return {
            "throughput": list(self.resource_usage_history[ResourceType.CPU])[-10:],
            "latency": [],  # Would be populated with actual latency data
            "success_rate": [],  # Would be populated with task success rates
        }

    def _get_system_constraints(self) -> Dict[str, Any]:
        """Get current system constraints."""
        return {
            "max_queue_size": self.max_queue_size,
            "max_concurrent_tasks": sum(
                cap.max_concurrent_tasks for cap in self.agent_capacities.values()
            ),
            "resource_limits": dict(self.resource_pool),
            "scheduling_strategy": self.scheduling_strategy.value,
        }

    async def _update_performance_metrics(self):
        """Update performance metrics for monitoring."""

        current_time = datetime.now(timezone.utc)

        metrics = {
            "timestamp": current_time.isoformat(),
            "queue_size": len(self.task_queue),
            "running_tasks": len(self.running_tasks),
            "completed_tasks": len(self.completed_tasks),
            "failed_tasks": len(self.failed_tasks),
            "resource_utilization": self._calculate_resource_utilization(),
            "system_load": self._calculate_current_load(),
            "average_wait_time": self._calculate_average_wait_time(),
        }

        self.scheduling_metrics[current_time.isoformat()] = metrics

    # Public API methods

    async def get_scheduling_status(self) -> Dict[str, Any]:
        """Get current scheduling status and metrics."""

        return {
            "queue_size": len(self.task_queue),
            "running_tasks": len(self.running_tasks),
            "completed_tasks": len(self.completed_tasks),
            "failed_tasks": len(self.failed_tasks),
            "resource_utilization": self._calculate_resource_utilization(),
            "system_load": self._calculate_current_load(),
            "available_agents": len(self._get_available_agents()),
            "scheduling_strategy": self.scheduling_strategy.value,
            "average_wait_time_minutes": self._calculate_average_wait_time(),
        }

    async def update_agent_capacity(self, agent_id: str, capacity: AgentCapacity):
        """Update agent capacity information."""

        self.agent_capacities[agent_id] = capacity
        capacity.last_updated = datetime.now(timezone.utc)

        self.logger.info(
            "Agent capacity updated",
            agent_id=agent_id,
            max_concurrent_tasks=capacity.max_concurrent_tasks,
            current_tasks=capacity.current_tasks,
        )

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled or running task."""

        # Check if task is in queue
        for i, (score, task) in enumerate(self.task_queue):
            if task.task_id == task_id:
                del self.task_queue[i]
                heapq.heapify(self.task_queue)  # Restore heap property
                return True

        # Check if task is running
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            del self.running_tasks[task_id]

            # Release resources
            allocation = next(
                (
                    alloc
                    for alloc in self.allocated_resources.values()
                    if alloc.task_id == task_id
                ),
                None,
            )
            if allocation:
                await self._release_resources(allocation)

            return True

        return False


class SchedulingOptimizer:
    """AI-powered scheduling optimization engine."""

    def __init__(self, claude_agent: ClaudeAgentWrapper):
        self.claude_agent = claude_agent

    async def optimize_schedule(
        self, task_queue: List[Tuple[float, ScheduledTask]], context: SchedulingContext
    ) -> Dict[str, Any]:
        """Optimize task scheduling order using AI analysis."""

        optimization_prompt = f"""
        Optimize task scheduling order for maximum system efficiency:
        
        Current Queue: {json.dumps([{
            "task_id": task.task_id,
            "priority": task.priority.value,
            "estimated_duration": task.estimated_duration,
            "resource_requirements": [{
                "type": req.resource_type.value,
                "amount": req.amount
            } for req in task.resource_requirements],
            "dependencies": task.dependencies,
            "deadline": task.deadline.isoformat() if task.deadline else None
        } for score, task in task_queue[:10]], indent=2)}  # Analyze top 10 tasks
        
        System Context: {json.dumps({
            "current_load": context.current_load,
            "resource_availability": {rt.value: amount for rt, amount in context.resource_availability.items()},
            "optimization_goals": context.optimization_goals
        }, indent=2)}
        
        Optimization objectives:
        1. Maximize overall system throughput
        2. Minimize average task wait time
        3. Optimize resource utilization efficiency
        4. Respect task deadlines and priorities
        5. Balance load across available agents
        6. Minimize resource fragmentation
        7. Reduce dependency blocking chains
        8. Maintain system stability and responsiveness
        
        Analyze current scheduling order and provide optimizations:
        - Are there opportunities to reorder tasks for better resource utilization?
        - Can dependency chains be optimized to reduce blocking?
        - Should any tasks be prioritized differently based on system state?
        - Are there resource allocation inefficiencies that could be improved?
        - What scheduling adjustments would improve overall throughput?
        
        Provide optimization recommendations in JSON format with:
        - reorder_required: boolean indicating if reordering would improve performance
        - new_priorities: mapping of task_id to new priority scores
        - optimization_rationale: explanation of recommended changes
        - expected_improvements: predicted performance gains
        - resource_optimization: suggested resource allocation improvements
        - risk_assessment: potential risks of the optimization changes
        
        Focus on practical optimizations that provide measurable performance improvements.
        """

        result = await self.claude_agent.execute_task(
            {"type": "scheduling_optimization", "prompt": optimization_prompt},
            shared_memory={"scheduling_context": context.__dict__},
        )

        try:
            return json.loads(result["result"])
        except (json.JSONDecodeError, KeyError):
            return {"reorder_required": False}


class AdaptiveSchedulingController:
    """Controller for adaptive scheduling strategy selection."""

    def __init__(self):
        self.strategy_performance: Dict[SchedulingStrategy, deque] = {
            strategy: deque(maxlen=100) for strategy in SchedulingStrategy
        }
        self.current_strategy = SchedulingStrategy.AI_OPTIMIZED

    def should_adapt_strategy(self, current_metrics: Dict[str, Any]) -> bool:
        """Determine if scheduling strategy should be adapted."""

        # Simple adaptation logic based on system load
        system_load = current_metrics.get("system_load", {})
        queue_utilization = system_load.get("queue_utilization", 0.0)

        # Switch to more aggressive strategies under high load
        if (
            queue_utilization > 0.8
            and self.current_strategy != SchedulingStrategy.AI_OPTIMIZED
        ):
            return True

        return False

    def get_recommended_strategy(self, metrics: Dict[str, Any]) -> SchedulingStrategy:
        """Get recommended scheduling strategy based on current metrics."""

        system_load = metrics.get("system_load", {})
        queue_utilization = system_load.get("queue_utilization", 0.0)

        if queue_utilization > 0.8:
            return SchedulingStrategy.AI_OPTIMIZED
        elif queue_utilization > 0.5:
            return SchedulingStrategy.PRIORITY
        else:
            return SchedulingStrategy.ADAPTIVE


class LoadPredictor:
    """Predicts future system load for proactive scheduling."""

    def __init__(self):
        self.load_history: deque = deque(maxlen=1000)

    def predict_load(self, horizon_minutes: int = 60) -> Dict[str, float]:
        """Predict system load for the next time horizon."""

        # Simple prediction based on recent trends
        if len(self.load_history) < 10:
            return {"predicted_load": 0.5, "confidence": 0.3}

        recent_loads = list(self.load_history)[-10:]
        average_load = sum(recent_loads) / len(recent_loads)

        # Simple trend calculation
        if len(recent_loads) >= 2:
            trend = recent_loads[-1] - recent_loads[0]
        else:
            trend = 0.0

        predicted_load = max(0.0, min(1.0, average_load + trend))

        return {"predicted_load": predicted_load, "confidence": 0.7, "trend": trend}


# Factory function for easy integration
async def create_dynamic_task_scheduler(
    claude_api_key: Optional[str] = None,
) -> DynamicTaskScheduler:
    """Factory function to create configured dynamic task scheduler."""

    claude_agent = ClaudeAgentWrapper(api_key=claude_api_key)
    scheduler = DynamicTaskScheduler(claude_agent)
    await scheduler.start()
    return scheduler
