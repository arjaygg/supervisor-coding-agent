"""
Multi-Provider System Initializer
Responsible for initializing and configuring the multi-provider architecture.
"""
import logging
from typing import Optional

from supervisor_agent.config import settings
from supervisor_agent.providers.provider_registry import ProviderRegistry, LoadBalancingStrategy
from supervisor_agent.core.provider_coordinator import (
    ProviderCoordinator, TaskAffinityStrategy
)
from supervisor_agent.core.multi_provider_subscription_intelligence import (
    MultiProviderSubscriptionIntelligence
)
from supervisor_agent.core.multi_provider_task_processor import (
    MultiProviderTaskProcessor, RoutingStrategy
)

logger = logging.getLogger(__name__)


class MultiProviderInitializer:
    """Handles initialization of the multi-provider system components."""
    
    def __init__(self):
        self.provider_registry: Optional[ProviderRegistry] = None
        self.provider_coordinator: Optional[ProviderCoordinator] = None
        self.subscription_intelligence: Optional[MultiProviderSubscriptionIntelligence] = None
        self.task_processor: Optional[MultiProviderTaskProcessor] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize all multi-provider system components."""
        if self._initialized:
            return self._get_components()
        
        try:
            logger.info("Initializing Multi-Provider System Components")
            
            # Initialize provider registry
            self.provider_registry = ProviderRegistry(
                load_balancing_strategy=LoadBalancingStrategy.CAPABILITY_BASED
            )
            
            # Initialize subscription intelligence
            self.subscription_intelligence = MultiProviderSubscriptionIntelligence(
                provider_registry=self.provider_registry,
                cache_ttl=300,  # 5 minutes
                quota_check_interval=60  # 1 minute
            )
            
            # Initialize provider coordinator
            self.provider_coordinator = ProviderCoordinator(
                registry=self.provider_registry,
                strategy=LoadBalancingStrategy.CAPABILITY_BASED,
                affinity_strategy=TaskAffinityStrategy.CAPABILITY_BASED
            )
            
            # Initialize task processor
            self.task_processor = MultiProviderTaskProcessor(
                provider_registry=self.provider_registry,
                provider_coordinator=self.provider_coordinator,
                subscription_intelligence=self.subscription_intelligence,
                default_routing_strategy=RoutingStrategy.OPTIMAL,
                max_retry_attempts=3,
                failover_enabled=True,
                batch_optimization_enabled=True
            )
            
            self._initialized = True
            logger.info("Multi-Provider System Components initialized successfully")
            
            return self._get_components()
            
        except Exception as e:
            logger.error(f"Failed to initialize Multi-Provider System: {str(e)}")
            raise
    
    def _get_components(self):
        """Return initialized components."""
        return {
            'provider_registry': self.provider_registry,
            'provider_coordinator': self.provider_coordinator,
            'subscription_intelligence': self.subscription_intelligence,
            'task_processor': self.task_processor
        }
    
    def is_initialized(self) -> bool:
        """Check if components are initialized."""
        return self._initialized