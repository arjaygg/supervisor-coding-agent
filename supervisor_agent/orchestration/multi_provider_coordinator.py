"""
Multi-Provider Coordination System
Coordinates execution across multiple AI providers with load balancing and failover.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import structlog
from collections import defaultdict

from supervisor_agent.providers.base_provider import (
    AIProvider,
    ProviderType,
    TaskCapability,
)
from supervisor_agent.core.multi_provider_service import MultiProviderService
from supervisor_agent.orchestration.agent_specialization_engine import (
    AgentSpecializationEngine,
    AgentSpecialty,
)


logger = structlog.get_logger(__name__)


class CoordinationStrategy(Enum):
    """Coordination strategies for multi-provider execution."""

    ROUND_ROBIN = "round_robin"
    LOAD_BALANCED = "load_balanced"
    CAPABILITY_BASED = "capability_based"
    FAILOVER_CHAIN = "failover_chain"
    PARALLEL_EXECUTION = "parallel_execution"
    COST_OPTIMIZED = "cost_optimized"


# Alias for backward compatibility
ProviderOrchestrationStrategy = CoordinationStrategy


class ProviderStatus(Enum):
    """Provider status tracking."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    OVERLOADED = "overloaded"


@dataclass
class ProviderMetrics:
    """Metrics for provider performance tracking."""

    provider_type: ProviderType
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    current_load: int = 0
    max_capacity: int = 100
    cost_per_request: float = 0.0
    last_health_check: Optional[datetime] = None
    status: ProviderStatus = ProviderStatus.HEALTHY

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    @property
    def load_percentage(self) -> float:
        """Calculate current load percentage."""
        return (self.current_load / self.max_capacity) * 100

    @property
    def availability_score(self) -> float:
        """Calculate availability score based on multiple factors."""
        if self.status == ProviderStatus.UNAVAILABLE:
            return 0.0

        base_score = 1.0

        # Factor in success rate
        base_score *= self.success_rate

        # Factor in load (lower load = higher score)
        load_factor = max(0, 1 - (self.load_percentage / 100))
        base_score *= 0.7 + 0.3 * load_factor

        # Factor in status
        if self.status == ProviderStatus.DEGRADED:
            base_score *= 0.7
        elif self.status == ProviderStatus.OVERLOADED:
            base_score *= 0.3

        return base_score


