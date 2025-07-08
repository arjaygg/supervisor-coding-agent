"""
Provider Coordinator - Intelligent Provider Selection Engine

This module implements the core logic for selecting optimal providers for task execution
based on provider capabilities, health, load, and cost considerations.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from supervisor_agent.db.models import Provider, ProviderUsage, Task
from supervisor_agent.providers.base_provider import (
    AIProvider,
    CostEstimate,
    ProviderCapabilities,
    ProviderError,
    ProviderHealth,
    ProviderResponse,
)

# Import CRUD classes lazily to avoid circular imports
# from supervisor_agent.db.crud import ProviderCRUD, ProviderUsageCRUD, TaskCRUD
from supervisor_agent.providers.provider_registry import (
    LoadBalancingStrategy,
    ProviderRegistry,
)

logger = logging.getLogger(__name__)


class TaskAffinityStrategy(str, Enum):
    """Task affinity strategies for provider selection"""

    NONE = "none"  # No affinity preference
    PROVIDER_STICKY = "provider_sticky"  # Prefer same provider for related tasks
    CAPABILITY_BASED = "capability_based"  # Group by task capabilities
    COST_OPTIMIZED = "cost_optimized"  # Balance between affinity and cost


class ExecutionContext:
    """Context information for task execution"""

    def __init__(
        self,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        priority: int = 5,
        max_cost_usd: Optional[float] = None,
        preferred_providers: Optional[List[str]] = None,
        exclude_providers: Optional[List[str]] = None,
        require_capabilities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.user_id = user_id
        self.organization_id = organization_id
        self.priority = priority
        self.max_cost_usd = max_cost_usd
        self.preferred_providers = preferred_providers or []
        self.exclude_providers = exclude_providers or []
        self.require_capabilities = require_capabilities or []
        self.metadata = metadata or {}
        self.created_at = datetime.now(timezone.utc)


class TaskAffinityTracker:
    """Tracks task relationships and provider affinity for intelligent routing"""

    def __init__(self):
        self.task_relationships: Dict[str, List[str]] = (
            {}
        )  # task_id -> related_task_ids
        self.provider_assignments: Dict[str, str] = {}  # task_id -> provider_id
        self.provider_performance: Dict[str, List[float]] = (
            {}
        )  # provider_id -> success_rates
        self._cleanup_interval = timedelta(hours=24)

    def record_assignment(self, task: Task, provider_id: str) -> None:
        """Record a task-to-provider assignment"""
        task_key = f"{task.id}"
        self.provider_assignments[task_key] = provider_id
        logger.debug(f"Recorded assignment: Task {task.id} -> Provider {provider_id}")

    def record_performance(
        self, provider_id: str, success: bool, execution_time: float
    ) -> None:
        """Record provider performance metrics"""
        if provider_id not in self.provider_performance:
            self.provider_performance[provider_id] = []

        # Simple success rate calculation (1.0 for success, 0.0 for failure)
        score = 1.0 if success else 0.0

        # Factor in execution time (faster is better)
        if execution_time > 0:
            # Normalize execution time to 0-1 range (assuming 60s is max acceptable)
            time_factor = max(0.0, 1.0 - (execution_time / 60.0))
            score *= time_factor

        self.provider_performance[provider_id].append(score)

        # Keep only recent performance data (last 100 executions)
        if len(self.provider_performance[provider_id]) > 100:
            self.provider_performance[provider_id] = self.provider_performance[
                provider_id
            ][-100:]

    def get_provider_score(self, provider_id: str) -> float:
        """Get aggregated performance score for a provider"""
        if provider_id not in self.provider_performance:
            return 0.5  # Neutral score for new providers

        scores = self.provider_performance[provider_id]
        if not scores:
            return 0.5

        # Weighted average with more weight on recent performance
        weights = [i + 1 for i in range(len(scores))]  # Linear weighting
        weighted_sum = sum(score * weight for score, weight in zip(scores, weights))
        weight_sum = sum(weights)

        return weighted_sum / weight_sum if weight_sum > 0 else 0.5

    def find_related_provider(self, task: Task) -> Optional[str]:
        """Find provider used for related tasks"""
        # Simple heuristic: tasks from same user/org are related
        if hasattr(task.payload, "user_id"):
            user_id = task.payload.get("user_id")
            if user_id:
                # Find recent tasks from same user
                for task_key, provider_id in self.provider_assignments.items():
                    # In a real implementation, you'd query the database
                    # For now, return the most recent assignment
                    return provider_id

        return None


class ProviderCoordinator:
    """Coordinates provider selection and task routing"""

    def __init__(
        self,
        registry: ProviderRegistry,
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.CAPABILITY_BASED,
        affinity_strategy: TaskAffinityStrategy = TaskAffinityStrategy.CAPABILITY_BASED,
    ):
        self.registry = registry
        self.strategy = strategy
        self.affinity_strategy = affinity_strategy
        self.task_affinity_tracker = TaskAffinityTracker()
        self._provider_cache: Dict[str, Tuple[datetime, Dict]] = {}
        self._cache_ttl = timedelta(minutes=5)

        logger.info(
            f"Provider Coordinator initialized with strategy: {strategy}, affinity: {affinity_strategy}"
        )

    async def select_provider(self, task: Task, context: ExecutionContext) -> str:
        """
        Select the optimal provider for a given task and context

        Returns:
            Provider ID of the selected provider

        Raises:
            ProviderError: If no suitable provider is available
        """
        try:
            logger.info(f"Selecting provider for task {task.id} (type: {task.type})")

            # Step 1: Apply context filters (preferred/excluded providers)
            available_providers = await self._filter_by_context(context)
            if not available_providers:
                raise ProviderError("No providers available after context filtering")

            logger.debug(
                f"Available providers after context filtering: {available_providers}"
            )

            # Step 2: Filter by task capabilities
            capable_providers = await self._filter_by_capabilities(
                task, available_providers
            )
            if not capable_providers:
                raise ProviderError(
                    f"No providers capable of handling task type: {task.type}"
                )

            logger.debug(f"Capable providers: {capable_providers}")

            # Step 3: Filter by health and availability
            healthy_providers = await self._filter_by_health(capable_providers)
            if not healthy_providers:
                raise ProviderError("No healthy providers available")

            logger.debug(f"Healthy providers: {healthy_providers}")

            # Step 4: Filter by cost constraints
            if context.max_cost_usd:
                cost_viable_providers = await self._filter_by_cost(
                    task, healthy_providers, context.max_cost_usd
                )
                if cost_viable_providers:
                    healthy_providers = cost_viable_providers
                else:
                    logger.warning(
                        f"No providers within cost limit ${context.max_cost_usd}, proceeding with all healthy providers"
                    )

            # Step 5: Apply task affinity if enabled
            affinity_provider = None
            if self.affinity_strategy != TaskAffinityStrategy.NONE:
                affinity_provider = await self._check_task_affinity(
                    task, healthy_providers
                )
                if affinity_provider:
                    logger.info(
                        f"Selected provider {affinity_provider} based on task affinity"
                    )
                    await self._record_selection(
                        task, affinity_provider, context, "affinity"
                    )
                    return affinity_provider

            # Step 6: Apply load balancing strategy
            selected_provider = await self._apply_load_balancing_strategy(
                task, healthy_providers, context
            )

            if not selected_provider:
                raise ProviderError(
                    "Load balancing strategy failed to select a provider"
                )

            # Record the selection for future affinity tracking
            await self._record_selection(
                task, selected_provider, context, str(self.strategy)
            )

            logger.info(f"Selected provider {selected_provider} for task {task.id}")
            return selected_provider

        except Exception as e:
            logger.error(f"Provider selection failed for task {task.id}: {str(e)}")
            raise ProviderError(f"Provider selection failed: {str(e)}")

    async def select_backup_provider(
        self, task: Task, failed_provider_id: str, context: ExecutionContext
    ) -> str:
        """Select a backup provider when the primary provider fails"""
        logger.warning(
            f"Selecting backup provider for task {task.id}, failed provider: {failed_provider_id}"
        )

        # Temporarily exclude the failed provider
        original_excluded = context.exclude_providers.copy()
        context.exclude_providers.append(failed_provider_id)

        try:
            backup_provider = await self.select_provider(task, context)
            logger.info(
                f"Selected backup provider {backup_provider} for task {task.id}"
            )
            return backup_provider
        finally:
            # Restore original excluded providers
            context.exclude_providers = original_excluded

    async def get_provider_recommendations(
        self, task: Task, context: ExecutionContext
    ) -> List[Dict[str, Any]]:
        """Get ranked list of provider recommendations for a task"""
        try:
            # Get all capable providers
            available_providers = await self._filter_by_context(context)
            capable_providers = await self._filter_by_capabilities(
                task, available_providers
            )

            recommendations = []

            for provider_id in capable_providers:
                provider = self.registry.get_provider(provider_id)
                if not provider:
                    continue

                health = await provider.get_health_status()
                cost_estimate = provider.estimate_cost(task)
                performance_score = self.task_affinity_tracker.get_provider_score(
                    provider_id
                )

                recommendation = {
                    "provider_id": provider_id,
                    "provider_name": provider.name,
                    "health_status": health.status,
                    "health_score": health.success_rate,
                    "estimated_cost_usd": cost_estimate.estimated_cost_usd,
                    "estimated_duration_seconds": 60.0,  # Default estimate
                    "performance_score": performance_score,
                    "capabilities": [
                        cap.value for cap in provider.get_capabilities().supported_tasks
                    ],
                    "current_load": 0,  # Default load
                    "recommendation_score": self._calculate_recommendation_score(
                        health.success_rate,
                        performance_score,
                        cost_estimate.estimated_cost_usd,
                    ),
                }

                recommendations.append(recommendation)

            # Sort by recommendation score (highest first)
            recommendations.sort(key=lambda x: x["recommendation_score"], reverse=True)

            return recommendations

        except Exception as e:
            logger.error(f"Failed to get provider recommendations: {str(e)}")
            return []

    def _calculate_recommendation_score(
        self, health_score: float, performance_score: float, cost_usd: float
    ) -> float:
        """Calculate overall recommendation score for a provider"""
        # Normalize cost (lower is better, assume $1 is high cost)
        cost_score = max(0.0, 1.0 - (cost_usd / 1.0))

        # Weighted combination of factors
        score = health_score * 0.4 + performance_score * 0.4 + cost_score * 0.2

        return score

    async def _filter_by_context(self, context: ExecutionContext) -> List[str]:
        """Filter providers based on execution context preferences"""
        all_providers = list(self.registry.providers.keys())

        # Apply preferred providers filter
        if context.preferred_providers:
            available = [p for p in context.preferred_providers if p in all_providers]
            if available:
                all_providers = available

        # Apply excluded providers filter
        if context.exclude_providers:
            all_providers = [
                p for p in all_providers if p not in context.exclude_providers
            ]

        return all_providers

    async def _filter_by_capabilities(
        self, task: Task, provider_ids: List[str]
    ) -> List[str]:
        """Filter providers that can handle the task type"""
        capable_providers = []

        for provider_id in provider_ids:
            provider = self.registry.get_provider(provider_id)
            if not provider:
                continue

            capabilities = provider.get_capabilities()
            if capabilities.supports_task(
                task.type.value if hasattr(task.type, "value") else str(task.type)
            ):
                capable_providers.append(provider_id)

        return capable_providers

    async def _filter_by_health(self, provider_ids: List[str]) -> List[str]:
        """Filter out unhealthy providers"""
        healthy_providers = []

        # Use cached health status if available and recent
        for provider_id in provider_ids:
            if await self._is_provider_healthy(provider_id):
                healthy_providers.append(provider_id)

        return healthy_providers

    async def _filter_by_cost(
        self, task: Task, provider_ids: List[str], max_cost_usd: float
    ) -> List[str]:
        """Filter providers that fit within cost constraints"""
        cost_viable_providers = []

        for provider_id in provider_ids:
            provider = self.registry.get_provider(provider_id)
            if not provider:
                continue

            cost_estimate = provider.estimate_cost(task)
            if cost_estimate.estimated_cost_usd <= max_cost_usd:
                cost_viable_providers.append(provider_id)

        return cost_viable_providers

    async def _check_task_affinity(
        self, task: Task, provider_ids: List[str]
    ) -> Optional[str]:
        """Check for task affinity and return preferred provider if available"""
        if self.affinity_strategy == TaskAffinityStrategy.NONE:
            return None

        related_provider = self.task_affinity_tracker.find_related_provider(task)
        if related_provider and related_provider in provider_ids:
            # Verify the related provider is still healthy
            if await self._is_provider_healthy(related_provider):
                return related_provider

        return None

    async def _apply_load_balancing_strategy(
        self, task: Task, provider_ids: List[str], context: ExecutionContext
    ) -> Optional[str]:
        """Apply the configured load balancing strategy"""
        if not provider_ids:
            return None

        if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return await self._round_robin_selection(provider_ids)
        elif self.strategy == LoadBalancingStrategy.LEAST_LOADED:
            return await self._least_loaded_selection(provider_ids)
        elif self.strategy == LoadBalancingStrategy.FASTEST_RESPONSE:
            return await self._fastest_response_selection(provider_ids)
        elif self.strategy == LoadBalancingStrategy.PRIORITY_BASED:
            return await self._priority_based_selection(provider_ids)
        elif self.strategy == LoadBalancingStrategy.CAPABILITY_BASED:
            return await self._capability_based_selection(task, provider_ids)
        else:
            # Default to round robin
            return await self._round_robin_selection(provider_ids)

    async def _round_robin_selection(self, provider_ids: List[str]) -> str:
        """Simple round-robin selection"""
        if not hasattr(self, "_round_robin_index"):
            self._round_robin_index = 0

        selected = provider_ids[self._round_robin_index % len(provider_ids)]
        self._round_robin_index = (self._round_robin_index + 1) % len(provider_ids)

        return selected

    async def _least_loaded_selection(self, provider_ids: List[str]) -> str:
        """Select provider with least current load"""
        min_load = float("inf")
        selected_provider = provider_ids[0]

        for provider_id in provider_ids:
            provider = self.registry.get_provider(provider_id)
            if not provider:
                continue

            health = await provider.get_health_status()
            current_load = (
                0  # Default to 0 since ProviderHealth doesn't have metrics yet
            )

            if current_load < min_load:
                min_load = current_load
                selected_provider = provider_id

        return selected_provider

    async def _fastest_response_selection(self, provider_ids: List[str]) -> str:
        """Select provider with fastest average response time"""
        best_score = 0.0
        selected_provider = provider_ids[0]

        for provider_id in provider_ids:
            score = self.task_affinity_tracker.get_provider_score(provider_id)
            if score > best_score:
                best_score = score
                selected_provider = provider_id

        return selected_provider

    async def _priority_based_selection(self, provider_ids: List[str]) -> str:
        """Select provider based on configured priority"""
        # Get provider priorities from registry
        provider_priorities = {}

        for provider_id in provider_ids:
            # In a real implementation, priorities would come from provider configuration
            # For now, use a simple scoring system
            provider_priorities[provider_id] = (
                self.task_affinity_tracker.get_provider_score(provider_id)
            )

        # Select provider with highest priority
        return max(provider_priorities.items(), key=lambda x: x[1])[0]

    async def _capability_based_selection(
        self, task: Task, provider_ids: List[str]
    ) -> str:
        """Select provider with best capability match for the task"""
        best_match_score = 0.0
        selected_provider = provider_ids[0]

        for provider_id in provider_ids:
            provider = self.registry.get_provider(provider_id)
            if not provider:
                continue

            capabilities = provider.get_capabilities()

            # Score based on capability specificity and performance
            capability_score = 1.0  # Base score for capability match

            # Bonus for specialized capabilities
            if len(capabilities.supported_tasks) <= 3:
                capability_score += 0.2  # Specialist bonus

            # Factor in performance score
            performance_score = self.task_affinity_tracker.get_provider_score(
                provider_id
            )
            total_score = capability_score * 0.6 + performance_score * 0.4

            if total_score > best_match_score:
                best_match_score = total_score
                selected_provider = provider_id

        return selected_provider

    async def _is_provider_healthy(self, provider_id: str) -> bool:
        """Check if a provider is healthy (with caching)"""
        # Check cache first
        if provider_id in self._provider_cache:
            cached_time, cached_data = self._provider_cache[provider_id]
            if datetime.now(timezone.utc) - cached_time < self._cache_ttl:
                return cached_data.get("healthy", False)

        # Get fresh health status
        provider = self.registry.get_provider(provider_id)
        if not provider:
            return False

        try:
            health = await provider.get_health_status(use_cache=False)
            is_healthy = health.is_healthy  # Use the built-in health check logic

            # Cache the result
            self._provider_cache[provider_id] = (
                datetime.now(timezone.utc),
                {"healthy": is_healthy, "health_score": health.success_rate},
            )

            return is_healthy

        except Exception as e:
            logger.warning(f"Health check failed for provider {provider_id}: {str(e)}")
            return False

    async def _record_selection(
        self,
        task: Task,
        provider_id: str,
        context: ExecutionContext,
        reason: str,
    ) -> None:
        """Record provider selection for analytics and future optimization"""
        self.task_affinity_tracker.record_assignment(task, provider_id)

        # Log selection for debugging
        logger.info(
            f"Provider selection recorded - Task: {task.id}, Provider: {provider_id}, Reason: {reason}"
        )

        # In a real implementation, you might also record this in the database
        # for persistent analytics and audit trails
