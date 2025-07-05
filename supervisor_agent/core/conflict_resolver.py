# supervisor_agent/core/conflict_resolver.py
import asyncio
import heapq
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from supervisor_agent.core.resource_allocation_engine import (
    AllocationPlan,
    ResourceType,
)
from supervisor_agent.models.task import Task


class ConflictType(Enum):
    """Types of resource conflicts."""

    OVERALLOCATION = "overallocation"
    PRIORITY_CONFLICT = "priority_conflict"
    TEMPORAL_CONFLICT = "temporal_conflict"
    DEPENDENCY_CONFLICT = "dependency_conflict"
    QUOTA_EXCEEDED = "quota_exceeded"
    HARDWARE_LIMITATION = "hardware_limitation"


class ResolutionStrategy(Enum):
    """Strategies for resolving resource conflicts."""

    RESCHEDULE = "reschedule"
    PREEMPT = "preempt"
    SHARE_RESOURCES = "share_resources"
    QUEUE = "queue"
    SCALE_UP = "scale_up"
    OPTIMIZE_ALLOCATION = "optimize_allocation"
    REJECT = "reject"


class QueueType(Enum):
    """Types of task queues."""

    HIGH_PRIORITY = "high_priority"
    NORMAL_PRIORITY = "normal_priority"
    LOW_PRIORITY = "low_priority"
    BACKGROUND = "background"
    URGENT = "urgent"
    BATCH = "batch"


@dataclass
class ResourceConflict:
    """Represents a resource conflict between tasks."""

    conflict_id: str
    conflict_type: ConflictType
    affected_tasks: List[str]
    resource_type: ResourceType
    requested_amount: float
    available_amount: float
    severity: str  # low, medium, high, critical
    detected_at: datetime = field(default_factory=datetime.now)
    description: str = ""


@dataclass
class ResolutionPlan:
    """Plan for resolving a resource conflict."""

    conflict_id: str
    strategy: ResolutionStrategy
    affected_tasks: List[str]
    actions: List[Dict]
    estimated_resolution_time: int  # minutes
    cost_impact: float
    performance_impact: str
    reasoning: str


@dataclass
class TaskReservation:
    """Resource reservation for a task."""

    task_id: str
    resource_type: ResourceType
    amount: float
    start_time: datetime
    end_time: datetime
    priority: int
    is_preemptible: bool = True
    reservation_id: str = field(
        default_factory=lambda: f"res_{int(datetime.now().timestamp())}"
    )


@dataclass
class QueuedTask:
    """Task in a priority queue."""

    task: Task
    allocation_plan: AllocationPlan
    queue_time: datetime = field(default_factory=datetime.now)
    estimated_wait_time: int = 0  # minutes
    priority_score: float = 0.0

    def __lt__(self, other):
        # For heapq - higher priority scores come first (negate for min-heap)
        return -self.priority_score < -other.priority_score