@dataclass
class CoordinationTask:
    """Task for multi-provider coordination."""

    task_id: str
    task_type: TaskCapability
    specialty_required: Optional[AgentSpecialty] = None
    priority: int = 5
    timeout_seconds: int = 300
    retry_count: int = 0
    max_retries: int = 3
    cost_limit: Optional[float] = None
    preferred_providers: List[ProviderType] = field(default_factory=list)
    excluded_providers: List[ProviderType] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Result of coordinated execution."""

    task_id: str
    success: bool
    provider_used: ProviderType
    execution_time: float
    cost: float
    result_data: Optional[Any] = None
    error_message: Optional[str] = None
    retry_attempts: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


# Alias for backward compatibility
CoordinationResult = ExecutionResult


class MultiProviderCoordinator:
    """
    Coordinates execution across multiple AI providers with intelligent
    load balancing, failover, and optimization strategies.
    """

    def __init__(
        self,
        provider_service: MultiProviderService,
        specialization_engine: Optional[AgentSpecializationEngine] = None,
        default_strategy: CoordinationStrategy = CoordinationStrategy.CAPABILITY_BASED,
    ):
        self.provider_service = provider_service
        self.specialization_engine = specialization_engine
        self.default_strategy = default_strategy

        # Provider metrics tracking
        self.provider_metrics: Dict[ProviderType, ProviderMetrics] = {}

        # Task queue and execution tracking
        self.task_queue: List[CoordinationTask] = []
        self.executing_tasks: Dict[str, CoordinationTask] = {}
        self.execution_history: List[ExecutionResult] = []

        # Coordination state
        self.round_robin_index = 0
        self.provider_locks: Dict[ProviderType, asyncio.Lock] = {}

        # Initialize metrics for available providers
        self._initialize_provider_metrics()

        self.logger = logger.bind(component="multi_provider_coordinator")

    def _initialize_provider_metrics(self):
        """Initialize metrics for all available providers."""
        for provider_type in ProviderType:
            self.provider_metrics[provider_type] = ProviderMetrics(
                provider_type=provider_type,
                max_capacity=self._get_provider_capacity(provider_type),
            )
            self.provider_locks[provider_type] = asyncio.Lock()

    def _get_provider_capacity(self, provider_type: ProviderType) -> int:
        """Get estimated capacity for a provider type."""
        capacity_map = {
            ProviderType.CLAUDE_CLI: 50,
            ProviderType.ANTHROPIC_API: 100,
            ProviderType.OPENAI: 80,
            ProviderType.LOCAL_MOCK: 1000,
            ProviderType.CUSTOM: 50,
        }
        return capacity_map.get(provider_type, 50)

    async def coordinate_task(
        self, task: CoordinationTask, strategy: Optional[CoordinationStrategy] = None
    ) -> ExecutionResult:
        """
        Coordinate execution of a task across providers.

        Args:
            task: Task to coordinate
            strategy: Coordination strategy to use

        Returns:
            ExecutionResult with execution details
        """
        strategy = strategy or self.default_strategy

        self.logger.info(
            "Coordinating task execution",
            task_id=task.task_id,
            strategy=strategy.value,
            task_type=task.task_type.value,
        )

        # Add task to execution tracking
        self.executing_tasks[task.task_id] = task

        try:
            # Select provider(s) based on strategy
            providers = await self._select_providers(task, strategy)

            if not providers:
                return ExecutionResult(
                    task_id=task.task_id,
                    success=False,
                    provider_used=ProviderType.LOCAL_MOCK,
                    execution_time=0.0,
                    cost=0.0,
                    error_message="No suitable providers available",
                )

            # Execute based on strategy
            if strategy == CoordinationStrategy.PARALLEL_EXECUTION:
                result = await self._execute_parallel(task, providers)
            elif strategy == CoordinationStrategy.FAILOVER_CHAIN:
                result = await self._execute_with_failover(task, providers)
            else:
                # Single provider execution
                result = await self._execute_single(task, providers[0])

            # Update metrics
            self._update_provider_metrics(result)

            # Store execution history
            self.execution_history.append(result)

            return result

        except Exception as e:
            self.logger.error(
                "Task coordination failed",
                task_id=task.task_id,
                error=str(e),
                exc_info=True,
            )

            return ExecutionResult(
                task_id=task.task_id,
                success=False,
                provider_used=ProviderType.LOCAL_MOCK,
                execution_time=0.0,
                cost=0.0,
                error_message=f"Coordination failed: {str(e)}",
            )

        finally:
            # Clean up execution tracking
            self.executing_tasks.pop(task.task_id, None)

    async def _select_providers(
        self, task: CoordinationTask, strategy: CoordinationStrategy
    ) -> List[ProviderType]:
        """Select providers based on coordination strategy."""
        available_providers = await self._get_available_providers(task)

        if not available_providers:
            return []

        if strategy == CoordinationStrategy.ROUND_ROBIN:
            return [self._select_round_robin(available_providers)]

        elif strategy == CoordinationStrategy.LOAD_BALANCED:
            return [self._select_load_balanced(available_providers)]

        elif strategy == CoordinationStrategy.CAPABILITY_BASED:
            return [await self._select_capability_based(task, available_providers)]

        elif strategy == CoordinationStrategy.COST_OPTIMIZED:
            return [self._select_cost_optimized(available_providers)]

        elif strategy == CoordinationStrategy.FAILOVER_CHAIN:
            return self._order_failover_chain(available_providers)

        elif strategy == CoordinationStrategy.PARALLEL_EXECUTION:
            return available_providers[:3]  # Limit parallel execution

        else:
            return [available_providers[0]]

    async def _get_available_providers(
        self, task: CoordinationTask
    ) -> List[ProviderType]:
        """Get available providers for a task."""
        available = []

        for provider_type in ProviderType:
            # Skip excluded providers
            if provider_type in task.excluded_providers:
                continue

            # Check if provider is available
            if not await self._is_provider_available(provider_type):
                continue

            # Check if provider supports task type
            if not await self._supports_task_type(provider_type, task.task_type):
                continue

            available.append(provider_type)

        # Prioritize preferred providers
        if task.preferred_providers:
            preferred = [p for p in task.preferred_providers if p in available]
            other = [p for p in available if p not in task.preferred_providers]
            available = preferred + other

        return available

    async def _is_provider_available(self, provider_type: ProviderType) -> bool:
        """Check if a provider is available."""
        metrics = self.provider_metrics.get(provider_type)
        if not metrics:
            return False

        return metrics.status in [ProviderStatus.HEALTHY, ProviderStatus.DEGRADED]

    async def _supports_task_type(
        self, provider_type: ProviderType, task_type: TaskCapability
    ) -> bool:
        """Check if provider supports task type."""
        # For now, assume all providers support all task types
        # In a real implementation, this would check provider capabilities
        return True

    def _select_round_robin(self, providers: List[ProviderType]) -> ProviderType:
        """Select provider using round-robin strategy."""
        if not providers:
            return ProviderType.LOCAL_MOCK

        provider = providers[self.round_robin_index % len(providers)]
        self.round_robin_index += 1
        return provider

    def _select_load_balanced(self, providers: List[ProviderType]) -> ProviderType:
        """Select provider with lowest load."""
        if not providers:
            return ProviderType.LOCAL_MOCK

        best_provider = providers[0]
        best_score = float("inf")

        for provider in providers:
            metrics = self.provider_metrics.get(provider)
            if metrics:
                score = metrics.load_percentage
                if score < best_score:
                    best_score = score
                    best_provider = provider

        return best_provider

    async def _select_capability_based(
        self, task: CoordinationTask, providers: List[ProviderType]
    ) -> ProviderType:
        """Select provider based on capabilities and specialization."""
        if not providers:
            return ProviderType.LOCAL_MOCK

        # Use specialization engine if available
        if self.specialization_engine and task.specialty_required:
            recommended = await self.specialization_engine.select_best_agent(
                task_type=task.task_type,
                specialty=task.specialty_required,
                available_providers=providers,
            )
            if recommended:
                return recommended

        # Fall back to availability scoring
        best_provider = providers[0]
        best_score = 0.0

        for provider in providers:
            metrics = self.provider_metrics.get(provider)
            if metrics:
                score = metrics.availability_score
                if score > best_score:
                    best_score = score
                    best_provider = provider

        return best_provider

    def _select_cost_optimized(self, providers: List[ProviderType]) -> ProviderType:
        """Select provider with lowest cost."""
        if not providers:
            return ProviderType.LOCAL_MOCK

        best_provider = providers[0]
        best_cost = float("inf")

        for provider in providers:
            metrics = self.provider_metrics.get(provider)
            if metrics and metrics.cost_per_request < best_cost:
                best_cost = metrics.cost_per_request
                best_provider = provider

        return best_provider

    def _order_failover_chain(
        self, providers: List[ProviderType]
    ) -> List[ProviderType]:
        """Order providers for failover chain."""
        # Sort by availability score descending
        return sorted(
            providers,
            key=lambda p: self.provider_metrics.get(
                p, ProviderMetrics(p)
            ).availability_score,
            reverse=True,
        )

    async def _execute_single(
        self, task: CoordinationTask, provider_type: ProviderType
    ) -> ExecutionResult:
        """Execute task on a single provider."""
        start_time = datetime.now()

        try:
            # Get provider instance
            provider = await self.provider_service.get_provider(provider_type)
            if not provider:
                raise Exception(f"Provider {provider_type} not available")

            # Acquire provider lock
            async with self.provider_locks[provider_type]:
                # Update current load
                metrics = self.provider_metrics[provider_type]
                metrics.current_load += 1

                try:
                    # Execute task (mock implementation)
                    result_data = await self._execute_on_provider(provider, task)

                    execution_time = (datetime.now() - start_time).total_seconds()

                    return ExecutionResult(
                        task_id=task.task_id,
                        success=True,
                        provider_used=provider_type,
                        execution_time=execution_time,
                        cost=self._calculate_cost(provider_type, execution_time),
                        result_data=result_data,
                    )

                finally:
                    # Release load
                    metrics.current_load = max(0, metrics.current_load - 1)

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()

            return ExecutionResult(
                task_id=task.task_id,
                success=False,
                provider_used=provider_type,
                execution_time=execution_time,
                cost=0.0,
                error_message=str(e),
            )

    async def _execute_with_failover(
        self, task: CoordinationTask, providers: List[ProviderType]
    ) -> ExecutionResult:
        """Execute task with failover chain."""
        last_error = None

        for provider_type in providers:
            try:
                result = await self._execute_single(task, provider_type)
                if result.success:
                    return result
                last_error = result.error_message

            except Exception as e:
                last_error = str(e)
                continue

        # All providers failed
        return ExecutionResult(
            task_id=task.task_id,
            success=False,
            provider_used=providers[0] if providers else ProviderType.LOCAL_MOCK,
            execution_time=0.0,
            cost=0.0,
            error_message=f"All providers failed. Last error: {last_error}",
        )

    async def _execute_parallel(
        self, task: CoordinationTask, providers: List[ProviderType]
    ) -> ExecutionResult:
        """Execute task in parallel on multiple providers."""
        # Create tasks for parallel execution
        tasks = [self._execute_single(task, provider) for provider in providers]

        # Wait for first successful result
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Find first successful result
            for result in results:
                if isinstance(result, ExecutionResult) and result.success:
                    # Cancel remaining tasks if needed
                    return result

            # All failed, return first result
            for result in results:
                if isinstance(result, ExecutionResult):
                    return result

            # Fallback
            return ExecutionResult(
                task_id=task.task_id,
                success=False,
                provider_used=providers[0] if providers else ProviderType.LOCAL_MOCK,
                execution_time=0.0,
                cost=0.0,
                error_message="Parallel execution failed",
            )

        except Exception as e:
            return ExecutionResult(
                task_id=task.task_id,
                success=False,
                provider_used=providers[0] if providers else ProviderType.LOCAL_MOCK,
                execution_time=0.0,
                cost=0.0,
                error_message=f"Parallel execution error: {str(e)}",
            )

    async def _execute_on_provider(
        self, provider: AIProvider, task: CoordinationTask
    ) -> Any:
        """Execute task on a specific provider (mock implementation)."""
        # Mock implementation - in real system would call provider's execute method
        await asyncio.sleep(0.1)  # Simulate execution time

        return {
            "task_id": task.task_id,
            "task_type": task.task_type.value,
            "result": "Task completed successfully",
            "provider": provider.provider_type.value,
        }

    def _calculate_cost(
        self, provider_type: ProviderType, execution_time: float
    ) -> float:
        """Calculate cost for task execution."""
        # Mock cost calculation - in real system would be more sophisticated
        base_costs = {
            ProviderType.CLAUDE_CLI: 0.01,
            ProviderType.ANTHROPIC_API: 0.02,
            ProviderType.OPENAI: 0.015,
            ProviderType.LOCAL_MOCK: 0.0,
            ProviderType.CUSTOM: 0.01,
        }

        base_cost = base_costs.get(provider_type, 0.01)
        return base_cost * (1 + execution_time * 0.1)

    def _update_provider_metrics(self, result: ExecutionResult):
        """Update provider metrics based on execution result."""
        metrics = self.provider_metrics.get(result.provider_used)
        if not metrics:
            return

        metrics.total_requests += 1

        if result.success:
            metrics.successful_requests += 1
        else:
            metrics.failed_requests += 1

        # Update average response time
        if metrics.total_requests == 1:
            metrics.avg_response_time = result.execution_time
        else:
            metrics.avg_response_time = (
                metrics.avg_response_time * (metrics.total_requests - 1)
                + result.execution_time
            ) / metrics.total_requests

        # Update cost per request
        if result.cost > 0:
            if metrics.total_requests == 1:
                metrics.cost_per_request = result.cost
            else:
                metrics.cost_per_request = (
                    metrics.cost_per_request * (metrics.total_requests - 1)
                    + result.cost
                ) / metrics.total_requests

        # Update health check
        metrics.last_health_check = datetime.now()

        # Update status based on success rate
        if metrics.success_rate < 0.5:
            metrics.status = ProviderStatus.DEGRADED
        elif metrics.success_rate < 0.8:
            metrics.status = ProviderStatus.DEGRADED
        else:
            metrics.status = ProviderStatus.HEALTHY

    def get_provider_metrics(self) -> Dict[ProviderType, ProviderMetrics]:
        """Get current provider metrics."""
        return self.provider_metrics.copy()

    def get_coordination_stats(self) -> Dict[str, Any]:
        """Get coordination statistics."""
        total_executions = len(self.execution_history)
        successful_executions = sum(1 for r in self.execution_history if r.success)

        provider_usage = defaultdict(int)
        for result in self.execution_history:
            provider_usage[result.provider_used] += 1

        return {
            "total_coordinated_tasks": total_executions,
            "successful_tasks": successful_executions,
            "success_rate": (
                successful_executions / total_executions if total_executions > 0 else 0
            ),
            "provider_usage": dict(provider_usage),
            "average_execution_time": (
                sum(r.execution_time for r in self.execution_history) / total_executions
                if total_executions > 0
                else 0
            ),
            "total_cost": sum(r.cost for r in self.execution_history),
            "currently_executing": len(self.executing_tasks),
        }


def create_multi_provider_coordinator(
    provider_service: MultiProviderService,
    specialization_engine: Optional[AgentSpecializationEngine] = None,
    default_strategy: CoordinationStrategy = CoordinationStrategy.CAPABILITY_BASED,
) -> MultiProviderCoordinator:
    """
    Factory function to create a MultiProviderCoordinator instance.

    Args:
        provider_service: Multi-provider service instance
        specialization_engine: Optional specialization engine
        default_strategy: Default coordination strategy

    Returns:
        Configured MultiProviderCoordinator instance
    """
    return MultiProviderCoordinator(
        provider_service=provider_service,
        specialization_engine=specialization_engine,
        default_strategy=default_strategy,
    )
