"""
Status and Analytics Reporting Service
Responsible for collecting and reporting provider status and analytics.
"""
import logging
from typing import Dict, Any, Optional

from supervisor_agent.providers.provider_registry import ProviderRegistry
from supervisor_agent.core.multi_provider_subscription_intelligence import (
    MultiProviderSubscriptionIntelligence
)
from supervisor_agent.core.multi_provider_task_processor import (
    MultiProviderTaskProcessor
)
from supervisor_agent.core.provider_coordinator import ProviderCoordinator
from supervisor_agent.db.models import Task

logger = logging.getLogger(__name__)


class StatusReporter:
    """Handles status reporting and analytics collection."""
    
    def __init__(
        self,
        provider_registry: ProviderRegistry,
        subscription_intelligence: MultiProviderSubscriptionIntelligence,
        task_processor: MultiProviderTaskProcessor,
        provider_coordinator: ProviderCoordinator
    ):
        self.provider_registry = provider_registry
        self.subscription_intelligence = subscription_intelligence
        self.task_processor = task_processor
        self.provider_coordinator = provider_coordinator
    
    async def get_provider_status(self) -> Dict[str, Any]:
        """Get comprehensive status of all providers."""
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
        """Get cross-provider analytics."""
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
        execution_context
    ) -> list[Dict[str, Any]]:
        """Get provider recommendations for a specific task."""
        return await self.provider_coordinator.get_provider_recommendations(
            task, execution_context
        )