class ResourceConflictResolver:
    """Advanced resource conflict detection and resolution system."""

    def __init__(self):
        self.active_conflicts: Dict[str, ResourceConflict] = {}
        self.resolution_history: List[ResolutionPlan] = []
        self.resource_reservations: Dict[str, List[TaskReservation]] = defaultdict(list)
        self.priority_queues: Dict[QueueType, List[QueuedTask]] = {
            queue_type: [] for queue_type in QueueType
        }
        self.resource_limits = {
            ResourceType.CPU: 16.0,  # 16 CPUs
            ResourceType.MEMORY: 32768,  # 32GB in MB
            ResourceType.DISK: 1000,  # 1TB in GB
            ResourceType.NETWORK: 1000,  # 1Gbps
            ResourceType.GPU: 4.0,  # 4 GPUs
        }
        self.preemption_policies = {
            "urgent": {
                "can_preempt": ["normal", "low", "background"],
                "grace_period": 30,
            },
            "high": {
                "can_preempt": ["normal", "low", "background"],
                "grace_period": 60,
            },
            "normal": {
                "can_preempt": ["low", "background"],
                "grace_period": 120,
            },
            "low": {"can_preempt": ["background"], "grace_period": 300},
            "background": {"can_preempt": [], "grace_period": 600},
        }

    async def detect_resource_conflicts(
        self, allocations: List[AllocationPlan]
    ) -> List[ResourceConflict]:
        """Detect various types of resource conflicts."""
        conflicts = []

        # Check for overallocation conflicts
        conflicts.extend(await self._detect_overallocation_conflicts(allocations))

        # Check for priority conflicts
        conflicts.extend(await self._detect_priority_conflicts(allocations))

        # Check for temporal conflicts
        conflicts.extend(await self._detect_temporal_conflicts(allocations))

        # Check for quota exceeded conflicts
        conflicts.extend(await self._detect_quota_conflicts(allocations))

        # Store detected conflicts
        for conflict in conflicts:
            self.active_conflicts[conflict.conflict_id] = conflict

        return conflicts

    async def _detect_overallocation_conflicts(
        self, allocations: List[AllocationPlan]
    ) -> List[ResourceConflict]:
        """Detect resource overallocation conflicts."""
        conflicts = []

        # Aggregate resource usage by type
        resource_usage = defaultdict(float)
        task_allocations = defaultdict(list)

        for allocation in allocations:
            resource_usage[ResourceType.CPU] += allocation.cpu_allocation
            resource_usage[ResourceType.MEMORY] += allocation.memory_allocation
            resource_usage[ResourceType.DISK] += allocation.disk_allocation
            resource_usage[ResourceType.NETWORK] += allocation.network_allocation

            task_allocations[ResourceType.CPU].append(allocation.task_id)
            task_allocations[ResourceType.MEMORY].append(allocation.task_id)
            task_allocations[ResourceType.DISK].append(allocation.task_id)
            task_allocations[ResourceType.NETWORK].append(allocation.task_id)

        # Check each resource type for overallocation
        for resource_type, total_usage in resource_usage.items():
            limit = self.resource_limits[resource_type]
            if total_usage > limit:
                severity = "critical" if total_usage > limit * 1.2 else "high"
                conflict = ResourceConflict(
                    conflict_id=f"overalloc_{resource_type.value}_{int(datetime.now().timestamp())}",
                    conflict_type=ConflictType.OVERALLOCATION,
                    affected_tasks=task_allocations[resource_type],
                    resource_type=resource_type,
                    requested_amount=total_usage,
                    available_amount=limit,
                    severity=severity,
                    description=f"{resource_type.value.upper()} overallocated: {total_usage:.2f} > {limit:.2f}",
                )
                conflicts.append(conflict)

        return conflicts

    async def _detect_priority_conflicts(
        self, allocations: List[AllocationPlan]
    ) -> List[ResourceConflict]:
        """Detect priority-based conflicts."""
        conflicts = []

        # Group allocations by priority
        priority_groups = defaultdict(list)
        for allocation in allocations:
            priority_groups[allocation.priority].append(allocation)

        # Check if high-priority tasks are being starved by low-priority tasks
        for priority, group_allocations in priority_groups.items():
            if priority <= 2:  # High priority tasks
                for allocation in group_allocations:
                    # Check if this high-priority task has insufficient resources
                    # compared to lower priority tasks
                    low_priority_total = sum(
                        a.cpu_allocation
                        for a in allocations
                        if a.priority > priority and a.task_id != allocation.task_id
                    )

                    if low_priority_total > allocation.cpu_allocation * 2:
                        conflict = ResourceConflict(
                            conflict_id=f"priority_{allocation.task_id}_{int(datetime.now().timestamp())}",
                            conflict_type=ConflictType.PRIORITY_CONFLICT,
                            affected_tasks=[allocation.task_id],
                            resource_type=ResourceType.CPU,
                            requested_amount=allocation.cpu_allocation,
                            available_amount=low_priority_total,
                            severity="medium",
                            description=f"High-priority task {allocation.task_id} starved by low-priority tasks",
                        )
                        conflicts.append(conflict)

        return conflicts

    async def _detect_temporal_conflicts(
        self, allocations: List[AllocationPlan]
    ) -> List[ResourceConflict]:
        """Detect temporal resource conflicts."""
        conflicts = []

        # Check reservations for overlapping time periods
        for resource_type, reservations in self.resource_reservations.items():
            # Sort reservations by start time
            sorted_reservations = sorted(reservations, key=lambda r: r.start_time)

            for i in range(len(sorted_reservations) - 1):
                current = sorted_reservations[i]
                next_reservation = sorted_reservations[i + 1]

                # Check for overlap
                if current.end_time > next_reservation.start_time:
                    # Calculate resource conflict amount
                    overlap_amount = min(current.amount, next_reservation.amount)

                    conflict = ResourceConflict(
                        conflict_id=f"temporal_{current.task_id}_{next_reservation.task_id}",
                        conflict_type=ConflictType.TEMPORAL_CONFLICT,
                        affected_tasks=[
                            current.task_id,
                            next_reservation.task_id,
                        ],
                        resource_type=ResourceType(resource_type),
                        requested_amount=overlap_amount,
                        available_amount=0,
                        severity="medium",
                        description=f"Temporal overlap between {current.task_id} and {next_reservation.task_id}",
                    )
                    conflicts.append(conflict)

        return conflicts

    async def _detect_quota_conflicts(
        self, allocations: List[AllocationPlan]
    ) -> List[ResourceConflict]:
        """Detect quota exceeded conflicts."""
        conflicts = []

        # Check if total estimated cost exceeds budget
        total_cost = sum(allocation.cost_estimate for allocation in allocations)
        budget_limit = 100.0  # $100 budget limit

        if total_cost > budget_limit:
            high_cost_tasks = [a.task_id for a in allocations if a.cost_estimate > 10.0]

            conflict = ResourceConflict(
                conflict_id=f"quota_cost_{int(datetime.now().timestamp())}",
                conflict_type=ConflictType.QUOTA_EXCEEDED,
                affected_tasks=high_cost_tasks,
                resource_type=ResourceType.CPU,  # Generic
                requested_amount=total_cost,
                available_amount=budget_limit,
                severity=("high" if total_cost > budget_limit * 1.5 else "medium"),
                description=f"Total cost ${total_cost:.2f} exceeds budget ${budget_limit:.2f}",
            )
            conflicts.append(conflict)

        return conflicts

    async def implement_resolution_strategies(
        self, conflicts: List[ResourceConflict]
    ) -> List[ResolutionPlan]:
        """Implement strategies to resolve detected conflicts."""
        resolution_plans = []

        for conflict in conflicts:
            # Determine best resolution strategy
            strategy = await self._select_resolution_strategy(conflict)

            # Create resolution plan
            plan = await self._create_resolution_plan(conflict, strategy)
            resolution_plans.append(plan)

            # Execute the resolution
            await self._execute_resolution_plan(plan)

        # Store resolution history
        self.resolution_history.extend(resolution_plans)

        return resolution_plans

    async def _select_resolution_strategy(
        self, conflict: ResourceConflict
    ) -> ResolutionStrategy:
        """Select the best resolution strategy for a conflict."""
        if conflict.conflict_type == ConflictType.OVERALLOCATION:
            if conflict.severity == "critical":
                return ResolutionStrategy.SCALE_UP
            else:
                return ResolutionStrategy.OPTIMIZE_ALLOCATION

        elif conflict.conflict_type == ConflictType.PRIORITY_CONFLICT:
            return ResolutionStrategy.PREEMPT

        elif conflict.conflict_type == ConflictType.TEMPORAL_CONFLICT:
            return ResolutionStrategy.RESCHEDULE

        elif conflict.conflict_type == ConflictType.QUOTA_EXCEEDED:
            return ResolutionStrategy.QUEUE

        else:
            return ResolutionStrategy.RESCHEDULE

    async def _create_resolution_plan(
        self, conflict: ResourceConflict, strategy: ResolutionStrategy
    ) -> ResolutionPlan:
        """Create a detailed resolution plan."""
        actions = []
        estimated_time = 5  # Default 5 minutes
        cost_impact = 0.0
        performance_impact = "minimal"

        if strategy == ResolutionStrategy.RESCHEDULE:
            actions = [
                {
                    "action": "reschedule_task",
                    "task_id": task_id,
                    "delay_minutes": 30,
                }
                for task_id in conflict.affected_tasks[1:]  # Reschedule all but first
            ]
            estimated_time = 10
            performance_impact = "low"

        elif strategy == ResolutionStrategy.PREEMPT:
            actions = [
                {
                    "action": "preempt_task",
                    "task_id": task_id,
                    "grace_period": 60,
                }
                for task_id in conflict.affected_tasks[1:]  # Preempt lower priority
            ]
            estimated_time = 2
            performance_impact = "medium"

        elif strategy == ResolutionStrategy.SCALE_UP:
            actions = [
                {
                    "action": "scale_up_resource",
                    "resource_type": conflict.resource_type.value,
                    "scale_factor": 1.5,
                }
            ]
            estimated_time = 15
            cost_impact = 50.0  # Additional cost for scaling
            performance_impact = "positive"

        elif strategy == ResolutionStrategy.OPTIMIZE_ALLOCATION:
            actions = [
                {
                    "action": "optimize_allocation",
                    "task_id": task_id,
                    "reduction_factor": 0.8,
                }
                for task_id in conflict.affected_tasks
            ]
            estimated_time = 5
            performance_impact = "minimal"

        elif strategy == ResolutionStrategy.QUEUE:
            actions = [
                {
                    "action": "queue_task",
                    "task_id": task_id,
                    "queue_type": "normal_priority",
                }
                for task_id in conflict.affected_tasks[-2:]  # Queue last 2 tasks
            ]
            estimated_time = 1
            performance_impact = "delayed_execution"

        return ResolutionPlan(
            conflict_id=conflict.conflict_id,
            strategy=strategy,
            affected_tasks=conflict.affected_tasks,
            actions=actions,
            estimated_resolution_time=estimated_time,
            cost_impact=cost_impact,
            performance_impact=performance_impact,
            reasoning=f"Resolving {conflict.conflict_type.value} using {strategy.value} strategy",
        )

    async def _execute_resolution_plan(self, plan: ResolutionPlan):
        """Execute a resolution plan."""
        for action in plan.actions:
            if action["action"] == "reschedule_task":
                # Simulate rescheduling
                print(
                    f"Rescheduling task {action['task_id']} by {action['delay_minutes']} minutes"
                )

            elif action["action"] == "preempt_task":
                # Simulate preemption
                print(
                    f"Preempting task {action['task_id']} with {action['grace_period']}s grace period"
                )

            elif action["action"] == "scale_up_resource":
                # Simulate scaling
                print(
                    f"Scaling up {action['resource_type']} by factor {action['scale_factor']}"
                )

            elif action["action"] == "optimize_allocation":
                # Simulate optimization
                print(f"Optimizing allocation for task {action['task_id']}")

            elif action["action"] == "queue_task":
                # Simulate queuing
                print(f"Queuing task {action['task_id']} in {action['queue_type']}")

    async def manage_priority_queues(self, tasks: List[Task]) -> Dict:
        """Manage priority-based task queues."""
        # Clear existing queues
        for queue_type in QueueType:
            self.priority_queues[queue_type] = []

        # Categorize tasks into appropriate queues
        for task in tasks:
            priority = getattr(task, "priority", 5)
            complexity = self._calculate_task_complexity(task)

            # Determine queue type based on priority and characteristics
            if priority <= 1:
                queue_type = QueueType.URGENT
            elif priority <= 3:
                queue_type = QueueType.HIGH_PRIORITY
            elif priority <= 6:
                queue_type = QueueType.NORMAL_PRIORITY
            elif complexity < 1.0:
                queue_type = QueueType.BACKGROUND
            elif hasattr(task, "batch") and getattr(task, "batch", False):
                queue_type = QueueType.BATCH
            else:
                queue_type = QueueType.LOW_PRIORITY

            # Calculate priority score for queue ordering
            priority_score = self._calculate_priority_score(task, priority, complexity)

            # Create queued task
            queued_task = QueuedTask(
                task=task,
                allocation_plan=None,  # Will be set when allocated
                priority_score=priority_score,
            )

            # Add to appropriate queue (using heapq for priority ordering)
            heapq.heappush(self.priority_queues[queue_type], queued_task)

        # Calculate wait times
        await self._calculate_wait_times()

        # Return queue summary
        return {
            queue_type.value: {
                "count": len(self.priority_queues[queue_type]),
                "tasks": [
                    qt.task.id for qt in list(self.priority_queues[queue_type])[:5]
                ],  # First 5
            }
            for queue_type in QueueType
        }

    def _calculate_task_complexity(self, task: Task) -> float:
        """Calculate task complexity for queue management."""
        if hasattr(task, "config") and "description" in task.config:
            description = task.config["description"].lower()
            complexity_keywords = [
                "analyze",
                "optimize",
                "process",
                "transform",
                "compute",
            ]
            complexity = sum(
                1 for keyword in complexity_keywords if keyword in description
            )
            return min(3.0, complexity * 0.5)
        return 1.0

    def _calculate_priority_score(
        self, task: Task, priority: int, complexity: float
    ) -> float:
        """Calculate priority score for queue ordering."""
        # Base score from priority (lower number = higher priority = higher score)
        base_score = 10 - priority

        # Adjust for complexity
        complexity_bonus = complexity * 0.5

        # Time-based urgency (older tasks get higher scores)
        age_bonus = 0.1  # Simplified - in real implementation, calculate from task creation time

        return base_score + complexity_bonus + age_bonus

    async def _calculate_wait_times(self):
        """Calculate estimated wait times for queued tasks."""
        for queue_type, queue in self.priority_queues.items():
            cumulative_time = 0
            for i, queued_task in enumerate(queue):
                queued_task.estimated_wait_time = cumulative_time
                # Estimate task duration (simplified)
                task_duration = (
                    15 + self._calculate_task_complexity(queued_task.task) * 10
                )
                cumulative_time += task_duration

    async def coordinate_resource_reservation(
        self, task: Task, allocation_plan: AllocationPlan
    ) -> Dict:
        """Coordinate resource reservation for a task."""
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=allocation_plan.estimated_duration)
        priority = allocation_plan.priority

        reservations = []

        # Create reservations for each resource type
        if allocation_plan.cpu_allocation > 0:
            cpu_reservation = TaskReservation(
                task_id=task.id,
                resource_type=ResourceType.CPU,
                amount=allocation_plan.cpu_allocation,
                start_time=start_time,
                end_time=end_time,
                priority=priority,
                is_preemptible=priority > 2,
            )
            reservations.append(cpu_reservation)
            self.resource_reservations[ResourceType.CPU.value].append(cpu_reservation)

        if allocation_plan.memory_allocation > 0:
            memory_reservation = TaskReservation(
                task_id=task.id,
                resource_type=ResourceType.MEMORY,
                amount=allocation_plan.memory_allocation,
                start_time=start_time,
                end_time=end_time,
                priority=priority,
                is_preemptible=priority > 2,
            )
            reservations.append(memory_reservation)
            self.resource_reservations[ResourceType.MEMORY.value].append(
                memory_reservation
            )

        return {
            "reservation_status": "success",
            "reservations": [r.reservation_id for r in reservations],
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "total_cost": allocation_plan.cost_estimate,
        }

    async def handle_resource_preemption(
        self, high_priority_task: Task, target_tasks: List[str] = None
    ) -> Dict:
        """Handle resource preemption for high-priority tasks."""
        priority = getattr(high_priority_task, "priority", 5)
        priority_level = (
            "urgent" if priority <= 1 else "high" if priority <= 3 else "normal"
        )

        policy = self.preemption_policies.get(
            priority_level, self.preemption_policies["normal"]
        )
        preemptible_levels = policy["can_preempt"]
        grace_period = policy["grace_period"]

        preempted_tasks = []
        freed_resources = {
            ResourceType.CPU: 0.0,
            ResourceType.MEMORY: 0.0,
            ResourceType.DISK: 0.0,
            ResourceType.NETWORK: 0.0,
        }

        # Find preemptible reservations
        for resource_type, reservations in self.resource_reservations.items():
            for reservation in reservations[:]:
                if target_tasks and reservation.task_id not in target_tasks:
                    continue

                # Check if this reservation can be preempted
                task_priority_level = (
                    "background"
                    if reservation.priority > 7
                    else "low" if reservation.priority > 5 else "normal"
                )

                if (
                    task_priority_level in preemptible_levels
                    and reservation.is_preemptible
                ):
                    # Preempt this reservation
                    preempted_tasks.append(
                        {
                            "task_id": reservation.task_id,
                            "resource_type": resource_type,
                            "amount_freed": reservation.amount,
                            "grace_period_seconds": grace_period,
                        }
                    )

                    freed_resources[ResourceType(resource_type)] += reservation.amount

                    # Remove the reservation
                    reservations.remove(reservation)

        return {
            "preemption_status": (
                "success" if preempted_tasks else "no_preemption_needed"
            ),
            "preempted_tasks": preempted_tasks,
            "freed_resources": {
                resource_type.value: amount
                for resource_type, amount in freed_resources.items()
            },
            "high_priority_task": high_priority_task.id,
            "grace_period_seconds": grace_period,
        }

    async def get_conflict_resolution_report(self) -> Dict:
        """Generate comprehensive conflict resolution report."""
        return {
            "active_conflicts": {
                "count": len(self.active_conflicts),
                "by_type": {
                    conflict_type.value: len(
                        [
                            c
                            for c in self.active_conflicts.values()
                            if c.conflict_type == conflict_type
                        ]
                    )
                    for conflict_type in ConflictType
                },
                "by_severity": {
                    severity: len(
                        [
                            c
                            for c in self.active_conflicts.values()
                            if c.severity == severity
                        ]
                    )
                    for severity in ["low", "medium", "high", "critical"]
                },
            },
            "resolution_history": {
                "total_resolutions": len(self.resolution_history),
                "successful_strategies": {
                    strategy.value: len(
                        [p for p in self.resolution_history if p.strategy == strategy]
                    )
                    for strategy in ResolutionStrategy
                },
                "average_resolution_time": (
                    (
                        sum(
                            p.estimated_resolution_time for p in self.resolution_history
                        )
                        / len(self.resolution_history)
                    )
                    if self.resolution_history
                    else 0
                ),
            },
            "queue_status": {
                queue_type.value: len(self.priority_queues[queue_type])
                for queue_type in QueueType
            },
            "resource_reservations": {
                resource_type: len(reservations)
                for resource_type, reservations in self.resource_reservations.items()
            },
        }
