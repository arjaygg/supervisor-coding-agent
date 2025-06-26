"""
Multi-Provider Service Integration - Refactored

This service provides a facade interface for the multi-provider architecture,
using composition and dependency injection to separate concerns.
"""

import logging
from typing import Dict, List, Optional, Any

from supervisor_agent.config import settings
from supervisor_agent.core.multi_provider_initializer import MultiProviderInitializer
from supervisor_agent.core.provider_manager import ProviderManager
from supervisor_agent.core.status_reporter import StatusReporter
from supervisor_agent.core.configuration_manager import ConfigurationManager
from supervisor_agent.core.multi_provider_task_processor import RoutingStrategy
from supervisor_agent.db.models import Task

logger = logging.getLogger(__name__)


class MultiProviderService:
    """
    Facade for multi-provider architecture using composition and separation of concerns.
    
    This refactored service delegates responsibilities to focused components:
    - MultiProviderInitializer: System initialization
    - ProviderManager: Provider registration and management
    - StatusReporter: Status and analytics reporting
    - ConfigurationManager: Configuration and context management
    """
    
    def __init__(self):
        self.initializer = MultiProviderInitializer()
        self.provider_manager: Optional[ProviderManager] = None
        self.status_reporter: Optional[StatusReporter] = None
        self.configuration_manager = ConfigurationManager()
        self.task_processor = None
        self._initialized = False
        
    async def initialize(self) -> None:
        """Initialize the multi-provider system using dedicated initializer."""
        if self._initialized:
            return
            
        try:
            logger.info("Initializing Multi-Provider Service")
            
            # Initialize components using dedicated initializer
            components = await self.initializer.initialize()
            
            # Set up component dependencies
            self.provider_manager = ProviderManager(components['provider_registry'])
            self.status_reporter = StatusReporter(
                provider_registry=components['provider_registry'],
                subscription_intelligence=components['subscription_intelligence'],
                task_processor=components['task_processor'],
                provider_coordinator=components['provider_coordinator']
            )
            self.task_processor = components['task_processor']
            
            # Register providers from configuration
            await self.provider_manager.register_providers_from_config()
            
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
        """Process a task using the multi-provider system."""
        if not self._initialized:
            await self.initialize()
            
        # Convert context to ExecutionContext using configuration manager
        execution_context = self.configuration_manager.create_execution_context(context)
        
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
        """Process multiple tasks with batch optimization."""
        if not self._initialized:
            await self.initialize()
            
        execution_context = self.configuration_manager.create_execution_context(context)
        
        return await self.task_processor.process_task_batch(
            tasks=tasks,
            agent_processor=agent_processor,
            context=execution_context,
            max_concurrent=max_concurrent
        )
        
    async def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all providers using dedicated status reporter."""
        if not self._initialized:
            await self.initialize()
            
        return await self.status_reporter.get_provider_status()
        
    async def get_analytics(self) -> Dict[str, Any]:
        """Get cross-provider analytics using dedicated status reporter."""
        if not self._initialized:
            await self.initialize()
            
        return await self.status_reporter.get_analytics()
            
    async def get_provider_recommendations(
        self,
        task: Task,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Get provider recommendations for a specific task."""
        if not self._initialized:
            await self.initialize()
            
        execution_context = self.configuration_manager.create_execution_context(context)
        
        return await self.status_reporter.get_provider_recommendations(
            task, execution_context
        )
        
    async def register_provider(
        self,
        provider_id: str,
        provider_type: str,
        config: Dict[str, Any]
    ) -> bool:
        """Register a new provider using dedicated provider manager."""
        if not self._initialized:
            await self.initialize()
            
        return await self.provider_manager.register_provider(
            provider_id, provider_type, config
        )
            
    async def unregister_provider(self, provider_id: str) -> bool:
        """Unregister a provider using dedicated provider manager."""
        if not self._initialized:
            await self.initialize()
            
        return await self.provider_manager.unregister_provider(provider_id)
            
    def is_enabled(self) -> bool:
        """Check if multi-provider system is enabled."""
        return settings.multi_provider_enabled and self._initialized


# Global service instance
multi_provider_service = MultiProviderService()