"""
Base provider implementation with common functionality.
Provides default implementations for common provider behaviors.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

from supervisor_agent.providers.base_provider import (
    Task, ProviderResponse, ProviderCapabilities, ProviderHealth, CostEstimate, ProviderStatus
)
from supervisor_agent.providers.provider_interfaces import (
    TaskExecutor, CapabilityProvider, HealthMonitor, CostEstimator, 
    ProviderLifecycle, ConfigurationValidator
)


class BaseProviderImpl:
    """Base implementation providing common provider functionality."""
    
    def __init__(self, provider_id: str, config: Dict[str, Any]):
        self.provider_id = provider_id
        self.config = config
        self._initialized = False
        self._health_cache: Optional[ProviderHealth] = None
        self._health_cache_time: Optional[datetime] = None
    
    @property
    def is_initialized(self) -> bool:
        """Check if provider has been initialized."""
        return self._initialized
    
    def _estimate_tokens_from_text(self, text: str) -> int:
        """
        Estimate token count from text (rough approximation).
        
        Args:
            text: The text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        # Rough approximation: 1 token per 4 characters
        return max(len(text) // 4, 1)
    
    def _should_cache_health(self, cache_duration_seconds: int = 30) -> bool:
        """Check if health status should be cached."""
        if not self._health_cache or not self._health_cache_time:
            return False
        
        elapsed = (datetime.now() - self._health_cache_time).total_seconds()
        return elapsed < cache_duration_seconds
    
    def _cache_health(self, health: ProviderHealth) -> None:
        """Cache health status."""
        self._health_cache = health
        self._health_cache_time = datetime.now()
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(id={self.provider_id})"
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id='{self.provider_id}', config={self.config})"


class DefaultLifecycleMixin(ProviderLifecycle):
    """Default implementation of provider lifecycle."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initialized = False
    
    async def initialize(self) -> None:
        """Default initialization - mark as initialized."""
        self._initialized = True
    
    async def shutdown(self) -> None:
        """Default shutdown - clean up state."""
        self._initialized = False


class DefaultConfigurationValidatorMixin(ConfigurationValidator):
    """Default implementation of configuration validation."""
    
    async def validate_configuration(self) -> List[str]:
        """Validate the provider configuration."""
        errors = []
        
        if not hasattr(self, 'provider_id') or not self.provider_id:
            errors.append("Provider ID is required")
        
        if not hasattr(self, 'config') or not isinstance(self.config, dict):
            errors.append("Configuration must be a dictionary")
        
        return errors


class DefaultHealthMonitorMixin(HealthMonitor):
    """Default implementation of health monitoring."""
    
    async def get_health_status(self, use_cache: bool = True) -> ProviderHealth:
        """Get basic health status."""
        if use_cache and hasattr(self, '_should_cache_health') and self._should_cache_health():
            return self._health_cache
        
        # Basic health check - override in subclasses for more sophisticated checks
        health = ProviderHealth(
            status=ProviderStatus.ACTIVE if getattr(self, '_initialized', True) else ProviderStatus.INACTIVE,
            response_time_ms=50.0,  # Default response time
            success_rate=0.95,  # Default success rate
            error_count=0,
            last_check_time=datetime.now()
        )
        
        if hasattr(self, '_cache_health'):
            self._cache_health(health)
        
        return health


class DefaultCostEstimatorMixin(CostEstimator):
    """Default implementation of cost estimation."""
    
    def estimate_cost(self, task: Task) -> CostEstimate:
        """Provide basic cost estimation."""
        # Basic token estimation
        payload_str = str(task.payload)
        estimated_tokens = len(payload_str) // 4  # Rough approximation
        
        # Default cost per token (can be overridden in subclasses)
        cost_per_token = getattr(self, 'default_cost_per_token', 0.001)
        
        return CostEstimate.from_tokens(
            tokens=estimated_tokens,
            cost_per_token=cost_per_token,
            model=getattr(self, 'model_name', 'unknown')
        )


class TaskExecutionHelper:
    """Helper methods for task execution."""
    
    async def can_execute_task(self, task: Task) -> bool:
        """
        Check if this provider can execute the given task.
        Requires the provider to implement CapabilityProvider interface.
        """
        if not isinstance(self, CapabilityProvider):
            return True  # If no capabilities defined, assume it can handle anything
        
        capabilities = self.get_capabilities()
        
        # Check if provider supports this task type
        if not capabilities.supports_task(task.type):
            return False
        
        # Check if provider is healthy (if health monitoring is available)
        if isinstance(self, HealthMonitor):
            health = await self.get_health_status()
            if not health.is_available:
                return False
        
        # Estimate tokens and check if provider can handle the request size (if cost estimation is available)
        if isinstance(self, CostEstimator):
            cost_estimate = self.estimate_cost(task)
            if not capabilities.can_handle_request_size(cost_estimate.estimated_tokens):
                return False
        
        return True