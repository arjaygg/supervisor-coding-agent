"""
Provider Registry and Factory for managing AI provider instances.

This module provides centralized management of AI providers, including
registration, discovery, health monitoring, and failover capabilities.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from supervisor_agent.utils.logger import get_logger

from .base_provider import (AIProvider, ProviderError, ProviderHealth,
                            ProviderResponse, ProviderStatus, ProviderType,
                            ProviderUnavailableError, Task)

logger = get_logger(__name__)

# Provider registration will be done after class definitions


class LoadBalancingStrategy(str, Enum):
    """Load balancing strategies for provider selection."""

    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    FASTEST_RESPONSE = "fastest_response"
    PRIORITY_BASED = "priority_based"
    CAPABILITY_BASED = "capability_based"


@dataclass
class ProviderConfig:
    """Configuration for a provider instance."""

    provider_id: str
    provider_type: ProviderType
    config: Dict[str, Any]
    priority: int = 5
    enabled: bool = True
    max_concurrent_requests: int = 10
    health_check_interval_seconds: int = 60
    failure_threshold: int = 3
    recovery_timeout_seconds: int = 300
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderMetrics:
    """Runtime metrics for a provider."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time_ms: float = 0.0
    last_request_time: Optional[datetime] = None
    consecutive_failures: int = 0
    last_failure_time: Optional[datetime] = None
    current_load: int = 0  # Number of concurrent requests

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100.0

    def record_request(self, success: bool, response_time_ms: float):
        """Record a request execution."""
        self.total_requests += 1
        self.last_request_time = datetime.now()

        if success:
            self.successful_requests += 1
            self.consecutive_failures = 0
            # Update average response time
            if self.total_requests == 1:
                self.average_response_time_ms = response_time_ms
            else:
                self.average_response_time_ms = (
                    self.average_response_time_ms * (self.total_requests - 1)
                    + response_time_ms
                ) / self.total_requests
        else:
            self.failed_requests += 1
            self.consecutive_failures += 1
            self.last_failure_time = datetime.now()


class ProviderFactory:
    """Factory for creating provider instances."""

    _provider_classes: Dict[ProviderType, Type[AIProvider]] = {}

    @classmethod
    def register_provider_class(
        cls, provider_type: ProviderType, provider_class: Type[AIProvider]
    ):
        """Register a provider class for a specific type."""
        cls._provider_classes[provider_type] = provider_class
        logger.info(
            f"Registered provider class {provider_class.__name__} for type {provider_type}"
        )

    @classmethod
    async def create_provider(cls, config: ProviderConfig) -> AIProvider:
        """Create a provider instance from configuration."""
        provider_class = cls._provider_classes.get(config.provider_type)
        if not provider_class:
            raise ValueError(
                f"No provider class registered for type: {config.provider_type}"
            )

        # Create the provider instance
        provider = provider_class(config.provider_id, config.config)

        # Initialize the provider
        await provider.initialize()

        logger.info(
            f"Created provider {config.provider_id} of type {config.provider_type}"
        )
        return provider

    @classmethod
    def get_supported_types(cls) -> List[ProviderType]:
        """Get list of supported provider types."""
        return list(cls._provider_classes.keys())


