"""Resource Conflict Resolution System
Intelligent detection and resolution of resource allocation conflicts.

This module implements advanced conflict resolution capabilities including:
- Multi-dimensional conflict detection algorithms
- Priority-based conflict resolution strategies
- Resource reservation and preemption management
- Fair resource distribution mechanisms
- Integration with dynamic resource allocation

Follows SOLID principles and integrates with existing resource management infrastructure.
"""

import asyncio
import heapq
import json
import statistics
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple, Union

import structlog

from supervisor_agent.core.resource_allocation_engine import (
    AllocationStrategy,
    DynamicResourceAllocator,
    ResourceAllocation,
    ResourceMetrics,
    ResourceStatus,
    ResourceType,
    ResourceUsage,
)
from supervisor_agent.providers.base_provider import ProviderType
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)
structured_logger = structlog.get_logger(__name__)


class ConflictType(Enum):
    """Types of resource conflicts."""

    CAPACITY_EXCEEDED = "capacity_exceeded"  # Total demand exceeds capacity
    PRIORITY_COLLISION = "priority_collision"  # High priority tasks competing
    DEADLINE_CONFLICT = "deadline_conflict"  # Overlapping deadline constraints
    RESERVATION_OVERLAP = "reservation_overlap"  # Conflicting reservations
    PROVIDER_OVERLOAD = "provider_overload"  # Single provider overloaded
    DEPENDENCY_DEADLOCK = "dependency_deadlock"  # Circular resource dependencies
    FAIRNESS_VIOLATION = "fairness_violation"  # Unfair resource distribution
    COST_CONSTRAINT = "cost_constraint"  # Budget limitations
    QUALITY_DEGRADATION = "quality_degradation"  # Service quality issues


class ConflictSeverity(Enum):
    """Severity levels for conflicts."""

    LOW = "low"  # Minor inefficiency
    MEDIUM = "medium"  # Noticeable impact
    HIGH = "high"  # Significant performance impact
    CRITICAL = "critical"  # System stability at risk
    EMERGENCY = "emergency"  # Immediate intervention required


class ResolutionStrategy(Enum):
    """Conflict resolution strategies."""

    FIRST_COME_FIRST_SERVED = "fcfs"
    PRIORITY_BASED = "priority_based"
    DEADLINE_AWARE = "deadline_aware"
    FAIR_SHARE = "fair_share"
    COST_OPTIMIZED = "cost_optimized"
    PREEMPTION = "preemption"
    LOAD_BALANCING = "load_balancing"
    RESOURCE_SCALING = "resource_scaling"
    QUEUE_MANAGEMENT = "queue_management"


class PreemptionType(Enum):
    """Types of preemption actions."""

    NONE = "none"  # No preemption
    PAUSE = "pause"  # Temporarily pause task
    MIGRATE = "migrate"  # Move task to different provider
    RESCALE = "rescale"  # Reduce resource allocation
    TERMINATE = "terminate"  # Stop low-priority task


@dataclass
class Conflict:
    """Represents a resource allocation conflict."""

    conflict_id: str
    conflict_type: ConflictType
    severity: ConflictSeverity
    affected_tasks: List[str]
    affected_providers: List[str]
    resource_type: ResourceType
    description: str
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Conflict details
    required_resources: Dict[str, float] = field(
        default_factory=dict
    )  # task_id -> amount
    available_capacity: float = 0.0
    capacity_shortfall: float = 0.0

    # Resolution info
    resolution_strategy: Optional[ResolutionStrategy] = None
    estimated_resolution_time: int = 0  # minutes
    resolution_cost: float = 0.0

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Resolution:
    """Resolution action for a conflict."""

    resolution_id: str
    conflict_id: str
    strategy: ResolutionStrategy
    actions: List[Dict[str, Any]]
    estimated_impact: Dict[str, float]  # performance, cost, fairness
    confidence_score: float  # 0.0-1.0
    implementation_order: List[str]  # Order of action execution
    rollback_plan: List[Dict[str, Any]]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Status tracking
    status: str = "planned"  # planned, executing, completed, failed
    execution_log: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PriorityQueue:
    """Priority-based task queue for resource allocation."""

    queue_id: str
    resource_type: ResourceType
    provider_id: str
    tasks: List[Tuple[int, str, ResourceAllocation]]  # (priority, task_id, allocation)
    max_size: int = 100
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        # Convert to heap (min-heap, so negate priorities for max behavior)
        self.tasks = [
            (-priority, task_id, allocation)
            for priority, task_id, allocation in self.tasks
        ]
        heapq.heapify(self.tasks)

    def push(self, priority: int, task_id: str, allocation: ResourceAllocation):
        """Add task to priority queue."""
        if len(self.tasks) >= self.max_size:
            # Remove lowest priority task
            heapq.heappop(self.tasks)
        heapq.heappush(self.tasks, (-priority, task_id, allocation))

    def pop(self) -> Optional[Tuple[int, str, ResourceAllocation]]:
        """Get highest priority task."""
        if self.tasks:
            neg_priority, task_id, allocation = heapq.heappop(self.tasks)
            return (-neg_priority, task_id, allocation)
        return None

    def peek(self) -> Optional[Tuple[int, str, ResourceAllocation]]:
        """Look at highest priority task without removing."""
        if self.tasks:
            neg_priority, task_id, allocation = self.tasks[0]
            return (-neg_priority, task_id, allocation)
        return None

    def size(self) -> int:
        """Get queue size."""
        return len(self.tasks)


