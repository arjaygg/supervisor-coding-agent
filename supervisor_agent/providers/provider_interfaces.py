"""
Segregated provider interfaces following Interface Segregation Principle.
Breaks down the monolithic AIProvider interface into focused, cohesive interfaces.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from supervisor_agent.providers.base_provider import (
    Task, ProviderResponse, ProviderCapabilities, ProviderHealth, CostEstimate
)


class TaskExecutor(ABC):
    """Interface for basic task execution capabilities."""
    
    @abstractmethod
    async def execute_task(self, task: Task, context: Dict[str, Any] = None) -> ProviderResponse:
        """Execute a single task."""
        pass


class BatchExecutor(ABC):
    """Interface for batch execution capabilities."""
    
    @abstractmethod
    async def execute_batch(self, tasks: List[Task], context: Dict[str, Any] = None) -> List[ProviderResponse]:
        """Execute multiple tasks as a batch."""
        pass


class CapabilityProvider(ABC):
    """Interface for providers that can describe their capabilities."""
    
    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        """Get the capabilities of this provider."""
        pass


class HealthMonitor(ABC):
    """Interface for providers that support health monitoring."""
    
    @abstractmethod
    async def get_health_status(self, use_cache: bool = True) -> ProviderHealth:
        """Get the current health status of the provider."""
        pass


class CostEstimator(ABC):
    """Interface for providers that can estimate costs."""
    
    @abstractmethod
    def estimate_cost(self, task: Task) -> CostEstimate:
        """Estimate the cost of executing a task."""
        pass


class ProviderLifecycle(ABC):
    """Interface for provider initialization and shutdown."""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the provider with its configuration."""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Gracefully shutdown the provider."""
        pass


class ConfigurationValidator(ABC):
    """Interface for providers that can validate their configuration."""
    
    @abstractmethod
    async def validate_configuration(self) -> List[str]:
        """Validate the provider configuration."""
        pass


# Composed interfaces for common provider combinations

class BasicProvider(TaskExecutor, CapabilityProvider, ProviderLifecycle):
    """Basic provider that can execute tasks and describes capabilities."""
    pass


class AdvancedProvider(
    TaskExecutor, 
    BatchExecutor, 
    CapabilityProvider, 
    HealthMonitor, 
    CostEstimator, 
    ProviderLifecycle,
    ConfigurationValidator
):
    """Full-featured provider with all capabilities."""
    pass


class MockProvider(TaskExecutor, CapabilityProvider):
    """Simple mock provider for testing - no lifecycle management needed."""
    pass


class HealthAwareProvider(TaskExecutor, CapabilityProvider, HealthMonitor, ProviderLifecycle):
    """Provider with health monitoring but no cost estimation or batching."""
    pass


class CostAwareProvider(TaskExecutor, CapabilityProvider, CostEstimator, ProviderLifecycle):
    """Provider with cost estimation but no health monitoring or batching."""
    pass