class ProviderRegistry:
    """
    Central registry for managing AI provider instances.

    Provides provider discovery, health monitoring, load balancing,
    and failover capabilities.
    """

    def __init__(
        self,
        load_balancing_strategy: LoadBalancingStrategy = LoadBalancingStrategy.PRIORITY_BASED,
    ):
        self._providers: Dict[str, AIProvider] = {}
        self._configs: Dict[str, ProviderConfig] = {}
        self._metrics: Dict[str, ProviderMetrics] = {}
        self._health_cache: Dict[str, ProviderHealth] = {}
        self._load_balancing_strategy = load_balancing_strategy
        self._round_robin_index = 0
        self._health_check_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

        logger.info(
            f"Provider Registry initialized with strategy: {load_balancing_strategy}"
        )

    async def register_provider(self, config: ProviderConfig) -> None:
        """Register a new provider with the registry."""
        try:
            # Create the provider instance
            provider = await ProviderFactory.create_provider(config)

            # Validate configuration
            validation_errors = await provider.validate_configuration()
            if validation_errors:
                raise ValueError(f"Provider configuration invalid: {validation_errors}")

            # Store provider and metadata
            self._providers[config.provider_id] = provider
            self._configs[config.provider_id] = config
            self._metrics[config.provider_id] = ProviderMetrics()

            # Initial health check
            health = await provider.get_health_status(use_cache=False)
            self._health_cache[config.provider_id] = health

            logger.info(f"Successfully registered provider: {config.provider_id}")

        except Exception as e:
            logger.error(f"Failed to register provider {config.provider_id}: {str(e)}")
            raise ProviderError(
                f"Provider registration failed: {str(e)}", config.provider_id
            )

    async def unregister_provider(self, provider_id: str) -> None:
        """Unregister a provider from the registry."""
        if provider_id not in self._providers:
            logger.warning(f"Attempt to unregister unknown provider: {provider_id}")
            return

        try:
            # Shutdown the provider
            provider = self._providers[provider_id]
            await provider.shutdown()

            # Remove from all tracking dictionaries
            del self._providers[provider_id]
            del self._configs[provider_id]
            del self._metrics[provider_id]
            del self._health_cache[provider_id]

            logger.info(f"Successfully unregistered provider: {provider_id}")

        except Exception as e:
            logger.error(
                f"Error during provider unregistration {provider_id}: {str(e)}"
            )

    def get_provider(self, provider_id: str) -> Optional[AIProvider]:
        """Get a specific provider by ID."""
        return self._providers.get(provider_id)

    def get_all_providers(self) -> Dict[str, AIProvider]:
        """Get all registered providers."""
        return self._providers.copy()

    def get_provider_ids(self) -> List[str]:
        """Get list of registered provider IDs."""
        return list(self._providers.keys())

    async def get_available_providers(self, task: Optional[Task] = None) -> List[str]:
        """
        Get list of available providers, optionally filtered by task compatibility.

        Args:
            task: Optional task to filter providers by compatibility

        Returns:
            List of provider IDs that are available and can handle the task
        """
        available = []

        for provider_id, provider in self._providers.items():
            config = self._configs[provider_id]

            # Skip disabled providers
            if not config.enabled:
                continue

            # Check health status
            health = await self._get_cached_health(provider_id)
            if not health.is_available:
                continue

            # Check task compatibility if provided
            if task and not await provider.can_execute_task(task):
                continue

            available.append(provider_id)

        return available

    async def select_provider(self, task: Task) -> Optional[str]:
        """
        Select the best provider for a given task using the configured strategy.

        Args:
            task: The task to select a provider for

        Returns:
            Provider ID of the selected provider, or None if no suitable provider found
        """
        available_providers = await self.get_available_providers(task)

        if not available_providers:
            logger.warning(f"No available providers for task {task.id}")
            return None

        if len(available_providers) == 1:
            return available_providers[0]

        # Apply load balancing strategy
        if self._load_balancing_strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return self._select_round_robin(available_providers)
        elif self._load_balancing_strategy == LoadBalancingStrategy.LEAST_LOADED:
            return self._select_least_loaded(available_providers)
        elif self._load_balancing_strategy == LoadBalancingStrategy.FASTEST_RESPONSE:
            return self._select_fastest_response(available_providers)
        elif self._load_balancing_strategy == LoadBalancingStrategy.PRIORITY_BASED:
            return self._select_priority_based(available_providers)
        elif self._load_balancing_strategy == LoadBalancingStrategy.CAPABILITY_BASED:
            return await self._select_capability_based(available_providers, task)
        else:
            # Default to priority-based
            return self._select_priority_based(available_providers)

    async def execute_task(
        self, task: Task, provider_id: Optional[str] = None
    ) -> ProviderResponse:
        """
        Execute a task using a specific provider or auto-select the best one.

        Args:
            task: The task to execute
            provider_id: Optional specific provider to use

        Returns:
            ProviderResponse with execution results

        Raises:
            ProviderError: If no suitable provider is found or execution fails
        """
        # Select provider if not specified
        if provider_id is None:
            provider_id = await self.select_provider(task)
            if provider_id is None:
                raise ProviderUnavailableError("No available providers for task")

        # Validate provider exists and is available
        provider = self._providers.get(provider_id)
        if not provider:
            raise ProviderError(f"Provider not found: {provider_id}")

        config = self._configs[provider_id]
        if not config.enabled:
            raise ProviderError(f"Provider is disabled: {provider_id}")

        # Track concurrent load
        metrics = self._metrics[provider_id]
        if metrics.current_load >= config.max_concurrent_requests:
            raise ProviderError(f"Provider at capacity: {provider_id}")

        # Execute the task
        start_time = datetime.now()
        metrics.current_load += 1

        try:
            response = await provider.execute_task(task)
            execution_time_ms = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )

            # Record successful execution
            metrics.record_request(True, execution_time_ms)

            logger.info(
                f"Task {task.id} executed successfully by provider {provider_id}"
            )
            return response

        except Exception as e:
            execution_time_ms = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )

            # Record failed execution
            metrics.record_request(False, execution_time_ms)

            logger.error(f"Task {task.id} failed on provider {provider_id}: {str(e)}")
            raise

        finally:
            metrics.current_load -= 1

    async def get_provider_health(self, provider_id: str) -> Optional[ProviderHealth]:
        """Get health status for a specific provider."""
        return await self._get_cached_health(provider_id)

    async def get_all_provider_health(self) -> Dict[str, ProviderHealth]:
        """Get health status for all providers."""
        health_status = {}

        for provider_id in self._providers.keys():
            health = await self._get_cached_health(provider_id)
            if health:
                health_status[provider_id] = health

        return health_status

    def get_provider_metrics(self, provider_id: str) -> Optional[ProviderMetrics]:
        """Get runtime metrics for a specific provider."""
        return self._metrics.get(provider_id)

    def get_all_provider_metrics(self) -> Dict[str, ProviderMetrics]:
        """Get runtime metrics for all providers."""
        return self._metrics.copy()

    async def start_health_monitoring(self, check_interval_seconds: int = 60):
        """Start background health monitoring for all providers."""
        if self._health_check_task and not self._health_check_task.done():
            logger.warning("Health monitoring already running")
            return

        self._health_check_task = asyncio.create_task(
            self._health_check_loop(check_interval_seconds)
        )
        logger.info(
            f"Started health monitoring with {check_interval_seconds}s interval"
        )

    async def stop_health_monitoring(self):
        """Stop background health monitoring."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
            logger.info("Stopped health monitoring")

    async def shutdown(self):
        """Shutdown the registry and all providers."""
        logger.info("Shutting down Provider Registry")

        # Stop health monitoring
        await self.stop_health_monitoring()

        # Shutdown all providers
        for provider_id in list(self._providers.keys()):
            await self.unregister_provider(provider_id)

        self._shutdown_event.set()
        logger.info("Provider Registry shutdown complete")

    # Private methods for load balancing strategies

    def _select_round_robin(self, providers: List[str]) -> str:
        """Select provider using round-robin strategy."""
        if not providers:
            raise ProviderError("No providers available for round-robin selection")

        selected = providers[self._round_robin_index % len(providers)]
        self._round_robin_index += 1
        return selected

    def _select_least_loaded(self, providers: List[str]) -> str:
        """Select provider with least current load."""
        min_load = float("inf")
        selected = providers[0]

        for provider_id in providers:
            metrics = self._metrics[provider_id]
            if metrics.current_load < min_load:
                min_load = metrics.current_load
                selected = provider_id

        return selected

    def _select_fastest_response(self, providers: List[str]) -> str:
        """Select provider with fastest average response time."""
        min_response_time = float("inf")
        selected = providers[0]

        for provider_id in providers:
            metrics = self._metrics[provider_id]
            if metrics.average_response_time_ms < min_response_time:
                min_response_time = metrics.average_response_time_ms
                selected = provider_id

        return selected

    def _select_priority_based(self, providers: List[str]) -> str:
        """Select provider with highest priority (lowest priority number)."""
        highest_priority = float("inf")
        selected = providers[0]

        for provider_id in providers:
            config = self._configs[provider_id]
            if config.priority < highest_priority:
                highest_priority = config.priority
                selected = provider_id

        return selected

    async def _select_capability_based(self, providers: List[str], task: Task) -> str:
        """Select provider based on task-specific capabilities."""
        # Score providers based on capability match
        best_score = -1
        selected = providers[0]

        for provider_id in providers:
            provider = self._providers[provider_id]
            capabilities = provider.get_capabilities()

            # Simple scoring based on capability match
            score = 0
            if capabilities.supports_task(task.type):
                score += 10

            # Prefer providers with lower current load
            metrics = self._metrics[provider_id]
            score += 10 - metrics.current_load

            # Prefer providers with better success rate
            score += metrics.success_rate / 10

            if score > best_score:
                best_score = score
                selected = provider_id

        return selected

    async def _get_cached_health(self, provider_id: str) -> Optional[ProviderHealth]:
        """Get cached health status for a provider."""
        if provider_id not in self._providers:
            return None

        # Check if we have cached health data
        cached_health = self._health_cache.get(provider_id)
        if cached_health:
            # Check if cache is still valid (1 minute)
            age = (datetime.now() - cached_health.last_check_time).total_seconds()
            if age < 60:
                return cached_health

        # Get fresh health data
        try:
            provider = self._providers[provider_id]
            health = await provider.get_health_status(use_cache=False)
            self._health_cache[provider_id] = health
            return health
        except Exception as e:
            logger.error(f"Failed to get health for provider {provider_id}: {str(e)}")
            return None

    async def _health_check_loop(self, check_interval_seconds: int):
        """Background health checking loop."""
        while not self._shutdown_event.is_set():
            try:
                # Check health for all providers
                for provider_id in list(self._providers.keys()):
                    await self._get_cached_health(provider_id)

                # Wait for next check
                await asyncio.sleep(check_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {str(e)}")
                await asyncio.sleep(
                    min(check_interval_seconds, 30)
                )  # Retry after shorter interval on error


# Register default provider classes after definitions
def register_default_providers():
    """Register default provider implementations."""
    try:
        from .claude_cli_provider import ClaudeCliProvider
        from .local_mock_provider import LocalMockProvider

        ProviderFactory.register_provider_class(
            ProviderType.CLAUDE_CLI, ClaudeCliProvider
        )
        ProviderFactory.register_provider_class(
            ProviderType.LOCAL_MOCK, LocalMockProvider
        )

        logger.info("Default provider classes registered successfully")
    except ImportError as e:
        logger.warning(f"Failed to register some provider classes: {e}")


# Register providers on module load
register_default_providers()