@dataclass
class ReservationResult:
    """Result of resource reservation attempt."""

    reservation_id: str
    task_id: str
    provider_id: str
    resources: Dict[ResourceType, float]
    reserved_until: datetime
    success: bool
    failure_reason: Optional[str] = None
    alternative_providers: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PreemptionResult:
    """Result of resource preemption action."""

    preemption_id: str
    preempted_task_id: str
    beneficiary_task_id: str
    preemption_type: PreemptionType
    resources_freed: Dict[ResourceType, float]
    estimated_recovery_time: int  # minutes
    compensation_cost: float
    success: bool
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ResourceConflictResolver:
    """Intelligent resource conflict detection and resolution system."""

    def __init__(self, resource_allocator: Optional[DynamicResourceAllocator] = None):
        self.logger = structured_logger.bind(component="conflict_resolver")
        self.resource_allocator = resource_allocator or DynamicResourceAllocator()

        # Internal state
        self._active_conflicts: Dict[str, Conflict] = {}
        self._conflict_history: deque = deque(maxlen=1000)
        self._priority_queues: Dict[str, PriorityQueue] = {}  # provider_id -> queue
        self._reservations: Dict[str, ReservationResult] = {}
        self._preemption_policies = self._load_preemption_policies()

        # Metrics
        self._resolution_stats = defaultdict(int)
        self._conflict_patterns = defaultdict(list)

    def _load_preemption_policies(self) -> Dict[str, Any]:
        """Load preemption policies for different scenarios."""
        return {
            "priority_threshold": 8,  # Tasks with priority >= 8 can preempt
            "preemption_cost_threshold": 100.0,  # Max cost for preemption
            "allowed_preemption_types": [
                PreemptionType.PAUSE,
                PreemptionType.MIGRATE,
                PreemptionType.RESCALE,
            ],
            "forbidden_preemption_types": [PreemptionType.TERMINATE],
            "max_preemptions_per_hour": 10,
            "cooldown_minutes": 15,
        }

    async def detect_resource_conflicts(
        self, allocations: List[ResourceAllocation]
    ) -> List[Conflict]:
        """Detect resource conflicts in current allocations."""
        self.logger.info(
            "Detecting resource conflicts", allocation_count=len(allocations)
        )

        conflicts = []

        # Group allocations by provider and resource type
        provider_allocations = self._group_allocations_by_provider(allocations)

        for provider_id, provider_allocs in provider_allocations.items():
            # Get current resource usage for provider
            try:
                current_usage = (
                    await self.resource_allocator.monitor.collect_system_metrics(
                        provider_id
                    )
                )
                provider_conflicts = await self._detect_provider_conflicts(
                    provider_id, provider_allocs, current_usage
                )
                conflicts.extend(provider_conflicts)
            except Exception as e:
                self.logger.error(
                    "Failed to detect conflicts for provider",
                    provider_id=provider_id,
                    error=str(e),
                )

        # Detect cross-provider conflicts
        cross_provider_conflicts = self._detect_cross_provider_conflicts(allocations)
        conflicts.extend(cross_provider_conflicts)

        # Store detected conflicts
        for conflict in conflicts:
            self._active_conflicts[conflict.conflict_id] = conflict
            self._conflict_history.append(conflict)
            self._conflict_patterns[conflict.conflict_type].append(
                datetime.now(timezone.utc)
            )

        self.logger.info(
            "Conflict detection completed",
            conflicts_detected=len(conflicts),
            active_conflicts=len(self._active_conflicts),
        )

        return conflicts

    def _group_allocations_by_provider(
        self, allocations: List[ResourceAllocation]
    ) -> Dict[str, List[ResourceAllocation]]:
        """Group allocations by provider."""
        provider_allocs = defaultdict(list)
        for allocation in allocations:
            provider_allocs[allocation.provider_id].append(allocation)
        return dict(provider_allocs)

    async def _detect_provider_conflicts(
        self,
        provider_id: str,
        allocations: List[ResourceAllocation],
        current_usage: ResourceUsage,
    ) -> List[Conflict]:
        """Detect conflicts within a single provider."""
        conflicts = []

        # Group by resource type
        resource_demands = defaultdict(lambda: {"total": 0.0, "tasks": []})

        for allocation in allocations:
            for resource_type, amount in allocation.resources.items():
                resource_demands[resource_type]["total"] += amount
                resource_demands[resource_type]["tasks"].append(
                    {
                        "task_id": allocation.task_id,
                        "amount": amount,
                        "priority": allocation.priority,
                        "deadline": allocation.deadline,
                    }
                )

        # Check capacity conflicts
        for resource_type, demand_info in resource_demands.items():
            if resource_type in current_usage.metrics:
                metrics = current_usage.metrics[resource_type]
                total_demand = demand_info["total"]
                available_capacity = metrics.available

                if total_demand > available_capacity:
                    # Capacity exceeded conflict
                    conflict = Conflict(
                        conflict_id=str(uuid.uuid4()),
                        conflict_type=ConflictType.CAPACITY_EXCEEDED,
                        severity=self._calculate_conflict_severity(
                            total_demand, available_capacity
                        ),
                        affected_tasks=[
                            task["task_id"] for task in demand_info["tasks"]
                        ],
                        affected_providers=[provider_id],
                        resource_type=resource_type,
                        description=f"{resource_type.value} demand ({total_demand:.1f}) exceeds capacity ({available_capacity:.1f})",
                        required_resources={
                            task["task_id"]: task["amount"]
                            for task in demand_info["tasks"]
                        },
                        available_capacity=available_capacity,
                        capacity_shortfall=total_demand - available_capacity,
                    )
                    conflicts.append(conflict)

        # Check priority conflicts
        priority_conflicts = self._detect_priority_conflicts(allocations, provider_id)
        conflicts.extend(priority_conflicts)

        # Check deadline conflicts
        deadline_conflicts = self._detect_deadline_conflicts(allocations, provider_id)
        conflicts.extend(deadline_conflicts)

        return conflicts

    def _calculate_conflict_severity(
        self, demand: float, capacity: float
    ) -> ConflictSeverity:
        """Calculate conflict severity based on demand vs capacity."""
        shortage_ratio = (
            (demand - capacity) / capacity if capacity > 0 else float("inf")
        )

        if shortage_ratio >= 1.0:  # Demand is 2x+ capacity
            return ConflictSeverity.EMERGENCY
        elif shortage_ratio >= 0.5:  # Demand is 1.5x+ capacity
            return ConflictSeverity.CRITICAL
        elif shortage_ratio >= 0.25:  # Demand is 1.25x+ capacity
            return ConflictSeverity.HIGH
        elif shortage_ratio >= 0.1:  # Demand is 1.1x+ capacity
            return ConflictSeverity.MEDIUM
        else:
            return ConflictSeverity.LOW

    def _detect_priority_conflicts(
        self, allocations: List[ResourceAllocation], provider_id: str
    ) -> List[Conflict]:
        """Detect conflicts between high-priority tasks."""
        conflicts = []

        # Find high priority tasks competing for same resources
        high_priority_tasks = [a for a in allocations if a.priority >= 8]

        if len(high_priority_tasks) > 1:
            # Group by resource type to find competition
            resource_competition = defaultdict(list)
            for allocation in high_priority_tasks:
                for resource_type in allocation.resources:
                    resource_competition[resource_type].append(allocation)

            for resource_type, competing_allocations in resource_competition.items():
                if len(competing_allocations) > 1:
                    conflict = Conflict(
                        conflict_id=str(uuid.uuid4()),
                        conflict_type=ConflictType.PRIORITY_COLLISION,
                        severity=ConflictSeverity.HIGH,
                        affected_tasks=[a.task_id for a in competing_allocations],
                        affected_providers=[provider_id],
                        resource_type=resource_type,
                        description=f"Multiple high-priority tasks competing for {resource_type.value}",
                        required_resources={
                            a.task_id: a.resources[resource_type]
                            for a in competing_allocations
                        },
                    )
                    conflicts.append(conflict)

        return conflicts

    def _detect_deadline_conflicts(
        self, allocations: List[ResourceAllocation], provider_id: str
    ) -> List[Conflict]:
        """Detect conflicts between tasks with tight deadlines."""
        conflicts = []

        # Find tasks with deadlines
        deadline_tasks = [a for a in allocations if a.deadline is not None]

        if len(deadline_tasks) > 1:
            # Sort by deadline
            deadline_tasks.sort(key=lambda a: a.deadline)

            # Check for overlapping resource needs with conflicting deadlines
            for i, task1 in enumerate(deadline_tasks[:-1]):
                for task2 in deadline_tasks[i + 1 :]:
                    # Check if they compete for same resources
                    shared_resources = set(task1.resources.keys()) & set(
                        task2.resources.keys()
                    )

                    if shared_resources and self._has_deadline_conflict(task1, task2):
                        conflict = Conflict(
                            conflict_id=str(uuid.uuid4()),
                            conflict_type=ConflictType.DEADLINE_CONFLICT,
                            severity=ConflictSeverity.HIGH,
                            affected_tasks=[task1.task_id, task2.task_id],
                            affected_providers=[provider_id],
                            resource_type=list(shared_resources)[
                                0
                            ],  # Use first shared resource
                            description=f"Deadline conflict between tasks {task1.task_id} and {task2.task_id}",
                            required_resources={
                                task1.task_id: sum(task1.resources.values()),
                                task2.task_id: sum(task2.resources.values()),
                            },
                            metadata={
                                "deadline1": task1.deadline.isoformat(),
                                "deadline2": task2.deadline.isoformat(),
                            },
                        )
                        conflicts.append(conflict)

        return conflicts

    def _has_deadline_conflict(
        self, task1: ResourceAllocation, task2: ResourceAllocation
    ) -> bool:
        """Check if two tasks have conflicting deadlines."""
        if not task1.deadline or not task2.deadline:
            return False

        # Simple heuristic: if deadlines are within 1 hour and tasks compete for resources
        time_diff = abs((task1.deadline - task2.deadline).total_seconds())
        return time_diff < 3600  # 1 hour

    def _detect_cross_provider_conflicts(
        self, allocations: List[ResourceAllocation]
    ) -> List[Conflict]:
        """Detect conflicts across multiple providers."""
        conflicts = []

        # Check for provider overload patterns
        provider_loads = defaultdict(
            lambda: {"count": 0, "total_cost": 0.0, "tasks": []}
        )

        for allocation in allocations:
            provider_loads[allocation.provider_id]["count"] += 1
            provider_loads[allocation.provider_id][
                "total_cost"
            ] += allocation.cost_per_hour
            provider_loads[allocation.provider_id]["tasks"].append(allocation.task_id)

        # Detect overloaded providers
        for provider_id, load_info in provider_loads.items():
            if load_info["count"] > 50:  # Arbitrary threshold
                conflict = Conflict(
                    conflict_id=str(uuid.uuid4()),
                    conflict_type=ConflictType.PROVIDER_OVERLOAD,
                    severity=ConflictSeverity.MEDIUM,
                    affected_tasks=load_info["tasks"],
                    affected_providers=[provider_id],
                    resource_type=ResourceType.CONCURRENT_REQUESTS,
                    description=f"Provider {provider_id} is overloaded with {load_info['count']} tasks",
                    metadata={
                        "task_count": load_info["count"],
                        "total_cost": load_info["total_cost"],
                    },
                )
                conflicts.append(conflict)

        return conflicts

    async def implement_resolution_strategies(
        self, conflicts: List[Conflict]
    ) -> List[Resolution]:
        """Implement resolution strategies for detected conflicts."""
        self.logger.info(
            "Implementing resolution strategies", conflict_count=len(conflicts)
        )

        resolutions = []

        for conflict in conflicts:
            try:
                resolution = await self._resolve_conflict(conflict)
                if resolution:
                    resolutions.append(resolution)
                    await self._execute_resolution(resolution)
            except Exception as e:
                self.logger.error(
                    "Failed to resolve conflict",
                    conflict_id=conflict.conflict_id,
                    error=str(e),
                )

        self.logger.info(
            "Resolution strategies implemented",
            resolutions_created=len(resolutions),
            successful_resolutions=len(
                [r for r in resolutions if r.status == "completed"]
            ),
        )

        return resolutions

    async def _resolve_conflict(self, conflict: Conflict) -> Optional[Resolution]:
        """Resolve a specific conflict."""
        strategy = self._select_resolution_strategy(conflict)
        actions = await self._generate_resolution_actions(conflict, strategy)

        if not actions:
            return None

        resolution = Resolution(
            resolution_id=str(uuid.uuid4()),
            conflict_id=conflict.conflict_id,
            strategy=strategy,
            actions=actions,
            estimated_impact=self._estimate_resolution_impact(conflict, actions),
            confidence_score=self._calculate_resolution_confidence(conflict, strategy),
            implementation_order=self._determine_implementation_order(actions),
            rollback_plan=self._create_rollback_plan(actions),
        )

        return resolution

    def _select_resolution_strategy(self, conflict: Conflict) -> ResolutionStrategy:
        """Select appropriate resolution strategy for conflict."""
        strategy_map = {
            ConflictType.CAPACITY_EXCEEDED: ResolutionStrategy.RESOURCE_SCALING,
            ConflictType.PRIORITY_COLLISION: ResolutionStrategy.PRIORITY_BASED,
            ConflictType.DEADLINE_CONFLICT: ResolutionStrategy.DEADLINE_AWARE,
            ConflictType.RESERVATION_OVERLAP: ResolutionStrategy.QUEUE_MANAGEMENT,
            ConflictType.PROVIDER_OVERLOAD: ResolutionStrategy.LOAD_BALANCING,
            ConflictType.DEPENDENCY_DEADLOCK: ResolutionStrategy.PREEMPTION,
            ConflictType.FAIRNESS_VIOLATION: ResolutionStrategy.FAIR_SHARE,
            ConflictType.COST_CONSTRAINT: ResolutionStrategy.COST_OPTIMIZED,
            ConflictType.QUALITY_DEGRADATION: ResolutionStrategy.RESOURCE_SCALING,
        }

        return strategy_map.get(conflict.conflict_type, ResolutionStrategy.FAIR_SHARE)

    async def _generate_resolution_actions(
        self, conflict: Conflict, strategy: ResolutionStrategy
    ) -> List[Dict[str, Any]]:
        """Generate specific actions for conflict resolution."""
        actions = []

        if strategy == ResolutionStrategy.RESOURCE_SCALING:
            actions.extend(await self._generate_scaling_actions(conflict))
        elif strategy == ResolutionStrategy.PRIORITY_BASED:
            actions.extend(self._generate_priority_actions(conflict))
        elif strategy == ResolutionStrategy.DEADLINE_AWARE:
            actions.extend(self._generate_deadline_actions(conflict))
        elif strategy == ResolutionStrategy.LOAD_BALANCING:
            actions.extend(await self._generate_load_balancing_actions(conflict))
        elif strategy == ResolutionStrategy.PREEMPTION:
            actions.extend(await self._generate_preemption_actions(conflict))
        elif strategy == ResolutionStrategy.QUEUE_MANAGEMENT:
            actions.extend(self._generate_queue_actions(conflict))
        else:
            # Default fair share actions
            actions.extend(self._generate_fair_share_actions(conflict))

        return actions

    async def _generate_scaling_actions(
        self, conflict: Conflict
    ) -> List[Dict[str, Any]]:
        """Generate resource scaling actions."""
        actions = []

        # Calculate how much additional capacity is needed
        additional_capacity = conflict.capacity_shortfall * 1.2  # 20% buffer

        for provider_id in conflict.affected_providers:
            actions.append(
                {
                    "type": "scale_up",
                    "provider_id": provider_id,
                    "resource_type": conflict.resource_type.value,
                    "additional_capacity": additional_capacity,
                    "estimated_cost": additional_capacity * 0.1,  # Cost estimate
                    "estimated_time": 5,  # minutes
                }
            )

        return actions

    def _generate_priority_actions(self, conflict: Conflict) -> List[Dict[str, Any]]:
        """Generate priority-based resolution actions."""
        actions = []

        # Sort affected tasks by priority
        task_priorities = []
        for task_id in conflict.affected_tasks:
            # Find allocation for task (simplified)
            priority = 5  # Default priority
            for allocation in self.resource_allocator._allocations.values():
                if allocation.task_id == task_id:
                    priority = allocation.priority
                    break
            task_priorities.append((priority, task_id))

        task_priorities.sort(reverse=True)  # Highest priority first

        # Give resources to highest priority tasks first
        for i, (priority, task_id) in enumerate(task_priorities):
            if i == 0:
                # Highest priority gets full allocation
                actions.append(
                    {
                        "type": "guarantee_resources",
                        "task_id": task_id,
                        "priority": priority,
                        "resource_percentage": 100,
                    }
                )
            else:
                # Lower priority tasks get reduced allocation
                reduction = min(50, i * 10)  # Reduce by 10% per priority level
                actions.append(
                    {
                        "type": "reduce_allocation",
                        "task_id": task_id,
                        "priority": priority,
                        "reduction_percentage": reduction,
                    }
                )

        return actions

    def _generate_deadline_actions(self, conflict: Conflict) -> List[Dict[str, Any]]:
        """Generate deadline-aware resolution actions."""
        actions = []

        # Sort tasks by deadline urgency
        current_time = datetime.now(timezone.utc)
        task_deadlines = []

        for task_id in conflict.affected_tasks:
            # Find allocation with deadline
            deadline = None
            for allocation in self.resource_allocator._allocations.values():
                if allocation.task_id == task_id and allocation.deadline:
                    deadline = allocation.deadline
                    break

            if deadline:
                urgency = (
                    deadline - current_time
                ).total_seconds() / 3600  # Hours until deadline
                task_deadlines.append((urgency, task_id))

        task_deadlines.sort()  # Most urgent first

        # Prioritize tasks based on deadline urgency
        for i, (urgency, task_id) in enumerate(task_deadlines):
            if urgency < 1:  # Less than 1 hour
                actions.append(
                    {
                        "type": "emergency_priority",
                        "task_id": task_id,
                        "urgency_hours": urgency,
                        "resource_boost": 150,  # 50% more resources
                    }
                )
            elif urgency < 6:  # Less than 6 hours
                actions.append(
                    {
                        "type": "high_priority",
                        "task_id": task_id,
                        "urgency_hours": urgency,
                        "resource_boost": 120,  # 20% more resources
                    }
                )
            else:
                actions.append(
                    {
                        "type": "normal_priority",
                        "task_id": task_id,
                        "urgency_hours": urgency,
                        "resource_boost": 100,  # Normal resources
                    }
                )

        return actions

    async def _generate_load_balancing_actions(
        self, conflict: Conflict
    ) -> List[Dict[str, Any]]:
        """Generate load balancing actions."""
        actions = []

        # Find alternative providers
        current_usage = await self.resource_allocator.monitor_resource_usage()
        available_providers = []

        for provider_id, usage in current_usage.items():
            if provider_id not in conflict.affected_providers:
                if usage.overall_utilization < 70:  # Less than 70% utilized
                    available_providers.append((provider_id, usage.overall_utilization))

        # Sort by utilization (prefer less utilized providers)
        available_providers.sort(key=lambda x: x[1])

        # Migrate some tasks to less utilized providers
        tasks_to_migrate = conflict.affected_tasks[: len(available_providers)]

        for i, task_id in enumerate(tasks_to_migrate):
            if i < len(available_providers):
                target_provider = available_providers[i][0]
                actions.append(
                    {
                        "type": "migrate_task",
                        "task_id": task_id,
                        "source_provider": conflict.affected_providers[0],
                        "target_provider": target_provider,
                        "estimated_time": 10,  # minutes
                    }
                )

        return actions

    async def _generate_preemption_actions(
        self, conflict: Conflict
    ) -> List[Dict[str, Any]]:
        """Generate preemption actions."""
        actions = []

        # Find preemption candidates (low priority tasks)
        preemption_candidates = []

        for allocation in self.resource_allocator._allocations.values():
            if (
                allocation.provider_id in conflict.affected_providers
                and allocation.priority < 5
            ):  # Low priority threshold
                preemption_candidates.append(allocation)

        # Sort by priority (lowest first)
        preemption_candidates.sort(key=lambda a: a.priority)

        # Generate preemption actions
        resources_needed = conflict.capacity_shortfall
        resources_freed = 0.0

        for candidate in preemption_candidates:
            if resources_freed >= resources_needed:
                break

            candidate_resources = sum(candidate.resources.values())

            if candidate.priority <= 3:
                # Very low priority - can be paused
                actions.append(
                    {
                        "type": "preempt_pause",
                        "task_id": candidate.task_id,
                        "priority": candidate.priority,
                        "resources_freed": candidate_resources,
                        "estimated_recovery_time": 60,  # minutes
                    }
                )
            else:
                # Medium priority - reduce allocation
                reduction = min(50, (resources_needed / candidate_resources) * 100)
                actions.append(
                    {
                        "type": "preempt_reduce",
                        "task_id": candidate.task_id,
                        "priority": candidate.priority,
                        "reduction_percentage": reduction,
                        "resources_freed": candidate_resources * (reduction / 100),
                    }
                )

            resources_freed += candidate_resources

        return actions

    def _generate_queue_actions(self, conflict: Conflict) -> List[Dict[str, Any]]:
        """Generate queue management actions."""
        actions = []

        # Create priority queues for affected providers
        for provider_id in conflict.affected_providers:
            queue_id = f"queue_{provider_id}_{conflict.resource_type.value}"

            actions.append(
                {
                    "type": "create_priority_queue",
                    "provider_id": provider_id,
                    "resource_type": conflict.resource_type.value,
                    "queue_id": queue_id,
                    "max_size": 50,
                }
            )

            # Add tasks to queue based on priority
            for task_id in conflict.affected_tasks:
                actions.append(
                    {
                        "type": "enqueue_task",
                        "task_id": task_id,
                        "queue_id": queue_id,
                        "scheduling_policy": "priority_based",
                    }
                )

        return actions

    def _generate_fair_share_actions(self, conflict: Conflict) -> List[Dict[str, Any]]:
        """Generate fair share resolution actions."""
        actions = []

        # Calculate fair share allocation
        num_tasks = len(conflict.affected_tasks)
        if num_tasks > 0:
            fair_share_percentage = 100 / num_tasks

            for task_id in conflict.affected_tasks:
                actions.append(
                    {
                        "type": "set_fair_share",
                        "task_id": task_id,
                        "allocation_percentage": fair_share_percentage,
                        "resource_type": conflict.resource_type.value,
                    }
                )

        return actions

    def _estimate_resolution_impact(
        self, conflict: Conflict, actions: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Estimate impact of resolution actions."""
        impact = {"performance": 0.0, "cost": 0.0, "fairness": 0.0, "stability": 0.0}

        for action in actions:
            action_type = action.get("type", "")

            if "scale_up" in action_type:
                impact["performance"] += 30.0
                impact["cost"] += action.get("estimated_cost", 10.0)
                impact["stability"] += 20.0
            elif "migrate" in action_type:
                impact["performance"] += 10.0
                impact["cost"] += 5.0
                impact["fairness"] += 15.0
            elif "preempt" in action_type:
                impact["performance"] += 20.0
                impact["cost"] -= 5.0  # Negative cost (savings)
                impact["fairness"] -= 10.0  # Reduced fairness
            elif "fair_share" in action_type:
                impact["fairness"] += 25.0
                impact["stability"] += 10.0

        return impact

    def _calculate_resolution_confidence(
        self, conflict: Conflict, strategy: ResolutionStrategy
    ) -> float:
        """Calculate confidence in resolution strategy."""
        base_confidence = 0.7

        # Adjust based on conflict severity
        severity_adjustments = {
            ConflictSeverity.LOW: 0.9,
            ConflictSeverity.MEDIUM: 0.8,
            ConflictSeverity.HIGH: 0.7,
            ConflictSeverity.CRITICAL: 0.6,
            ConflictSeverity.EMERGENCY: 0.5,
        }

        confidence = base_confidence * severity_adjustments.get(conflict.severity, 0.7)

        # Adjust based on number of affected tasks (more tasks = lower confidence)
        task_factor = max(0.5, 1.0 - (len(conflict.affected_tasks) / 20))
        confidence *= task_factor

        return max(0.1, min(1.0, confidence))

    def _determine_implementation_order(
        self, actions: List[Dict[str, Any]]
    ) -> List[str]:
        """Determine optimal order for implementing actions."""
        # Priority order for action types
        priority_order = {
            "scale_up": 1,
            "create_priority_queue": 2,
            "migrate_task": 3,
            "set_fair_share": 4,
            "preempt_pause": 5,
            "preempt_reduce": 6,
        }

        # Sort actions by priority
        sorted_actions = sorted(
            actions, key=lambda a: priority_order.get(a.get("type", ""), 999)
        )

        return [
            action.get("type", f"action_{i}") for i, action in enumerate(sorted_actions)
        ]

    def _create_rollback_plan(
        self, actions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Create rollback plan for resolution actions."""
        rollback_plan = []

        for action in reversed(actions):  # Reverse order for rollback
            action_type = action.get("type", "")

            if action_type == "scale_up":
                rollback_plan.append(
                    {
                        "type": "scale_down",
                        "provider_id": action.get("provider_id"),
                        "resource_type": action.get("resource_type"),
                        "capacity_reduction": action.get("additional_capacity"),
                    }
                )
            elif action_type == "migrate_task":
                rollback_plan.append(
                    {
                        "type": "migrate_back",
                        "task_id": action.get("task_id"),
                        "source_provider": action.get("target_provider"),
                        "target_provider": action.get("source_provider"),
                    }
                )
            elif "preempt" in action_type:
                rollback_plan.append(
                    {
                        "type": "restore_allocation",
                        "task_id": action.get("task_id"),
                        "original_allocation": action.get("original_allocation", {}),
                    }
                )

        return rollback_plan

    async def _execute_resolution(self, resolution: Resolution):
        """Execute a resolution plan."""
        resolution.status = "executing"

        try:
            for i, action_type in enumerate(resolution.implementation_order):
                action = resolution.actions[i] if i < len(resolution.actions) else None
                if action:
                    await self._execute_action(action, resolution)

            resolution.status = "completed"
            self._resolution_stats["completed"] += 1

        except Exception as e:
            resolution.status = "failed"
            resolution.execution_log.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event": "execution_failed",
                    "error": str(e),
                }
            )
            self._resolution_stats["failed"] += 1

            # Execute rollback if possible
            await self._execute_rollback(resolution)

    async def _execute_action(self, action: Dict[str, Any], resolution: Resolution):
        """Execute a single resolution action."""
        action_type = action.get("type", "")

        try:
            if action_type == "scale_up":
                await self._execute_scale_up_action(action)
            elif action_type == "migrate_task":
                await self._execute_migration_action(action)
            elif "preempt" in action_type:
                await self._execute_preemption_action(action)
            elif action_type == "create_priority_queue":
                self._execute_queue_creation_action(action)
            elif action_type == "set_fair_share":
                await self._execute_fair_share_action(action)

            # Log successful execution
            resolution.execution_log.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event": "action_executed",
                    "action_type": action_type,
                    "status": "success",
                }
            )

        except Exception as e:
            resolution.execution_log.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event": "action_failed",
                    "action_type": action_type,
                    "error": str(e),
                }
            )
            raise

    async def _execute_scale_up_action(self, action: Dict[str, Any]):
        """Execute resource scaling action."""
        # This would integrate with actual infrastructure scaling
        self.logger.info(
            "Executing scale up action",
            provider_id=action.get("provider_id"),
            resource_type=action.get("resource_type"),
            additional_capacity=action.get("additional_capacity"),
        )

        # Simulate scaling delay
        await asyncio.sleep(0.1)

    async def _execute_migration_action(self, action: Dict[str, Any]):
        """Execute task migration action."""
        task_id = action.get("task_id")
        source_provider = action.get("source_provider")
        target_provider = action.get("target_provider")

        self.logger.info(
            "Executing migration action",
            task_id=task_id,
            source_provider=source_provider,
            target_provider=target_provider,
        )

        # Update allocation provider
        for allocation in self.resource_allocator._allocations.values():
            if allocation.task_id == task_id:
                allocation.provider_id = target_provider
                allocation.metadata["migrated_from"] = source_provider
                allocation.metadata["migration_time"] = datetime.now(
                    timezone.utc
                ).isoformat()
                break

        await asyncio.sleep(0.1)

    async def _execute_preemption_action(self, action: Dict[str, Any]):
        """Execute preemption action."""
        task_id = action.get("task_id")

        self.logger.info(
            "Executing preemption action",
            task_id=task_id,
            action_type=action.get("type"),
        )

        # Update allocation status
        for allocation in self.resource_allocator._allocations.values():
            if allocation.task_id == task_id:
                if "pause" in action.get("type", ""):
                    allocation.status = ResourceStatus.RESERVED
                elif "reduce" in action.get("type", ""):
                    # Reduce resource allocation
                    reduction = action.get("reduction_percentage", 0) / 100
                    for resource_type in allocation.resources:
                        allocation.resources[resource_type] *= 1 - reduction
                break

        await asyncio.sleep(0.1)

    def _execute_queue_creation_action(self, action: Dict[str, Any]):
        """Execute priority queue creation."""
        queue_id = action.get("queue_id")
        provider_id = action.get("provider_id")
        resource_type_str = action.get("resource_type")

        try:
            resource_type = ResourceType(resource_type_str)
            queue = PriorityQueue(
                queue_id=queue_id,
                resource_type=resource_type,
                provider_id=provider_id,
                tasks=[],
                max_size=action.get("max_size", 100),
            )
            self._priority_queues[queue_id] = queue

            self.logger.info(
                "Priority queue created",
                queue_id=queue_id,
                provider_id=provider_id,
                resource_type=resource_type_str,
            )
        except ValueError as e:
            self.logger.error(
                "Invalid resource type for queue",
                resource_type=resource_type_str,
                error=str(e),
            )

    async def _execute_fair_share_action(self, action: Dict[str, Any]):
        """Execute fair share allocation."""
        task_id = action.get("task_id")
        allocation_percentage = action.get("allocation_percentage", 100)

        self.logger.info(
            "Executing fair share action",
            task_id=task_id,
            allocation_percentage=allocation_percentage,
        )

        # Update allocation
        for allocation in self.resource_allocator._allocations.values():
            if allocation.task_id == task_id:
                factor = allocation_percentage / 100
                for resource_type in allocation.resources:
                    allocation.resources[resource_type] *= factor
                allocation.metadata["fair_share_applied"] = True
                break

        await asyncio.sleep(0.1)

    async def _execute_rollback(self, resolution: Resolution):
        """Execute rollback plan for failed resolution."""
        self.logger.warning(
            "Executing rollback plan", resolution_id=resolution.resolution_id
        )

        try:
            for rollback_action in resolution.rollback_plan:
                await self._execute_action(rollback_action, resolution)

            resolution.execution_log.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event": "rollback_completed",
                    "status": "success",
                }
            )

        except Exception as e:
            resolution.execution_log.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event": "rollback_failed",
                    "error": str(e),
                }
            )

    async def manage_priority_queues(
        self, tasks: List[ResourceAllocation]
    ) -> Dict[str, PriorityQueue]:
        """Manage priority queues for resource allocation."""
        self.logger.info("Managing priority queues", task_count=len(tasks))

        # Group tasks by provider and resource type
        provider_resource_tasks = defaultdict(lambda: defaultdict(list))

        for task in tasks:
            for resource_type in task.resources:
                provider_resource_tasks[task.provider_id][resource_type].append(task)

        # Create or update queues
        for provider_id, resource_tasks in provider_resource_tasks.items():
            for resource_type, task_list in resource_tasks.items():
                queue_id = f"queue_{provider_id}_{resource_type.value}"

                if queue_id not in self._priority_queues:
                    # Create new queue
                    self._priority_queues[queue_id] = PriorityQueue(
                        queue_id=queue_id,
                        resource_type=resource_type,
                        provider_id=provider_id,
                        tasks=[],
                    )

                queue = self._priority_queues[queue_id]

                # Add tasks to queue
                for task in task_list:
                    queue.push(task.priority, task.task_id, task)

        return self._priority_queues

    async def coordinate_resource_reservation(
        self,
        task_id: str,
        provider_id: str,
        resources: Dict[ResourceType, float],
        duration_minutes: int = 60,
    ) -> ReservationResult:
        """Coordinate resource reservation for a task."""
        reservation_id = str(uuid.uuid4())
        reserved_until = datetime.now(timezone.utc) + timedelta(
            minutes=duration_minutes
        )

        self.logger.info(
            "Coordinating resource reservation",
            reservation_id=reservation_id,
            task_id=task_id,
            provider_id=provider_id,
            duration_minutes=duration_minutes,
        )

        try:
            # Check resource availability
            current_usage = (
                await self.resource_allocator.monitor.collect_system_metrics(
                    provider_id
                )
            )

            # Verify capacity
            can_reserve = True
            failure_reason = None

            for resource_type, amount in resources.items():
                if resource_type in current_usage.metrics:
                    available = current_usage.metrics[resource_type].available
                    if amount > available:
                        can_reserve = False
                        failure_reason = f"Insufficient {resource_type.value}: need {amount}, available {available}"
                        break

            if can_reserve:
                # Create reservation
                reservation = ReservationResult(
                    reservation_id=reservation_id,
                    task_id=task_id,
                    provider_id=provider_id,
                    resources=resources,
                    reserved_until=reserved_until,
                    success=True,
                )

                self._reservations[reservation_id] = reservation

                self.logger.info(
                    "Resource reservation successful",
                    reservation_id=reservation_id,
                    reserved_until=reserved_until.isoformat(),
                )

            else:
                # Find alternative providers
                alternative_providers = await self._find_alternative_providers(
                    resources
                )

                reservation = ReservationResult(
                    reservation_id=reservation_id,
                    task_id=task_id,
                    provider_id=provider_id,
                    resources=resources,
                    reserved_until=reserved_until,
                    success=False,
                    failure_reason=failure_reason,
                    alternative_providers=alternative_providers,
                )

                self.logger.warning(
                    "Resource reservation failed",
                    reservation_id=reservation_id,
                    reason=failure_reason,
                    alternatives=len(alternative_providers),
                )

            return reservation

        except Exception as e:
            self.logger.error(
                "Resource reservation error",
                reservation_id=reservation_id,
                error=str(e),
            )

            return ReservationResult(
                reservation_id=reservation_id,
                task_id=task_id,
                provider_id=provider_id,
                resources=resources,
                reserved_until=reserved_until,
                success=False,
                failure_reason=f"Reservation error: {str(e)}",
            )

    async def _find_alternative_providers(
        self, resources: Dict[ResourceType, float]
    ) -> List[str]:
        """Find alternative providers that can satisfy resource requirements."""
        alternatives = []

        try:
            current_usage = await self.resource_allocator.monitor_resource_usage()

            for provider_id, usage in current_usage.items():
                can_satisfy = True

                for resource_type, amount in resources.items():
                    if resource_type in usage.metrics:
                        available = usage.metrics[resource_type].available
                        if amount > available:
                            can_satisfy = False
                            break

                if can_satisfy:
                    alternatives.append(provider_id)

        except Exception as e:
            self.logger.error("Error finding alternative providers", error=str(e))

        return alternatives

    async def handle_resource_preemption(
        self, high_priority_task: ResourceAllocation
    ) -> PreemptionResult:
        """Handle resource preemption for high-priority task."""
        preemption_id = str(uuid.uuid4())

        self.logger.info(
            "Handling resource preemption",
            preemption_id=preemption_id,
            high_priority_task=high_priority_task.task_id,
            priority=high_priority_task.priority,
        )

        # Check preemption policies
        if (
            high_priority_task.priority
            < self._preemption_policies["priority_threshold"]
        ):
            return PreemptionResult(
                preemption_id=preemption_id,
                preempted_task_id="",
                beneficiary_task_id=high_priority_task.task_id,
                preemption_type=PreemptionType.NONE,
                resources_freed={},
                estimated_recovery_time=0,
                compensation_cost=0.0,
                success=False,
            )

        # Find preemption candidate
        candidate = self._find_preemption_candidate(high_priority_task)

        if not candidate:
            return PreemptionResult(
                preemption_id=preemption_id,
                preempted_task_id="",
                beneficiary_task_id=high_priority_task.task_id,
                preemption_type=PreemptionType.NONE,
                resources_freed={},
                estimated_recovery_time=0,
                compensation_cost=0.0,
                success=False,
            )

        # Determine preemption type
        preemption_type = self._determine_preemption_type(candidate, high_priority_task)

        # Execute preemption
        success = await self._execute_preemption(
            candidate, high_priority_task, preemption_type
        )

        # Calculate resources freed
        resources_freed = candidate.resources.copy()

        # Calculate compensation cost
        compensation_cost = candidate.cost_per_hour * 0.5  # 50% compensation

        result = PreemptionResult(
            preemption_id=preemption_id,
            preempted_task_id=candidate.task_id,
            beneficiary_task_id=high_priority_task.task_id,
            preemption_type=preemption_type,
            resources_freed=resources_freed,
            estimated_recovery_time=(
                30 if preemption_type == PreemptionType.PAUSE else 60
            ),
            compensation_cost=compensation_cost,
            success=success,
        )

        self.logger.info(
            "Resource preemption completed",
            preemption_id=preemption_id,
            success=success,
            preemption_type=preemption_type.value,
        )

        return result

    def _find_preemption_candidate(
        self, high_priority_task: ResourceAllocation
    ) -> Optional[ResourceAllocation]:
        """Find suitable candidate for preemption."""
        candidates = []

        # Find tasks on same provider with lower priority
        for allocation in self.resource_allocator._allocations.values():
            if (
                allocation.provider_id == high_priority_task.provider_id
                and allocation.priority < high_priority_task.priority
                and allocation.status == ResourceStatus.ALLOCATED
            ):
                candidates.append(allocation)

        if not candidates:
            return None

        # Sort by priority (lowest first)
        candidates.sort(key=lambda a: a.priority)

        return candidates[0]

    def _determine_preemption_type(
        self, candidate: ResourceAllocation, high_priority_task: ResourceAllocation
    ) -> PreemptionType:
        """Determine appropriate preemption type."""
        if candidate.priority <= 2:
            return PreemptionType.PAUSE
        elif candidate.priority <= 4:
            return PreemptionType.RESCALE
        else:
            return PreemptionType.MIGRATE

    async def _execute_preemption(
        self,
        candidate: ResourceAllocation,
        high_priority_task: ResourceAllocation,
        preemption_type: PreemptionType,
    ) -> bool:
        """Execute the preemption action."""
        try:
            if preemption_type == PreemptionType.PAUSE:
                candidate.status = ResourceStatus.RESERVED
                candidate.metadata["preempted_by"] = high_priority_task.task_id
                candidate.metadata["preempted_at"] = datetime.now(
                    timezone.utc
                ).isoformat()

            elif preemption_type == PreemptionType.RESCALE:
                # Reduce resources by 50%
                for resource_type in candidate.resources:
                    candidate.resources[resource_type] *= 0.5
                candidate.metadata["rescaled_due_to_preemption"] = True

            elif preemption_type == PreemptionType.MIGRATE:
                # Find alternative provider
                alternatives = await self._find_alternative_providers(
                    candidate.resources
                )
                if alternatives:
                    candidate.provider_id = alternatives[0]
                    candidate.metadata["migrated_due_to_preemption"] = True
                else:
                    # No alternatives, pause instead
                    candidate.status = ResourceStatus.RESERVED

            return True

        except Exception as e:
            self.logger.error("Preemption execution failed", error=str(e))
            return False

    def get_conflict_statistics(self) -> Dict[str, Any]:
        """Get conflict resolution statistics."""
        current_time = datetime.now(timezone.utc)
        recent_conflicts = [
            c
            for c in self._conflict_history
            if (current_time - c.detected_at).total_seconds() < 3600  # Last hour
        ]

        conflict_types = defaultdict(int)
        severity_counts = defaultdict(int)

        for conflict in recent_conflicts:
            conflict_types[conflict.conflict_type.value] += 1
            severity_counts[conflict.severity.value] += 1

        return {
            "total_conflicts": len(self._conflict_history),
            "active_conflicts": len(self._active_conflicts),
            "recent_conflicts": len(recent_conflicts),
            "conflict_types": dict(conflict_types),
            "severity_distribution": dict(severity_counts),
            "resolution_stats": dict(self._resolution_stats),
            "priority_queues": len(self._priority_queues),
            "active_reservations": len(self._reservations),
        }
