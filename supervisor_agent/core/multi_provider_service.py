"""
Multi-Provider Service Integration

This service initializes and manages the multi-provider architecture,
providing a unified interface for the API layer to interact with
the provider coordination system.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from supervisor_agent.config import settings
from supervisor_agent.providers.provider_registry import ProviderRegistry, LoadBalancingStrategy
from supervisor_agent.providers.claude_cli_provider import ClaudeCliProvider
from supervisor_agent.providers.local_mock_provider import LocalMockProvider
from supervisor_agent.core.provider_coordinator import (
    ProviderCoordinator, ExecutionContext, TaskAffinityStrategy
)
from supervisor_agent.core.multi_provider_subscription_intelligence import (
    MultiProviderSubscriptionIntelligence
)
from supervisor_agent.core.multi_provider_task_processor import (
    MultiProviderTaskProcessor, RoutingStrategy
)
from supervisor_agent.db.models import Task
from supervisor_agent.db.crud import ProviderCRUD
from supervisor_agent.db.database import get_db

logger = logging.getLogger(__name__)


class MultiProviderService:
    """
    Central service for managing multi-provider architecture.
    
    Provides a simplified interface for the API layer to interact with
    the provider coordination system without needing to understand
    the internal complexity.
    """
    
    def __init__(self):
        self.provider_registry: Optional[ProviderRegistry] = None
        self.provider_coordinator: Optional[ProviderCoordinator] = None
        self.subscription_intelligence: Optional[MultiProviderSubscriptionIntelligence] = None
        self.task_processor: Optional[MultiProviderTaskProcessor] = None
        self._initialized = False
        
    async def initialize(self) -> None:
        """Initialize the multi-provider system"""
        if self._initialized:
            return
            
        try:
            logger.info("Initializing Multi-Provider Service")
            
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
            
            # Register providers from configuration
            await self._register_providers_from_config()
            
            self._initialized = True
            logger.info("Multi-Provider Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Multi-Provider Service: {str(e)}")
            raise
            
    async def process_task(
        self,
        task: Task,
        agent_processor: callable,
        context: Optional[Dict[str, Any]] = None,
        routing_strategy: Optional[str] = None,
        shared_memory: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a task using the multi-provider system
        
        Args:
            task: Task to process
            agent_processor: Legacy agent processor function
            context: Additional context for execution
            routing_strategy: Override routing strategy
            shared_memory: Shared memory between tasks
            
        Returns:
            Task execution result
        """
        if not self._initialized:
            await self.initialize()
            
        # Convert context to ExecutionContext
        execution_context = self._create_execution_context(context)
        
        # Convert routing strategy
        strategy = None
        if routing_strategy:
            try:
                strategy = RoutingStrategy(routing_strategy.lower())
            except ValueError:
                logger.warning(f"Unknown routing strategy: {routing_strategy}, using default")
                
        # Process task with multi-provider system
        return await self.task_processor.process_task(
            task=task,
            agent_processor=agent_processor,
            context=execution_context,
            routing_strategy=strategy,
            shared_memory=shared_memory
        )
        
    async def process_task_batch(
        self,
        tasks: List[Task],
        agent_processor: callable,
        context: Optional[Dict[str, Any]] = None,
        max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """Process multiple tasks with batch optimization"""
        if not self._initialized:
            await self.initialize()
            
        execution_context = self._create_execution_context(context)
        
        return await self.task_processor.process_task_batch(
            tasks=tasks,
            agent_processor=agent_processor,
            context=execution_context,
            max_concurrent=max_concurrent
        )
        
    async def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all providers"""
        if not self._initialized:
            await self.initialize()
            
        status = {
            "providers": {},
            "total_providers": 0,
            "healthy_providers": 0,
            "quota_status": {},
            "system_metrics": {}
        }
        
        try:
            # Get provider registry status
            for provider_id, provider in self.provider_registry.providers.items():
                health = await provider.get_health_status()
                capabilities = provider.get_capabilities()
                
                status["providers"][provider_id] = {
                    "name": provider.name,
                    "type": provider.__class__.__name__,
                    "health_status": health.status,
                    "health_score": health.score,
                    "capabilities": capabilities.supported_task_types,
                    "max_concurrent": capabilities.max_concurrent_tasks,
                    "metrics": health.metrics
                }
                
                if health.status in ["healthy", "degraded"]:
                    status["healthy_providers"] += 1
                    
            status["total_providers"] = len(self.provider_registry.providers)
            
            # Get quota status
            quota_status = await self.subscription_intelligence.get_quota_status()
            status["quota_status"] = {
                provider_id: {
                    "daily_limit": info.daily_limit,
                    "current_usage": info.current_usage,
                    "usage_percentage": info.usage_percentage,
                    "status": info.status,
                    "requests_remaining": info.requests_remaining
                }
                for provider_id, info in quota_status.items()
            }
            
            # Get processing statistics
            processing_stats = await self.task_processor.get_processing_stats()
            status["system_metrics"] = processing_stats
            
        except Exception as e:
            logger.error(f"Error getting provider status: {str(e)}")
            status["error"] = str(e)
            
        return status
        
    async def get_analytics(self) -> Dict[str, Any]:
        """Get cross-provider analytics"""
        if not self._initialized:
            await self.initialize()
            
        try:
            analytics = await self.subscription_intelligence.get_cross_provider_analytics()
            
            return {
                "total_requests_today": analytics.total_requests_today,
                "total_cost_today": analytics.total_cost_today,
                "average_response_time": analytics.average_response_time,
                "success_rate": analytics.success_rate,
                "provider_count": analytics.provider_count,
                "most_used_provider": analytics.most_used_provider,
                "most_cost_effective_provider": analytics.most_cost_effective_provider,
                "quota_utilization": analytics.quota_utilization,
                "recommendations": analytics.recommendations
            }
            
        except Exception as e:
            logger.error(f"Error getting analytics: {str(e)}")
            return {"error": str(e)}
            
    async def get_provider_recommendations(
        self,
        task: Task,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Get provider recommendations for a specific task"""
        if not self._initialized:
            await self.initialize()
            
        execution_context = self._create_execution_context(context)
        
        return await self.provider_coordinator.get_provider_recommendations(
            task, execution_context
        )
        
    async def register_provider(
        self,
        provider_id: str,
        provider_type: str,
        config: Dict[str, Any]
    ) -> bool:
        """Register a new provider"""
        if not self._initialized:
            await self.initialize()
            
        try:
            if provider_type == "claude_cli":
                provider = ClaudeCliProvider(provider_id, config)
            elif provider_type == "local_mock":
                provider = LocalMockProvider(provider_id, config)
            else:
                logger.error(f"Unknown provider type: {provider_type}")
                return False
                
            await self.provider_registry.register_provider(provider_id, provider)
            logger.info(f"Registered provider {provider_id} of type {provider_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error registering provider {provider_id}: {str(e)}")
            return False
            
    async def unregister_provider(self, provider_id: str) -> bool:
        """Unregister a provider"""
        if not self._initialized:
            await self.initialize()
            
        try:
            await self.provider_registry.unregister_provider(provider_id)
            logger.info(f"Unregistered provider {provider_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error unregistering provider {provider_id}: {str(e)}")
            return False
            
    def is_enabled(self) -> bool:
        """Check if multi-provider system is enabled"""
        return settings.multi_provider_enabled and self._initialized
        
    async def _register_providers_from_config(self) -> None:
        """Register providers from configuration"""
        try:
            provider_configs = settings.get_provider_configs()
            
            if not provider_configs:
                # Fallback to legacy configuration
                await self._register_legacy_providers()
                return
                
            for config in provider_configs:
                provider_id = config.get("id")
                provider_type = config.get("type")
                provider_config = config.get("config", {})
                
                if not provider_id or not provider_type:
                    logger.warning(f"Invalid provider configuration: {config}")
                    continue
                    
                success = await self.register_provider(provider_id, provider_type, provider_config)
                if not success:
                    logger.warning(f"Failed to register provider {provider_id}")
                    
        except Exception as e:
            logger.error(f"Error registering providers from config: {str(e)}")
            # Fallback to legacy providers
            await self._register_legacy_providers()
            
    async def _register_legacy_providers(self) -> None:
        """Register providers using legacy configuration for backward compatibility"""
        try:
            # Register Claude CLI providers based on API keys
            claude_keys = settings.claude_api_keys_list
            if claude_keys:
                for i, api_key in enumerate(claude_keys):
                    provider_id = f"claude-cli-{i+1}"
                    config = {
                        "api_keys": [api_key],
                        "rate_limit_per_day": 1000,
                        "priority": i + 1
                    }
                    await self.register_provider(provider_id, "claude_cli", config)
                    
            # Always register local mock provider for testing
            mock_config = {
                "deterministic": True,
                "failure_rate": 0.01,
                "response_delay_seconds": 1.0
            }
            await self.register_provider("local-mock", "local_mock", mock_config)
            
            logger.info("Registered legacy providers for backward compatibility")
            
        except Exception as e:
            logger.error(f"Error registering legacy providers: {str(e)}")
            
    def _create_execution_context(self, context: Optional[Dict[str, Any]]) -> ExecutionContext:
        """Create ExecutionContext from API context"""
        if not context:
            return ExecutionContext()
            
        return ExecutionContext(
            user_id=context.get("user_id"),
            organization_id=context.get("organization_id"),
            priority=context.get("priority", 5),
            max_cost_usd=context.get("max_cost_usd"),
            preferred_providers=context.get("preferred_providers"),
            exclude_providers=context.get("exclude_providers"),
            require_capabilities=context.get("require_capabilities"),
            metadata=context.get("metadata", {})
        )


# Global service instance
multi_provider_service = MultiProviderService()